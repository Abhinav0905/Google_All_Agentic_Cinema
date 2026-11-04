"""Multimodal analysis client using Google GenAI on Vertex AI.

Orchestrates Gemini Flash/Pro multimodal calls for:
- Transcription (speech segments with timestamps & speaker labels)
- Non-speech audio event listening (salient & ambient audio events)
- Visual accessibility pass (speaker on-screen visibility & visual events)
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from engine.models import AudioEvent, Segment, VisualEvent

logger = logging.getLogger("cuecheck.multimodal")

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


class TranscribeResponse(BaseModel):
    segments: List[Segment] = Field(default_factory=list)


class ListenResponse(BaseModel):
    events: List[AudioEvent] = Field(default_factory=list)


class SpeakerVisibilityItem(BaseModel):
    segment_index: int
    speaker_on_screen: bool


class LookResponse(BaseModel):
    speaker_visibilities: List[SpeakerVisibilityItem] = Field(default_factory=list)
    visual_events: List[VisualEvent] = Field(default_factory=list)


def log_model_call(
    model_id: str, purpose: str, input_desc: str, duration_s: float, status: str
) -> None:
    """Log every model call (model id, purpose, input size, duration)
    without logging secrets or media.
    """
    print(
        f"[model_call] model={model_id} purpose='{purpose}' "
        f"input='{input_desc}' duration={duration_s:.2f}s status={status}"
    )


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}_prompt.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_genai_client():
    """Create GenAI client configured for Vertex AI backend."""
    from google import genai

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    return genai.Client(vertexai=True, project=project, location=location)


def run_transcribe(
    media_uri: str,
    model_id: Optional[str] = None,
    offline_fixture: Optional[Path] = None,
) -> List[Segment]:
    """Transcribe spoken dialogue from video into Segment models."""
    if offline_fixture and offline_fixture.exists():
        with open(offline_fixture, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Segment.model_validate(s) for s in data.get("segments", [])]

    model = model_id or os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    prompt = _load_prompt("transcribe")
    client = get_genai_client()

    start_time = time.time()
    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=media_uri, mime_type="video/mp4"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TranscribeResponse,
            ),
        )
        duration = time.time() - start_time
        log_model_call(model, "transcribe", media_uri, duration, "SUCCESS")

        parsed = TranscribeResponse.model_validate_json(response.text)
        return parsed.segments
    except Exception as e:
        duration = time.time() - start_time
        log_model_call(model, "transcribe", media_uri, duration, f"FAILED: {e}")
        raise


def run_listen(
    media_uri: str,
    model_id: Optional[str] = None,
    offline_fixture: Optional[Path] = None,
) -> List[AudioEvent]:
    """Detect non-speech audio events from video."""
    if offline_fixture and offline_fixture.exists():
        with open(offline_fixture, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [AudioEvent.model_validate(e) for e in data.get("events", [])]

    model = model_id or os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    prompt = _load_prompt("listen")
    client = get_genai_client()

    start_time = time.time()
    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=media_uri, mime_type="video/mp4"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ListenResponse,
            ),
        )
        duration = time.time() - start_time
        log_model_call(model, "listen", media_uri, duration, "SUCCESS")

        parsed = ListenResponse.model_validate_json(response.text)
        return parsed.events
    except Exception as e:
        duration = time.time() - start_time
        log_model_call(model, "listen", media_uri, duration, f"FAILED: {e}")
        raise


def run_look(
    media_uri: str,
    segments: List[Segment],
    model_id: Optional[str] = None,
    offline_fixture: Optional[Path] = None,
) -> Tuple[List[Segment], List[VisualEvent]]:
    """Perform visual pass: speaker on-screen visibility and essential visual events."""
    if offline_fixture and offline_fixture.exists():
        with open(offline_fixture, "r", encoding="utf-8") as f:
            data = json.load(f)
        vis_map: Dict[int, bool] = {
            item["segment_index"]: item["speaker_on_screen"]
            for item in data.get("speaker_visibilities", [])
        }
        updated_segments = []
        for i, seg in enumerate(segments):
            seg_copy = seg.model_copy()
            if i in vis_map:
                seg_copy.speaker_on_screen = vis_map[i]
            updated_segments.append(seg_copy)
        visual_events = [VisualEvent.model_validate(e) for e in data.get("visual_events", [])]
        return updated_segments, visual_events

    model = model_id or os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    base_prompt = _load_prompt("look")
    seg_summary = [
        {"index": i, "start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
        for i, s in enumerate(segments)
    ]
    full_prompt = f"{base_prompt}\n\nTranscript Segments to evaluate:\n{json.dumps(seg_summary)}"

    client = get_genai_client()
    start_time = time.time()
    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=media_uri, mime_type="video/mp4"),
                full_prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LookResponse,
            ),
        )
        duration = time.time() - start_time
        log_model_call(model, "look", media_uri, duration, "SUCCESS")

        parsed = LookResponse.model_validate_json(response.text)
        vis_map = {
            item.segment_index: item.speaker_on_screen for item in parsed.speaker_visibilities
        }
        updated_segments = []
        for i, seg in enumerate(segments):
            seg_copy = seg.model_copy()
            if i in vis_map:
                seg_copy.speaker_on_screen = vis_map[i]
            updated_segments.append(seg_copy)

        return updated_segments, parsed.visual_events
    except Exception as e:
        duration = time.time() - start_time
        log_model_call(model, "look", media_uri, duration, f"FAILED: {e}")
        raise
