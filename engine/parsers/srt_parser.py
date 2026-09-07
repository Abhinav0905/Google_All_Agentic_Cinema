"""SRT subtitle parser returning Cue objects."""

import re
from pathlib import Path
from typing import List, Literal, Union

import srt

from engine.models import Cue
from engine.parsers.timecodes import parse_timecode_str, timedelta_to_ms


def parse_srt_content(content: str, kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Parse SRT string content into a list of Cue objects."""
    # Strip UTF-8 BOM if present and normalize line breaks
    cleaned = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    cues: List[Cue] = []
    try:
        parsed = list(srt.parse(cleaned))
        for item in parsed:
            lines = [line for line in item.content.split("\n")]
            cue = Cue(
                index=item.index or (len(cues) + 1),
                start_ms=timedelta_to_ms(item.start),
                end_ms=timedelta_to_ms(item.end),
                lines=lines,
                raw_text=item.content,
                kind=kind,
            )
            cues.append(cue)
        return cues
    except Exception:
        # Fallback manual block parser in case srt library stumbles on formatting anomalies
        return _fallback_parse_srt(cleaned, kind=kind)


def _fallback_parse_srt(content: str, kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Fallback manual regex parser for resilient SRT parsing."""
    blocks = re.split(r"\n\s*\n", content.strip())
    cues: List[Cue] = []
    idx_counter = 1

    time_pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})"
    )

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
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
        index = idx_counter
        if match_line_idx > 0 and lines[0].isdigit():
            index = int(lines[0])

        cues.append(
            Cue(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                lines=text_lines,
                raw_text="\n".join(text_lines),
                kind=kind,
            )
        )
        idx_counter += 1

    return cues


def parse_srt_file(path: Union[str, Path], kind: Literal["caption", "ad"] = "caption") -> List[Cue]:
    """Read an SRT file from disk and parse into Cue objects."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_srt_content(content, kind=kind)
