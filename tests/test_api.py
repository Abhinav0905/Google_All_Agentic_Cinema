"""API tests for run lifecycle, sample QC, fix decisions, and export."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from api import main as api_main
from api.main import app
from api.security import COOKIE_NAME
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
        assert body["database"] in ("sqlite", "postgres")
        assert body["history_persisted"] is True


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

        store.drop_cache()
        listed_again = client.get("/api/runs")
        assert any(row["id"] == body["id"] for row in listed_again.json())


def test_sample_run_accept_and_export():
    store.clear()
    with TestClient(app) as client:
        started = client.post("/api/runs/sample")
        assert started.status_code == 200
        run_id = started.json()["id"]
        finished = _wait_complete(client, run_id)
        assert finished["status"] == "completed"
        store.drop_cache()
        finished = client.get(f"/api/runs/{run_id}").json()
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
        assert "FrameKind" in report.text


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


def test_anonymous_session_owns_history_and_all_run_routes():
    with TestClient(app) as owner:
        run_id = owner.post("/api/runs/sample").json()["id"]
        finished = _wait_complete(owner, run_id)
        assert COOKIE_NAME in owner.cookies
        store.drop_cache()
        assert owner.get(f"/api/runs/{run_id}").status_code == 200
        outsider = TestClient(app)
        try:
            assert outsider.get("/api/runs").json() == []
            for suffix in ("", "/events", "/media", "/export?format=srt"):
                assert outsider.get(f"/api/runs/{run_id}{suffix}").status_code == 404
            for suffix in ("/start", "/assets", f"/fixes/{finished['fixes'][0]['id']}"):
                response = outsider.post(f"/api/runs/{run_id}{suffix}", json={"decision": "accept"})
                assert response.status_code == 404
        finally:
            outsider.close()


def test_cookie_and_cross_origin_mutations():
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/api/health")
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
        assert response.headers["cache-control"] == "no-store"
        forbidden = client.post("/api/runs", headers={"Origin": "https://unrelated.example"})
        assert forbidden.status_code == 403


def test_spa_rejects_encoded_traversal_and_absolute_paths(tmp_path, monkeypatch):
    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text("FrameKind")
    outside = tmp_path / "outside.txt"
    outside.write_text("PRIVATE_SENTINEL")
    monkeypatch.setattr(api_main, "WEB_DIST", root)
    with TestClient(app) as client:
        for path in ("/%2e%2e/outside.txt", "/" + quote(str(outside), safe="")):
            response = client.get(path)
            assert response.status_code == 404
            assert "PRIVATE_SENTINEL" not in response.text
        assert client.get("/api/does-not-exist").status_code == 404
        assert client.get("/workspace").text == "FrameKind"


def test_custom_local_captions_do_not_receive_sample_semantics(monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        raw = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nA completely different sentence.\n"
        uploaded = client.post(
            f"/api/runs/{run_id}/assets", files={"captions": ("test.vtt", raw, "text/vtt")}
        )
        assert uploaded.status_code == 200
        started = client.post(f"/api/runs/{run_id}/start", json={})
        assert started.status_code == 200
        finished = _wait_complete(client, run_id)
        assert finished["analysis_mode"] == "caption_only"
        assert finished["status"] == "completed"
        assert finished["media_url"] is None
        assert finished["scorecard"]["accuracy"] is None
        assert finished["scorecard"]["completeness"] is None
        assert not any(
            f["code"].startswith(("SDH_", "AD_", "MISSING_")) for f in finished["findings"]
        )
        exported = client.get(f"/api/runs/{run_id}/export?format=json").json()
        assert exported["after_scorecard"]["accuracy"] is None
        assert "A completely different sentence." in exported["cues"][0]["lines"]


def test_missing_upload_does_not_leave_run_running():
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        assert client.post(f"/api/runs/{run_id}/start", json={}).status_code == 400
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "pending"


def test_cloud_video_reopens_via_redirect(monkeypatch):
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        stored = store.get(run_id)
        stored.run.media_uri = "gs://test-bucket/clip.mp4"
        stored.run.analysis_mode = "live"
        store.save(stored)
        monkeypatch.setattr(api_main, "gcs_configured", lambda: True)
        monkeypatch.setattr(
            "engine.gcs.generate_signed_download_url",
            lambda *a, **kw: "https://storage.example/clip.mp4?signed=test",
        )
        response = client.get(f"/api/runs/{run_id}/media", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"].startswith("https://storage.example/")


def test_signed_upload_is_bound_to_declared_file_size(monkeypatch):
    calls = []

    class Blob:
        def generate_signed_url(self, **kwargs):
            calls.append(kwargs)
            return "https://storage.example/upload"

    bucket = SimpleNamespace(blob=lambda name: Blob())
    monkeypatch.setattr(
        "engine.gcs.get_gcs_client", lambda: SimpleNamespace(bucket=lambda name: bucket)
    )
    slot = api_main._signed_put("file.mp4", "video/mp4", 1234)
    assert slot.url
    assert calls[0]["headers"]["Content-Length"] == "1234"


def test_cloud_asset_size_is_checked_before_analysis(monkeypatch):
    monkeypatch.setattr(api_main, "gcs_bucket", lambda: "test-bucket")
    blob = SimpleNamespace(size=3000)
    bucket = SimpleNamespace(get_blob=lambda name: blob)
    monkeypatch.setattr(
        "engine.gcs.get_gcs_client", lambda: SimpleNamespace(bucket=lambda name: bucket)
    )
    with pytest.raises(api_main.HTTPException) as error:
        api_main._validate_cloud_asset("gs://test-bucket/file", maximum=2000)
    assert error.value.status_code == 413


def test_rate_limit_is_enforced(monkeypatch):
    from api.security import limit_request

    limit_request("test-burst", 1)
    with pytest.raises(api_main.HTTPException) as error:
        limit_request("test-burst", 1)
    assert error.value.status_code == 429


def test_inline_video_is_private_and_restored_from_database(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    monkeypatch.setattr(api_main, "gcp_configured", lambda: False)
    monkeypatch.setattr(api_main, "DATA_DIR", tmp_path)
    video = b"small-test-video-bytes"
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        response = client.post(
            f"/api/runs/{run_id}/assets",
            files={
                "video": ("clip.mp4", video, "video/mp4"),
                "captions": ("clip.srt", "1\n00:00:00,000 --> 00:00:02,000\nHello.\n"),
            },
        )
        assert response.status_code == 200
        started = client.post(f"/api/runs/{run_id}/start", json={}).json()
        assert started["analysis_mode"] == "caption_only"
        local_path = tmp_path / run_id / "source.mp4"
        local_path.unlink()
        store.drop_cache()
        media = client.get(f"/api/runs/{run_id}/media")
        assert media.status_code == 200
        assert media.content == video
        assert local_path.exists()
        with client.stream(
            "GET", f"/api/runs/{run_id}/media", headers={"Range": "bytes=0-4"}
        ) as partial:
            assert partial.status_code == 206
            assert partial.read() == video[:5]


def test_inline_video_with_credentials_selects_live_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    monkeypatch.setattr(api_main, "gcp_configured", lambda: True)
    monkeypatch.setattr(api_main, "DATA_DIR", tmp_path)
    observed = []

    async def fake_execute(run, **kwargs):
        observed.append((run.media_uri, kwargs["analysis_mode"]))
        run.status = "completed"
        assert store.get(run.id).run.status == "running"
        return SimpleNamespace(
            run=run, cues=[], ad_cues=[], segments=[], audio_events=[], visual_events=[]
        )

    monkeypatch.setattr(api_main, "execute_pipeline_with_context", fake_execute)
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        client.post(
            f"/api/runs/{run_id}/assets",
            files={
                "video": ("clip.mp4", b"video", "video/mp4"),
                "captions": ("clip.srt", "1\n00:00:00,000 --> 00:00:02,000\nHello.\n"),
            },
        )
        response = client.post(f"/api/runs/{run_id}/start", json={})
        assert response.status_code == 200
        assert response.json()["analysis_mode"] == "live"
        assert observed == [(str(tmp_path / run_id / "source.mp4"), "live")]


def test_inline_video_size_and_extension_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    monkeypatch.setattr(api_main, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        too_large = client.post(
            "/api/runs", json={"video_size_bytes": api_main.INLINE_VIDEO_MAX_BYTES + 1}
        )
        assert too_large.status_code == 413
        run_id = client.post("/api/runs").json()["id"]
        response = client.post(
            f"/api/runs/{run_id}/assets", files={"video": ("file.mov", b"video", "video/quicktime")}
        )
        assert response.status_code == 415


def test_express_api_key_reports_configured_without_project(monkeypatch):
    from api.config import gcp_configured

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("VERTEX_API_KEY", "test-placeholder-not-a-real-key")
    assert gcp_configured() is True


def test_chunked_request_is_capped_before_json_parsing():
    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            content=iter([b"x" * 40000, b"y" * 40000]),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413


def test_invalid_upload_does_not_partially_save_video(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    monkeypatch.setattr(api_main, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        response = client.post(
            f"/api/runs/{run_id}/assets",
            files={"video": ("clip.mp4", b"video"), "captions": ("clip.srt", b"")},
        )
        assert response.status_code == 400
        assert not (tmp_path / run_id / "source.mp4").exists()
        assert store.get(run_id).run.media_uri is None


def test_upload_cannot_replace_input_after_analysis_started(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "gcs_configured", lambda: False)
    monkeypatch.setattr(api_main, "DATA_DIR", tmp_path)
    ready, resume = Event(), Event()
    save_uploads = api_main._save_uploads
    with TestClient(app) as client:
        run_id = client.post("/api/runs").json()["id"]
        original = "1\n00:00:00,000 --> 00:00:02,000\nOriginal.\n"
        client.post(f"/api/runs/{run_id}/assets", files={"captions": ("a.srt", original)})

        def paused_save(stored, files):
            ready.set()
            assert resume.wait(5)
            return save_uploads(stored, files)

        monkeypatch.setattr(api_main, "_save_uploads", paused_save)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                client.post,
                f"/api/runs/{run_id}/assets",
                files={"captions": ("b.srt", original.replace("Original", "Replacement"))},
            )
            assert ready.wait(5)
            try:
                started = client.post(f"/api/runs/{run_id}/start", json={})
                assert started.status_code == 200
            finally:
                resume.set()
            assert future.result(timeout=5).status_code == 409
        assert (tmp_path / run_id / "captions.srt").read_text() == original


def test_terminal_failure_is_emitted_once_after_persistence(monkeypatch):
    from api.db import load_payload
    from engine.models import TraceStep

    terminal = []
    publish = api_main._publish

    async def fail_execute(run, trace_callback, **kwargs):
        trace_callback(TraceStep(step_name="run.failed", status="failed"), run)
        raise ValueError("internal failure detail must remain private")

    def checked_publish(stored, payload):
        if payload.get("type") == "run.failed":
            assert load_payload(stored.run.id)["run"]["status"] == "failed"
            terminal.append(payload)
        publish(stored, payload)

    monkeypatch.setattr(api_main, "execute_pipeline_with_context", fail_execute)
    monkeypatch.setattr(api_main, "_publish", checked_publish)
    with TestClient(app) as client:
        run_id = client.post("/api/runs/sample").json()["id"]
        assert len(terminal) == 1
        response = client.get(f"/api/runs/{run_id}")
        assert response.json()["status"] == "failed"
        assert "internal failure detail" not in response.text


def test_failure_event_survives_database_failure(monkeypatch):
    import asyncio

    from api.store import StoredRun
    from engine.models import Run

    stored = store.put(StoredRun(run=Run(id="storage-failure", profile_id="adult")))

    async def failed_execute(*args, **kwargs):
        raise RuntimeError("pipeline failed")

    def failed_save(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(api_main, "execute_pipeline_with_context", failed_execute)
    monkeypatch.setattr(store, "save", failed_save)
    asyncio.run(api_main._run_pipeline(stored.run.id, "sample"))
    assert stored.run.status == "failed"
    assert [event["type"] for event in stored.events] == ["run.failed"]
