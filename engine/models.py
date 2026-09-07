"""Data models for CueCheck (Pydantic).

All models represent core entities across the QC pipeline:
cues, transcript segments, audio events, visual events, findings, fixes,
scorecards, and runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Cue(BaseModel):
    """A timed-text cue (caption or audio description)."""

    index: int
    start_ms: int
    end_ms: int
    lines: List[str] = Field(default_factory=list)
    raw_text: str = ""
    kind: Literal["caption", "ad"] = "caption"

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def text(self) -> str:
        if self.lines:
            return "\n".join(self.lines)
        return self.raw_text


class Segment(BaseModel):
    """A speech segment from transcript / STT."""

    start_ms: int
    end_ms: int
    text: str
    speaker_label: Optional[str] = None
    speaker_on_screen: Optional[bool] = None  # Populated by visual pass
    confidence: float = 1.0


class AudioEvent(BaseModel):
    """Non-speech audio event (sound effects, music, ambient cues)."""

    t_ms: int
    label: str
    salience: Literal["plot", "ambient"] = "plot"
    source: str = "gemini"


class VisualEvent(BaseModel):
    """Visual event extracted from video."""

    t_ms: int
    label: str
    essential: bool = True
    kind: Literal["action", "scene_change", "onscreen_text", "expression"] = "action"


class Finding(BaseModel):
    """A QC finding/defect identified by deterministic rules or semantic passes."""

    id: str
    code: str
    severity: Literal["error", "warning", "info"]
    cue_index: Optional[int] = None
    start_ms: int
    end_ms: int
    message: str
    evidence: str
    spec_ref: str
    fix_id: Optional[str] = None


class Fix(BaseModel):
    """A proposed or applied fix for one or more findings."""

    id: str
    finding_ids: List[str] = Field(default_factory=list)
    type: str  # e.g. extend, re-wrap, split, trim, global_shift, normalize
    before: Optional[Cue] = None
    after: Optional[Cue] = None
    after_extra: Optional[Cue] = None  # second half for split
    auto: bool = True
    status: Literal["proposed", "accepted", "rejected"] = "proposed"


class DimensionScore(BaseModel):
    """Individual scorecard dimension."""

    score: float  # 0.0 to 1.0
    threshold: float
    status: Literal["pass", "warn", "fail"]
    counts: Dict[str, Any] = Field(default_factory=dict)


class Scorecard(BaseModel):
    """Overall QC scorecard evaluating against spec profile."""

    accuracy: Optional[DimensionScore] = None
    synchronicity: Optional[DimensionScore] = None
    completeness: Optional[DimensionScore] = None
    readability: Optional[DimensionScore] = None
    sdh_coverage: Optional[DimensionScore] = None
    ad_coverage: Optional[DimensionScore] = None
    overall_status: Literal["pass", "warn", "fail"] = "pass"


class RuleConfig(BaseModel):
    """A rule threshold configuration with documentation source."""

    value: Any
    source: str


class Profile(BaseModel):
    """Spec profile configuration containing all QC thresholds."""

    id: str
    name: str
    description: str
    max_cps: RuleConfig
    max_chars_per_line: RuleConfig
    max_lines: RuleConfig
    min_duration_ms: RuleConfig
    max_duration_ms: RuleConfig
    min_gap_ms: RuleConfig
    sync_tolerance_ms: RuleConfig
    ad_overlap_tolerance_ms: RuleConfig
    ad_max_wpm: RuleConfig
    pass_thresholds: Dict[str, RuleConfig] = Field(default_factory=dict)


class TraceStep(BaseModel):
    """A pipeline step trace event."""

    step_name: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    duration_s: float = 0.0
    summary: str = ""
    error: Optional[str] = None


class Run(BaseModel):
    """A complete QC analysis run."""

    id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile_id: str
    sdh_mode: bool = True
    has_ad: bool = False
    media_uri: Optional[str] = None
    caption_uri: Optional[str] = None
    ad_uri: Optional[str] = None
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    steps: List[TraceStep] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    fixes: List[Fix] = Field(default_factory=list)
    scorecard: Optional[Scorecard] = None
    exports: Dict[str, str] = Field(default_factory=dict)
