"""Alignment engine matching timed-text cues to speech segments.

Computes:
- Token similarity and Levenshtein Word Error Rate (WER)
- Temporal cue-to-segment matching within ±5s window
- SYNC_OFFSET, MISSING_DIALOGUE, EXTRA_CAPTION, ACCURACY_LOW findings
- Median offset across matched cues
"""

import re
import statistics
from typing import List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from engine.models import Cue, Finding, Profile, Segment

RE_TAGS_STRIP = re.compile(r"<[^>]+>|\[[^\]]+\]|\([^\)]+\)|[♪#]")
RE_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_tokens(text: str) -> List[str]:
    """Strip tags, lowercase, remove punctuation, and tokenize words."""
    cleaned = RE_TAGS_STRIP.sub(" ", text)
    cleaned = RE_PUNCTUATION.sub(" ", cleaned).lower()
    return [w for w in cleaned.split() if w]


def levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Compute word-level Levenshtein edit distance."""
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = [[0] * size_y for _ in range(size_x)]

    for x in range(size_x):
        matrix[x][0] = x
    for y in range(size_y):
        matrix[0][y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x - 1] == seq2[y - 1]:
                matrix[x][y] = matrix[x - 1][y - 1]
            else:
                matrix[x][y] = min(
                    matrix[x - 1][y] + 1,      # deletion
                    matrix[x][y - 1] + 1,      # insertion
                    matrix[x - 1][y - 1] + 1,  # substitution
                )
    return matrix[size_x - 1][size_y - 1]


def compute_wer(ref_tokens: List[str], hyp_tokens: List[str]) -> float:
    """Compute Word Error Rate (WER) between reference and hypothesis tokens."""
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    dist = levenshtein_distance(ref_tokens, hyp_tokens)
    return min(1.0, round(dist / len(ref_tokens), 4))


def token_similarity(tokens1: List[str], tokens2: List[str]) -> float:
    """Jaccard token similarity between two token lists."""
    s1: Set[str] = set(tokens1)
    s2: Set[str] = set(tokens2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1.intersection(s2))
    union = len(s1.union(s2))
    return intersection / union if union > 0 else 0.0


class MatchedPair(BaseModel):
    cue: Cue
    segment: Segment
    offset_ms: int
    wer: float
    similarity: float


class AlignmentResult(BaseModel):
    matches: List[MatchedPair] = Field(default_factory=list)
    unmatched_cues: List[Cue] = Field(default_factory=list)
    unmatched_segments: List[Segment] = Field(default_factory=list)
    median_offset_ms: Optional[int] = None
    mean_wer: float = 0.0
    findings: List[Finding] = Field(default_factory=list)


def align_cues_to_segments(
    cues: List[Cue],
    segments: List[Segment],
    profile: Profile,
    window_ms: int = 5000,
) -> AlignmentResult:
    """Align captions to speech segments and generate alignment findings."""
    matches: List[MatchedPair] = []
    matched_segment_indices: Set[int] = set()
    matched_cue_indices: Set[int] = set()
    findings: List[Finding] = []

    sync_tol = profile.sync_tolerance_ms.value

    # Match cues to speech segments within ±5000ms window
    for cue_idx, cue in enumerate(cues):
        cue_tokens = normalize_tokens(cue.raw_text)
        if not cue_tokens:
            continue

        best_match: Optional[Tuple[int, Segment, float, float, int]] = None
        best_score = -1.0

        for seg_idx, seg in enumerate(segments):
            if seg_idx in matched_segment_indices:
                continue

            # Temporal proximity check
            time_diff = abs(cue.start_ms - seg.start_ms)
            if time_diff > window_ms:
                continue

            seg_tokens = normalize_tokens(seg.text)
            sim = token_similarity(cue_tokens, seg_tokens)
            # Require minimum token similarity or close temporal match with overlap
            if sim >= 0.20 or (time_diff <= 1000 and sim > 0.0):
                # Score combines token similarity and temporal proximity
                proximity_score = 1.0 - (time_diff / window_ms)
                score = (sim * 0.7) + (proximity_score * 0.3)
                if score > best_score:
                    best_score = score
                    wer = compute_wer(seg_tokens, cue_tokens)
                    offset_ms = cue.start_ms - seg.start_ms
                    best_match = (seg_idx, seg, sim, wer, offset_ms)

        if best_match:
            seg_idx, seg, sim, wer, offset_ms = best_match
            matched_segment_indices.add(seg_idx)
            matched_cue_indices.add(cue_idx)
            pair = MatchedPair(
                cue=cue,
                segment=seg,
                offset_ms=offset_ms,
                wer=wer,
                similarity=sim,
            )
            matches.append(pair)

            # SYNC_OFFSET check
            if abs(offset_ms) > sync_tol:
                direction = "late" if offset_ms > 0 else "early"
                findings.append(
                    Finding(
                        id=f"SYNC_OFFSET_{cue.index}_{cue.start_ms}",
                        code="SYNC_OFFSET",
                        severity="error",
                        cue_index=cue.index,
                        start_ms=cue.start_ms,
                        end_ms=cue.end_ms,
                        message=(
                            f"Cue start time is {abs(offset_ms)}ms {direction} relative "
                            f"to speech onset (tolerance {sync_tol}ms)"
                        ),
                        evidence=(
                            f"cue_start={cue.start_ms}ms, speech_start={seg.start_ms}ms, "
                            f"offset={offset_ms}ms"
                        ),
                        spec_ref=profile.sync_tolerance_ms.source,
                    )
                )

            # ACCURACY_LOW check (word error rate > 0.15)
            if wer > 0.15:
                findings.append(
                    Finding(
                        id=f"ACCURACY_LOW_{cue.index}_{cue.start_ms}",
                        code="ACCURACY_LOW",
                        severity="warning",
                        cue_index=cue.index,
                        start_ms=cue.start_ms,
                        end_ms=cue.end_ms,
                        message=f"Low text accuracy: WER {wer:.1%} exceeds 15% threshold",
                        evidence=f"Spoken: '{seg.text}' | Caption: '{cue.text}'",
                        spec_ref="FCC caption accuracy standard",
                    )
                )

    # Detect UNMATCHED segments (MISSING_DIALOGUE)
    unmatched_segments = [
        seg for idx, seg in enumerate(segments) if idx not in matched_segment_indices
    ]
    for seg in unmatched_segments:
        # Only flag if spoken segment has meaningful content
        if len(normalize_tokens(seg.text)) >= 2:
            findings.append(
                Finding(
                    id=f"MISSING_DIALOGUE_seg_{seg.start_ms}",
                    code="MISSING_DIALOGUE",
                    severity="error",
                    cue_index=None,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    message=f"Spoken dialogue missing from captions: '{seg.text}'",
                    evidence=(
                        f"Spoken speech at {seg.start_ms}ms-{seg.end_ms}ms has no matching cue"
                    ),
                    spec_ref="FCC caption completeness standard",
                )
            )

    # Detect UNMATCHED cues (EXTRA_CAPTION)
    unmatched_cues = []
    for idx, cue in enumerate(cues):
        if idx not in matched_cue_indices:
            unmatched_cues.append(cue)
            # If cue is not a tagged sound effect (e.g. [DOOR SLAMS] or ♪ ... ♪), flag extra caption
            text = cue.raw_text.strip()
            is_tag = (
                (text.startswith("[") and text.endswith("]"))
                or (text.startswith("(") and text.endswith(")"))
                or "♪" in text
            )
            if not is_tag and text:
                findings.append(
                    Finding(
                        id=f"EXTRA_CAPTION_{cue.index}_{cue.start_ms}",
                        code="EXTRA_CAPTION",
                        severity="info",
                        cue_index=cue.index,
                        start_ms=cue.start_ms,
                        end_ms=cue.end_ms,
                        message=f"Caption has no matching speech in video: '{cue.text}'",
                        evidence=f"No speech segment found within ±5s of {cue.start_ms}ms",
                        spec_ref="Caption dialogue presence verification",
                    )
                )

    # Median offset and mean WER
    offsets = [p.offset_ms for p in matches]
    median_offset = int(statistics.median(offsets)) if offsets else None
    mean_wer = statistics.mean([p.wer for p in matches]) if matches else 0.0

    return AlignmentResult(
        matches=matches,
        unmatched_cues=unmatched_cues,
        unmatched_segments=unmatched_segments,
        median_offset_ms=median_offset,
        mean_wer=mean_wer,
        findings=findings,
    )
