"""Tests for HTML QC audit report generator."""

from pathlib import Path

from engine.models import DimensionScore, Finding, Fix, Scorecard
from engine.profiles import load_profile
from engine.report import generate_html_report, save_html_report


def test_generate_html_report():
    profile = load_profile("adult")
    scorecard = Scorecard(
        accuracy=DimensionScore(score=0.99, threshold=0.98, status="pass"),
        synchronicity=DimensionScore(score=0.96, threshold=0.95, status="pass"),
        completeness=DimensionScore(score=0.99, threshold=0.98, status="pass"),
        readability=DimensionScore(score=0.94, threshold=0.95, status="warn"),
        sdh_coverage=DimensionScore(score=0.92, threshold=0.90, status="pass"),
        overall_status="warn",
    )
    after_scorecard = Scorecard(
        accuracy=DimensionScore(score=0.99, threshold=0.98, status="pass"),
        synchronicity=DimensionScore(score=1.0, threshold=0.95, status="pass"),
        completeness=DimensionScore(score=1.0, threshold=0.98, status="pass"),
        readability=DimensionScore(score=1.0, threshold=0.95, status="pass"),
        sdh_coverage=DimensionScore(score=1.0, threshold=0.90, status="pass"),
        overall_status="pass",
    )
    finding = Finding(
        id="F1",
        code="CPS",
        severity="error",
        cue_index=1,
        start_ms=1000,
        end_ms=2000,
        message="Reading speed too high",
        evidence="35 cps",
        spec_ref="Max 20 cps",
    )
    fix = Fix(
        id="FIX_F1",
        finding_ids=["F1"],
        type="extend",
        status="proposed",
    )

    html = generate_html_report(
        run_id="test-run-999",
        profile=profile,
        scorecard=scorecard,
        findings=[finding],
        fixes=[fix],
        after_scorecard=after_scorecard,
    )

    assert "<!DOCTYPE html>" in html
    assert "FrameKind" in html
    assert "test-run-999" in html
    assert "General reading (project preset)" in html
    assert "Before / After Accepted Repairs" in html
    assert "Reading speed too high" in html
    assert "FIX_F1" or "FIX #" in html


def test_save_html_report(tmp_path: Path):
    profile = load_profile("adult")
    scorecard = Scorecard(
        accuracy=DimensionScore(score=0.99, threshold=0.98, status="pass"),
        synchronicity=DimensionScore(score=0.96, threshold=0.95, status="pass"),
        completeness=DimensionScore(score=0.99, threshold=0.98, status="pass"),
        readability=DimensionScore(score=0.97, threshold=0.95, status="pass"),
        overall_status="pass",
    )
    out_file = tmp_path / "audit_report.html"
    res_path = save_html_report(
        filepath=out_file,
        run_id="test-save-123",
        profile=profile,
        scorecard=scorecard,
        findings=[],
        fixes=[],
    )
    assert res_path.exists()
    assert "test-save-123" in res_path.read_text(encoding="utf-8")


def test_caption_only_report_handles_unchecked_dimensions_and_escapes_evidence():
    scorecard = Scorecard(readability=DimensionScore(score=1, threshold=0.95, status="pass"))
    finding = Finding(
        id="unsafe",
        code="CPS",
        severity="warning",
        start_ms=0,
        end_ms=1000,
        message="<script>alert(1)</script>",
        evidence="<img src=x onerror=alert(1)>",
        spec_ref="Project threshold",
    )
    html = generate_html_report(
        "caption-only", load_profile("adult"), scorecard, [finding], [], after_scorecard=scorecard
    )
    assert "Not checked" in html
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
