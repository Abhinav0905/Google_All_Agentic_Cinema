"""SRT subtitle exporter."""

from pathlib import Path
from typing import List, Union

from engine.models import Cue
from engine.parsers.timecodes import ms_to_srt_timecode


def export_cues_to_srt(cues: List[Cue]) -> str:
    """Serialize a list of Cue objects into an SRT formatted string."""
    blocks = []
    for i, cue in enumerate(cues, start=1):
        start_tc = ms_to_srt_timecode(cue.start_ms)
        end_tc = ms_to_srt_timecode(cue.end_ms)
        text = cue.text
        block = f"{i}\n{start_tc} --> {end_tc}\n{text}"
        blocks.append(block)

    return "\n\n".join(blocks) + "\n" if blocks else ""


def write_cues_to_srt_file(cues: List[Cue], target_path: Union[str, Path]) -> Path:
    """Write a list of Cue objects to an SRT file."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = export_cues_to_srt(cues)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
