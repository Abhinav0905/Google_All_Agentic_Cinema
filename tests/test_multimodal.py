"""Vertex transport regressions; model responses are mocked and no network is used."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agents import multimodal


def test_vertex_express_key_uses_vertex_backend(monkeypatch):
    from google import genai

    client = Mock()
    monkeypatch.setattr(genai, "Client", client)
    monkeypatch.setenv("VERTEX_API_KEY", "test-only-key")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "unused-project")
    multimodal.get_genai_client()
    client.assert_called_once_with(vertexai=True, api_key="test-only-key")


def test_adc_project_backend_remains_supported(monkeypatch):
    from google import genai

    client = Mock()
    monkeypatch.setattr(genai, "Client", client)
    monkeypatch.setenv("VERTEX_API_KEY", "")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    multimodal.get_genai_client()
    client.assert_called_once_with(vertexai=True, project="test-project", location="us-central1")


def test_local_video_uses_inline_bytes_and_gcs_uses_uri(tmp_path):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"test-mp4-data")
    local = multimodal.media_part(str(video))
    assert local.inline_data.data == b"test-mp4-data"
    assert local.inline_data.mime_type == "video/mp4"
    cloud = multimodal.media_part("gs://test-bucket/source.mp4")
    assert cloud.file_data.file_uri == "gs://test-bucket/source.mp4"


def test_inline_limit_rejects_oversized_file_before_reading(tmp_path, monkeypatch):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"too large")
    monkeypatch.setattr(multimodal, "INLINE_VIDEO_MAX_BYTES", 3)
    with pytest.raises(ValueError, match="no larger"):
        multimodal.media_part(str(video))


def test_all_three_live_steps_send_inline_video(tmp_path, monkeypatch):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"test-video")
    generate = Mock(
        side_effect=[
            SimpleNamespace(text='{"segments": [{"start_ms": 0, "end_ms": 1000, "text": "Hi"}]}'),
            SimpleNamespace(text='{"events": [{"t_ms": 1100, "label": "[KNOCK]"}]}'),
            SimpleNamespace(text='{"speaker_visibilities": [], "visual_events": []}'),
        ]
    )
    monkeypatch.setattr(
        multimodal,
        "get_genai_client",
        lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)),
    )
    segments = multimodal.run_transcribe(str(video))
    events = multimodal.run_listen(str(video))
    updated, _ = multimodal.run_look(str(video), segments)
    assert events[0].label == "[KNOCK]"
    assert updated[0].text == "Hi"
    assert generate.call_count == 3
    for call in generate.call_args_list:
        assert call.kwargs["contents"][0].inline_data.data == b"test-video"
