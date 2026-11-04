"""CueCheck QC Pipeline using google-adk SequentialAgent.

Orchestrates the 8 accessibility QC pipeline steps:
1. Ingest (deterministic): parse SRT/VTT, validate duration, load profile
2. Transcribe (Gemini Flash): dialogue transcription
3. Listen (Gemini Flash): audio events detection
4. Look (Gemini Pro/Flash): speaker on-screen visibility & visual events
5. Rules (deterministic): caption-only timed-text rules
6. Align (deterministic): temporal cue-to-segment matching, WER, sync offsets
7. Semantic checks (deterministic): SDH & AD rules
8. Score and plan fixes (deterministic): compute scorecard, generate fix proposals

Each step agent implements execute() for the CLI/API runner and
_run_async_impl() so `adk web` can drive the SequentialAgent from session state.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event

from agents.multimodal import run_listen, run_look, run_transcribe
from engine.alignment import AlignmentResult, align_cues_to_segments
from engine.export import export_cues
from engine.fixer import plan_fixes
from engine.models import (
    AudioEvent,
    Cue,
    Finding,
    Profile,
    Run,
    Segment,
    TraceStep,
    VisualEvent,
)
from engine.parsers import parse_timed_text
from engine.profiles import load_profile
from engine.rules import run_caption_rules, run_semantic_rules
from engine.scoring import compute_scorecard


def load_cues_from_uri(uri: str, kind: str = "caption"):
    """Parse cues from a local path or a gs:// text object."""
    if uri.startswith("gs://"):
        from engine.gcs import download_blob_to_string

        content = download_blob_to_string(uri)
        return parse_timed_text(content, kind=kind)
    return parse_timed_text(uri, kind=kind)

TraceCallback = Callable[[TraceStep, Run], None]

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"
SAMPLES_DIR = ROOT_DIR / "samples"


class PipelineContext:
    """Carries in-flight execution state across the 8 pipeline steps."""

    def __init__(
        self,
        run: Run,
        live: bool = False,
        trace_callback: Optional[TraceCallback] = None,
    ):
        self.run = run
        self.live = live
        self.trace_callback = trace_callback
        self.profile: Optional[Profile] = None
        self.cues: List[Cue] = []
        self.ad_cues: Optional[List[Cue]] = None
        self.segments: List[Segment] = []
        self.audio_events: List[AudioEvent] = []
        self.visual_events: List[VisualEvent] = []
        self.caption_findings: List[Finding] = []
        self.alignment_result: Optional[AlignmentResult] = None
        self.semantic_findings: List[Finding] = []

    def emit_trace(
        self,
        step_name: str,
        status: str,
        duration_s: float = 0.0,
        summary: str = "",
        error: Optional[str] = None,
    ) -> None:
        step = TraceStep(
            step_name=step_name,
            status=status,
            duration_s=round(duration_s, 2),
            summary=summary,
            error=error,
        )
        existing_idx = next(
            (i for i, s in enumerate(self.run.steps) if s.step_name == step_name), None
        )
        if existing_idx is not None:
            self.run.steps[existing_idx] = step
        else:
            self.run.steps.append(step)

        if self.trace_callback:
            try:
                self.trace_callback(step, self.run)
            except Exception:
                pass


def serialize_pipeline(pctx: PipelineContext) -> Dict[str, Any]:
    """JSON-safe snapshot of pipeline state for ADK session.state."""
    return {
        "qc_run": pctx.run.model_dump(),
        "qc_live": pctx.live,
        "qc_cues": [c.model_dump() for c in pctx.cues],
        "qc_ad_cues": [c.model_dump() for c in (pctx.ad_cues or [])],
        "qc_segments": [s.model_dump() for s in pctx.segments],
        "qc_audio_events": [e.model_dump() for e in pctx.audio_events],
        "qc_visual_events": [e.model_dump() for e in pctx.visual_events],
        "qc_caption_findings": [f.model_dump() for f in pctx.caption_findings],
        "qc_alignment": (
            pctx.alignment_result.model_dump() if pctx.alignment_result else None
        ),
        "qc_semantic_findings": [f.model_dump() for f in pctx.semantic_findings],
    }


