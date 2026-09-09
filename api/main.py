"""CueCheck FastAPI application.

Thin HTTP layer over the engine and ADK pipeline. Serves the React SPA from
web/dist when present.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agents.multimodal import INLINE_VIDEO_MAX_BYTES
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
from api.db import (
    database_backend,
    dispose_engine,
    load_asset,
    record_decision,
    reset_engine,
    save_asset,
)
from api.export_service import apply_and_export
from api.security import (
    COOKIE_NAME,
    RequestBodyLimit,
    browser_identity,
    limit_request,
    reset_limits,
    verify_origin,
)
from api.store import StoredRun, store
from engine.models import Run, TraceStep

bootstrap_env()

VIDEO_MAX_BYTES = 500 * 1024 * 1024
TEXT_MAX_BYTES = 2 * 1024 * 1024
_start_guard = threading.Lock()
log = logging.getLogger(__name__)


class StartBody(BaseModel):
    profile_id: Literal["adult", "kids"] = "adult"
    sdh_mode: bool = True
    has_ad: bool = False


class CreateBody(BaseModel):
    captions_size_bytes: Optional[int] = Field(default=None, gt=0, le=TEXT_MAX_BYTES)
    ad_size_bytes: Optional[int] = Field(default=None, gt=0, le=TEXT_MAX_BYTES)
    video_size_bytes: Optional[int] = Field(default=None, gt=0, le=VIDEO_MAX_BYTES)


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
    inline_video_max_bytes: int = INLINE_VIDEO_MAX_BYTES


@asynccontextmanager
async def lifespan(_app: FastAPI):
    reset_engine()
    reset_limits()
    store.drop_cache()
    # A single serving process owns background jobs. Mark interrupted work after
    # a restart instead of leaving an unfinishable "running" entry in History.
    for stored in store.list():
        if stored.run.status == "running":
            stored.run.status = "failed"
            stored.events.append({"type": "run.failed", "status": "failed"})
            store.save(stored)
    try:
        yield
    finally:
        dispose_engine()


app = FastAPI(title="FrameKind", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    RequestBodyLimit, upload_max_bytes=INLINE_VIDEO_MAX_BYTES + 2 * TEXT_MAX_BYTES + 65536
)


@app.middleware("http")
async def session_boundary(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    token, owner_id, fresh = browser_identity(request)
    request.state.owner_id = owner_id
    try:
        verify_origin(request)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    if request.url.path.endswith("/assets"):
        try:
            limit_request(f"upload-owner:{owner_id}", 30)
            peer = request.client.host if request.client else "unknown"
            limit_request(f"upload-peer:{peer}", 120)
        except HTTPException as exc:
            return JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid request size"}, status_code=400)
        if size > INLINE_VIDEO_MAX_BYTES + 2 * TEXT_MAX_BYTES + 65536:
            return JSONResponse({"detail": "Upload is too large"}, status_code=413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if fresh:
        secure = (
            request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        )
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=30 * 24 * 3600,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
    return response


def _owned_run(run_id: str, request: Request) -> StoredRun:
    try:
        stored = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    if not stored.owner_id or stored.owner_id != request.state.owner_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return stored


def _limit_creation(request: Request) -> None:
    limit_request(f"create-owner:{request.state.owner_id}", 30)
    # The socket peer is used, not an untrusted forwarded header. On a proxy this
    # becomes a conservative shared cap for the public demo.
    peer = request.client.host if request.client else "unknown"
    limit_request(f"create-peer:{peer}", 120)


def _safe_step(step: TraceStep) -> Dict[str, Any]:
    result = step.model_dump()
    if step.status == "failed":
        result["summary"] = (
            "Analysis failed at this step. Verify the input and cloud configuration."
        )
        result["error"] = result["summary"]
    return result


def _local_asset_path(stored: StoredRun, kind: str, uri: Optional[str]) -> Optional[Path]:
    if not uri or uri.startswith("gs://"):
        return None
    path = Path(uri).resolve()
    if path.is_relative_to(DATA_DIR.resolve()) and path.is_file():
        return path
    # Replit deployment files are ephemeral. Inline videos have a durable copy
    # in the database; cache it locally again to support HTTP range playback.
    try:
        uuid.UUID(stored.run.id)
    except ValueError:
        return None
    content = load_asset(stored.run.id, kind)
    if content:
        name = {"video": "source.mp4", "captions": "captions.srt", "ad": "ad.srt"}[kind]
        path = DATA_DIR / stored.run.id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path
    return None


def _local_media_path(stored: StoredRun) -> Optional[Path]:
    path = _local_asset_path(stored, "video", stored.run.media_uri)
    if path:
        stored.run.media_uri = str(path)
    return path


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
        if step.step_name in {"run.complete", "run.failed"}:
            return  # Emit only after the final result has been persisted.
        stored.run.steps = [item.model_copy(deep=True) for item in _run.steps]
        event_type = step.step_name if step.step_name.startswith("run.") else "trace"
        _publish(
            stored,
            {
                "type": event_type,
                "step": _safe_step(step),
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
        "analysis_mode": run.analysis_mode,
        "status": run.status,
        "steps": [_safe_step(s) for s in run.steps],
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
        "media_url": (
            f"/api/runs/{run.id}/media"
            if (run.analysis_mode == "live" and run.media_uri)
            or _local_media_path(stored)
            or (run.analysis_mode == "sample" and (SAMPLES_DIR / "clip.mp4").exists())
            else None
        ),
        "cues": [c.model_dump() for c in stored.cues],
        "local_video": stored.local_video,
        "caption_ready": stored.caption_ready,
        "gcs_configured": gcs_configured(),
    }


def _signed_put(blob_name: str, content_type: str, size_bytes: int) -> UploadSlot:
    from engine.gcs import get_gcs_client

    bucket = gcs_bucket()
    blob = get_gcs_client().bucket(bucket).blob(blob_name)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=signed_url_ttl()),
        method="PUT",
        content_type=content_type,
        headers={"Content-Length": str(size_bytes)},
    )
    return UploadSlot(
        url=url,
        gs_uri=f"gs://{bucket}/{blob_name}",
        content_type=content_type,
        max_bytes=VIDEO_MAX_BYTES if "video" in content_type else TEXT_MAX_BYTES,
    )


def _local_slot(content_type: str, max_bytes: int) -> UploadSlot:
    return UploadSlot(url=None, gs_uri=None, content_type=content_type, max_bytes=max_bytes)


async def _run_pipeline(run_id: str, analysis_mode: str) -> None:
    stored = store.get(run_id)
    try:
        pctx = await execute_pipeline_with_context(
            stored.run.model_copy(deep=True),
            analysis_mode=analysis_mode,
            trace_callback=_trace_callback(stored),
        )
        stored = store.apply_pipeline_result(stored, pctx)
        _publish(stored, {"type": "run.complete", "status": stored.run.status})
    except Exception as exc:
        log.error("Run %s failed (%s)", run_id, type(exc).__name__)
        stored.run.status = "failed"
        try:
            store.save(stored)
        except Exception as save_error:
            # Keep the owning browser informed even during a storage outage.
            # A second database error must not swallow the terminal SSE event.
            log.error("Run %s failure state was not saved (%s)", run_id, type(save_error).__name__)
        _publish(
            stored,
            {
                "type": "run.failed",
                "step": {
                    "step_name": "run.failed",
                    "status": "failed",
                    "summary": "Analysis failed. Verify the input and cloud configuration.",
                    "error": "Analysis failed. Verify the input and cloud configuration.",
                    "duration_s": 0,
                },
                "status": "failed",
            },
        )


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "vertex": gcp_configured(),
        "vertex_mode": (
            "express"
            if os.environ.get("VERTEX_API_KEY", "").strip()
            else "adc"
            if gcp_configured()
            else "offline"
        ),
        "inline_video_max_bytes": INLINE_VIDEO_MAX_BYTES,
        "gcs": gcs_configured(),
        "stt": os.environ.get("ENABLE_STT", "false").lower() == "true",
        "sample_clip": (SAMPLES_DIR / "clip.mp4").exists(),
        "database": database_backend(),
        "history_persisted": True,
    }


@app.get("/api/runs")
def list_runs(request: Request) -> List[Dict[str, Any]]:
    return [
        {
            "id": s.run.id,
            "created_at": s.run.created_at,
            "profile_id": s.run.profile_id,
            "status": s.run.status,
            "analysis_mode": s.run.analysis_mode,
            "overall": s.run.scorecard.overall_status if s.run.scorecard else None,
            "finding_count": len(s.run.findings),
        }
        for s in store.list()
        if s.owner_id == request.state.owner_id
    ]


@app.post("/api/runs", status_code=201)
def create_run(request: Request, body: Optional[CreateBody] = None) -> CreateRunResponse:
    _limit_creation(request)
    sizes = body or CreateBody()
    if not gcs_configured() and (sizes.video_size_bytes or 0) > INLINE_VIDEO_MAX_BYTES:
        raise HTTPException(
            status_code=413, detail="Direct video uploads must be 14 MiB or smaller"
        )
    if gcs_configured() and not sizes.captions_size_bytes:
        raise HTTPException(
            status_code=422, detail="Caption file size is required for cloud uploads"
        )
    run_id = _new_run_id()
    run = Run(id=run_id, profile_id="adult", status="pending")
    stored = StoredRun(run=run, owner_id=request.state.owner_id)

    if gcs_configured():
        prefix = f"runs/{run_id}"
        uploads = {}
        for name, filename, content_type, size in (
            ("video", "source.mp4", "video/mp4", sizes.video_size_bytes),
            ("captions", "captions.srt", "text/plain", sizes.captions_size_bytes),
            ("ad", "ad.srt", "text/plain", sizes.ad_size_bytes),
        ):
            if size:
                try:
                    uploads[name] = _signed_put(f"{prefix}/{filename}", content_type, size)
                except Exception as exc:
                    log.error("Cloud upload signing failed (%s)", type(exc).__name__)
                    raise HTTPException(
                        status_code=503, detail="Cloud uploads are unavailable. Try the sample."
                    ) from exc
                stored.upload_sizes[name] = size
            else:
                uploads[name] = _local_slot(
                    content_type, VIDEO_MAX_BYTES if name == "video" else TEXT_MAX_BYTES
                )
        stored.run.media_uri = uploads["video"].gs_uri
        stored.run.caption_uri = uploads["captions"].gs_uri
        stored.run.ad_uri = uploads["ad"].gs_uri
    else:
        uploads = {
            "video": _local_slot("video/mp4", INLINE_VIDEO_MAX_BYTES),
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
    request: Request,
    captions: Optional[UploadFile] = File(default=None),
    ad: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
) -> Dict[str, Any]:
    """Store session-owned text and a small inline video for Vertex Express."""
    stored = _owned_run(run_id, request)
    if stored.run.status != "pending":
        raise HTTPException(status_code=409, detail="Create a new run to upload different files")

    pending_files: Dict[str, bytes] = {}
    if video is not None:
        if not (video.filename or "").lower().endswith(".mp4"):
            raise HTTPException(status_code=415, detail="Use an MP4 video")
        raw_video = await video.read(INLINE_VIDEO_MAX_BYTES + 1)
        if not raw_video or len(raw_video) > INLINE_VIDEO_MAX_BYTES:
            raise HTTPException(
                status_code=413, detail="Direct video uploads must be 14 MiB or smaller"
            )
        pending_files["video"] = raw_video

    if captions is not None:
        raw = await captions.read(TEXT_MAX_BYTES + 1)
        if len(raw) > TEXT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Caption file exceeds 2 MB")
        if not raw.strip():
            raise HTTPException(status_code=400, detail="Caption file is empty")
        pending_files["captions"] = raw

    if ad is not None:
        raw = await ad.read(TEXT_MAX_BYTES + 1)
        if len(raw) > TEXT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="AD file exceeds 2 MB")
        if not raw.strip():
            raise HTTPException(status_code=400, detail="Audio description file is empty")
        pending_files["ad"] = raw

    await asyncio.to_thread(_save_uploads, stored, pending_files)
    return {"id": run_id, "caption_ready": stored.caption_ready}


def _save_uploads(stored: StoredRun, files: Dict[str, bytes]) -> None:
    """An upload and start cannot interleave or replace an in-flight input."""
    with store.lock_for(stored.run.id):
        if stored.run.status != "pending":
            raise HTTPException(status_code=409, detail="Create a new run for different files")
        dest = DATA_DIR / stored.run.id
        dest.mkdir(parents=True, exist_ok=True)
        names = {"video": "source.mp4", "captions": "captions.srt", "ad": "ad.srt"}
        for kind, raw in files.items():
            path = dest / names[kind]
            path.write_bytes(raw)
            save_asset(stored.run.id, kind, raw)
            if kind == "video":
                stored.run.media_uri = str(path)
                stored.local_video = True
            elif kind == "captions":
                stored.run.caption_uri = str(path)
                stored.caption_ready = True
            else:
                stored.run.ad_uri = str(path)
                stored.run.has_ad = True
            stored.upload_sizes[kind] = len(raw)
        store.save(stored)


def _validate_cloud_asset(uri: Optional[str], maximum: int, expected: int = 0) -> bool:
    if not uri or not uri.startswith("gs://"):
        return False
    from engine.gcs import get_gcs_client, parse_gs_uri

    bucket, name = parse_gs_uri(uri)
    if bucket != gcs_bucket():
        raise HTTPException(status_code=400, detail="Invalid upload location")
    try:
        blob = get_gcs_client().bucket(bucket).get_blob(name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not verify uploaded files") from exc
    if blob is None:
        return False
    size = int(blob.size or 0)
    if size <= 0 or size > maximum:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the supported size")
    if expected and size != expected:
        raise HTTPException(
            status_code=400, detail="Uploaded file size does not match the selected file"
        )
    return True


@app.post("/api/runs/{run_id}/start")
def start_run(
    run_id: str, body: StartBody, background: BackgroundTasks, request: Request
) -> Dict[str, Any]:
    stored = _owned_run(run_id, request)
    with _start_guard, store.lock_for(run_id):
        if stored.run.status != "pending":
            raise HTTPException(status_code=409, detail="Create a new run to analyze again")
        if not stored.run.caption_uri:
            raise HTTPException(status_code=400, detail="Captions have not been uploaded")
        cloud = stored.run.caption_uri.startswith("gs://")
        if not cloud:
            captions = _local_asset_path(stored, "captions", stored.run.caption_uri)
            if captions is None:
                raise HTTPException(status_code=400, detail="Upload the caption file again")
            stored.run.caption_uri = str(captions)
        if cloud and not _validate_cloud_asset(
            stored.run.caption_uri, TEXT_MAX_BYTES, stored.upload_sizes.get("captions", 0)
        ):
            raise HTTPException(status_code=400, detail="Finish uploading captions before starting")
        if body.has_ad:
            ad_ready = bool(stored.run.ad_uri)
            if cloud:
                ad_ready = _validate_cloud_asset(
                    stored.run.ad_uri, TEXT_MAX_BYTES, stored.upload_sizes.get("ad", 0)
                )
            else:
                ad_path = _local_asset_path(stored, "ad", stored.run.ad_uri)
                ad_ready = bool(ad_path)
                if ad_path:
                    stored.run.ad_uri = str(ad_path)
            if not ad_ready:
                raise HTTPException(status_code=400, detail="The audio description file is missing")
        has_video = cloud and _validate_cloud_asset(
            stored.run.media_uri, VIDEO_MAX_BYTES, stored.upload_sizes.get("video", 0)
        )
        if not cloud:
            local_media = _local_media_path(stored)
            has_video = bool(local_media and local_media.stat().st_size <= INLINE_VIDEO_MAX_BYTES)
        if stored.upload_sizes.get("video") and not has_video:
            raise HTTPException(
                status_code=400, detail="Finish uploading the video before starting"
            )
        mode = "live" if has_video and gcp_configured() else "caption_only"
        if mode == "live":
            active = sum(
                s.run.status == "running" and s.run.analysis_mode == "live" for s in store.list()
            )
            if active >= int(os.getenv("MAX_CONCURRENT_LIVE_RUNS", "2")):
                raise HTTPException(
                    status_code=429, detail="The analysis queue is busy. Try again shortly"
                )
            limit_request(
                f"live-owner:{stored.owner_id}", int(os.getenv("LIVE_RUNS_PER_HOUR", "6"))
            )
            limit_request("live-global", int(os.getenv("GLOBAL_LIVE_RUNS_PER_HOUR", "24")))
        stored.run.profile_id = body.profile_id
        stored.run.sdh_mode = body.sdh_mode
        stored.run.has_ad = body.has_ad
        stored.run.analysis_mode = mode
        stored.run.status = "running"
        stored.caption_ready = True
        store.save(stored)
    background.add_task(_run_pipeline, run_id, mode)
    return _serialize_run(stored)


@app.post("/api/runs/sample")
def start_sample(
    background: BackgroundTasks, request: Request, body: Optional[StartBody] = None
) -> Dict[str, Any]:
    _limit_creation(request)
    cfg = body or StartBody(profile_id="adult", sdh_mode=True, has_ad=True)
    run_id = _new_run_id()
    run = Run(
        id=run_id,
        profile_id=cfg.profile_id,
        sdh_mode=cfg.sdh_mode,
        has_ad=cfg.has_ad,
        media_uri=None,
        analysis_mode="sample",
        caption_uri=str(SAMPLES_DIR / "captions_bad.srt"),
        ad_uri=str(SAMPLES_DIR / "ad_script.srt") if cfg.has_ad else None,
        status="running",
    )
    stored = store.put(
        StoredRun(run=run, owner_id=request.state.owner_id, local_video=True, caption_ready=True)
    )
    background.add_task(_run_pipeline, run_id, "sample")
    return _serialize_run(stored)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request) -> Dict[str, Any]:
    stored = _owned_run(run_id, request)
    return _serialize_run(stored)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    stored = _owned_run(run_id, request)
    if stored.run.status == "pending":
        raise HTTPException(status_code=409, detail="Start the analysis before subscribing")
    if len(stored.subscribers) >= 8:
        raise HTTPException(status_code=429, detail="Too many open views for this run")

    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    stored.subscribers.append(queue)

    async def gen():
        try:
            for past in stored.events:
                yield {"event": past.get("type", "trace"), "data": _json(past)}
                if past.get("type") in ("run.complete", "run.failed"):
                    return
            if stored.run.status in {"completed", "failed"}:
                event = "run.complete" if stored.run.status == "completed" else "run.failed"
                yield {"event": event, "data": _json({"status": stored.run.status})}
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
def decide_fix(run_id: str, fix_id: str, body: FixDecisionBody, request: Request) -> Dict[str, Any]:
    _owned_run(run_id, request)
    with store.lock_for(run_id):
        stored = _owned_run(run_id, request)
        if stored.run.status != "completed":
            raise HTTPException(
                status_code=409, detail="Wait for analysis to finish before reviewing fixes"
            )

        target = next((fx for fx in stored.run.fixes if fx.id == fix_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Fix not found")

        previous = target.status
        previous_score = stored.after_scorecard
        target.status = "accepted" if body.decision == "accept" else "rejected"
        try:
            apply_and_export(stored, "json")
        except ValueError as exc:
            target.status = previous
            stored.after_scorecard = previous_score
            raise HTTPException(
                status_code=409,
                detail="These fixes conflict. Reject another fix for this cue, then try again.",
            ) from exc
        record_decision(run_id, fix_id, body.decision)
        store.save(stored)
        return _serialize_run(stored)


@app.get("/api/runs/{run_id}/export")
def export_run(
    run_id: str,
    request: Request,
    format: Literal["vtt", "srt", "json", "report"] = Query(default="srt"),
):
    stored = _owned_run(run_id, request)
    if stored.run.status != "completed":
        raise HTTPException(status_code=409, detail="Run is not complete")

    with store.lock_for(run_id):
        try:
            media_type, body = apply_and_export(stored, format)
        except ValueError as exc:
            raise HTTPException(
                status_code=409, detail="Review conflicting fixes before exporting"
            ) from exc
        store.save(stored)
    filename = f"framekind-{run_id}.{format if format != 'report' else 'html'}"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/runs/{run_id}/media")
def run_media(run_id: str, request: Request):
    stored = _owned_run(run_id, request)

    local_media = _local_media_path(stored)
    if local_media:
        return FileResponse(local_media, media_type="video/mp4")
    clip = SAMPLES_DIR / "clip.mp4"
    if stored.run.analysis_mode == "sample" and clip.exists():
        return FileResponse(clip, media_type="video/mp4")

    if stored.run.media_uri and stored.run.media_uri.startswith("gs://") and gcs_configured():
        from engine.gcs import generate_signed_download_url, parse_gs_uri

        bucket, blob = parse_gs_uri(stored.run.media_uri)
        try:
            url = generate_signed_download_url(bucket, blob, ttl_seconds=signed_url_ttl())
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Video playback is temporarily unavailable"
            ) from exc
        return RedirectResponse(url, status_code=307)

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
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        root_path = WEB_DIST.resolve()
        candidate = (root_path / full_path).resolve()
        if not candidate.is_relative_to(root_path):
            raise HTTPException(status_code=404, detail="File not found")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = WEB_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<p>FrameKind API is running. Build web/ to serve the UI.</p>")


@app.get("/")
def root():
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<p>FrameKind API is running. Start the Vite app in <code>web/</code> "
        "or run <code>npm run build</code>.</p>"
    )
