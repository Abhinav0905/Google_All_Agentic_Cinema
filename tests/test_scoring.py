"""Unit tests for scorecard calculator."""

import pytest

from engine.alignment import AlignmentResult, MatchedPair
from engine.models import Cue, Finding, Profile, Segment
from engine.profiles import load_profile
from engine.scoring import compute_dimension_status, compute_scorecard


@pytest.fixture
def adult_profile() -> Profile:
    return load_profile("adult")


def test_dimension_status_bands():
    threshold = 0.95
    assert compute_dimension_status(0.98, threshold) == "pass"
    assert compute_dimension_status(0.95, threshold) == "pass"
    # Warn band is [0.90, 0.95)
    assert compute_dimension_status(0.93, threshold) == "warn"
    assert compute_dimension_status(0.90, threshold) == "warn"
    # Below 0.90 is fail
    assert compute_dimension_status(0.89, threshold) == "fail"


def test_scorecard_perfect_scores(adult_profile):
    cues = [
        Cue(index=1, start_ms=1000, end_ms=3000, lines=["Hello"], raw_text="Hello"),
    ]
    seg = Segment(start_ms=1000, end_ms=3000, text="Hello", speaker_on_screen=True)
    alignment = AlignmentResult(
        matches=[MatchedPair(cue=cues[0], segment=seg, offset_ms=0, wer=0.0, similarity=1.0)],
        unmatched_cues=[],
        unmatched_segments=[],
        median_offset_ms=0,
        mean_wer=0.0,
    )
    scorecard = compute_scorecard(
        cues=cues,
        profile=adult_profile,
        alignment=alignment,
        findings=[],
        audio_events=[],
        visual_events=[],
        ad_cues=None,
        sdh_mode=True,
    )

    assert scorecard.overall_status == "pass"
    assert scorecard.accuracy.score == 1.0
    assert scorecard.synchronicity.score == 1.0
    assert scorecard.completeness.score == 1.0
    assert scorecard.readability.score == 1.0
    assert scorecard.sdh_coverage.score == 1.0


def test_scorecard_failing_dimensions(adult_profile):
    # Cue out of sync by 2000ms
    cues = [
        Cue(index=1, start_ms=3000, end_ms=5000, lines=["Hello"], raw_text="Hello"),
    ]
    seg = Segment(start_ms=1000, end_ms=3000, text="Hello", speaker_on_screen=True)
    alignment = AlignmentResult(
        matches=[MatchedPair(cue=cues[0], segment=seg, offset_ms=2000, wer=0.0, similarity=1.0)],
        unmatched_cues=[],
        unmatched_segments=[],
        median_offset_ms=2000,
        mean_wer=0.0,
    )
    finding = Finding(
        id="F1", code="SYNC_OFFSET", severity="error", cue_index=1,
        start_ms=3000, end_ms=5000, message="offset", evidence="", spec_ref="",
    )

    scorecard = compute_scorecard(
        cues=cues,
        profile=adult_profile,
        alignment=alignment,
        findings=[finding],
        audio_events=[],
        visual_events=[],
        ad_cues=None,
        sdh_mode=True,
    )

    # In sync is 0/1 = 0.0 -> fail
    assert scorecard.synchronicity.score == 0.0
    assert scorecard.synchronicity.status == "fail"
    assert scorecard.overall_status == "fail"
