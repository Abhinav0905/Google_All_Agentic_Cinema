"""SQLAlchemy persistence for QC runs, findings, fixes, and decisions.

SQLite by default (local / tests). Replit Postgres when DATABASE_URL is set.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Integer, LargeBinary, String, Text, create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from api.config import ROOT_DIR
from engine.models import (
    AudioEvent,
    Cue,
    Run,
    Scorecard,
    Segment,
    VisualEvent,
)


class Base(DeclarativeBase):
    pass


class QcRun(Base):
    __tablename__ = "qc_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64))
    profile_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), index=True)
    sdh_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    has_ad: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[str] = mapped_column(Text)


class QcFinding(Base):
    __tablename__ = "qc_findings"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str] = mapped_column(Text)


class QcFix(Base):
    __tablename__ = "qc_fixes"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), index=True)
    payload: Mapped[str] = mapped_column(Text)


class QcDecision(Base):
    __tablename__ = "qc_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    fix_id: Mapped[str] = mapped_column(String(160), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(64))


class QcAsset(Base):
    """Small inline videos survive deployment restarts when Postgres is configured."""

    __tablename__ = "qc_assets"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    content: Mapped[bytes] = mapped_column(LargeBinary)


_engine: Optional[Engine] = None
_Session: Optional[sessionmaker[Session]] = None


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def default_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if raw:
        return normalize_database_url(raw)
    db_path = ROOT_DIR / ".data" / "cuecheck.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def database_backend(url: Optional[str] = None) -> str:
    resolved = url or default_database_url()
    if resolved.startswith("postgresql"):
        return "postgres"
    return "sqlite"


def _create_engine(url: str) -> Engine:
    if url in {"sqlite://", "sqlite:///:memory:"}:
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if url.startswith("sqlite:///"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


def reset_engine(url: Optional[str] = None) -> Engine:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    resolved = url or default_database_url()
    _engine = _create_engine(resolved)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    return _engine


def dispose_engine() -> None:
    """Release pooled connections. Safe to call when no engine exists."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def get_session() -> Session:
    global _Session
    if _Session is None:
        reset_engine()
    assert _Session is not None
    return _Session()


def dump_json(value: Any) -> str:
    return json.dumps(value, default=str)


def stored_payload(stored: Any) -> Dict[str, Any]:
    return {
        # Kept in the existing JSON payload: old databases need no destructive
        # migration. Legacy rows without an owner remain private and unclaimed.
        "owner_id": stored.owner_id,
        "upload_sizes": stored.upload_sizes,
        "run": stored.run.model_dump(),
        "cues": [c.model_dump() for c in stored.cues],
        "ad_cues": [c.model_dump() for c in stored.ad_cues],
        "segments": [s.model_dump() for s in stored.segments],
        "audio_events": [e.model_dump() for e in stored.audio_events],
        "visual_events": [e.model_dump() for e in stored.visual_events],
        "events": stored.events,
        "after_scorecard": (
            stored.after_scorecard.model_dump() if stored.after_scorecard else None
        ),
        "local_video": stored.local_video,
        "caption_ready": stored.caption_ready,
    }


def persist_run(stored: Any) -> None:
    payload = stored_payload(stored)
    run = stored.run
    with get_session() as session:
        row = session.get(QcRun, run.id)
        if row is None:
            row = QcRun(
                id=run.id,
                created_at=run.created_at,
                profile_id=run.profile_id,
                status=run.status,
            )
            session.add(row)
        row.created_at = run.created_at
        row.profile_id = run.profile_id
        row.status = run.status
        row.sdh_mode = run.sdh_mode
        row.has_ad = run.has_ad
        row.payload = dump_json(payload)

        session.execute(delete(QcFinding).where(QcFinding.run_id == run.id))
        session.execute(delete(QcFix).where(QcFix.run_id == run.id))
        # These are projection rows, not the logical finding identity. Include
        # the observation position so a repeated model timestamp / legacy ID
        # cannot abort the entire run transaction. Logical IDs stay in payload.
        for position, finding in enumerate(run.findings):
            session.add(
                QcFinding(
                    id=f"{run.id}:finding:{position}",
                    run_id=run.id,
                    code=finding.code,
                    severity=finding.severity,
                    start_ms=finding.start_ms,
                    payload=dump_json(finding.model_dump()),
                )
            )
        for position, fix in enumerate(run.fixes):
            session.add(
                QcFix(
                    id=f"{run.id}:fix:{position}",
                    run_id=run.id,
                    type=fix.type,
                    status=fix.status,
                    payload=dump_json(fix.model_dump()),
                )
            )
        session.commit()


