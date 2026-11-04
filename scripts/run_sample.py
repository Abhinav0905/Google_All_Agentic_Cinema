#!/usr/bin/env python3
"""CLI runner for CueCheck QC pipeline on sample media deliverables.

Executes the 8-step ADK pipeline, simulates fix application, produces
before/after scorecard metrics, and exports an HTML audit report.

Usage:
  python scripts/run_sample.py [--live] [--profile adult] [--no-sdh] [--no-ad]
"""

import argparse
import asyncio
from pathlib import Path

from agents.pipeline import execute_pipeline
from engine.alignment import align_cues_to_segments
from engine.fixer import apply_accepted_fixes
from engine.models import Finding, Fix, Run, Scorecard, TraceStep
from engine.parsers import ms_to_srt_timecode
from engine.profiles import load_profile
from engine.report import save_html_report
from engine.rules import run_caption_rules, run_semantic_rules
from engine.scoring import compute_scorecard

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "samples"


def print_findings_table(findings: list[Finding]) -> None:
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


def print_scorecard_comparison(before: Scorecard, after: Scorecard) -> None:
    """Print terminal comparison table of before and after scores."""
    print("\n" + "=" * 70)
    print("ACCESSIBILITY SCORECARD: BEFORE vs AFTER ACCEPTED FIXES")
    print("-" * 70)
    print(f"{'DIMENSION':<18} | {'BEFORE':<8} | {'AFTER':<8} | {'STATUS':<6} | {'IMPACT'}")
    print("-" * 70)

    dims = [
        ("Accuracy", before.accuracy, after.accuracy),
        ("Synchronicity", before.synchronicity, after.synchronicity),
        ("Completeness", before.completeness, after.completeness),
        ("Readability", before.readability, after.readability),
    ]
    if before.sdh_coverage and after.sdh_coverage:
        dims.append(("SDH Coverage", before.sdh_coverage, after.sdh_coverage))
    if before.ad_coverage and after.ad_coverage:
        dims.append(("AD Coverage", before.ad_coverage, after.ad_coverage))

    for name, b_dim, a_dim in dims:
        b_pct = f"{b_dim.score * 100:.1f}%"
        a_pct = f"{a_dim.score * 100:.1f}%"
        diff = (a_dim.score - b_dim.score) * 100
        diff_str = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
        print(f"{name:<18} | {b_pct:<8} | {a_pct:<8} | {a_dim.status.upper():<6} | {diff_str}")

    print("=" * 70)
    print(
        f"Overall Status: {before.overall_status.upper()} -> {after.overall_status.upper()}\n"
    )


def simulate_after_fixes(
    run: Run, fixes: list[Fix], profile
) -> tuple[Scorecard, list[Finding]]:
    """Simulate accepting all auto fixes, regenerate cues, and re-score."""
    # Mark all automated fixes as accepted
    for fix in fixes:
        if fix.auto:
            fix.status = "accepted"

    # Ingest original cues
    from engine.parsers import parse_timed_text

    cues = parse_timed_text(run.caption_uri, kind="caption") if run.caption_uri else []
    ad_cues = parse_timed_text(run.ad_uri, kind="ad") if (run.has_ad and run.ad_uri) else []

    # Get median shift from alignment
    from agents.multimodal import run_listen, run_look, run_transcribe
    from agents.pipeline import FIXTURES_DIR

    fixture_t = FIXTURES_DIR / "transcribe_fixture.json"
    segments = run_transcribe(run.media_uri or "", offline_fixture=fixture_t)
    audio_events = run_listen(
        run.media_uri or "", offline_fixture=FIXTURES_DIR / "listen_fixture.json"
    )
    segments, visual_events = run_look(
        run.media_uri or "", segments, offline_fixture=FIXTURES_DIR / "look_fixture.json"
    )

    orig_align = align_cues_to_segments(cues, segments, profile)
    median_shift = orig_align.median_offset_ms or 0

    new_cues, new_ad = apply_accepted_fixes(
        cues, fixes, ad_cues, median_shift_ms=median_shift
    )

    # Re-evaluate
    caption_findings = run_caption_rules(new_cues, profile)
    alignment = align_cues_to_segments(new_cues, segments, profile)
    semantic_findings = run_semantic_rules(
        profile=profile,
        alignment=alignment,
        audio_events=audio_events,
        visual_events=visual_events,
        captions=new_cues,
        ad_cues=new_ad,
        sdh_mode=run.sdh_mode,
    )
    all_findings = caption_findings + alignment.findings + semantic_findings

    after_scorecard = compute_scorecard(
        cues=new_cues,
        profile=profile,
        alignment=alignment,
        findings=all_findings,
        audio_events=audio_events,
        visual_events=visual_events,
        ad_cues=new_ad,
        sdh_mode=run.sdh_mode,
    )

    return after_scorecard, all_findings


async def async_main() -> int:
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
    parser.add_argument(
        "--report", default=str(SAMPLES_DIR / "report.html"), help="Output HTML report path"
    )

    args = parser.parse_args()

    profile = load_profile(args.profile)

    run = Run(
        id="sample-run-001",
        profile_id=args.profile,
        sdh_mode=not args.no_sdh,
        has_ad=not args.no_ad,
        media_uri=args.media,
        caption_uri=args.captions,
        ad_uri=args.ad,
    )

    def on_trace(step: TraceStep, _run: Run) -> None:
        dur_str = f"({step.duration_s}s)" if step.duration_s > 0 else ""
        print(f"[{step.step_name:<14}] {step.status.upper():<9} {step.summary} {dur_str}")

    print("=== CueCheck QC SequentialAgent Pipeline ===")
    await execute_pipeline(run, live=args.live, trace_callback=on_trace)

    print_findings_table(run.findings)

    print("\nSummary:")
    print(f"  Status: {run.status}")
    print(f"  Findings: {len(run.findings)}")
    print(f"  Fixes: {len(run.fixes)}")
    if run.scorecard:
        print(f"  Overall: {run.scorecard.overall_status}")

    # Calculate after scores
    after_scorecard, _ = simulate_after_fixes(run, run.fixes, profile)
    if run.scorecard:
        print_scorecard_comparison(run.scorecard, after_scorecard)

    # Save HTML report
    report_path = Path(args.report)
    save_html_report(
        filepath=report_path,
        run_id=run.id,
        profile=profile,
        scorecard=run.scorecard,  # type: ignore
        findings=run.findings,
        fixes=run.fixes,
        after_scorecard=after_scorecard,
    )
    print(f"[report] Saved HTML audit report with before/after scores to: {report_path.resolve()}")

    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    import sys
    sys.exit(main())
