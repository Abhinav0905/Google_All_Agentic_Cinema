"""CueCheck FastAPI application.

Thin HTTP layer over the engine and ADK pipeline. Serves the React SPA from
web/dist when present.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agents.pipeline import execute_pipeline_with_context
from api.config import (
    DATA_DIR,
    SAMPLES_DIR,
    WEB_DIST,
    bootstrap_env,
    gcp_configured,
    gcs_bucket,
    gcs_configured,
    signed_url_ttl,
)
from api.db import database_backend, record_decision, reset_engine
from api.export_service import apply_and_export
from api.store import StoredRun, store
from engine.models import Run, TraceStep

bootstrap_env()

VIDEO_MAX_BYTES = 500 * 1024 * 1024
TEXT_MAX_BYTES = 2 * 1024 * 1024


class StartBody(BaseModel):
    profile_id: str = "adult"
    sdh_mode: bool = True
    has_ad: bool = False


class FixDecisionBody(BaseModel):
    decision: Literal["accept", "reject"]


class UploadSlot(BaseModel):
    url: Optional[str] = None
    gs_uri: Optional[str] = None
    content_type: str
    max_bytes: int


class CreateRunResponse(BaseModel):
    id: str
    gcs_configured: bool
    uploads: Dict[str, UploadSlot]
    ttl_seconds: int = Field(default=900)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    reset_engine()
    yield


app = FastAPI(title="CueCheck", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _new_run_id() -> str:
    return str(uuid.uuid4())


def _publish(stored: StoredRun, payload: Dict[str, Any]) -> None:
    stored.events.append(payload)
    for queue in list(stored.subscribers):
        try:
            queue.put_nowait(payload)
        except Exception:
            pass


def _trace_callback(stored: StoredRun):
    def on_trace(step: TraceStep, _run: Run) -> None:
        event_type = step.step_name if step.step_name.startswith("run.") else "trace"
        _publish(
            stored,
            {
                "type": event_type,
                "step": step.model_dump(),
                "status": stored.run.status,
            },
        )

    return on_trace


def _serialize_run(stored: StoredRun) -> Dict[str, Any]:
    run = stored.run
    return {
        "id": run.id,
        "created_at": run.created_at,
        "profile_id": run.profile_id,
        "sdh_mode": run.sdh_mode,
        "has_ad": run.has_ad,
        "media_uri": run.media_uri,
        "caption_uri": run.caption_uri,
        "ad_uri": run.ad_uri,
        "status": run.status,
        "steps": [s.model_dump() for s in run.steps],
        "findings": [f.model_dump() for f in run.findings],
        "fixes": [fx.model_dump() for fx in run.fixes],
        "scorecard": run.scorecard.model_dump() if run.scorecard else None,
        "after_scorecard": (
            stored.after_scorecard.model_dump() if stored.after_scorecard else None
        ),
        "exports": {
            "srt": f"/api/runs/{run.id}/export?format=srt",
            "vtt": f"/api/runs/{run.id}/export?format=vtt",
            "json": f"/api/runs/{run.id}/export?format=json",
            "report": f"/api/runs/{run.id}/export?format=report",
        },
        "media_url": f"/api/runs/{run.id}/media",
        "cues": [c.model_dump() for c in stored.cues],
        "local_video": stored.local_video,
        "caption_ready": stored.caption_ready,
        "gcs_configured": gcs_configured(),
    }


def _signed_put(blob_name: str, content_type: str) -> UploadSlot:
    from engine.gcs import generate_signed_upload_url

    bucket = gcs_bucket()
    url = generate_signed_upload_url(
        bucket, blob_name, content_type=content_type, ttl_seconds=signed_url_ttl()
    )
    return UploadSlot(
        url=url,
        gs_uri=f"gs://{bucket}/{blob_name}",
        content_type=content_type,
        max_bytes=VIDEO_MAX_BYTES if "video" in content_type else TEXT_MAX_BYTES,
    )


def _local_slot(content_type: str, max_bytes: int) -> UploadSlot:
    return UploadSlot(url=None, gs_uri=None, content_type=content_type, max_bytes=max_bytes)


async def _run_pipeline(run_id: str, live: bool) -> None:
    stored = store.get(run_id)
    try:
        pctx = await execute_pipeline_with_context(
            stored.run, live=live, trace_callback=_trace_callback(stored)
        )
        stored.cues = pctx.cues
        stored.ad_cues = pctx.ad_cues or []
        stored.segments = pctx.segments
        stored.audio_events = pctx.audio_events
        stored.visual_events = pctx.visual_events
        stored.run = pctx.run
        stored.caption_ready = True
        store.save(stored)
    except Exception as exc:
        stored.run.status = "failed"
        _publish(
            stored,
            {
                "type": "run.failed",
                "step": {
                    "step_name": "run.failed",
                    "status": "failed",
                    "summary": str(exc),
                    "error": str(exc),
                    "duration_s": 0,
                },
                "status": "failed",
            },
        )
        store.save(stored)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "vertex": gcp_configured(),
        "gcs": gcs_configured(),
        "stt": os.environ.get("ENABLE_STT", "false").lower() == "true",
        "sample_clip": (SAMPLES_DIR / "clip.mp4").exists(),
        "database": database_backend(),
        "history_persisted": True,
    }


@app.get("/api/runs")
def list_runs() -> List[Dict[str, Any]]:
    return [
        {
            "id": s.run.id,
            "created_at": s.run.created_at,
            "profile_id": s.run.profile_id,
            "status": s.run.status,
            "overall": s.run.scorecard.overall_status if s.run.scorecard else None,
            "finding_count": len(s.run.findings),
        }
        for s in store.list()
    ]


@app.post("/api/runs", status_code=201)
def create_run() -> CreateRunResponse:
    run_id = _new_run_id()
    run = Run(id=run_id, profile_id="adult", status="pending")
    stored = store.put(StoredRun(run=run))

    if gcs_configured():
        prefix = f"runs/{run_id}"
        uploads = {
            "video": _signed_put(f"{prefix}/source.mp4", "video/mp4"),
            "captions": _signed_put(f"{prefix}/captions.srt", "text/plain"),
            "ad": _signed_put(f"{prefix}/ad.srt", "text/plain"),
        }
        stored.run.media_uri = uploads["video"].gs_uri
        stored.run.caption_uri = uploads["captions"].gs_uri
        stored.run.ad_uri = uploads["ad"].gs_uri
    else:
        uploads = {
            "video": _local_slot("video/mp4", VIDEO_MAX_BYTES),
            "captions": _local_slot("text/plain", TEXT_MAX_BYTES),
            "ad": _local_slot("text/plain", TEXT_MAX_BYTES),
        }
        stored.local_video = True

    store.save(stored)
    return CreateRunResponse(
        id=run_id,
        gcs_configured=gcs_configured(),
        uploads=uploads,
        ttl_seconds=signed_url_ttl(),
    )


@app.post("/api/runs/{run_id}/assets")
async def upload_text_assets(
    run_id: str,
    captions: Optional[UploadFile] = File(default=None),
    ad: Optional[UploadFile] = File(default=None),
) -> Dict[str, Any]:
    """Accept caption/AD text locally when GCS is not configured. Video never lands here."""
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    dest = DATA_DIR / run_id
    dest.mkdir(parents=True, exist_ok=True)

    if captions is not None:
        raw = await captions.read()
        if len(raw) > TEXT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Caption file exceeds 2 MB")
        path = dest / "captions.srt"
        path.write_bytes(raw)
        stored.run.caption_uri = str(path)
        stored.caption_ready = True

    if ad is not None:
        raw = await ad.read()
        if len(raw) > TEXT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="AD file exceeds 2 MB")
        path = dest / "ad.srt"
        path.write_bytes(raw)
        stored.run.ad_uri = str(path)
        stored.run.has_ad = True

    store.save(stored)
    return {"id": run_id, "caption_uri": stored.run.caption_uri, "ad_uri": stored.run.ad_uri}


@app.post("/api/runs/{run_id}/start")
def start_run(run_id: str, body: StartBody, background: BackgroundTasks) -> Dict[str, Any]:
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if stored.run.status == "running":
        raise HTTPException(status_code=409, detail="Run already started")

    stored.run.profile_id = body.profile_id
    stored.run.sdh_mode = body.sdh_mode
    stored.run.has_ad = body.has_ad
    stored.run.status = "running"

    if not stored.run.caption_uri:
        raise HTTPException(status_code=400, detail="Captions have not been uploaded")

    live = gcs_configured() and bool(stored.run.media_uri and stored.run.media_uri.startswith("gs://"))
    store.save(stored)
    background.add_task(_run_pipeline, run_id, live)
    return _serialize_run(stored)


@app.post("/api/runs/sample")
def start_sample(background: BackgroundTasks, body: Optional[StartBody] = None) -> Dict[str, Any]:
    cfg = body or StartBody(profile_id="adult", sdh_mode=True, has_ad=True)
    run_id = _new_run_id()
    run = Run(
        id=run_id,
        profile_id=cfg.profile_id,
        sdh_mode=cfg.sdh_mode,
        has_ad=cfg.has_ad,
        media_uri="gs://cuecheck-media/sample_clip.mp4",
        caption_uri=str(SAMPLES_DIR / "captions_bad.srt"),
        ad_uri=str(SAMPLES_DIR / "ad_script.srt") if cfg.has_ad else None,
        status="running",
    )
    stored = store.put(StoredRun(run=run, local_video=True, caption_ready=True))
    background.add_task(_run_pipeline, run_id, False)
    return _serialize_run(stored)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return _serialize_run(stored)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    queue: asyncio.Queue = asyncio.Queue()
    stored.subscribers.append(queue)

    async def gen():
        try:
            for past in stored.events:
                yield {"event": past.get("type", "trace"), "data": _json(past)}
                if past.get("type") in ("run.complete", "run.failed"):
                    return
            while True:
                item = await queue.get()
                yield {"event": item.get("type", "trace"), "data": _json(item)}
                if item.get("type") in ("run.complete", "run.failed"):
                    return
        finally:
            if queue in stored.subscribers:
                stored.subscribers.remove(queue)

    return EventSourceResponse(gen())


@app.post("/api/runs/{run_id}/fixes/{fix_id}")
def decide_fix(run_id: str, fix_id: str, body: FixDecisionBody) -> Dict[str, Any]:
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    target = next((fx for fx in stored.run.fixes if fx.id == fix_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Fix not found")

    target.status = "accepted" if body.decision == "accept" else "rejected"
    record_decision(run_id, fix_id, body.decision)
    store.save(stored)
    return _serialize_run(stored)


@app.get("/api/runs/{run_id}/export")
def export_run(
    run_id: str,
    format: Literal["vtt", "srt", "json", "report"] = Query(default="srt"),
):
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    if stored.run.status != "completed":
        raise HTTPException(status_code=409, detail="Run is not complete")

    media_type, body = apply_and_export(stored, format)
    filename = f"cuecheck-{run_id}.{format if format != 'report' else 'html'}"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/runs/{run_id}/media")
def run_media(run_id: str):
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    clip = SAMPLES_DIR / "clip.mp4"
    if stored.local_video and clip.exists():
        return FileResponse(clip, media_type="video/mp4")

    if stored.run.media_uri and stored.run.media_uri.startswith("gs://") and gcs_configured():
        from engine.gcs import generate_signed_download_url, parse_gs_uri

        bucket, blob = parse_gs_uri(stored.run.media_uri)
        url = generate_signed_download_url(bucket, blob, ttl_seconds=signed_url_ttl())
        return {"url": url}

    return Response(status_code=204)


@app.get("/api/samples/clip")
def sample_clip():
    clip = SAMPLES_DIR / "clip.mp4"
    if not clip.exists():
        raise HTTPException(status_code=404, detail="Sample clip not yet available")
    return FileResponse(clip, media_type="video/mp4")


def _json(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload)


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = WEB_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<p>CueCheck API is running. Build web/ to serve the UI.</p>")


@app.get("/")
def root():
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<p>CueCheck API is running. Start the Vite app in <code>web/</code> "
        "or run <code>npm run build</code>.</p>"
    )
