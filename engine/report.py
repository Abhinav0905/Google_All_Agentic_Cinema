"""HTML QC Report generator for CueCheck using Jinja2."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from jinja2 import Template

from engine.models import Finding, Fix, Profile, Scorecard
from engine.parsers import ms_to_srt_timecode

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_PATH = TEMPLATES_DIR / "report_template.html"


def generate_html_report(
    run_id: str,
    profile: Profile,
    scorecard: Scorecard,
    findings: List[Finding],
    fixes: List[Fix],
    after_scorecard: Optional[Scorecard] = None,
    created_at: Optional[str] = None,
) -> str:
    """Generate standalone HTML QC audit report."""
    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_str)
    sorted_findings = sorted(findings, key=lambda f: f.start_ms)

    timestamp = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return template.render(
        run_id=run_id,
        created_at=timestamp,
        profile=profile,
        scorecard=scorecard,
        after_scorecard=after_scorecard,
        findings=sorted_findings,
        fixes=fixes,
        format_tc=ms_to_srt_timecode,
    )


def save_html_report(
    filepath: Path,
    run_id: str,
    profile: Profile,
    scorecard: Scorecard,
    findings: List[Finding],
    fixes: List[Fix],
    after_scorecard: Optional[Scorecard] = None,
) -> Path:
    """Write HTML audit report to disk."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    html_content = generate_html_report(
        run_id=run_id,
        profile=profile,
        scorecard=scorecard,
        findings=findings,
        fixes=fixes,
        after_scorecard=after_scorecard,
    )
    filepath.write_text(html_content, encoding="utf-8")
    return filepath
