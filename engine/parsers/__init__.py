"""Timed-text parser module for CueCheck."""

from pathlib import Path
from typing import List, Literal, Optional, Union

from engine.models import Cue
from engine.parsers.srt_parser import parse_srt_content, parse_srt_file
from engine.parsers.timecodes import (
    ms_to_srt_timecode,
    ms_to_vtt_timecode,
    parse_timecode_str,
)
from engine.parsers.vtt_parser import parse_vtt_content, parse_vtt_file


def parse_timed_text(
    source: Union[str, Path],
    format_hint: Optional[str] = None,
    kind: Literal["caption", "ad"] = "caption",
) -> List[Cue]:
    """Parse timed-text content or file path into a list of Cue objects.

    Detects SRT vs WebVTT automatically.
    """
    # Check if source is an existing file path
    if isinstance(source, Path) or (
        isinstance(source, str) and "\n" not in source and Path(source).exists()
    ):
        p = Path(source)
        ext = format_hint or p.suffix.lower().lstrip(".")
        if ext in ("vtt", "webvtt"):
            return parse_vtt_file(p, kind=kind)
        return parse_srt_file(p, kind=kind)

    # String content
    content = str(source)
    is_vtt = (format_hint and format_hint.lower() in ("vtt", "webvtt")) or (
        content.lstrip().startswith("WEBVTT")
    )
    if is_vtt:
        return parse_vtt_content(content, kind=kind)
    return parse_srt_content(content, kind=kind)


__all__ = [
    "Cue",
    "parse_timed_text",
    "parse_srt_file",
    "parse_srt_content",
    "parse_vtt_file",
    "parse_vtt_content",
    "ms_to_srt_timecode",
    "ms_to_vtt_timecode",
    "parse_timecode_str",
]
