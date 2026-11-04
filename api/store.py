"""Run store with SQLAlchemy persistence.

SQLite locally (`.data/cuecheck.sqlite`). Replit Postgres when DATABASE_URL is set.
SSE subscriber queues stay in process memory.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from api.db import clear_all, hydrate_stored, list_payloads, load_payload, persist_run
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

    def put(self, stored: StoredRun) -> StoredRun:
        self._runs[stored.run.id] = stored
        persist_run(stored)
        return stored

    def save(self, stored: StoredRun) -> StoredRun:
        self._runs[stored.run.id] = stored
        persist_run(stored)
        return stored

    def get(self, run_id: str) -> StoredRun:
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
        for payload in list_payloads():
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

    def drop_cache(self) -> None:
        """Drop in-process objects. Used to prove History reloads from the database."""
        self._runs.clear()

    def clear(self) -> None:
        self._runs.clear()
        clear_all()


store = RunStore()
