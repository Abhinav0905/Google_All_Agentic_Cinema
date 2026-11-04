"""Test CLI runner scripts/run_sample.py."""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_cli_run_sample():
    script_path = ROOT_DIR / "scripts" / "run_sample.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--profile", "adult"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "TIME" in res.stdout
    assert "SYNC_OFFSET" in res.stdout
    assert "SDH_MISSING_SFX" in res.stdout
    assert "AD_OVERLAPS_DIALOGUE" in res.stdout
    assert "Summary:" in res.stdout


def test_after_score_uses_this_runs_evidence_not_sample_fixtures(monkeypatch):
    from agents import multimodal
    from agents.pipeline import PipelineContext
    from engine.models import Cue, Run, Segment
    from engine.profiles import load_profile
    from scripts.run_sample import simulate_after_fixes

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "After-score must reuse the completed run, without model/fixture calls"
        )

    for name in ("run_transcribe", "run_listen", "run_look"):
        monkeypatch.setattr(multimodal, name, forbidden)
    pctx = PipelineContext(Run(id="own-evidence", profile_id="adult"), analysis_mode="live")
    pctx.cues = [
        Cue(
            index=1,
            start_ms=1000,
            end_ms=3000,
            lines=["Different film."],
            raw_text="Different film.",
        )
    ]
    pctx.segments = [Segment(start_ms=1000, end_ms=3000, text="Different film.")]
    score, findings = simulate_after_fixes(pctx, [], load_profile("adult"))
    assert score.accuracy.score == 1
    assert score.completeness.score == 1
    assert not any(f.code == "MISSING_DIALOGUE" for f in findings)
