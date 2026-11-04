"""Timecode parsing and formatting utilities."""

from datetime import timedelta
from typing import Tuple


def ms_to_hmsm(ms: int) -> Tuple[int, int, int, int]:
    """Convert total milliseconds into (hours, minutes, seconds, milliseconds)."""
    if ms < 0:
        ms = 0
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1_000
    milliseconds = ms % 1_000
    return hours, minutes, seconds, milliseconds


def parse_timecode_str(tc_str: str) -> int:
    """Parse a timecode string in either SRT ('00:00:00,000') or VTT ('00:00:00.000') format
    to milliseconds.
    """
    tc = tc_str.strip().replace(",", ".")
    parts = tc.split(":")
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_part = float(parts[2])
        s = int(s_part)
        ms = int(round((s_part - s) * 1000))
        return (h * 3600 + m * 60 + s) * 1000 + ms
    elif len(parts) == 2:
        m = int(parts[0])
        s_part = float(parts[1])
        s = int(s_part)
        ms = int(round((s_part - s) * 1000))
        return (m * 60 + s) * 1000 + ms
    else:
        raise ValueError(f"Invalid timecode format: '{tc_str}'")


def ms_to_srt_timecode(ms: int) -> str:
    """Format milliseconds into SRT timecode: HH:MM:SS,mmm"""
    h, m, s, milli = ms_to_hmsm(ms)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def ms_to_vtt_timecode(ms: int) -> str:
    """Format milliseconds into WebVTT timecode: HH:MM:SS.mmm"""
    h, m, s, milli = ms_to_hmsm(ms)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def timedelta_to_ms(td: timedelta) -> int:
    """Convert timedelta to integer milliseconds."""
    return int(round(td.total_seconds() * 1000))


def ms_to_timedelta(ms: int) -> timedelta:
    """Convert milliseconds to timedelta."""
    return timedelta(milliseconds=ms)
