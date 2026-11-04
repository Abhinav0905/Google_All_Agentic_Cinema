"""Unit tests for every deterministic caption-only rule in Section 6."""

import pytest

from engine.models import Cue
from engine.profiles import load_profile
from engine.rules.caption_rules import (
    check_cpl,
    check_cps,
    check_duration,
    check_empty,
    check_gap_and_overlap,
    check_lines,
    check_order,
    check_tag_format,
    run_caption_rules,
)


@pytest.fixture
def adult_profile():
    return load_profile("adult")


def test_rule_empty():
    blank_cue = Cue(index=1, start_ms=1000, end_ms=3000, lines=["   "], raw_text="   ")
    findings = check_empty(blank_cue)
    assert len(findings) == 1
    assert findings[0].code == "EMPTY"
    assert findings[0].severity == "warning"

    normal_cue = Cue(index=2, start_ms=1000, end_ms=3000, lines=["Hello"], raw_text="Hello")
    assert len(check_empty(normal_cue)) == 0


def test_rule_order():
    # Inverted timing (start >= end)
    inverted_cue = Cue(index=1, start_ms=3000, end_ms=2000, lines=["Error"], raw_text="Error")
    findings = check_order(inverted_cue, None)
    assert len(findings) == 1
    assert findings[0].code == "ORDER"
    assert findings[0].severity == "error"

    # Start before previous start
    cue1 = Cue(index=1, start_ms=5000, end_ms=7000, lines=["One"], raw_text="One")
    cue2 = Cue(index=2, start_ms=4000, end_ms=6000, lines=["Two"], raw_text="Two")
    findings2 = check_order(cue2, cue1)
    assert len(findings2) == 1
    assert findings2[0].code == "ORDER"


def test_rule_duration_min(adult_profile):
    # min_duration is 833ms
    short_cue = Cue(index=1, start_ms=1000, end_ms=1500, lines=["Fast"], raw_text="Fast")  # 500ms
    findings = check_duration(short_cue, adult_profile)
    assert any(f.code == "DUR_MIN" and f.severity == "error" for f in findings)

    valid_cue = Cue(index=2, start_ms=1000, end_ms=2000, lines=["OK"], raw_text="OK")  # 1000ms
    assert not any(f.code == "DUR_MIN" for f in check_duration(valid_cue, adult_profile))


def test_rule_duration_max(adult_profile):
    # max_duration is 7000ms
    long_cue = Cue(
        index=1, start_ms=1000, end_ms=9000, lines=["Too long"], raw_text="Too long"
    )  # 8000ms
    findings = check_duration(long_cue, adult_profile)
    assert any(f.code == "DUR_MAX" and f.severity == "warning" for f in findings)


def test_rule_cps(adult_profile):
    # max_cps is 20 for adult
    # 50 chars in 1.0s = 50 cps
    fast_cue = Cue(
        index=1,
        start_ms=1000,
        end_ms=2000,
        lines=["This text is way too fast to read in one second!"],
        raw_text="This text is way too fast to read in one second!",
    )
    findings = check_cps(fast_cue, adult_profile)
    assert len(findings) == 1
    assert findings[0].code == "CPS"
    assert findings[0].severity == "error"

    # HTML tags should be excluded from CPS calculation
    tag_cue = Cue(
        index=2,
        start_ms=1000,
        end_ms=3000,
        lines=["<i>Short</i>"],
        raw_text="<i>Short</i>",
    )  # "Short" is 5 chars / 2s = 2.5 cps
    assert len(check_cps(tag_cue, adult_profile)) == 0


def test_rule_cpl(adult_profile):
    # max_chars_per_line is 42
    long_line = "A" * 45
    cue = Cue(index=1, start_ms=1000, end_ms=3000, lines=[long_line], raw_text=long_line)
    findings = check_cpl(cue, adult_profile)
    assert len(findings) == 1
    assert findings[0].code == "CPL"
    assert findings[0].severity == "error"

    valid_cue = Cue(
        index=2, start_ms=1000, end_ms=3000, lines=["A" * 42], raw_text="A" * 42
    )
    assert len(check_cpl(valid_cue, adult_profile)) == 0


def test_rule_lines(adult_profile):
    # max_lines is 2
    cue_three_lines = Cue(
        index=1,
        start_ms=1000,
        end_ms=4000,
        lines=["Line 1", "Line 2", "Line 3"],
        raw_text="Line 1\nLine 2\nLine 3",
    )
    findings = check_lines(cue_three_lines, adult_profile)
    assert len(findings) == 1
    assert findings[0].code == "LINES"
    assert findings[0].severity == "error"


def test_rule_gap_min(adult_profile):
    # min_gap_ms is 83ms
    cue1 = Cue(index=1, start_ms=1000, end_ms=2000, lines=["One"], raw_text="One")
    cue2 = Cue(index=2, start_ms=2040, end_ms=3000, lines=["Two"], raw_text="Two")  # gap = 40ms
    findings = check_gap_and_overlap(cue1, cue2, adult_profile)
    assert any(f.code == "GAP_MIN" and f.severity == "warning" for f in findings)

    # Valid gap (100ms)
    cue3 = Cue(index=3, start_ms=2100, end_ms=3000, lines=["Three"], raw_text="Three")
    assert not any(f.code == "GAP_MIN" for f in check_gap_and_overlap(cue1, cue3, adult_profile))


def test_rule_overlap(adult_profile):
    cue1 = Cue(index=1, start_ms=1000, end_ms=2500, lines=["One"], raw_text="One")
    cue2 = Cue(index=2, start_ms=2200, end_ms=3000, lines=["Two"], raw_text="Two")  # overlaps 300ms
    findings = check_gap_and_overlap(cue1, cue2, adult_profile)
    assert any(f.code == "OVERLAP" and f.severity == "error" for f in findings)


def test_rule_tag_format():
    # Parentheses used for sound effects instead of brackets
    paren_cue = Cue(
        index=1,
        start_ms=1000,
        end_ms=3000,
        lines=["(DOOR SLAMS)"],
        raw_text="(DOOR SLAMS)",
    )
    findings = check_tag_format(paren_cue)
    assert any(f.code == "TAG_FORMAT" and f.severity == "info" for f in findings)

    # Unpaired music note
    unpaired_cue = Cue(
        index=2,
        start_ms=1000,
        end_ms=3000,
        lines=["♪ Sing a single song"],
        raw_text="♪ Sing a single song",
    )
    findings2 = check_tag_format(unpaired_cue)
    assert any(f.code == "TAG_FORMAT" and f.severity == "info" for f in findings2)

    # Valid bracketed sound tag
    valid_cue = Cue(
        index=3,
        start_ms=1000,
        end_ms=3000,
        lines=["[DOOR SLAMS]", "♪ Sing a full song ♪"],
        raw_text="[DOOR SLAMS]\n♪ Sing a full song ♪",
    )
    assert len(check_tag_format(valid_cue)) == 0


def test_run_all_caption_rules(adult_profile):
    fast_text = "Too fast and short!" * 3
    cues = [
        Cue(index=1, start_ms=1000, end_ms=2000, lines=["Valid cue"], raw_text="Valid cue"),
        Cue(index=2, start_ms=2050, end_ms=2100, lines=[fast_text], raw_text=fast_text),
    ]
    findings = run_caption_rules(cues, adult_profile)
    assert len(findings) > 0
