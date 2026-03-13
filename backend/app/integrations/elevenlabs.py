"""ElevenLabs voice-cloning integration helpers."""

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Iterable, Optional

from app.core.config import settings


class ElevenLabsError(Exception):
    """Raised when ElevenLabs rejects or fails a request."""


@dataclass(frozen=True)
class ElevenLabsSample:
    """Binary voice sample sent to the cloning API."""

    file_name: str
    content: bytes
    content_type: Optional[str]


@dataclass(frozen=True)
class ElevenLabsVoice:
    """Minimal cloned voice payload returned by ElevenLabs."""

    voice_id: str


class _NamedBytesIO(BytesIO):
    """In-memory file object with a stable filename for the SDK upload API."""

    def __init__(self, *, content: bytes, file_name: str) -> None:
        super().__init__(content)
        self.name = file_name


def _get_sdk_client_class():
    try:
        from elevenlabs.client import ElevenLabs  # type: ignore[import-not-found]
    except ImportError:
        try:
            from elevenlabs import ElevenLabs  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised in environments missing the SDK
            raise ElevenLabsError("The elevenlabs package is not installed") from exc

    return ElevenLabs


def _extract_voice_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        voice_id = payload.get("voice_id")
    else:
        voice_id = getattr(payload, "voice_id", None)

    if isinstance(voice_id, str) and voice_id.strip():
        return voice_id
    return None


class ElevenLabsClient:
    """Small SDK-backed wrapper for voice cloning."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def clone_voice(
        self,
        *,
        display_name: str,
        samples: Iterable[ElevenLabsSample],
    ) -> ElevenLabsVoice:
        if not self.api_key:
            raise ElevenLabsError("ElevenLabs is not configured")

        sdk_client_class = _get_sdk_client_class()
        file_uploads = [
            _NamedBytesIO(content=sample.content, file_name=sample.file_name)
            for sample in samples
        ]

        try:
            client = sdk_client_class(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            payload = client.voices.ivc.create(
                name=display_name,
                files=file_uploads,
            )
        except ElevenLabsError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via mocks in tests
            detail = str(exc).strip() or "ElevenLabs cloning failed"
            raise ElevenLabsError(detail) from exc
        finally:
            for file_upload in file_uploads:
                file_upload.close()

        voice_id = _extract_voice_id(payload)
        if voice_id is None:
            raise ElevenLabsError("ElevenLabs response did not include a voice_id")

        return ElevenLabsVoice(voice_id=voice_id)


def get_elevenlabs_client() -> ElevenLabsClient:
    """Build an ElevenLabs client from app settings."""
    return ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        base_url=settings.elevenlabs_base_url,
    )
