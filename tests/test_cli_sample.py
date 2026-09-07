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
