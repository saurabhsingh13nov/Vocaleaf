"""Tests for the ElevenLabs integration wrapper."""

from types import SimpleNamespace

import pytest

from app.integrations.elevenlabs import ElevenLabsClient, ElevenLabsError, ElevenLabsSample


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
