"""Tests for subtitle parsers and exporters (lossless round-trip)."""

from engine.export import export_cues_to_srt, export_cues_to_vtt
from engine.parsers import (
    ms_to_srt_timecode,
    ms_to_vtt_timecode,
    parse_srt_content,
    parse_timecode_str,
    parse_vtt_content,
)


def test_timecode_conversions():
    # Test millisecond conversion
    assert parse_timecode_str("00:01:23,456") == 83456
    assert parse_timecode_str("00:01:23.456") == 83456
    assert parse_timecode_str("01:23.456") == 83456

    assert ms_to_srt_timecode(83456) == "00:01:23,456"
    assert ms_to_vtt_timecode(83456) == "00:01:23.456"


def test_srt_parsing_and_lossless_roundtrip():
    sample_srt = (
        "1\n"
        "00:00:01,500 --> 00:00:04,200\n"
        "First line of text.\n"
        "Second line of text.\n"
        "\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "Another subtitle block."
    )

    cues = parse_srt_content(sample_srt)
    assert len(cues) == 2

    assert cues[0].index == 1
    assert cues[0].start_ms == 1500
    assert cues[0].end_ms == 4200
    assert len(cues[0].lines) == 2
    assert cues[0].lines[0] == "First line of text."
    assert cues[0].lines[1] == "Second line of text."

    assert cues[1].index == 2
    assert cues[1].start_ms == 5000
    assert cues[1].end_ms == 8000
    assert cues[1].lines == ["Another subtitle block."]

    # Round-trip export -> parse
    exported = export_cues_to_srt(cues)
    roundtrip_cues = parse_srt_content(exported)

    assert len(roundtrip_cues) == len(cues)
    for orig, rt in zip(cues, roundtrip_cues):
        assert orig.start_ms == rt.start_ms
        assert orig.end_ms == rt.end_ms
        assert orig.lines == rt.lines
        assert orig.text == rt.text


def test_vtt_parsing_and_lossless_roundtrip():
    sample_vtt = (
        "WEBVTT\n"
        "\n"
        "1\n"
        "00:00:01.200 --> 00:00:03.500\n"
        "Hello from WebVTT\n"
        "\n"
        "2\n"
        "00:00:04.000 --> 00:00:07.800\n"
        "Second cue here"
    )

    cues = parse_vtt_content(sample_vtt)
    assert len(cues) == 2

    assert cues[0].start_ms == 1200
    assert cues[0].end_ms == 3500
    assert cues[0].lines == ["Hello from WebVTT"]

    assert cues[1].start_ms == 4000
    assert cues[1].end_ms == 7800

    # Round-trip export -> parse
    exported = export_cues_to_vtt(cues)
    roundtrip_cues = parse_vtt_content(exported)

    assert len(roundtrip_cues) == len(cues)
    for orig, rt in zip(cues, roundtrip_cues):
        assert orig.start_ms == rt.start_ms
        assert orig.end_ms == rt.end_ms
        assert orig.lines == rt.lines
