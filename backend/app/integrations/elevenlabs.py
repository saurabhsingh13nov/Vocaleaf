"""ElevenLabs voice-cloning and TTS integration helpers."""

import base64
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


@dataclass(frozen=True)
class ElevenLabsNarrationAudio:
    """Generated narration audio plus best-effort metadata."""

    content: bytes
    mime_type: str
    duration_ms: int | None


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


def _normalize_error_detail(exc: Exception, *, operation: str) -> str:
    detail = str(exc).strip() or f"ElevenLabs {operation} failed"
    lowered = detail.lower()

    if "quota_exceeded" in lowered or "credits remaining" in lowered:
        return (
            "ElevenLabs text-to-speech quota is exhausted for the configured API key. "
            "Add more credits or use a key with sufficient quota, then restart the backend and worker."
        )

    if "missing_permissions" in lowered and "text_to_speech" in lowered:
        return (
            "ElevenLabs text-to-speech permission is missing for the configured API key. "
            "Use an API key with text_to_speech access and restart the backend and worker."
        )

    if "401" in lowered or "authentication" in lowered or "api key" in lowered:
        return (
            "ElevenLabs authentication failed. "
            "Update ELEVENLABS_API_KEY and restart the backend and worker."
        )

    return detail


class ElevenLabsClient:
    """Small SDK-backed wrapper for voice cloning and narration."""

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
            detail = _normalize_error_detail(exc, operation="cloning")
            raise ElevenLabsError(detail) from exc
        finally:
            for file_upload in file_uploads:
                file_upload.close()

        voice_id = _extract_voice_id(payload)
        if voice_id is None:
            raise ElevenLabsError("ElevenLabs response did not include a voice_id")

        return ElevenLabsVoice(voice_id=voice_id)

    def generate_narration(
        self,
        *,
        voice_id: str,
        text: str,
        language_code: str | None = None,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> ElevenLabsNarrationAudio:
        if not self.api_key:
            raise ElevenLabsError("ElevenLabs is not configured")

        normalized_text = text.strip()
        if not normalized_text:
            raise ElevenLabsError("Narration text is required")

        sdk_client_class = _get_sdk_client_class()

        try:
            client = sdk_client_class(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            request_kwargs: dict[str, Any] = {
                "voice_id": voice_id,
                "text": normalized_text,
                "model_id": settings.elevenlabs_tts_model,
                "output_format": "mp3_44100_128",
            }
            if language_code:
                request_kwargs["language_code"] = language_code
            if previous_text:
                request_kwargs["previous_text"] = previous_text
            if next_text:
                request_kwargs["next_text"] = next_text

            payload = client.text_to_speech.convert_with_timestamps(
                **request_kwargs,
            )
        except ElevenLabsError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via mocks in tests
            detail = _normalize_error_detail(exc, operation="narration")
            raise ElevenLabsError(detail) from exc

        audio_base64 = getattr(payload, "audio_base_64", None)
        if not isinstance(audio_base64, str) or not audio_base64.strip():
            raise ElevenLabsError("ElevenLabs response did not include audio")

        try:
            content = base64.b64decode(audio_base64)
        except Exception as exc:  # pragma: no cover - defensive decoding failure
            raise ElevenLabsError("ElevenLabs returned invalid audio data") from exc

        duration_ms = _extract_duration_ms(payload)
        return ElevenLabsNarrationAudio(
            content=content,
            mime_type="audio/mpeg",
            duration_ms=duration_ms,
        )


def _extract_duration_ms(payload: Any) -> int | None:
    for field_name in ("alignment", "normalized_alignment"):
        alignment = getattr(payload, field_name, None)
        end_times = getattr(alignment, "character_end_times_seconds", None)
        if not isinstance(end_times, list) or not end_times:
            continue
        last_end = end_times[-1]
        if isinstance(last_end, (int, float)) and last_end > 0:
            return int(round(last_end * 1000))
    return None


def get_elevenlabs_client() -> ElevenLabsClient:
    """Build an ElevenLabs client from app settings."""
    return ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        base_url=settings.elevenlabs_base_url,
    )
