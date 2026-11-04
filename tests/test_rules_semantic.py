"""Unit tests for semantic accessibility checks (SDH and Audio Description)."""

import pytest

from engine.alignment import AlignmentResult, MatchedPair
from engine.models import AudioEvent, Cue, Segment, VisualEvent
from engine.profiles import load_profile
from engine.rules.semantic import (
    check_ad_gap,
    check_ad_onscreen_text,
    check_ad_overlaps_dialogue,
    check_ad_reading_rate,
    check_sdh_missing_sfx,
    check_sdh_missing_speaker_id,
    run_semantic_rules,
)


@pytest.fixture
def adult_profile():
    return load_profile("adult")


def test_sdh_missing_sfx():
    # Audio event at 5000ms
    audio_events = [
        AudioEvent(t_ms=5000, label="[DOOR SLAMS]", salience="plot", source="gemini"),
        AudioEvent(t_ms=10000, label="[TRAFFIC HUM]", salience="ambient", source="gemini"),
    ]

    # No cues around 5000ms
    cues = [
        Cue(index=1, start_ms=1000, end_ms=3000, lines=["Hello"], raw_text="Hello"),
        Cue(
            index=2,
            start_ms=9500,
            end_ms=11000,
            lines=["[TRAFFIC HUM]"],
            raw_text="[TRAFFIC HUM]",
        ),
    ]

    findings = check_sdh_missing_sfx(audio_events, cues)
    assert len(findings) == 1
    assert findings[0].code == "SDH_MISSING_SFX"
    assert findings[0].severity == "error"  # plot event is error
    assert "DOOR SLAMS" in findings[0].message


def test_sdh_missing_speaker_id():
    cue1 = Cue(
        index=1,
        start_ms=1000,
        end_ms=3000,
        lines=["Where is everyone?"],
        raw_text="Where is everyone?",
    )
    seg1 = Segment(
        start_ms=1000,
        end_ms=3000,
        text="Where is everyone?",
        speaker_label="Alex",
        speaker_on_screen=False,
    )
    pair1 = MatchedPair(cue=cue1, segment=seg1, offset_ms=0, wer=0.0, similarity=1.0)

    cue2 = Cue(
        index=2,
        start_ms=4000,
        end_ms=6000,
        lines=["SARAH: Right here!"],
        raw_text="SARAH: Right here!",
    )
    seg2 = Segment(
        start_ms=4000,
        end_ms=6000,
        text="Right here!",
        speaker_label="Sarah",
        speaker_on_screen=False,
    )
    pair2 = MatchedPair(cue=cue2, segment=seg2, offset_ms=0, wer=0.0, similarity=1.0)

    alignment = AlignmentResult(matches=[pair1, pair2])
    findings = check_sdh_missing_speaker_id(alignment)

    assert len(findings) == 1
    assert findings[0].code == "SDH_MISSING_SPEAKER_ID"
    assert findings[0].cue_index == 1


def test_ad_overlaps_dialogue(adult_profile):
    # ad_overlap_tolerance_ms is 250ms
    segments = [
        Segment(start_ms=2000, end_ms=5000, text="Important dialogue."),
    ]
    # AD cue overlaps dialogue from 2000 to 3000 (1000ms overlap > 250ms)
    ad_cues = [
        Cue(
            index=1,
            start_ms=1500,
            end_ms=3000,
            lines=["He looks out the window."],
            raw_text="He looks out the window.",
            kind="ad",
        )
    ]
    findings = check_ad_overlaps_dialogue(ad_cues, segments, adult_profile)
    assert len(findings) == 1
    assert findings[0].code == "AD_OVERLAPS_DIALOGUE"
    assert findings[0].severity == "error"


def test_ad_gap():
    visual_events = [
        VisualEvent(
            t_ms=5000, label="He drops the glass on the floor", essential=True, kind="action"
        ),
        VisualEvent(
            t_ms=12000, label="Subtle breeze moves the curtain", essential=False, kind="action"
        ),
    ]
    # No AD cue in [4000, 9000]
    ad_cues = [
        Cue(
            index=1,
            start_ms=1000,
            end_ms=2000,
            lines=["Morning light enters the room."],
            raw_text="Morning light enters the room.",
            kind="ad",
        )
    ]
    findings = check_ad_gap(visual_events, ad_cues)
    assert len(findings) == 1
    assert findings[0].code == "AD_GAP"
    assert findings[0].severity == "error"
    assert "drops the glass" in findings[0].message


