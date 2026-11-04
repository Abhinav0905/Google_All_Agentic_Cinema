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
        "ingest", "transcribe", "listen", "look",
        "rules", "align", "semantic", "score_and_plan"
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
    step_names_completed = [
        t.step_name for t in traces if t.status == "completed"
    ]
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
