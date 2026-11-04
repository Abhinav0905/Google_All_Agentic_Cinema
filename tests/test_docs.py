"""Docs gates for Phase 5."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_architecture_doc_has_mermaid_and_layers():
    text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "```mermaid" in text
    assert "engine/" in text
    assert "SequentialAgent" in text
    assert "gs://" in text


def test_readme_leads_with_sample():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Load sample" in text
    assert "uvicorn api.main:app" in text
    assert "docs/ARCHITECTURE.md" in text