def restore_pipeline(
    state: Dict[str, Any],
    trace_callback: Optional[TraceCallback] = None,
) -> Optional[PipelineContext]:
    """Rebuild PipelineContext from ADK session.state."""
    raw_run = state.get("qc_run")
    if not raw_run:
        return None
    run = Run.model_validate(raw_run)
    pctx = PipelineContext(
        run, live=bool(state.get("qc_live", False)), trace_callback=trace_callback
    )
    pctx.profile = load_profile(run.profile_id)
    pctx.cues = [Cue.model_validate(c) for c in state.get("qc_cues", [])]
    ad_raw = state.get("qc_ad_cues") or []
    pctx.ad_cues = [Cue.model_validate(c) for c in ad_raw] if ad_raw else None
    pctx.segments = [Segment.model_validate(s) for s in state.get("qc_segments", [])]
    pctx.audio_events = [AudioEvent.model_validate(e) for e in state.get("qc_audio_events", [])]
    pctx.visual_events = [VisualEvent.model_validate(e) for e in state.get("qc_visual_events", [])]
    pctx.caption_findings = [
        Finding.model_validate(f) for f in state.get("qc_caption_findings", [])
    ]
    if state.get("qc_alignment"):
        pctx.alignment_result = AlignmentResult.model_validate(state["qc_alignment"])
    pctx.semantic_findings = [
        Finding.model_validate(f) for f in state.get("qc_semantic_findings", [])
    ]
    return pctx


def _user_text(ctx: InvocationContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return " ".join(part.text or "" for part in ctx.user_content.parts)


def bootstrap_pipeline(ctx: InvocationContext) -> PipelineContext:
    """Start a sample QC run from an adk web user message."""
    text = _user_text(ctx).lower()
    profile_id = "kids" if ("kids" in text or "children" in text) else "adult"
    live = "live" in text and "offline" not in text
    run = Run(
        id=ctx.session.id or "adk-web-run",
        profile_id=profile_id,
        sdh_mode="no-sdh" not in text,
        has_ad="no-ad" not in text,
        media_uri="gs://cuecheck-media/sample_clip.mp4",
        caption_uri=str(SAMPLES_DIR / "captions_bad.srt"),
        ad_uri=str(SAMPLES_DIR / "ad_script.srt"),
    )
    return PipelineContext(run, live=live)


def context_from_invocation(ctx: InvocationContext) -> PipelineContext:
    restored = restore_pipeline(dict(ctx.session.state))
    if restored is not None:
        return restored
    return bootstrap_pipeline(ctx)


class QcStepAgent(BaseAgent):
    """Base QC step: execute() for CLI, _run_async_impl() for adk web."""

    def execute(self, pctx: PipelineContext) -> None:
        raise NotImplementedError

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        pctx = context_from_invocation(ctx)
        try:
            self.execute(pctx)
        except Exception as exc:
            ctx.session.state.update(serialize_pipeline(pctx))
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                message=f"{self.name} failed: {exc}",
                state=serialize_pipeline(pctx),
            )
            raise

        delta = serialize_pipeline(pctx)
        ctx.session.state.update(delta)
        step = next((s for s in pctx.run.steps if s.step_name == self.name), None)
        summary = step.summary if step else f"{self.name} completed"
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            message=f"[{self.name}] {summary}",
            state=delta,
        )

    async def _run_impl(self, *, ctx: Any, node_input: Any) -> AsyncGenerator[Any, None]:
        pctx: PipelineContext = node_input
        self.execute(pctx)
        yield Event(author=self.name, output=pctx)


