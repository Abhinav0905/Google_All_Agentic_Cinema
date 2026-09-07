"""Unit tests for deterministic Fixer."""

import pytest

from engine.fixer import (
    apply_accepted_fixes,
    plan_fix_extend,
    plan_fix_insert_tag,
    plan_fix_normalize_tag,
    plan_fix_prepend_speaker,
    plan_fix_retime_ad,
    plan_fix_rewrap,
    plan_fix_split,
    plan_fix_trim,
    plan_fixes,
)
from engine.models import Cue, Finding, Fix, Profile, Segment
from engine.profiles import load_profile


@pytest.fixture
def adult_profile() -> Profile:
    return load_profile("adult")


def test_fix_trim_respects_min_gap_and_min_duration(adult_profile):
    # Cue 1 ends at 2500, Cue 2 starts at 2200 (overlap 300ms)
    cue1 = Cue(index=1, start_ms=1000, end_ms=2500, lines=["One"], raw_text="One")
    cue2 = Cue(index=2, start_ms=2200, end_ms=4000, lines=["Two"], raw_text="Two")
    finding = Finding(
        id="F1", code="OVERLAP", severity="error", cue_index=1,
        start_ms=1000, end_ms=2500, message="overlap", evidence="", spec_ref="",
    )

    fix = plan_fix_trim(finding, cue1, cue2, adult_profile)
    assert fix is not None
    assert fix.after is not None
    # Trimmed end_ms must be <= cue2.start_ms - min_gap_ms (2200 - 83 = 2117)
    assert fix.after.end_ms == 2200 - adult_profile.min_gap_ms.value
    # And duration must still be >= min_duration_ms
    assert fix.after.duration_ms >= adult_profile.min_duration_ms.value


def test_fix_extend_respects_gap_to_next(adult_profile):
    # Short cue (500ms), min_duration is 833ms
    cue1 = Cue(index=1, start_ms=1000, end_ms=1500, lines=["Hi"], raw_text="Hi")
    # Next cue starts at 3000ms (ample room to extend)
    cue2 = Cue(index=2, start_ms=3000, end_ms=5000, lines=["Next"], raw_text="Next")
    finding = Finding(
        id="F2", code="DUR_MIN", severity="error", cue_index=1,
        start_ms=1000, end_ms=1500, message="short", evidence="", spec_ref="",
    )

    fix = plan_fix_extend(finding, cue1, cue2, adult_profile)
    assert fix is not None
    assert fix.after is not None
    assert fix.after.end_ms == 1000 + adult_profile.min_duration_ms.value
    # Never encroaches closer than min_gap_ms to next cue
    assert fix.after.end_ms <= cue2.start_ms - adult_profile.min_gap_ms.value


def test_fix_rewrap(adult_profile):
    # One long line of 60 chars exceeding max_chars_per_line (42)
    long_text = "This is a rather long sentence that should be wrapped into two lines."
    cue = Cue(index=1, start_ms=1000, end_ms=4000, lines=[long_text], raw_text=long_text)
    finding = Finding(
        id="F3", code="CPL", severity="error", cue_index=1,
        start_ms=1000, end_ms=4000, message="long", evidence="", spec_ref="",
    )

    fix = plan_fix_rewrap(finding, cue, adult_profile)
    assert fix is not None
    assert fix.after is not None
    assert len(fix.after.lines) <= adult_profile.max_lines.value
    for line in fix.after.lines:
        assert len(line) <= adult_profile.max_chars_per_line.value


def test_fix_split_respects_min_durations(adult_profile):
    # Cue duration 4000ms with two clear clauses
    text = "Here is the first idea, and here is the second thought."
    cue = Cue(index=1, start_ms=1000, end_ms=5000, lines=[text], raw_text=text)
    finding = Finding(
        id="F4", code="CPS", severity="error", cue_index=1,
        start_ms=1000, end_ms=5000, message="cps", evidence="", spec_ref="",
    )

    res = plan_fix_split(finding, cue, adult_profile)
    assert res is not None
    c1, c2 = res
    assert c1.duration_ms >= adult_profile.min_duration_ms.value
    assert c2.duration_ms >= adult_profile.min_duration_ms.value
    assert c2.start_ms >= c1.end_ms + adult_profile.min_gap_ms.value


def test_fix_normalize_tag():
    cue = Cue(
        index=1, start_ms=1000, end_ms=3000,
        lines=["(DOOR SLAMS)"], raw_text="(DOOR SLAMS)",
    )
    finding = Finding(
        id="F5", code="TAG_FORMAT", severity="info", cue_index=1,
        start_ms=1000, end_ms=3000, message="tag", evidence="", spec_ref="",
    )

    fix = plan_fix_normalize_tag(finding, cue)
    assert fix is not None
    assert fix.after is not None
    assert fix.after.text == "[DOOR SLAMS]"


def test_fix_prepend_speaker():
    cue = Cue(
        index=1,
        start_ms=1000,
        end_ms=3000,
        lines=["Is anyone there?"],
        raw_text="Is anyone there?",
    )
    finding = Finding(
        id="F6", code="SDH_MISSING_SPEAKER_ID", severity="error", cue_index=1,
        start_ms=1000, end_ms=3000, message="missing speaker", evidence="", spec_ref="",
    )

    fix = plan_fix_prepend_speaker(finding, cue, "ALICE")
    assert fix.after is not None
    assert fix.after.lines[0] == "ALICE: Is anyone there?"


