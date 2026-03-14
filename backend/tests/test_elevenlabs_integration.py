"""Tests for the ElevenLabs integration wrapper."""

import base64
from types import SimpleNamespace

import pytest

from app.integrations.elevenlabs import (
    ElevenLabsClient,
    ElevenLabsError,
    ElevenLabsSample,
)


def test_clone_voice_uses_sdk_client_and_returns_voice_id(monkeypatch):
    captured: dict[str, object] = {}

    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

            def create(*, name: str, files):
                uploads = list(files)
                captured["name"] = name
                captured["files"] = uploads
                captured["file_names"] = [upload.name for upload in uploads]
                captured["file_contents"] = [upload.read() for upload in uploads]
                return SimpleNamespace(voice_id="voice_sdk_123")

            self.voices = SimpleNamespace(ivc=SimpleNamespace(create=create))

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")
    result = client.clone_voice(
        display_name="Storytime",
        samples=[
            ElevenLabsSample(file_name="sample-a.webm", content=b"sample-a", content_type="audio/webm"),
            ElevenLabsSample(file_name="sample-b.m4a", content=b"sample-b", content_type="audio/m4a"),
        ],
    )

    assert result.voice_id == "voice_sdk_123"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://api.elevenlabs.io"
    assert captured["name"] == "Storytime"

    uploads = captured["files"]
    assert isinstance(uploads, list)
    assert captured["file_names"] == ["sample-a.webm", "sample-b.m4a"]
    assert captured["file_contents"] == [b"sample-a", b"sample-b"]
    assert all(upload.closed for upload in uploads)


def test_clone_voice_wraps_sdk_errors(monkeypatch):
    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            def create(*, name: str, files):
                raise RuntimeError("provider unavailable")

            self.voices = SimpleNamespace(ivc=SimpleNamespace(create=create))

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")

    with pytest.raises(ElevenLabsError, match="provider unavailable"):
        client.clone_voice(
            display_name="Storytime",
            samples=[ElevenLabsSample(file_name="sample-a.webm", content=b"sample-a", content_type="audio/webm")],
        )


def test_clone_voice_requires_voice_id_in_response(monkeypatch):
    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            def create(*, name: str, files):
                return SimpleNamespace()

            self.voices = SimpleNamespace(ivc=SimpleNamespace(create=create))

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")

    with pytest.raises(ElevenLabsError, match="voice_id"):
        client.clone_voice(
            display_name="Storytime",
            samples=[ElevenLabsSample(file_name="sample-a.webm", content=b"sample-a", content_type="audio/webm")],
        )


def test_generate_narration_uses_sdk_client_and_returns_audio(monkeypatch):
    captured: dict[str, object] = {}

    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str, timeout: float) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout

            def convert_with_timestamps(**kwargs):
                captured["kwargs"] = kwargs
                return SimpleNamespace(
                    audio_base_64=base64.b64encode(b"narration-bytes").decode("ascii"),
                    alignment=SimpleNamespace(character_end_times_seconds=[0.12, 1.45]),
                    normalized_alignment=None,
                )

            self.text_to_speech = SimpleNamespace(convert_with_timestamps=convert_with_timestamps)

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")
    result = client.generate_narration(
        voice_id="voice_123",
        text="The moon glowed softly.",
        language_code="en",
        previous_text="Luna climbed into bed.",
        next_text="She smiled at the lantern.",
    )

    assert result.content == b"narration-bytes"
    assert result.mime_type == "audio/mpeg"
    assert result.duration_ms == 1450
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://api.elevenlabs.io"
    assert captured["timeout"] == 60.0
    assert captured["kwargs"] == {
        "voice_id": "voice_123",
        "text": "The moon glowed softly.",
        "model_id": "eleven_multilingual_v2",
        "language_code": "en",
        "previous_text": "Luna climbed into bed.",
        "next_text": "She smiled at the lantern.",
        "output_format": "mp3_44100_128",
    }


def test_generate_narration_requires_audio_in_response(monkeypatch):
    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str, timeout: float) -> None:
            def convert_with_timestamps(**kwargs):
                return SimpleNamespace(audio_base_64="")

            self.text_to_speech = SimpleNamespace(convert_with_timestamps=convert_with_timestamps)

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")

    with pytest.raises(ElevenLabsError, match="include audio"):
        client.generate_narration(
            voice_id="voice_123",
            text="A bedtime story.",
        )


def test_generate_narration_normalizes_missing_tts_permission(monkeypatch):
    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str, timeout: float) -> None:
            def convert_with_timestamps(**kwargs):
                raise RuntimeError(
                    "headers: {'content-type': 'application/json'}, status_code: 401, "
                    "body: {'detail': {'status': 'missing_permissions', "
                    "'message': 'The API key you used is missing the permission text_to_speech to execute this operation.'}}"
                )

            self.text_to_speech = SimpleNamespace(convert_with_timestamps=convert_with_timestamps)

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")

    with pytest.raises(
        ElevenLabsError,
        match="text-to-speech permission is missing",
    ):
        client.generate_narration(
            voice_id="voice_123",
            text="A bedtime story.",
        )


def test_generate_narration_normalizes_quota_exceeded(monkeypatch):
    class FakeElevenLabs:
        def __init__(self, *, api_key: str, base_url: str, timeout: float) -> None:
            def convert_with_timestamps(**kwargs):
                raise RuntimeError(
                    "headers: {'content-type': 'application/json'}, status_code: 401, "
                    "body: {'detail': {'status': 'quota_exceeded', "
                    "'message': 'This request exceeds your API key quota. You have 5 credits remaining, while 250 credits are required for this request.'}}"
                )

            self.text_to_speech = SimpleNamespace(convert_with_timestamps=convert_with_timestamps)

    monkeypatch.setattr("app.integrations.elevenlabs._get_sdk_client_class", lambda: FakeElevenLabs)

    client = ElevenLabsClient(api_key="test-key", base_url="https://api.elevenlabs.io")

    with pytest.raises(
        ElevenLabsError,
        match="quota is exhausted",
    ):
        client.generate_narration(
            voice_id="voice_123",
            text="A bedtime story.",
        )