class IngestAgent(QcStepAgent):
    name: str = "ingest"
    description: str = "Fetch files, validate media, parse timed-text cues, and load profile"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Parsing files and validating media...")
        try:
            pctx.profile = load_profile(pctx.run.profile_id)

            if pctx.run.caption_uri:
                pctx.cues = load_cues_from_uri(pctx.run.caption_uri, kind="caption")

            if pctx.run.has_ad and pctx.run.ad_uri:
                pctx.ad_cues = load_cues_from_uri(pctx.run.ad_uri, kind="ad")

            dur = time.time() - start
            summary = (
                f"Loaded profile '{pctx.profile.name}', parsed {len(pctx.cues)} captions"
                + (f" and {len(pctx.ad_cues)} AD cues" if pctx.ad_cues else "")
            )
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class TranscribeAgent(QcStepAgent):
    name: str = "transcribe"
    description: str = "Multimodal speech transcription using Gemini Flash"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Transcribing spoken dialogue...")
        try:
            can_live = pctx.live and os.environ.get("GOOGLE_CLOUD_PROJECT")
            fixture = (FIXTURES_DIR / "transcribe_fixture.json") if not can_live else None
            media_uri = pctx.run.media_uri or "gs://cuecheck-media/sample.mp4"

            pctx.segments = run_transcribe(media_uri, offline_fixture=fixture)
            dur = time.time() - start
            summary = f"Transcribed {len(pctx.segments)} speech segments"
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class ListenAgent(QcStepAgent):
    name: str = "listen"
    description: str = "Multimodal non-speech audio event detection using Gemini Flash"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Listening for Foley and sound effects...")
        try:
            can_live = pctx.live and os.environ.get("GOOGLE_CLOUD_PROJECT")
            fixture = (FIXTURES_DIR / "listen_fixture.json") if not can_live else None
            media_uri = pctx.run.media_uri or "gs://cuecheck-media/sample.mp4"

            pctx.audio_events = run_listen(media_uri, offline_fixture=fixture)
            dur = time.time() - start
            summary = f"Detected {len(pctx.audio_events)} non-speech audio events"
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class LookAgent(QcStepAgent):
    name: str = "look"
    description: str = "Multimodal visual pass for speaker visibility and visual events"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Analyzing speaker visibility & visuals...")
        try:
            can_live = pctx.live and os.environ.get("GOOGLE_CLOUD_PROJECT")
            fixture = (FIXTURES_DIR / "look_fixture.json") if not can_live else None
            media_uri = pctx.run.media_uri or "gs://cuecheck-media/sample.mp4"

            pctx.segments, pctx.visual_events = run_look(
                media_uri, pctx.segments, offline_fixture=fixture
            )
            dur = time.time() - start
            offscreen = sum(1 for s in pctx.segments if s.speaker_on_screen is False)
            summary = (
                f"Evaluated visual pass: {offscreen} off-screen segments, "
                f"{len(pctx.visual_events)} visual events"
            )
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class RulesAgent(QcStepAgent):
    name: str = "rules"
    description: str = "Deterministic timed-text rules execution on captions"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Checking CPS, CPL, lines, duration, gaps...")
        try:
            pctx.caption_findings = run_caption_rules(pctx.cues, pctx.profile)
            dur = time.time() - start
            summary = f"Generated {len(pctx.caption_findings)} deterministic caption findings"
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class AlignAgent(QcStepAgent):
    name: str = "align"
    description: str = "Align captions to speech segments and detect sync/accuracy defects"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Aligning captions with transcript...")
        try:
            pctx.alignment_result = align_cues_to_segments(pctx.cues, pctx.segments, pctx.profile)
            dur = time.time() - start
            shift_info = (
                f", median offset {pctx.alignment_result.median_offset_ms}ms"
                if pctx.alignment_result.median_offset_ms
                else ""
            )
            summary = (
                f"Matched {len(pctx.alignment_result.matches)} cues "
                f"({len(pctx.alignment_result.findings)} sync/accuracy findings{shift_info})"
            )
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class SemanticAgent(QcStepAgent):
    name: str = "semantic"
    description: str = "Evaluate SDH and Audio Description semantic accessibility rules"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Auditing SDH and AD rules...")
        try:
            pctx.semantic_findings = run_semantic_rules(
                profile=pctx.profile,
                alignment=pctx.alignment_result,
                audio_events=pctx.audio_events,
                visual_events=pctx.visual_events,
                captions=pctx.cues,
                ad_cues=pctx.ad_cues,
                sdh_mode=pctx.run.sdh_mode,
            )
            dur = time.time() - start
            summary = f"Identified {len(pctx.semantic_findings)} semantic accessibility findings"
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


