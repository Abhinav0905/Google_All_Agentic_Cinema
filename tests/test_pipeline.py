"""Tests for ADK SequentialAgent QC pipeline execution."""

from pathlib import Path

import pytest

from agents.agent import root_agent
from agents.pipeline import create_qc_sequential_agent, execute_pipeline
from engine.models import Run, TraceStep

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "samples"


def test_create_qc_sequential_agent():
    agent = create_qc_sequential_agent()
    assert agent.name == "cuecheck_qc_pipeline"
    # Verify all 8 step subagents are registered in order
    step_names = [a.name for a in agent.sub_agents]
    expected = [
        "ingest",
        "transcribe",
        "listen",
        "look",
        "rules",
        "align",
        "semantic",
        "score_and_plan",
    ]
    assert step_names == expected


@pytest.mark.anyio
async def test_execute_pipeline_end_to_end():
    run = Run(
        id="test-run-123",
        profile_id="adult",
        sdh_mode=True,
        has_ad=True,
        media_uri="gs://cuecheck-media/test_clip.mp4",
        caption_uri=str(SAMPLES_DIR / "captions_bad.srt"),
        ad_uri=str(SAMPLES_DIR / "ad_script.srt"),
    )

    traces = []

    def trace_collector(step: TraceStep, _r: Run):
        traces.append(step.model_copy())

    completed_run = await execute_pipeline(run, live=False, trace_callback=trace_collector)

    assert completed_run.status == "completed"
    assert len(completed_run.findings) > 0
    assert len(completed_run.fixes) > 0
    assert completed_run.scorecard is not None
    assert "srt" in completed_run.exports
    assert "vtt" in completed_run.exports

    # Verify all 8 steps were tracked in traces
    step_names_completed = [t.step_name for t in traces if t.status == "completed"]
    assert "ingest" in step_names_completed
    assert "transcribe" in step_names_completed
    assert "listen" in step_names_completed
    assert "look" in step_names_completed
    assert "rules" in step_names_completed
    assert "align" in step_names_completed
    assert "semantic" in step_names_completed
    assert "score_and_plan" in step_names_completed
    assert any(t.step_name == "run.complete" for t in traces)


def test_root_agent_is_sequential_pipeline():
    assert root_agent.name == "cuecheck_qc_pipeline"
    assert [a.name for a in root_agent.sub_agents] == [
        "ingest",
        "transcribe",
        "listen",
        "look",
        "rules",
        "align",
        "semantic",
        "score_and_plan",
    ]
    for agent in root_agent.sub_agents:
        assert hasattr(agent, "execute")
        assert hasattr(agent, "_run_async_impl")


@pytest.mark.anyio
async def test_custom_caption_only_never_uses_sample_evidence(tmp_path, monkeypatch):
    from agents import pipeline

    caption_file = tmp_path / "custom.srt"
    caption_file.write_text("1\n00:00:01,000 --> 00:00:03,000\nA different film.\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("Caption-only analysis must not call a model or sample fixture")

    for name in ("run_transcribe", "run_listen", "run_look"):
        monkeypatch.setattr(pipeline, name, forbidden)
    run = await pipeline.execute_pipeline(
        Run(id="custom", profile_id="adult", caption_uri=str(caption_file)),
        analysis_mode="caption_only",
    )
    assert run.status == "completed"
    assert run.analysis_mode == "caption_only"
    assert run.scorecard.readability is not None
    for field in ("accuracy", "synchronicity", "completeness", "sdh_coverage", "ad_coverage"):
        assert getattr(run.scorecard, field) is None
    assert not any(
        f.code in {"MISSING_DIALOGUE", "EXTRA_CAPTION", "SDH_MISSING_SFX"} for f in run.findings
    )


@pytest.mark.anyio
async def test_synchronous_step_yields_event_loop_and_publishes_on_owner_thread(monkeypatch):
    import asyncio
    import threading
    from types import SimpleNamespace

    from agents import pipeline

    entered, released = threading.Event(), threading.Event()
    callback_threads = []
    main_thread = threading.get_ident()

    class BlockingStep:
        def execute(self, pctx):
            entered.set()
            assert released.wait(timeout=2), "Pipeline blocked the event loop"
            pctx.emit_trace("worker", "completed")

    monkeypatch.setattr(
        pipeline, "create_qc_sequential_agent", lambda: SimpleNamespace(sub_agents=[BlockingStep()])
    )

    async def release_from_event_loop():
        assert await asyncio.to_thread(entered.wait, 1)
        released.set()

    await asyncio.gather(
        pipeline.execute_pipeline_with_context(
            Run(id="async", profile_id="adult"),
            analysis_mode="caption_only",
            trace_callback=lambda step, run: callback_threads.append(threading.get_ident()),
        ),
        release_from_event_loop(),
    )
    await asyncio.sleep(0)
    assert callback_threads
    assert set(callback_threads) == {main_thread}


@pytest.mark.anyio
async def test_actual_sample_exports_are_repeatable_and_source_is_unchanged():
    from agents.pipeline import execute_pipeline_with_context
    from engine.export import export_cues
    from engine.fixer import apply_accepted_fixes
    from engine.parsers import parse_timed_text

    captions = str(SAMPLES_DIR / "captions_bad.srt")
    original = [cue.model_dump() for cue in parse_timed_text(captions)]
    ctx = await execute_pipeline_with_context(
        Run(
            id="sample-regression",
            profile_id="adult",
            sdh_mode=True,
            has_ad=True,
            caption_uri=captions,
            ad_uri=str(SAMPLES_DIR / "ad_script.srt"),
        ),
        analysis_mode="sample",
    )
    assert [cue.model_dump() for cue in ctx.cues] == original
    for fix in ctx.run.fixes:
        if fix.auto:
            fix.status = "accepted"
    snapshots = [fix.model_dump() for fix in ctx.run.fixes]
    first, _ = apply_accepted_fixes(ctx.cues, ctx.run.fixes, ctx.ad_cues)
    second, _ = apply_accepted_fixes(ctx.cues, ctx.run.fixes, ctx.ad_cues)
    assert export_cues(first, "srt") == export_cues(second, "srt")
    assert [fix.model_dump() for fix in ctx.run.fixes] == snapshots


@pytest.mark.anyio
async def test_adk_step_emits_content_and_state_delta():
    from types import SimpleNamespace

    from google.genai import types

    from agents.pipeline import IngestAgent

    ctx = SimpleNamespace(
        session=SimpleNamespace(id="adk-test", state={}),
        invocation_id="invocation",
        user_content=types.Content(parts=[types.Part(text="run sample")]),
    )
    events = [event async for event in IngestAgent()._run_async_impl(ctx)]
    assert events[0].content.parts[0].text.startswith("[ingest]")
    assert events[0].actions.state_delta["qc_run"]["analysis_mode"] == "sample"


def test_missing_sample_fixture_does_not_fall_back_to_live(tmp_path, monkeypatch):
    from agents import multimodal

    monkeypatch.setattr(
        multimodal, "get_genai_client", lambda: pytest.fail("Missing sample must not call Vertex")
    )
    with pytest.raises(FileNotFoundError, match="Sample fixture is missing"):
        multimodal.run_transcribe("gs://unused", offline_fixture=tmp_path / "missing.json")
