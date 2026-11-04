"""Deterministic caption-only rules engine.

Evaluates cues against spec profile rules without any model dependencies:
DUR_MIN, DUR_MAX, CPS, CPL, LINES, GAP_MIN, OVERLAP, ORDER, EMPTY, TAG_FORMAT.
"""

import re
from typing import List

from engine.models import Cue, Finding, Profile

# Regex to strip HTML/styling tags
RE_HTML_TAGS = re.compile(r"<[^>]+>")

# Regex to detect sound effects enclosed in parentheses instead of square brackets
RE_PAREN_SOUND_TAG = re.compile(
    r"\(([A-Z\s]{2,}|[a-zA-Z\s]*(?:music|applause|laughter|screaming|cheering|sighs?|gasps?|cries?|groans?|door|footsteps|whispers?|engine|thunder|gunshot)[a-zA-Z\s]*)\)"
)

# Regex to detect unpaired music note symbols
RE_UNPAIRED_MUSIC_NOTE = re.compile(r"^[^♪]*♪[^♪]*$")


def check_empty(cue: Cue) -> List[Finding]:
    """EMPTY: blank cue with no text or whitespace only."""
    text = cue.raw_text.strip()
    if not text:
        return [
            Finding(
                id=f"EMPTY_{cue.index}_{cue.start_ms}",
                code="EMPTY",
                severity="warning",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message="Blank cue with no text",
                evidence=f"Cue {cue.index} has no display text",
                spec_ref="Timed-text content presence requirement",
            )
        ]
    return []


def check_order(cue: Cue, prev_cue: Cue | None) -> List[Finding]:
    """ORDER: non-monotonic timing (start >= end, or start < prev.start)."""
    findings = []
    if cue.start_ms >= cue.end_ms:
        findings.append(
            Finding(
                id=f"ORDER_{cue.index}_{cue.start_ms}",
                code="ORDER",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=(
                    f"Cue timing is non-monotonic: "
                    f"start ({cue.start_ms}ms) >= end ({cue.end_ms}ms)"
                ),
                evidence=f"start_ms={cue.start_ms}, end_ms={cue.end_ms}",
                spec_ref="Monotonic timing constraint",
            )
        )

    if prev_cue and cue.start_ms < prev_cue.start_ms:
        findings.append(
            Finding(
                id=f"ORDER_SEQ_{cue.index}_{cue.start_ms}",
                code="ORDER",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=(
                    f"Cue start time ({cue.start_ms}ms) occurs before previous cue start "
                    f"({prev_cue.start_ms}ms)"
                ),
                evidence=f"prev_cue {prev_cue.index} starts at {prev_cue.start_ms}ms",
                spec_ref="Monotonic sequence order requirement",
            )
        )
    return findings


def check_duration(cue: Cue, profile: Profile) -> List[Finding]:
    """DUR_MIN and DUR_MAX: cue duration checks against profile thresholds."""
    findings = []
    duration = cue.duration_ms
    min_dur = profile.min_duration_ms.value
    max_dur = profile.max_duration_ms.value

    if duration < min_dur and duration > 0:
        findings.append(
            Finding(
                id=f"DUR_MIN_{cue.index}_{cue.start_ms}",
                code="DUR_MIN",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=f"Cue duration ({duration}ms) is shorter than minimum limit ({min_dur}ms)",
                evidence=f"duration={duration}ms, min_threshold={min_dur}ms",
                spec_ref=profile.min_duration_ms.source,
            )
        )

    if duration > max_dur:
        findings.append(
            Finding(
                id=f"DUR_MAX_{cue.index}_{cue.start_ms}",
                code="DUR_MAX",
                severity="warning",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=f"Cue duration ({duration}ms) exceeds maximum limit ({max_dur}ms)",
                evidence=f"duration={duration}ms, max_threshold={max_dur}ms",
                spec_ref=profile.max_duration_ms.source,
            )
        )
    return findings


def check_cps(cue: Cue, profile: Profile) -> List[Finding]:
    """CPS: characters per second exceeds max_cps (spaces counted, tags excluded)."""
    text_clean = RE_HTML_TAGS.sub("", cue.raw_text).strip()
    if not text_clean:
        return []

    duration_s = (cue.end_ms - cue.start_ms) / 1000.0
    if duration_s <= 0:
        return []

    char_count = len(text_clean)
    cps = round(char_count / duration_s, 2)
    max_cps = profile.max_cps.value

    if cps > max_cps:
        return [
            Finding(
                id=f"CPS_{cue.index}_{cue.start_ms}",
                code="CPS",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=f"Reading speed of {cps:.1f} cps exceeds maximum limit of {max_cps} cps",
                evidence=(
                    f"text_length={char_count} chars, duration={duration_s:.2f}s, cps={cps:.1f}"
                ),
                spec_ref=profile.max_cps.source,
            )
        ]
    return []


def check_cpl(cue: Cue, profile: Profile) -> List[Finding]:
    """CPL: character count of any line exceeds max_chars_per_line."""
    findings = []
    max_cpl = profile.max_chars_per_line.value
    lines = cue.lines if cue.lines else cue.raw_text.split("\n")

    for line_idx, line in enumerate(lines, start=1):
        clean_line = RE_HTML_TAGS.sub("", line).rstrip("\r\n")
        if len(clean_line) > max_cpl:
            findings.append(
                Finding(
                    id=f"CPL_{cue.index}_{line_idx}_{cue.start_ms}",
                    code="CPL",
                    severity="error",
                    cue_index=cue.index,
                    start_ms=cue.start_ms,
                    end_ms=cue.end_ms,
                    message=(
                        f"Line {line_idx} length ({len(clean_line)} chars) "
                        f"exceeds limit ({max_cpl} chars)"
                    ),
                    evidence=f"'{clean_line}' ({len(clean_line)} chars)",
                    spec_ref=profile.max_chars_per_line.source,
                )
            )
    return findings


