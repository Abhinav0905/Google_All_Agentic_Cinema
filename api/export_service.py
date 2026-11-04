"""Regenerate deliverables from accepted fixes and re-score the result."""

from typing import List, Optional, Tuple

from api.store import StoredRun
from engine.alignment import AlignmentResult, align_cues_to_segments
from engine.export import export_cues
from engine.fixer import apply_accepted_fixes
from engine.models import Cue, Finding, Profile, Scorecard
from engine.profiles import load_profile
from engine.report import generate_html_report
from engine.rules import run_caption_rules, run_semantic_rules
from engine.scoring import compute_scorecard


def rescore_cues(
    stored: StoredRun,
    cues: List[Cue],
    ad_cues: Optional[List[Cue]],
    profile: Profile,
) -> Tuple[Scorecard, List[Finding]]:
    caption_findings = run_caption_rules(cues, profile)
    media_analyzed = stored.run.analysis_mode != "caption_only"
    alignment = (
        align_cues_to_segments(cues, stored.segments, profile)
        if media_analyzed
        else AlignmentResult()
    )
    semantic_findings = (
        run_semantic_rules(
            profile=profile,
            alignment=alignment,
            audio_events=stored.audio_events,
            visual_events=stored.visual_events,
            captions=cues,
            ad_cues=ad_cues,
            sdh_mode=stored.run.sdh_mode,
        )
        if media_analyzed
        else []
    )
    findings = caption_findings + alignment.findings + semantic_findings
    scorecard = compute_scorecard(
        cues=cues,
        profile=profile,
        alignment=alignment,
        findings=findings,
        audio_events=stored.audio_events,
        visual_events=stored.visual_events,
        ad_cues=ad_cues,
        sdh_mode=stored.run.sdh_mode,
        media_analyzed=media_analyzed,
    )
    return scorecard, findings


def apply_and_export(stored: StoredRun, fmt: str) -> Tuple[str, str]:
    """Return (media_type, body) for an export format."""
    profile = load_profile(stored.run.profile_id)
    median = 0
    # Median offset is stored on the first global_shift after cue start_ms hack
    for fix in stored.run.fixes:
        if fix.type == "global_shift" and fix.after is not None:
            median = fix.after.start_ms
            break

    new_cues, new_ad = apply_accepted_fixes(
        stored.cues, stored.run.fixes, stored.ad_cues or [], median_shift_ms=median
    )
    after_scorecard, after_findings = rescore_cues(stored, new_cues, new_ad, profile)
    stored.after_scorecard = after_scorecard

    if fmt == "srt":
        return "application/x-subrip", export_cues(new_cues, "srt")
    if fmt == "vtt":
        return "text/vtt", export_cues(new_cues, "vtt")
    if fmt == "json":
        import json

        payload = {
            "run": stored.run.model_dump(),
            "after_scorecard": after_scorecard.model_dump(),
            "after_findings": [f.model_dump() for f in after_findings],
            "cues": [c.model_dump() for c in new_cues],
            "ad_cues": [c.model_dump() for c in new_ad],
        }
        return "application/json", json.dumps(payload, indent=2)
    if fmt == "report":
        html = generate_html_report(
            run_id=stored.run.id,
            profile=profile,
            scorecard=stored.run.scorecard,
            findings=stored.run.findings,
            fixes=stored.run.fixes,
            after_scorecard=after_scorecard,
            created_at=stored.run.created_at,
        )
        return "text/html", html
    raise ValueError(f"Unsupported export format: {fmt}")
