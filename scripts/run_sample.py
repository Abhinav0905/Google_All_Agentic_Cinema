#!/usr/bin/env python3
"""CLI runner for CueCheck QC pipeline on sample media deliverables.

Usage:
  python scripts/run_sample.py [--live] [--profile adult] [--no-sdh] [--no-ad]
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

from engine.alignment import align_cues_to_segments
from engine.models import Finding
from engine.parsers import ms_to_srt_timecode, parse_timed_text
from engine.profiles import load_profile
from engine.rules import run_caption_rules, run_semantic_rules

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"
SAMPLES_DIR = ROOT_DIR / "samples"


def load_ground_truth(live: bool, media_uri: str):
    """Load segments, audio events, and visual events either from Vertex AI or offline fixtures."""
    from agents.multimodal import run_listen, run_look, run_transcribe

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    can_run_live = live and project and project != "your-gcp-project-id"

    if can_run_live:
        print("[mode] Running LIVE against Vertex AI Gemini models...")
        segments = run_transcribe(media_uri)
        audio_events = run_listen(media_uri)
        segments, visual_events = run_look(media_uri, segments)
    else:
        if live:
            print(
                "[warning] Live mode requested but GCP project not configured. "
                "Falling back to fixtures."
            )
        else:
            print("[mode] Running with recorded ground-truth fixtures...")

        transcribe_fix = FIXTURES_DIR / "transcribe_fixture.json"
        listen_fix = FIXTURES_DIR / "listen_fixture.json"
        look_fix = FIXTURES_DIR / "look_fixture.json"

        segments = run_transcribe(media_uri, offline_fixture=transcribe_fix)
        audio_events = run_listen(media_uri, offline_fixture=listen_fix)
        segments, visual_events = run_look(media_uri, segments, offline_fixture=look_fix)

    return segments, audio_events, visual_events


def print_findings_table(findings: List[Finding]) -> None:
    """Format and print findings report in terminal."""
    sorted_findings = sorted(findings, key=lambda f: f.start_ms)

    sev_colors = {
        "error": "\033[91mERROR\033[0m",
        "warning": "\033[93mWARN \033[0m",
        "info": "\033[94mINFO \033[0m",
    }

    print("\n" + "=" * 100)
    print(f"{'TIME':<13} | {'SEV':<5} | {'CODE':<22} | {'MESSAGE & EVIDENCE'}")
    print("-" * 100)

    for f in sorted_findings:
        tc = ms_to_srt_timecode(f.start_ms)
        sev_label = sev_colors.get(f.severity, f.severity.upper())
        msg = f.message
        if f.evidence and f.evidence not in f.message:
            msg += f"  [{f.evidence}]"
        print(f"{tc:<13} | {sev_label} | {f.code:<22} | {msg}")

    print("=" * 100)

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    infos = sum(1 for f in findings if f.severity == "info")

    print(
        f"Summary: {len(findings)} total findings "
        f"({errors} errors, {warnings} warnings, {infos} info)\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CueCheck QC pipeline on sample deliverables.")
    parser.add_argument("--live", action="store_true", help="Execute live Vertex AI model calls")
    parser.add_argument("--profile", default="adult", help="Profile ID (adult or kids)")
    parser.add_argument(
        "--captions", default=str(SAMPLES_DIR / "captions_bad.srt"), help="Path to captions file"
    )
    parser.add_argument(
        "--ad", default=str(SAMPLES_DIR / "ad_script.srt"), help="Path to Audio Description file"
    )
    parser.add_argument(
        "--media", default="gs://cuecheck-media/sample_clip.mp4", help="GCS URI or path to video"
    )
    parser.add_argument("--no-sdh", action="store_true", help="Disable SDH checks")
    parser.add_argument("--no-ad", action="store_true", help="Disable AD checks")

    args = parser.parse_args()

    # Load profile
    profile = load_profile(args.profile)
    print(f"[profile] Loaded profile '{profile.name}' (ID: {profile.id})")

    # Ingest captions
    caption_path = Path(args.captions)
    if not caption_path.exists():
        print(f"[error] Captions file not found: {caption_path}", file=sys.stderr)
        return 1
    cues = parse_timed_text(caption_path, kind="caption")
    print(f"[ingest] Parsed {len(cues)} caption cues from {caption_path.name}")

    # Ingest AD script if present
    ad_cues = None
    if not args.no_ad:
        ad_path = Path(args.ad)
        if ad_path.exists():
            ad_cues = parse_timed_text(ad_path, kind="ad")
            print(f"[ingest] Parsed {len(ad_cues)} AD cues from {ad_path.name}")

    # Step 1: Deterministic caption rules
    print("[pipeline] Running deterministic caption rules...")
    caption_findings = run_caption_rules(cues, profile)

    # Step 2: Ground truth pass (Transcribe, Listen, Look)
    print("[pipeline] Acquiring multimodal ground truth...")
    segments, audio_events, visual_events = load_ground_truth(args.live, args.media)
    print(
        f"[pipeline] Transcribed {len(segments)} segments, "
        f"{len(audio_events)} audio events, {len(visual_events)} visual events"
    )

    # Step 3: Alignment
    print("[pipeline] Aligning captions to speech segments...")
    alignment = align_cues_to_segments(cues, segments, profile)
    alignment_findings = alignment.findings

    # Step 4: Semantic rules (SDH & AD)
    print("[pipeline] Evaluating semantic accessibility rules...")
    semantic_findings = run_semantic_rules(
        profile=profile,
        alignment=alignment,
        audio_events=audio_events,
        visual_events=visual_events,
        captions=cues,
        ad_cues=ad_cues,
        sdh_mode=not args.no_sdh,
    )

    all_findings = caption_findings + alignment_findings + semantic_findings
    print_findings_table(all_findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