def check_lines(cue: Cue, profile: Profile) -> List[Finding]:
    """LINES: number of lines exceeds max_lines."""
    max_lines = profile.max_lines.value
    lines = [line for line in (cue.lines or cue.raw_text.split("\n")) if line.strip()]

    if len(lines) > max_lines:
        return [
            Finding(
                id=f"LINES_{cue.index}_{cue.start_ms}",
                code="LINES",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=f"Cue has {len(lines)} lines, exceeding maximum limit of {max_lines} lines",
                evidence=f"line_count={len(lines)}, max={max_lines}",
                spec_ref=profile.max_lines.source,
            )
        ]
    return []


def check_gap_and_overlap(cue: Cue, next_cue: Cue, profile: Profile) -> List[Finding]:
    """GAP_MIN and OVERLAP: checks between consecutive cues."""
    findings = []
    min_gap = profile.min_gap_ms.value

    # Overlap: cue ends after next cue starts
    if cue.end_ms > next_cue.start_ms:
        overlap_ms = cue.end_ms - next_cue.start_ms
        findings.append(
            Finding(
                id=f"OVERLAP_{cue.index}_{next_cue.index}_{cue.end_ms}",
                code="OVERLAP",
                severity="error",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=(
                    f"Cue {cue.index} overlaps next cue {next_cue.index} by {overlap_ms}ms"
                ),
                evidence=(
                    f"Cue {cue.index} end_ms={cue.end_ms} > "
                    f"Cue {next_cue.index} start_ms={next_cue.start_ms}"
                ),
                spec_ref="Non-overlapping subtitles rule",
            )
        )
    else:
        # Gap: next starts after current ends
        gap = next_cue.start_ms - cue.end_ms
        if 0 <= gap < min_gap:
            findings.append(
                Finding(
                    id=f"GAP_MIN_{cue.index}_{next_cue.index}_{cue.end_ms}",
                    code="GAP_MIN",
                    severity="warning",
                    cue_index=cue.index,
                    start_ms=cue.start_ms,
                    end_ms=cue.end_ms,
                    message=(
                        f"Gap between cue {cue.index} and {next_cue.index} ({gap}ms) "
                        f"is below minimum gap of {min_gap}ms"
                    ),
                    evidence=f"gap={gap}ms, min_gap={min_gap}ms",
                    spec_ref=profile.min_gap_ms.source,
                )
            )

    return findings


def check_tag_format(cue: Cue) -> List[Finding]:
    """TAG_FORMAT: sound tag not bracketed / music not properly marked."""
    findings = []
    text = cue.raw_text

    # Check for parentheses around sound effect
    m_paren = RE_PAREN_SOUND_TAG.search(text)
    if m_paren:
        tag = m_paren.group(0)
        findings.append(
            Finding(
                id=f"TAG_FORMAT_PAREN_{cue.index}_{cue.start_ms}",
                code="TAG_FORMAT",
                severity="info",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=(
                    f"Sound tag '{tag}' should use square brackets [TAG] instead of parentheses"
                ),
                evidence=f"Found: '{tag}'",
                spec_ref="SDH sound tag formatting standard",
            )
        )

    # Check for unpaired music notes (e.g. single ♪ without closing ♪)
    if "♪" in text and text.count("♪") % 2 != 0:
        findings.append(
            Finding(
                id=f"TAG_FORMAT_MUSIC_{cue.index}_{cue.start_ms}",
                code="TAG_FORMAT",
                severity="info",
                cue_index=cue.index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                message=(
                    "Music note ♪ should be paired at start and end of music lyric (e.g. ♪ ... ♪)"
                ),
                evidence=f"Unpaired music note in: '{text.strip()}'",
                spec_ref="Music notation subtitle guideline",
            )
        )

    return findings


def run_caption_rules(cues: List[Cue], profile: Profile) -> List[Finding]:
    """Execute all deterministic caption-only checks on a list of cues."""
    findings: List[Finding] = []

    for i, cue in enumerate(cues):
        prev_cue = cues[i - 1] if i > 0 else None
        next_cue = cues[i + 1] if i + 1 < len(cues) else None

        # Check empty
        empty_findings = check_empty(cue)
        findings.extend(empty_findings)
        if empty_findings:
            # Skip duration / cps checks for completely empty cues
            continue

        # Check ordering
        findings.extend(check_order(cue, prev_cue))

        # Check duration
        findings.extend(check_duration(cue, profile))

        # Check reading speed (CPS)
        findings.extend(check_cps(cue, profile))

        # Check line length (CPL)
        findings.extend(check_cpl(cue, profile))

        # Check line count (LINES)
        findings.extend(check_lines(cue, profile))

        # Check tag formatting (TAG_FORMAT)
        findings.extend(check_tag_format(cue))

        # Check gap & overlap against next cue
        if next_cue:
            findings.extend(check_gap_and_overlap(cue, next_cue, profile))

    return findings
