#!/usr/bin/env python3
"""Render an original illustrated fixture scene and synthesize its sound effects.

Requires Pillow plus ffmpeg/ffprobe. Optional segment_00.wav ... segment_12.wav
voices are fitted to the authored fixture intervals. No external media is fetched.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, DURATION = 1280, 720, 24, 60
FIXTURE = ROOT / "tests" / "fixtures" / "transcribe_fixture.json"


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


FONTS = {
    (size, bold): font(size, bold)
    for size in (12, 14, 16, 20, 24, 30, 42)
    for bold in (False, True)
}


def text(draw, xy, value, size=16, color="#c5d7dd", bold=False):
    draw.text(xy, value, font=FONTS[(size, bold)], fill=color)


def background():
    image = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(image)
    for y in range(H):
        k = y / H
        d.line((0, y, W, y), fill=(int(17 + 10 * k), int(29 + 11 * k), int(37 + 13 * k)))
    d.polygon([(0, 480), (1280, 480), (1280, 720), (0, 720)], fill="#243038")
    for x in range(-1200, 2500, 170):
        d.line((640 + (x - 640) * 0.25, 480, x, 720), fill="#344047", width=1)
    for y in (500, 531, 575, 635, 710):
        d.line((0, y, 1280, y), fill="#303c42", width=1)
    # Window and abstract dusk skyline, entirely authored geometric artwork.
    d.rounded_rectangle((34, 118, 184, 429), 7, fill="#597580", outline="#94a9ac", width=2)
    for x, height in ((43, 90), (72, 155), (111, 115), (145, 184)):
        d.rectangle((x, 422 - height, x + 29, 426), fill="#263d48")
        for yy in range(440 - height, 420, 20):
            d.rectangle((x + 6, yy, x + 10, yy + 4), fill="#8caaad")
    d.line((108, 118, 108, 429), fill="#9caeaf", width=4)
    d.line((34, 275, 184, 275), fill="#9caeaf", width=4)
    # Wall panels, projector and doorway.
    d.rectangle((201, 117, 771, 423), fill="#0b151d", outline="#4e616a", width=2)
    d.rectangle((211, 127, 761, 413), fill="#182b38")
    d.rounded_rectangle((1038, 146, 1217, 505), 8, fill="#101c25", outline="#62737a", width=3)
    d.rectangle((1053, 163, 1203, 498), fill="#3d515b")
    d.rectangle((1176, 318, 1182, 365), fill="#d1b785")
    text(d, (1054, 117), "CONFERENCE 04", 14, "#8eaaaE")
    # Suspended lights and a plant.
    for x in (280, 650, 966):
        d.line((x, 0, x, 69), fill="#617078", width=2)
        d.rounded_rectangle((x - 75, 69, x + 75, 77), 4, fill="#ecdec1")
        d.line((x - 69, 79, x + 69, 79), fill="#9aa6a1", width=2)
    d.polygon([(59, 476), (100, 476), (95, 527), (65, 527)], fill="#78827a")
    for ex, ey in ((37, 403), (68, 383), (115, 400), (99, 430), (46, 445)):
        d.line((80, 482, ex, ey), fill="#77937f", width=4)
        d.ellipse((ex - 16, ey - 7, ex + 16, ey + 7), fill="#719686")
    return image


def person(d, x, y, *, sarah=False, talking=False, hand=0):
    skin = "#bb8969" if sarah else "#ce9a7b"
    coat = "#a48063" if sarah else "#597183"
    # y is the head center. Figures are intentionally drawn illustrations.
    d.ellipse((x - 37, y + 227, x + 44, y + 244), fill="#15242c")
    d.line((x - 14, y + 154, x - 21, y + 227), fill="#253a48", width=19)
    d.line((x + 18, y + 154, x + 28, y + 227), fill="#253a48", width=19)
    d.polygon([(x - 26, y + 38), (x + 28, y + 38), (x + 42, y + 155), (x - 38, y + 155)], fill=coat)
    d.polygon([(x - 10, y + 36), (x + 12, y + 36), (x + 3, y + 111)], fill="#e1d3b7")
    d.line((x - 29, y + 49, x - 52, y + 105 + hand), fill=coat, width=19)
    d.line((x - 52, y + 105 + hand, x - 86, y + 84 + hand), fill=skin, width=11)
    d.line((x + 31, y + 50, x + 48, y + 116), fill=coat, width=18)
    d.ellipse((x + 39, y + 106, x + 54, y + 125), fill=skin)
    if sarah:
        d.ellipse((x - 27, y - 35, x + 29, y + 45), fill="#382e31")
    d.ellipse((x - 22, y - 29, x + 22, y + 31), fill=skin)
    d.pieslice((x - 24, y - 34, x + 23, y + 10), 170, 357, fill="#362e30")
    d.ellipse((x - 11, y - 3, x - 7, y + 1), fill="#25303a")
    d.ellipse((x + 9, y - 3, x + 13, y + 1), fill="#25303a")
    if talking:
        d.ellipse((x - 4, y + 14, x + 5, y + 20), fill="#67473f")
    else:
        d.line((x - 4, y + 17, x + 5, y + 17), fill="#67473f", width=2)
    if sarah:
        d.polygon(
            [(x + 6, y + 78), (x + 58, y + 89), (x + 44, y + 142), (x - 8, y + 129)], fill="#d7b67a"
        )
        d.line((x + 12, y + 94, x + 41, y + 100), fill="#967b50", width=2)


def frame(base, t, segments, has_voices):
    image = base.copy()
    d = ImageDraw.Draw(image)
    title_on = 9 <= t < 27
    text(d, (239, 151), "Q3 / OPERATIONS REVIEW", 14, "#82b2bd", True)
    if title_on:
        text(d, (239, 192), "Q3 FINANCIAL REPORT", 30, "#e5e3d6", True)
        text(d, (240, 235), "CONFIDENTIAL", 16, "#e1bb80", True)
    else:
        text(d, (239, 192), "The team briefing", 30, "#e5e3d6", True)
        text(d, (240, 235), "Quarterly review  /  Internal discussion", 14, "#9bb7c2")
    for i, height in enumerate((30, 55, 75, 96, 121)):
        x = 249 + i * 76
        d.rounded_rectangle(
            (x, 390 - height, x + 46, 390), 3, fill=(64 + i * 13, 109 + i * 13, 126 + i * 12)
        )
    d.line((239, 391, 676, 391), fill="#6b858f", width=1)
    spoken = any(
        s["start_ms"] <= t * 1000 < s["end_ms"] and s["speaker_label"] == "Alex" for s in segments
    )
    person(d, 874, 286, talking=spoken and int(t * 8) % 2 == 0, hand=int(4 * math.sin(t * 1.1)))
    # Door opens at Sarah's authored entrance, then closes with the slam.
    if 49.5 <= t < 56:
        d.polygon([(1053, 163), (1093, 180), (1093, 498), (1053, 498)], fill="#48616b")
        d.rectangle((1094, 164, 1203, 498), fill="#101b22")
    if t >= 50:
        progress = min(1, (t - 50) / 2.2)
        person(d, int(1215 - 112 * progress), 310, sarah=True)
    # Conference desk in the foreground, with folders and a physical phone.
    d.polygon([(304, 458), (980, 458), (1160, 612), (157, 612)], fill="#8a725b")
    d.polygon([(157, 612), (1160, 612), (1160, 631), (157, 631)], fill="#514b42")
    d.line((308, 461, 975, 461), fill="#bea485", width=3)
    d.polygon([(231, 527), (356, 527), (394, 570), (248, 570)], fill="#cbc8b4")
    d.line((259, 543, 338, 543), fill="#8d9085", width=2)
    d.line((264, 553, 347, 553), fill="#8d9085", width=2)
    d.rounded_rectangle((608, 511, 661, 542), 6, fill="#182631", outline="#9cb4b8", width=2)
    ringing = 18.5 <= t < 20.1
    d.rectangle((617, 517, 650, 536), fill="#88b6bd" if ringing else "#32454c")
    if ringing:
        for r in (9, 18):
            d.arc((598 - r, 505 - r, 671 + r, 549 + r), 185, 355, fill="#d8b982", width=2)
    for x in (431, 923):
        d.ellipse((x, 502, x + 28, 514), fill="#b4b4a4")
        d.rectangle((x, 505, x + 28, 527), fill="#afb4aa")
        d.ellipse((x, 518, x + 28, 532), fill="#afb4aa")
    # Letterbox and an explicit provenance label, not baked-in dialogue captions.
    d.rectangle((0, 0, W, 41), fill="#091116")
    d.rectangle((0, 665, W, 720), fill="#091116")
    text(d, (28, 13), "FRAMEKIND  /  THE BRIEFING", 14, "#d8d8c8", True)
    text(d, (905, 13), "ORIGINAL ILLUSTRATED TEST SCENE", 12, "#8cabb6")
    label = (
        "Synthetic voices + authored sound effects"
        if has_voices
        else "Authored sound effects / speech track pending"
    )
    text(d, (28, 684), label, 14, "#a7bdc4")
    text(d, (1090, 684), f"00:{int(t):02d} / 01:00", 14, "#a7bdc4")
    return image


def sound_effects(path):
    rate = 48000
    samples = array("h", [0]) * (rate * DURATION)
    # Original dual-tone phone bursts; no downloaded samples.
    for start in (18.5, 18.9, 19.3, 19.7):
        for i in range(int(0.23 * rate)):
            t = i / rate
            envelope = min(1, t / 0.012, (0.23 - t) / 0.025)
            value = (
                0.18
                * envelope
                * (math.sin(2 * math.pi * 480 * t) + math.sin(2 * math.pi * 620 * t))
            )
            samples[int(start * rate) + i] = int(value * 32767)
    # Original door impulse with a low wooden resonance and deterministic noise.
    rng = random.Random(4821)
    for i in range(int(0.65 * rate)):
        t = i / rate
        value = 0.52 * math.exp(-12 * t) * math.sin(2 * math.pi * (88 - 25 * t) * t)
        value += 0.27 * math.exp(-25 * t) * rng.uniform(-1, 1)
        samples[56 * rate + i] = int(max(-0.9, min(0.9, value)) * 32767)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def duration(path):
    return float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
    )


def tempo_filters(ratio):
    parts = []
    while ratio > 2:
        parts.append("atempo=2")
        ratio /= 2
    while ratio < 0.5:
        parts.append("atempo=0.5")
        ratio *= 2
    parts.append(f"atempo={ratio:.8f}")
    return ",".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-dir", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "samples" / "clip.mp4")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work" / "demo_media")
    args = parser.parse_args()
    segments = json.loads(FIXTURE.read_text())["segments"]
    voices = []
    voice_source = {}
    if args.voice_dir:
        metadata_file = args.voice_dir / "voice_provenance.json"
        if metadata_file.exists():
            raw_metadata = json.loads(metadata_file.read_text())
            voice_source = {
                key: raw_metadata[key]
                for key in ("provider", "voice_ids", "official_reference")
                if key in raw_metadata
            }

        voices = [args.voice_dir / f"segment_{i:02d}.wav" for i in range(len(segments))]
        missing = [p.name for p in voices if not p.is_file()]
        if missing:
            raise SystemExit(f"All 13 voice tracks are required. Missing: {', '.join(missing)}")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    silent = args.work_dir / "illustrated.mp4"
    fx = args.work_dir / "sound-effects.wav"
    sound_effects(fx)
    encoder = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{W}x{H}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            str(silent),
        ],
        stdin=subprocess.PIPE,
    )
    base = background()
    for i in range(FPS * DURATION):
        image = frame(base, i / FPS, segments, bool(voices))
        if i == 10 * FPS:
            image.save(args.work_dir / "preview.png")
        encoder.stdin.write(image.tobytes())
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise SystemExit("Video render failed")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(fx)]
    filters = ["[1:a]volume=0.85[fx]"]
    sources = ["[fx]"]
    voice_meta = []
    for i, path in enumerate(voices):
        segment = segments[i]
        target = (segment["end_ms"] - segment["start_ms"]) / 1000
        original_duration = duration(path)
        cmd += ["-i", str(path)]
        filters.append(
            f"[{i + 2}:a]aresample=48000,{tempo_filters(original_duration / target)},"
            f"apad,atrim=duration={target},adelay={segment['start_ms']}:all=1[v{i}]"
        )
        sources.append(f"[v{i}]")
        voice_meta.append(
            {
                "file": path.name,
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
                "original_duration_s": original_duration,
                "tempo_ratio": original_duration / target,
            }
        )
    filters.append(
        "".join(sources) + f"amix=inputs={len(sources)}:normalize=0,"
        f"alimiter=limit=0.94,atrim=duration={DURATION}[audio]"
    )
    cmd += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v",
        "-map",
        "[audio]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-t",
        str(DURATION),
        "-movflags",
        "+faststart",
        str(args.output),
    ]
    subprocess.run(cmd, check=True)
    provenance = {
        "title": "The Briefing",
        "duration_s": DURATION,
        "visuals": "Original geometric illustration rendered with Pillow; no external media",
        "audio": "Original synthesized phone and door effects"
        + ("; externally supplied synthetic voice tracks" if voices else "; no spoken dialogue"),
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "fixture_status": "Authored review scenario, not measured model accuracy",
        "phone_ms": 18500,
        "door_ms": 56000,
        "voice_tracks": voice_meta,
        "voice_source": voice_source,
    }
    args.output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
                "duration_s": duration(args.output),
                "voice_tracks": len(voices),
            }
        )
    )


if __name__ == "__main__":
    main()
