"""Semantic rules engine for SDH and Audio Description (AD) QC.

Evaluates:
- SDH_MISSING_SFX: salient audio event without tagged caption cue in [t-1s, t+2s]
- SDH_MISSING_SPEAKER_ID: off-screen speech segment without speaker label on cue
- AD_OVERLAPS_DIALOGUE: AD cue overlapping speech segment > tolerance
- AD_GAP: essential visual event undescribed in [t-1s, t+4s]
- AD_ONSCREEN_TEXT: onscreen text not read by AD or captions
- AD_READING_RATE: AD cue words per minute exceeding ad_max_wpm
"""

import re
from typing import List, Optional

from engine.alignment import AlignmentResult
from engine.models import AudioEvent, Cue, Finding, Profile, Segment, VisualEvent

RE_SPEAKER_LABEL = re.compile(r"^[A-Z0-9\s\-]+:|^\[[a-zA-Z0-9\s\-]+\]|^\([a-zA-Z0-9\s\-]+\)")


def check_sdh_missing_sfx(
    audio_events: List[AudioEvent],
    cues: List[Cue],
) -> List[Finding]:
    """SDH_MISSING_SFX: salient audio event with no tagged cue in [t-1000ms, t+2000ms]."""
    findings: List[Finding] = []

    for event_index, event in enumerate(audio_events):
        window_start = event.t_ms - 1000
        window_end = event.t_ms + 2000

        has_tag = False
        for cue in cues:
            # Overlaps window
            if cue.end_ms >= window_start and cue.start_ms <= window_end:
                text = cue.raw_text
                # Check for SDH brackets, parentheses or music notes
                if re.search(r"\[.+?\]|\(.+?\)|♪", text):
                    has_tag = True
                    break

        if not has_tag:
            severity = "error" if event.salience == "plot" else "warning"
            findings.append(
                Finding(
                    id=f"SDH_MISSING_SFX_{event.t_ms}_{event_index}",
                    code="SDH_MISSING_SFX",
                    severity=severity,
                    cue_index=None,
                    start_ms=event.t_ms,
                    end_ms=event.t_ms + 1000,
                    message=(
                        f"Missing SDH sound tag for {event.salience} audio event: {event.label}"
                    ),
                    evidence=(f"Event '{event.label}' at {event.t_ms}ms has no caption sound tag"),
                    spec_ref="SDH audio description standard for non-speech sound effects",
                )
            )

    return findings


def check_sdh_missing_speaker_id(
    alignment: AlignmentResult,
) -> List[Finding]:
    """SDH_MISSING_SPEAKER_ID: off-screen speech with no speaker label on matched cue."""
    findings: List[Finding] = []

    for pair in alignment.matches:
        seg = pair.segment
        cue = pair.cue

        # Only flag if visual pass identified speaker as definitely off-screen
        if seg.speaker_on_screen is False:
            first_line = cue.lines[0] if cue.lines else cue.raw_text
            if not RE_SPEAKER_LABEL.search(first_line.strip()):
                label = seg.speaker_label or "SPEAKER"
                findings.append(
                    Finding(
                        id=f"SDH_MISSING_SPEAKER_ID_{cue.index}_{cue.start_ms}",
                        code="SDH_MISSING_SPEAKER_ID",
                        severity="error",
                        cue_index=cue.index,
                        start_ms=cue.start_ms,
                        end_ms=cue.end_ms,
                        message=(f"Off-screen dialogue missing speaker label: '{cue.text}'"),
                        evidence=(
                            f"Speaker '{label}' is off-screen at {seg.start_ms}ms, "
                            f"cue {cue.index} lacks speaker identification prefix"
                        ),
                        spec_ref="SDH off-screen speaker identification guideline",
                    )
                )

    return findings


def check_ad_overlaps_dialogue(
    ad_cues: List[Cue],
    segments: List[Segment],
    profile: Profile,
) -> List[Finding]:
    """AD_OVERLAPS_DIALOGUE: AD cue overlaps speech segment beyond tolerance."""
    findings: List[Finding] = []
    tol_ms = profile.ad_overlap_tolerance_ms.value

    for ad_cue in ad_cues:
        overlaps = []
        for seg in segments:
            overlap = min(ad_cue.end_ms, seg.end_ms) - max(ad_cue.start_ms, seg.start_ms)
            if overlap > tol_ms:
                overlaps.append((seg, overlap))
        if overlaps:
            evidence = "; ".join(
                f"speech ({seg.start_ms}-{seg.end_ms}ms), overlap {overlap}ms: '{seg.text}'"
                for seg, overlap in overlaps
            )
            findings.append(
                Finding(
                    id=f"AD_OVERLAPS_DIALOGUE_{ad_cue.index}_{ad_cue.start_ms}",
                    code="AD_OVERLAPS_DIALOGUE",
                    severity="error",
                    cue_index=ad_cue.index,
                    start_ms=ad_cue.start_ms,
                    end_ms=ad_cue.end_ms,
                    message=(
                        f"Audio Description cue {ad_cue.index} overlaps "
                        f"{len(overlaps)} speech segment(s) beyond the {tol_ms}ms tolerance"
                    ),
                    evidence=(
                        f"AD cue {ad_cue.index} ({ad_cue.start_ms}-{ad_cue.end_ms}ms) "
                        f"overlaps {evidence}"
                    ),
                    spec_ref=profile.ad_overlap_tolerance_ms.source,
                )
            )

    return findings


