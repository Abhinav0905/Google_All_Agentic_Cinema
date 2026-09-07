"""WebVTT subtitle exporter."""

from pathlib import Path
from typing import List, Union

from engine.models import Cue
from engine.parsers.timecodes import ms_to_vtt_timecode


def export_cues_to_vtt(cues: List[Cue]) -> str:
    """Serialize a list of Cue objects into a WebVTT formatted string."""
    lines = ["WEBVTT", ""]
    for i, cue in enumerate(cues, start=1):
        start_tc = ms_to_vtt_timecode(cue.start_ms)
        end_tc = ms_to_vtt_timecode(cue.end_ms)
        text = cue.text
        lines.append(str(i))
        lines.append(f"{start_tc} --> {end_tc}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def write_cues_to_vtt_file(cues: List[Cue], target_path: Union[str, Path]) -> Path:
    """Write a list of Cue objects to a WebVTT file."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = export_cues_to_vtt(cues)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
