"""Run store with SQLAlchemy persistence.

SQLite locally (`.data/cuecheck.sqlite`). Replit Postgres when DATABASE_URL is set.
SSE subscriber queues stay in process memory.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from api.db import (
    apply_decisions_to_run,
    clear_all,
    hydrate_stored,
    list_payloads,
    load_payload,
    persist_run,
)
from engine.models import (
    AudioEvent,
    Cue,
    Run,
    Scorecard,
    Segment,
    VisualEvent,
)


@dataclass
class StoredRun:
    run: Run
    owner_id: str = ""
    upload_sizes: Dict[str, int] = field(default_factory=dict)
    cues: List[Cue] = field(default_factory=list)
    ad_cues: List[Cue] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    audio_events: List[AudioEvent] = field(default_factory=list)
    visual_events: List[VisualEvent] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    subscribers: List[asyncio.Queue] = field(default_factory=list)
    after_scorecard: Optional[Scorecard] = None
    local_video: bool = False
    caption_ready: bool = False


class RunStore:
    def __init__(self) -> None:
        self._runs: Dict[str, StoredRun] = {}
        self._guard = threading.Lock()
        self._run_locks: Dict[str, threading.Lock] = {}

    def lock_for(self, run_id: str) -> threading.Lock:
        with self._guard:
            lock = self._run_locks.get(run_id)
            if lock is None:
                lock = threading.Lock()
                self._run_locks[run_id] = lock
            return lock

    def put(self, stored: StoredRun) -> StoredRun:
        persist_run(stored)
        with self._guard:
            self._runs[stored.run.id] = stored
        return stored

    def save(self, stored: StoredRun) -> StoredRun:
        persist_run(stored)
        with self._guard:
            self._runs[stored.run.id] = stored
        return stored

    def get(self, run_id: str) -> StoredRun:
        # Concurrent first reads must share one object, otherwise one request
        # can overwrite another request's accepted fixes with a stale copy.
        with self._guard:
            if run_id in self._runs:
                return self._runs[run_id]
            payload = load_payload(run_id)
            if payload is None:
                raise KeyError(run_id)
            stored = hydrate_stored(payload, StoredRun)
            self._runs[run_id] = stored
            return stored

    def list(self) -> List[StoredRun]:
        result: List[StoredRun] = []
        seen = set()
        payloads = list_payloads()
        with self._guard:
            for payload in payloads:
                run_id = payload["run"]["id"]
                seen.add(run_id)
                if run_id in self._runs:
                    result.append(self._runs[run_id])
                else:
                    stored = hydrate_stored(payload, StoredRun)
                    self._runs[run_id] = stored
                    result.append(stored)
            for run_id, stored in self._runs.items():
                if run_id not in seen:
                    result.append(stored)
        return sorted(result, key=lambda s: s.run.created_at, reverse=True)

    def apply_pipeline_result(self, stored: StoredRun, pctx: Any) -> StoredRun:
        """Write pipeline output without dropping accept/reject made during the run.

        ScoreAndPlan replaces the fixes list with new objects. A concurrent
        decide_fix may have mutated the previous list and written qc_decisions.
        Merge both in-memory statuses and the decision log onto the new Run.
        """
        with self.lock_for(stored.run.id):
            current = self.get(stored.run.id)
            remembered = {
                fx.id: fx.status
                for fx in current.run.fixes
                if fx.status in ("accepted", "rejected")
            }
            current.cues = pctx.cues
            current.ad_cues = pctx.ad_cues or []
            current.segments = pctx.segments
            current.audio_events = pctx.audio_events
            current.visual_events = pctx.visual_events
            current.run = pctx.run
            current.caption_ready = True
            for fx in current.run.fixes:
                if fx.id in remembered:
                    fx.status = remembered[fx.id]
            apply_decisions_to_run(current.run)
            persist_run(current)
            with self._guard:
                self._runs[current.run.id] = current
            return current

    def drop_cache(self) -> None:
        """Drop in-process objects. Used to prove History reloads from the database."""
        with self._guard:
            self._runs.clear()

    def clear(self) -> None:
        with self._guard:
            self._runs.clear()
            self._run_locks.clear()
        clear_all()


store = RunStore()