def test_ad_onscreen_text():
    visual_events = [
        VisualEvent(t_ms=3000, label="SAN FRANCISCO - 1985", essential=True, kind="onscreen_text")
    ]
    captions = [Cue(index=1, start_ms=1000, end_ms=2000, lines=["Hello"], raw_text="Hello")]
    ad_cues = [
        Cue(
            index=1,
            start_ms=1000,
            end_ms=2000,
            lines=["A quiet road."],
            raw_text="A quiet road.",
            kind="ad",
        )
    ]
    findings = check_ad_onscreen_text(visual_events, captions, ad_cues)
    assert len(findings) == 1
    assert findings[0].code == "AD_ONSCREEN_TEXT"
    assert findings[0].severity == "warning"


def test_ad_reading_rate(adult_profile):
    # adult ad_max_wpm is 180
    # 20 words in 3 seconds = 400 wpm
    fast_text = (
        "The man walks quickly through the bustling crowded marketplace "
        "avoiding all the passing vendors."
    )
    fast_ad = Cue(
        index=1,
        start_ms=1000,
        end_ms=4000,
        lines=[fast_text],
        raw_text=fast_text,
        kind="ad",
    )
    findings = check_ad_reading_rate([fast_ad], adult_profile)
    assert len(findings) == 1
    assert findings[0].code == "AD_READING_RATE"
    assert findings[0].severity == "warning"


def test_run_semantic_rules_toggles(adult_profile):
    alignment = AlignmentResult()
    audio_events = [AudioEvent(t_ms=1000, label="[DOOR SLAMS]", salience="plot", source="gemini")]
    visual_events = []
    captions = []

    # SDH mode OFF -> no SDH findings
    findings_sdh_off = run_semantic_rules(
        profile=adult_profile,
        alignment=alignment,
        audio_events=audio_events,
        visual_events=visual_events,
        captions=captions,
        ad_cues=None,
        sdh_mode=False,
    )
    assert len(findings_sdh_off) == 0

    # SDH mode ON -> findings present
    findings_sdh_on = run_semantic_rules(
        profile=adult_profile,
        alignment=alignment,
        audio_events=audio_events,
        visual_events=visual_events,
        captions=captions,
        ad_cues=None,
        sdh_mode=True,
    )
    assert len(findings_sdh_on) == 1


def test_one_ad_cue_overlapping_two_live_speech_segments_has_one_linked_repair(adult_profile):
    from engine.fixer import plan_fixes

    ad = Cue(
        index=2,
        start_ms=5200,
        end_ms=6800,
        kind="ad",
        lines=["The report appears."],
        raw_text="The report appears.",
    )
    segments = [
        Segment(start_ms=2500, end_ms=5470, text="Welcome to the briefing."),
        Segment(start_ms=6170, end_ms=7880, text="The quarterly numbers are out."),
    ]
    findings = check_ad_overlaps_dialogue([ad], segments, adult_profile)
    assert len(findings) == 1
    assert "2500-5470ms" in findings[0].evidence
    assert "6170-7880ms" in findings[0].evidence
    assert "overlap 270ms" in findings[0].evidence
    assert "overlap 630ms" in findings[0].evidence
    alignment = AlignmentResult(unmatched_segments=segments)
    fixes = plan_fixes(findings, [], adult_profile, alignment=alignment, ad_cues=[ad])
    assert len(fixes) == 1
    assert fixes[0].finding_ids == [findings[0].id]
    assert findings[0].fix_id == fixes[0].id


def test_simultaneous_events_preserve_all_observations_and_unique_ids(adult_profile):
    from engine.fixer import plan_fixes

    audio = [
        AudioEvent(t_ms=5000, label="[PHONE RINGS]"),
        AudioEvent(t_ms=5000, label="[DOOR SLAMS]"),
        AudioEvent(t_ms=5000, label="[PHONE RINGS]"),
    ]
    findings = check_sdh_missing_sfx(audio, [])
    assert len(findings) == len({f.id for f in findings}) == 3
    fixes = plan_fixes(findings, [], adult_profile)
    assert len(fixes) == len({f.id for f in fixes}) == 2
    assert sorted(fid for fix in fixes for fid in fix.finding_ids) == sorted(f.id for f in findings)
    assert findings[0].fix_id == findings[2].fix_id
    visual = [
        VisualEvent(t_ms=5000, label="Confidential", kind="onscreen_text"),
        VisualEvent(t_ms=5000, label="Revenue", kind="onscreen_text"),
    ]
    for check in (lambda: check_ad_gap(visual, []), lambda: check_ad_onscreen_text(visual, [], [])):
        found = check()
        assert len(found) == len({f.id for f in found}) == 2
