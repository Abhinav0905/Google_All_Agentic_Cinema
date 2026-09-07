"""Golden test: verifies deterministic caption findings on captions_bad.srt
match expected_findings.json.
"""

import json
from pathlib import Path

from engine.parsers import parse_srt_file
from engine.profiles import load_profile
from engine.rules import run_caption_rules

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_golden_captions_bad():
    srt_path = SAMPLES_DIR / "captions_bad.srt"
    expected_path = SAMPLES_DIR / "expected_findings.json"

    assert srt_path.exists(), "captions_bad.srt does not exist"
    assert expected_path.exists(), "expected_findings.json does not exist"

    cues = parse_srt_file(srt_path)
    profile = load_profile("adult")
    findings = run_caption_rules(cues, profile)

    with open(expected_path, "r", encoding="utf-8") as f:
        expected_list = json.load(f)

    assert len(findings) == len(expected_list), (
        f"Expected {len(expected_list)} findings, got {len(findings)}: "
        f"{[(f.code, f.cue_index) for f in findings]}"
    )

    for actual, expected in zip(findings, expected_list):
        assert actual.code == expected["code"]
        assert actual.severity == expected["severity"]
        assert actual.cue_index == expected["cue_index"]
        assert actual.start_ms == expected["start_ms"]
        assert actual.end_ms == expected["end_ms"]
