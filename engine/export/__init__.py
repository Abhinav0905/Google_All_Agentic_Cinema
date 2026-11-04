"""Subtitle and timed-text exporters for CueCheck."""

from pathlib import Path
from typing import List, Literal, Optional, Union

from engine.export.srt_exporter import export_cues_to_srt, write_cues_to_srt_file
from engine.export.vtt_exporter import export_cues_to_vtt, write_cues_to_vtt_file
from engine.models import Cue


def export_cues(cues: List[Cue], format_type: Literal["srt", "vtt"] = "srt") -> str:
    """Export cues to requested format string."""
    if format_type.lower() in ("vtt", "webvtt"):
        return export_cues_to_vtt(cues)
    return export_cues_to_srt(cues)


def write_cues_file(
    cues: List[Cue], target_path: Union[str, Path], format_type: Optional[str] = None
) -> Path:
    """Write cues to disk in specified format."""
    path = Path(target_path)
    fmt = format_type or path.suffix.lower().lstrip(".")
    if fmt in ("vtt", "webvtt"):
        return write_cues_to_vtt_file(cues, path)
    return write_cues_to_srt_file(cues, path)


__all__ = [
    "export_cues",
    "export_cues_to_srt",
    "export_cues_to_vtt",
    "write_cues_file",
    "write_cues_to_srt_file",
    "write_cues_to_vtt_file",
]