class ScoreAndPlanAgent(QcStepAgent):
    name: str = "score_and_plan"
    description: str = "Calculate FCC/streaming scorecard and plan deterministic fixes"

    def execute(self, pctx: PipelineContext) -> None:
        start = time.time()
        pctx.emit_trace(self.name, "running", summary="Computing scorecard and planning fixes...")
        try:
            all_findings = (
                pctx.caption_findings
                + (pctx.alignment_result.findings if pctx.alignment_result else [])
                + pctx.semantic_findings
            )
            pctx.run.findings = all_findings

            scorecard = compute_scorecard(
                cues=pctx.cues,
                profile=pctx.profile,
                alignment=pctx.alignment_result,
                findings=all_findings,
                audio_events=pctx.audio_events,
                visual_events=pctx.visual_events,
                ad_cues=pctx.ad_cues,
                sdh_mode=pctx.run.sdh_mode,
            )
            pctx.run.scorecard = scorecard

            pctx.run.fixes = plan_fixes(
                findings=all_findings,
                cues=pctx.cues,
                profile=pctx.profile,
                alignment=pctx.alignment_result,
                ad_cues=pctx.ad_cues,
            )

            pctx.run.exports["srt"] = export_cues(pctx.cues, "srt")
            pctx.run.exports["vtt"] = export_cues(pctx.cues, "vtt")

            pctx.run.status = "completed"
            dur = time.time() - start
            summary = (
                f"Scorecard: {scorecard.overall_status.upper()} | "
                f"Planned {len(pctx.run.fixes)} fix proposals"
            )
            pctx.emit_trace(self.name, "completed", duration_s=dur, summary=summary)
        except Exception as e:
            dur = time.time() - start
            pctx.run.status = "failed"
            pctx.emit_trace(self.name, "failed", duration_s=dur, summary=str(e), error=str(e))
            raise


def create_qc_sequential_agent() -> SequentialAgent:
    """Create ADK SequentialAgent pipeline registering all 8 steps in order."""
    return SequentialAgent(
        name="cuecheck_qc_pipeline",
        description="End-to-end 8-step accessibility quality control pipeline",
        sub_agents=[
            IngestAgent(),
            TranscribeAgent(),
            ListenAgent(),
            LookAgent(),
            RulesAgent(),
            AlignAgent(),
            SemanticAgent(),
            ScoreAndPlanAgent(),
        ],
    )


async def execute_pipeline_with_context(
    run: Run,
    live: bool = False,
    trace_callback: Optional[TraceCallback] = None,
) -> PipelineContext:
    """Execute the 8-step pipeline and return the in-memory context."""
    pctx = PipelineContext(run, live=live, trace_callback=trace_callback)
    pipeline_agent = create_qc_sequential_agent()

    try:
        run.status = "running"
        for agent in pipeline_agent.sub_agents:
            agent.execute(pctx)
        run.status = "completed"
        if trace_callback:
            trace_callback(
                TraceStep(
                    step_name="run.complete",
                    status="completed",
                    summary=(
                        f"{len(run.findings)} findings, {len(run.fixes)} fixes, "
                        f"overall {run.scorecard.overall_status if run.scorecard else 'n/a'}"
                    ),
                ),
                run,
            )
    except Exception as e:
        run.status = "failed"
        if trace_callback:
            fail_step = TraceStep(
                step_name="run.failed",
                status="failed",
                summary=f"Pipeline aborted: {e}",
                error=str(e),
            )
            trace_callback(fail_step, run)
        raise

    return pctx


async def execute_pipeline(
    run: Run,
    live: bool = False,
    trace_callback: Optional[TraceCallback] = None,
) -> Run:
    """Execute the complete 8-step ADK pipeline on a Run instance."""
    pctx = await execute_pipeline_with_context(
        run, live=live, trace_callback=trace_callback
    )
    return pctx.run
