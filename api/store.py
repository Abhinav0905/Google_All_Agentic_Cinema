"""In-memory run store. Replaced by Postgres in Phase 6."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
        return stored

    def get(self, run_id: str) -> StoredRun:
        if run_id not in self._runs:
            raise KeyError(run_id)
        return self._runs[run_id]

    def list(self) -> List[StoredRun]:
        return sorted(self._runs.values(), key=lambda s: s.run.created_at, reverse=True)

    def clear(self) -> None:
        self._runs.clear()


store = RunStore()