def check_ad_gap(
    visual_events: List[VisualEvent],
    ad_cues: List[Cue],
) -> List[Finding]:
    """AD_GAP: essential visual event with no AD cue in [t-1000ms, t+4000ms]."""
    findings: List[Finding] = []

    for event_index, event in enumerate(visual_events):
        if not event.essential:
            continue

        window_start = event.t_ms - 1000
        window_end = event.t_ms + 4000

        covered = False
        for ad_cue in ad_cues:
            if ad_cue.end_ms >= window_start and ad_cue.start_ms <= window_end:
                covered = True
                break

        if not covered:
            findings.append(
                Finding(
                    id=f"AD_GAP_{event.t_ms}_{event_index}",
                    code="AD_GAP",
                    severity="error",
                    cue_index=None,
                    start_ms=event.t_ms,
                    end_ms=event.t_ms + 2000,
                    message=f"Essential visual event undescribed: {event.label}",
                    evidence=f"Visual event '{event.label}' at {event.t_ms}ms has no AD narration",
                    spec_ref="Audio description completeness for essential visual storytelling",
                )
            )

    return findings


def check_ad_onscreen_text(
    visual_events: List[VisualEvent],
    captions: List[Cue],
    ad_cues: List[Cue],
) -> List[Finding]:
    """AD_ONSCREEN_TEXT: on-screen text not read by AD or captions."""
    findings: List[Finding] = []
    text_events = [e for e in visual_events if e.kind == "onscreen_text"]

    for event_index, event in enumerate(text_events):
        label_lower = event.label.lower().strip()
        window_start = event.t_ms - 2000
        window_end = event.t_ms + 6000

        found = False
        # Check captions
        for cue in captions:
            if cue.end_ms >= window_start and cue.start_ms <= window_end:
                if label_lower in cue.raw_text.lower():
                    found = True
                    break

        # Check AD
        if not found:
            for ad in ad_cues:
                if ad.end_ms >= window_start and ad.start_ms <= window_end:
                    if label_lower in ad.raw_text.lower():
                        found = True
                        break

        if not found:
            findings.append(
                Finding(
                    id=f"AD_ONSCREEN_TEXT_{event.t_ms}_{event_index}",
                    code="AD_ONSCREEN_TEXT",
                    severity="warning",
                    cue_index=None,
                    start_ms=event.t_ms,
                    end_ms=event.t_ms + 2000,
                    message=f"On-screen text not read by AD or captions: '{event.label}'",
                    evidence=f"On-screen graphic text '{event.label}' at {event.t_ms}ms unvoiced",
                    spec_ref="Accessibility guidelines for on-screen textual information",
                )
            )

    return findings


def check_ad_reading_rate(
    ad_cues: List[Cue],
    profile: Profile,
) -> List[Finding]:
    """AD_READING_RATE: AD cue words per minute exceeding ad_max_wpm."""
    findings: List[Finding] = []
    max_wpm = profile.ad_max_wpm.value

    for cue in ad_cues:
        words = re.findall(r"\b\w+\b", cue.raw_text)
        duration_min = (cue.end_ms - cue.start_ms) / 60000.0
        if duration_min <= 0:
            continue

        wpm = round(len(words) / duration_min, 1)
        if wpm > max_wpm:
            findings.append(
                Finding(
                    id=f"AD_READING_RATE_{cue.index}_{cue.start_ms}",
                    code="AD_READING_RATE",
                    severity="warning",
                    cue_index=cue.index,
                    start_ms=cue.start_ms,
                    end_ms=cue.end_ms,
                    message=f"AD reading rate ({wpm:.0f} WPM) exceeds maximum ({max_wpm} WPM)",
                    evidence=(
                        f"word_count={len(words)}, duration={duration_min * 60:.1f}s, wpm={wpm}"
                    ),
                    spec_ref=profile.ad_max_wpm.source,
                )
            )

    return findings


def run_semantic_rules(
    profile: Profile,
    alignment: AlignmentResult,
    audio_events: List[AudioEvent],
    visual_events: List[VisualEvent],
    captions: List[Cue],
    ad_cues: Optional[List[Cue]] = None,
    sdh_mode: bool = True,
) -> List[Finding]:
    """Run all semantic checks based on sdh_mode and presence of AD script."""
    findings: List[Finding] = []

    # SDH checks
    if sdh_mode:
        findings.extend(check_sdh_missing_sfx(audio_events, captions))
        findings.extend(check_sdh_missing_speaker_id(alignment))

    # Audio Description checks
    if ad_cues:
        all_segments = [p.segment for p in alignment.matches] + alignment.unmatched_segments
        findings.extend(check_ad_overlaps_dialogue(ad_cues, all_segments, profile))
        findings.extend(check_ad_gap(visual_events, ad_cues))
        findings.extend(check_ad_onscreen_text(visual_events, captions, ad_cues))
        findings.extend(check_ad_reading_rate(ad_cues, profile))

    return findings
