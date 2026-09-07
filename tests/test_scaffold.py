"""Scaffold test to verify pytest environment and imports."""

import importlib


def test_packages_exist():
    for pkg in ["engine", "agents", "api", "scripts"]:
        mod = importlib.import_module(pkg)
        assert mod is not None


def test_license_exists():
    from pathlib import Path

    license_path = Path(__file__).resolve().parent.parent / "LICENSE"
    assert license_path.exists()
    assert "Apache License" in license_path.read_text()
