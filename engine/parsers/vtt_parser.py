"""WebVTT subtitle parser returning Cue objects."""

import re
from pathlib import Path
from typing import List, Literal, Union

import webvtt

from engine.models import Cue
from engine.parsers.timecodes import parse_timecode_str


def parse_vtt_content(content: str, kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Parse WebVTT string content into a list of Cue objects."""
    cleaned = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    cues: List[Cue] = []
    try:
        vtt = webvtt.from_string(cleaned)
        for i, caption in enumerate(vtt):
            start_ms = parse_timecode_str(caption.start)
            end_ms = parse_timecode_str(caption.end)
            raw = caption.raw_text.strip()
            if caption.lines:
                lines = list(caption.lines)
            else:
                lines = raw.split("\n") if raw else []
            cue = Cue(
                index=i + 1,
                start_ms=start_ms,
                end_ms=end_ms,
                lines=lines,
                raw_text=raw,
                kind=kind,
            )
            cues.append(cue)
        return cues
    except Exception:
        return _fallback_parse_vtt(cleaned, kind=kind)


def _fallback_parse_vtt(content: str, kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Fallback manual regex parser for WebVTT format."""
    blocks = re.split(r"\n\s*\n", content.strip())
    cues: List[Cue] = []
    idx_counter = 1

    time_pattern = re.compile(
        r"((?:\d{1,2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*((?:\d{1,2}:)?\d{2}:\d{2}\.\d{3})"
    )

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue

        match_line_idx = -1
        m = None
        for i, line in enumerate(lines):
            m = time_pattern.search(line)
            if m:
                match_line_idx = i
                break

        if not m or match_line_idx == -1:
            continue

        start_str, end_str = m.group(1), m.group(2)
        start_ms = parse_timecode_str(start_str)
        end_ms = parse_timecode_str(end_str)

        text_lines = lines[match_line_idx + 1 :]
        cues.append(
            Cue(
                index=idx_counter,
                start_ms=start_ms,
                end_ms=end_ms,
                lines=text_lines,
                raw_text="\n".join(text_lines),
                kind=kind,
            )
        )
        idx_counter += 1

    return cues


def parse_vtt_file(path: Union[str, Path], kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Read a WebVTT file from disk and parse into Cue objects."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_vtt_content(content, kind=kind)
