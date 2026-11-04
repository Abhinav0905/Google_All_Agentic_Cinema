"""Scorecard calculator for timed-text accessibility deliverables.

Evaluates:
- Accuracy: 1 - mean WER over matched cues
- Synchronicity: matched cues within sync tolerance / matched cues
- Completeness: speech segments with a matched cue / total speech segments
- SDH coverage: (tagged salient events / salient events) * 0.5
  + (labeled offscreen / offscreen) * 0.5
- AD coverage: described essential events / essential events
"""

from typing import Dict, List, Literal, Optional, Set

from engine.alignment import AlignmentResult
from engine.models import (
    AudioEvent,
    Cue,
    DimensionScore,
    Finding,
    Profile,
    Scorecard,
    VisualEvent,
)


def compute_dimension_status(
    score: float, threshold: float
) -> Literal["pass", "warn", "fail"]:
    """Compute pass / warn / fail status against profile threshold with 0.05 warn band."""
    if score >= threshold:
        return "pass"
    elif score >= (threshold - 0.05):
        return "warn"
    return "fail"


def compute_scorecard(
    cues: List[Cue],
    profile: Profile,
    alignment: AlignmentResult,
    findings: List[Finding],
    audio_events: Optional[List[AudioEvent]] = None,
    visual_events: Optional[List[VisualEvent]] = None,
    ad_cues: Optional[List[Cue]] = None,
    sdh_mode: bool = True,
) -> Scorecard:
    """Calculate overall and per-dimension scores against the spec profile."""
    thresholds: Dict[str, float] = {
        k: v.value for k, v in profile.pass_thresholds.items()
    }

    # 1. Accuracy: 1 - mean WER over matched cues
    if alignment.matches:
        acc_score = max(0.0, min(1.0, 1.0 - alignment.mean_wer))
    else:
        acc_score = 1.0 if not alignment.unmatched_segments else 0.0
    acc_thresh = thresholds.get("accuracy", 0.98)
    accuracy_dim = DimensionScore(
        score=round(acc_score, 4),
        threshold=acc_thresh,
        status=compute_dimension_status(acc_score, acc_thresh),
        counts={"matched_cues": len(alignment.matches), "mean_wer": round(alignment.mean_wer, 4)},
    )

    # 2. Synchronicity: matched cues within tolerance / matched cues
    sync_tol = profile.sync_tolerance_ms.value
    if alignment.matches:
        in_sync = sum(1 for m in alignment.matches if abs(m.offset_ms) <= sync_tol)
        sync_score = in_sync / len(alignment.matches)
    else:
        in_sync = 0
        sync_score = 1.0 if not cues else 0.0
    sync_thresh = thresholds.get("synchronicity", 0.95)
    sync_dim = DimensionScore(
        score=round(sync_score, 4),
        threshold=sync_thresh,
        status=compute_dimension_status(sync_score, sync_thresh),
        counts={
            "in_sync": in_sync,
            "total_matched": len(alignment.matches),
            "tolerance_ms": sync_tol,
        },
    )

    # 3. Completeness: speech segments with a match / total speech segments
    total_segments = len(alignment.matches) + len(alignment.unmatched_segments)
    if total_segments > 0:
        comp_score = len(alignment.matches) / total_segments
    else:
        comp_score = 1.0
    comp_thresh = thresholds.get("completeness", 0.98)
    comp_dim = DimensionScore(
        score=round(comp_score, 4),
        threshold=comp_thresh,
        status=compute_dimension_status(comp_score, comp_thresh),
        counts={"matched_segments": len(alignment.matches), "total_segments": total_segments},
    )

    # 4. Readability: 1 - (cues with any DUR/CPS/CPL/LINES/GAP violation / total cues)
    readability_codes = {"DUR_MIN", "DUR_MAX", "CPS", "CPL", "LINES", "GAP_MIN", "OVERLAP"}
    violating_cues: Set[int] = set()
    for f in findings:
        if f.code in readability_codes and f.cue_index is not None:
            violating_cues.add(f.cue_index)

    if cues:
        readability_score = max(0.0, 1.0 - (len(violating_cues) / len(cues)))
    else:
        readability_score = 1.0
    read_thresh = thresholds.get("readability", 0.95)
    read_dim = DimensionScore(
        score=round(readability_score, 4),
        threshold=read_thresh,
        status=compute_dimension_status(readability_score, read_thresh),
        counts={"violating_cues": len(violating_cues), "total_cues": len(cues)},
    )

    # 5. SDH Coverage: tagged salient events (0.5) + labeled off-screen segments (0.5)
    sdh_dim = None
    if sdh_mode:
        events = audio_events or []
        salient_events = [e for e in events if e.salience == "plot"]
        missing_sfx = [f for f in findings if f.code == "SDH_MISSING_SFX"]
        if salient_events:
            sfx_coverage = max(0.0, 1.0 - (len(missing_sfx) / len(salient_events)))
        else:
            sfx_coverage = 1.0

        all_segments = [p.segment for p in alignment.matches] + alignment.unmatched_segments
        offscreen_segs = [s for s in all_segments if s.speaker_on_screen is False]
        missing_speaker = [f for f in findings if f.code == "SDH_MISSING_SPEAKER_ID"]
        if offscreen_segs:
            spk_coverage = max(0.0, 1.0 - (len(missing_speaker) / len(offscreen_segs)))
        else:
            spk_coverage = 1.0

        if salient_events and offscreen_segs:
            sdh_score = (sfx_coverage * 0.5) + (spk_coverage * 0.5)
        elif salient_events:
            sdh_score = sfx_coverage
        elif offscreen_segs:
            sdh_score = spk_coverage
        else:
            sdh_score = 1.0

        sdh_thresh = thresholds.get("sdh", 0.90)
        sdh_dim = DimensionScore(
            score=round(sdh_score, 4),
            threshold=sdh_thresh,
            status=compute_dimension_status(sdh_score, sdh_thresh),
            counts={
                "salient_events": len(salient_events),
                "missing_sfx": len(missing_sfx),
                "offscreen_segments": len(offscreen_segs),
                "missing_speakers": len(missing_speaker),
            },
        )

    # 6. AD Coverage: described essential events / essential events
    ad_dim = None
    if ad_cues:
        v_events = visual_events or []
        essential_events = [e for e in v_events if e.essential]
        ad_gaps = [f for f in findings if f.code == "AD_GAP"]
        ad_overlaps = [f for f in findings if f.code == "AD_OVERLAPS_DIALOGUE"]

        if essential_events:
            ad_score = max(0.0, 1.0 - (len(ad_gaps) / len(essential_events)))
        else:
            ad_score = 1.0

        ad_thresh = thresholds.get("ad", 0.90)
        ad_dim = DimensionScore(
            score=round(ad_score, 4),
            threshold=ad_thresh,
            status=compute_dimension_status(ad_score, ad_thresh),
            counts={
                "essential_events": len(essential_events),
                "unvoiced_gaps": len(ad_gaps),
                "overlap_violations": len(ad_overlaps),
            },
        )

    # Compute overall status across all active dimensions
    all_dims = [accuracy_dim, sync_dim, comp_dim, read_dim]
    if sdh_dim:
        all_dims.append(sdh_dim)
    if ad_dim:
        all_dims.append(ad_dim)

    if any(d.status == "fail" for d in all_dims):
        overall: Literal["pass", "warn", "fail"] = "fail"
    elif any(d.status == "warn" for d in all_dims):
        overall = "warn"
    else:
        overall = "pass"

    return Scorecard(
        accuracy=accuracy_dim,
        synchronicity=sync_dim,
        completeness=comp_dim,
        readability=read_dim,
        sdh_coverage=sdh_dim,
        ad_coverage=ad_dim,
        overall_status=overall,
    )