def test_fix_retime_ad(adult_profile):
    # Dialogue segments at [1000, 3000] and [7000, 9000] -> silence is [3083, 6917]
    segments = [
        Segment(start_ms=1000, end_ms=3000, text="First dialogue."),
        Segment(start_ms=7000, end_ms=9000, text="Second dialogue."),
    ]
    # AD cue currently at [2500, 4500] (overlapping dialogue)
    ad_cue = Cue(
        index=1, start_ms=2500, end_ms=4500,
        lines=["He checks the documents."], raw_text="He checks the documents.",
        kind="ad",
    )
    finding = Finding(
        id="F7", code="AD_OVERLAPS_DIALOGUE", severity="error", cue_index=1,
        start_ms=2500, end_ms=4500, message="overlap", evidence="", spec_ref="",
    )

    fix = plan_fix_retime_ad(finding, ad_cue, segments, adult_profile)
    assert fix.type == "retime_ad"
    assert fix.after is not None
    # Retimed into silence starting after 3000 + min_gap
    assert fix.after.start_ms >= 3000 + adult_profile.min_gap_ms.value
    assert fix.after.end_ms <= 7000 - adult_profile.min_gap_ms.value


def test_apply_accepted_fixes():
    cues = [
        Cue(index=1, start_ms=1000, end_ms=2000, lines=["Old text"], raw_text="Old text"),
        Cue(index=2, start_ms=3000, end_ms=4000, lines=["Keep me"], raw_text="Keep me"),
    ]
    replaced_cue = Cue(index=1, start_ms=1000, end_ms=2200, lines=["New text"], raw_text="New text")
    fix = Fix(
        id="FIX_1",
        finding_ids=["F1"],
        type="extend",
        before=cues[0],
        after=replaced_cue,
        status="accepted",
    )

    new_cues, _ = apply_accepted_fixes(cues, [fix])
    assert len(new_cues) == 2
    assert new_cues[0].text == "New text"
    assert new_cues[0].end_ms == 2200
    assert new_cues[1].text == "Keep me"


def test_fix_insert_tag():
    finding = Finding(
        id="F8",
        code="SDH_MISSING_SFX",
        severity="error",
        start_ms=18500,
        end_ms=19500,
        message="missing sfx",
        evidence="Event '[PHONE RINGS]' at 18500ms has no caption sound tag",
        spec_ref="",
    )
    fix = plan_fix_insert_tag(finding, 18500, "[PHONE RINGS]")
    assert fix.type == "insert_tag_cue"
    assert fix.before is None
    assert fix.after is not None
    assert fix.after.text == "[PHONE RINGS]"
    assert fix.after.start_ms == 18500


def test_apply_split_keeps_both_halves(adult_profile):
    text = "Here is the first idea, and here is the second thought."
    cue = Cue(index=1, start_ms=1000, end_ms=5000, lines=[text], raw_text=text)
    finding = Finding(
        id="F9",
        code="CPS",
        severity="error",
        cue_index=1,
        start_ms=1000,
        end_ms=5000,
        message="cps",
        evidence="",
        spec_ref="",
    )
    halves = plan_fix_split(finding, cue, adult_profile)
    assert halves is not None
    c1, c2 = halves
    fix = Fix(
        id="FIX_F9",
        finding_ids=["F9"],
        type="split",
        before=cue,
        after=c1,
        after_extra=c2,
        status="accepted",
    )
    new_cues, _ = apply_accepted_fixes([cue], [fix])
    assert len(new_cues) == 2
    assert new_cues[0].duration_ms >= adult_profile.min_duration_ms.value
    assert new_cues[1].duration_ms >= adult_profile.min_duration_ms.value


def test_extend_never_violates_gap_rule(adult_profile):
    cue1 = Cue(index=1, start_ms=1000, end_ms=1400, lines=["Hi there"], raw_text="Hi there")
    cue2 = Cue(index=2, start_ms=1600, end_ms=3000, lines=["Next"], raw_text="Next")
    finding = Finding(
        id="F10",
        code="DUR_MIN",
        severity="error",
        cue_index=1,
        start_ms=1000,
        end_ms=1400,
        message="short",
        evidence="",
        spec_ref="",
    )
    fix = plan_fix_extend(finding, cue1, cue2, adult_profile)
    # Not enough room to reach min duration without violating gap -> no auto extend
    if fix is not None and fix.after is not None:
        assert fix.after.end_ms <= cue2.start_ms - adult_profile.min_gap_ms.value


def test_plan_fixes_links_fix_id(adult_profile):
    cues = [
        Cue(index=1, start_ms=1000, end_ms=1200, lines=[""], raw_text=""),
    ]
    finding = Finding(
        id="EMPTY_1_1000",
        code="EMPTY",
        severity="warning",
        cue_index=1,
        start_ms=1000,
        end_ms=1200,
        message="blank",
        evidence="",
        spec_ref="",
    )
    fixes = plan_fixes([finding], cues, adult_profile)
    assert len(fixes) == 1
    assert finding.fix_id == fixes[0].id
