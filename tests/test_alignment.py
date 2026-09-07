"""Alignment tests with synthetic transcripts and captions."""

from engine.alignment import (
    align_cues_to_segments,
    compute_wer,
    normalize_tokens,
    token_similarity,
)
from engine.models import Cue, Segment
from engine.profiles import load_profile


def test_token_normalization():
    text = "[DOOR SLAMS] Hello, world! How's it going? ♪"
    tokens = normalize_tokens(text)
    assert tokens == ["hello", "world", "how", "s", "it", "going"]


def test_wer_computation():
    ref = ["the", "quick", "brown", "fox"]
    hyp1 = ["the", "quick", "brown", "fox"]
    assert compute_wer(ref, hyp1) == 0.0

    hyp2 = ["the", "fast", "brown", "fox"]  # 1 substitution / 4 = 0.25
    assert compute_wer(ref, hyp2) == 0.25

    hyp3 = ["the", "quick"]  # 2 deletions / 4 = 0.5
    assert compute_wer(ref, hyp3) == 0.5


def test_token_similarity():
    t1 = ["welcome", "to", "the", "team"]
    t2 = ["welcome", "to", "our", "team"]
    assert token_similarity(t1, t2) == 3 / 5  # intersection=3, union=5


def test_alignment_consistent_shift():
    profile = load_profile("adult")
    # Segments start at 1000 and 5000
    segments = [
        Segment(start_ms=1000, end_ms=3000, text="First line of dialogue."),
        Segment(start_ms=5000, end_ms=7000, text="Second line of dialogue."),
    ]
    # Cues shifted by +1200ms (start at 2200 and 6200)
    cues = [
        Cue(
            index=1,
            start_ms=2200,
            end_ms=4200,
            lines=["First line of dialogue."],
            raw_text="First line of dialogue.",
        ),
        Cue(
            index=2,
            start_ms=6200,
            end_ms=8200,
            lines=["Second line of dialogue."],
            raw_text="Second line of dialogue.",
        ),
    ]

    result = align_cues_to_segments(cues, segments, profile)
    assert len(result.matches) == 2
    assert result.median_offset_ms == 1200

    sync_findings = [f for f in result.findings if f.code == "SYNC_OFFSET"]
    assert len(sync_findings) == 2
    assert sync_findings[0].cue_index == 1
    assert sync_findings[1].cue_index == 2


def test_alignment_missing_and_extra_dialogue():
    profile = load_profile("adult")
    segments = [
        Segment(start_ms=1000, end_ms=3000, text="Spoken line one here."),
        Segment(start_ms=5000, end_ms=7000, text="Completely missing line from captions."),
    ]
    cues = [
        Cue(
            index=1,
            start_ms=1000,
            end_ms=3000,
            lines=["Spoken line one here."],
            raw_text="Spoken line one here.",
        ),
        Cue(
            index=2,
            start_ms=9000,
            end_ms=11000,
            lines=["Extra caption with no speech."],
            raw_text="Extra caption with no speech.",
        ),
    ]

    result = align_cues_to_segments(cues, segments, profile)
    assert len(result.matches) == 1

    missing_findings = [f for f in result.findings if f.code == "MISSING_DIALOGUE"]
    assert len(missing_findings) == 1
    assert "Completely missing" in missing_findings[0].message

    extra_findings = [f for f in result.findings if f.code == "EXTRA_CAPTION"]
    assert len(extra_findings) == 1
    assert extra_findings[0].cue_index == 2


def test_alignment_low_accuracy():
    profile = load_profile("adult")
    segments = [
        Segment(
            start_ms=1000,
            end_ms=3000,
            text="The quarterly results exceeded all projections today.",
        ),
    ]
    # Paraphrased caption with substantial error rate (substitutions)
    cues = [
        Cue(
            index=1,
            start_ms=1000,
            end_ms=3000,
            lines=["The quarterly numbers beat all expectations today."],
            raw_text="The quarterly numbers beat all expectations today.",
        ),
    ]

    result = align_cues_to_segments(cues, segments, profile)
    accuracy_findings = [f for f in result.findings if f.code == "ACCURACY_LOW"]
    assert len(accuracy_findings) == 1
    assert accuracy_findings[0].severity == "warning"