def record_decision(run_id: str, fix_id: str, decision: str) -> None:
    with get_session() as session:
        session.add(
            QcDecision(
                run_id=run_id,
                fix_id=fix_id,
                decision=decision,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        session.commit()


def load_payload(run_id: str) -> Optional[Dict[str, Any]]:
    with get_session() as session:
        row = session.get(QcRun, run_id)
        if row is None:
            return None
        return json.loads(row.payload)


def save_asset(run_id: str, kind: str, content: bytes) -> None:
    with get_session() as session:
        asset_id = f"{run_id}:{kind}"
        row = session.get(QcAsset, asset_id)
        if row is None:
            row = QcAsset(id=asset_id, run_id=run_id, kind=kind, content=content)
            session.add(row)
        else:
            row.content = content
        session.commit()


def load_asset(run_id: str, kind: str) -> Optional[bytes]:
    with get_session() as session:
        row = session.get(QcAsset, f"{run_id}:{kind}")
        return row.content if row else None


def list_payloads() -> List[Dict[str, Any]]:
    with get_session() as session:
        rows = session.scalars(select(QcRun).order_by(QcRun.created_at.desc())).all()
        return [json.loads(row.payload) for row in rows]


def hydrate_stored(payload: Dict[str, Any], stored_cls: Any) -> Any:
    after = payload.get("after_scorecard")
    return stored_cls(
        run=Run.model_validate(payload["run"]),
        owner_id=payload.get("owner_id", ""),
        upload_sizes=payload.get("upload_sizes") or {},
        cues=[Cue.model_validate(c) for c in payload.get("cues", [])],
        ad_cues=[Cue.model_validate(c) for c in payload.get("ad_cues", [])],
        segments=[Segment.model_validate(s) for s in payload.get("segments", [])],
        audio_events=[AudioEvent.model_validate(e) for e in payload.get("audio_events", [])],
        visual_events=[VisualEvent.model_validate(e) for e in payload.get("visual_events", [])],
        events=list(payload.get("events") or []),
        after_scorecard=Scorecard.model_validate(after) if after else None,
        local_video=bool(payload.get("local_video")),
        caption_ready=bool(payload.get("caption_ready")),
    )


def decision_status_map(run_id: str) -> Dict[str, str]:
    """Latest accept/reject per fix id. Later rows win."""
    latest: Dict[str, str] = {}
    for row in list_decisions(run_id):
        latest[row["fix_id"]] = "accepted" if row["decision"] == "accept" else "rejected"
    return latest


def apply_decisions_to_run(run: Run) -> Run:
    """Replay qc_decisions onto a Run so a pipeline overwrite cannot drop them."""
    latest = decision_status_map(run.id)
    for fx in run.fixes:
        if fx.id in latest:
            fx.status = latest[fx.id]
    return run


def list_decisions(run_id: str) -> List[Dict[str, Any]]:
    with get_session() as session:
        rows = session.scalars(
            select(QcDecision).where(QcDecision.run_id == run_id).order_by(QcDecision.id)
        ).all()
        return [
            {
                "run_id": row.run_id,
                "fix_id": row.fix_id,
                "decision": row.decision,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def clear_all() -> None:
    with get_session() as session:
        session.execute(delete(QcAsset))
        session.execute(delete(QcDecision))
        session.execute(delete(QcFinding))
        session.execute(delete(QcFix))
        session.execute(delete(QcRun))
        session.commit()
