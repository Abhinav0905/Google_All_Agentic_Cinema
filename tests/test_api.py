"""API tests for run lifecycle, sample QC, fix decisions, and export."""

import time

from fastapi.testclient import TestClient

from api.main import app
from api.store import store


def _wait_complete(client: TestClient, run_id: str, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/runs/{run_id}")
        assert last.status_code == 200
        if last.json()["status"] in ("completed", "failed"):
            return last.json()
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not finish: {last.json() if last else None}")


def test_health():
    store.clear()
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert "vertex" in body
        assert "gcs" in body
        assert "stt" in body


def test_create_run_and_history():
    store.clear()
    with TestClient(app) as client:
        created = client.post("/api/runs")
        assert created.status_code == 201
        body = created.json()
        assert body["id"]
        assert "uploads" in body
        assert "video" in body["uploads"]
        listed = client.get("/api/runs")
        assert listed.status_code == 200
        assert any(row["id"] == body["id"] for row in listed.json())


def test_sample_run_accept_and_export():
    store.clear()
    with TestClient(app) as client:
        started = client.post("/api/runs/sample")
        assert started.status_code == 200
        run_id = started.json()["id"]
        finished = _wait_complete(client, run_id)
        assert finished["status"] == "completed"
        assert finished["scorecard"] is not None
        assert len(finished["findings"]) > 0
        assert len(finished["fixes"]) > 0
        assert finished["exports"]["srt"].endswith("format=srt")

        auto = next((fx for fx in finished["fixes"] if fx["auto"]), finished["fixes"][0])
        decided = client.post(
            f"/api/runs/{run_id}/fixes/{auto['id']}",
            json={"decision": "accept"},
        )
        assert decided.status_code == 200
        stored_fix = next(fx for fx in decided.json()["fixes"] if fx["id"] == auto["id"])
        assert stored_fix["status"] == "accepted"

        srt = client.get(f"/api/runs/{run_id}/export?format=srt")
        assert srt.status_code == 200
        assert "-->" in srt.text

        report = client.get(f"/api/runs/{run_id}/export?format=report")
        assert report.status_code == 200
        assert "CueCheck" in report.text


def test_sample_events_include_complete():
    store.clear()
    with TestClient(app) as client:
        started = client.post("/api/runs/sample")
        run_id = started.json()["id"]
        _wait_complete(client, run_id)
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            lines = []
            for line in stream.iter_lines():
                if line:
                    lines.append(line)
                if any("run.complete" in ln for ln in lines):
                    break
            joined = "\n".join(lines)
            assert "run.complete" in joined or "trace" in joined
