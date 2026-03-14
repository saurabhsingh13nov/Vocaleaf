"""Tests for Google Gemini image integration helpers."""

from app.core.config import Settings
from app.integrations.google_gemini_image import _normalize_error_detail


def test_normalize_error_detail_for_invalid_model() -> None:
    detail = _normalize_error_detail(
        Exception(
            "404 NOT_FOUND. {'error': {'code': 404, 'message': "
            "'models/gemini-1.5-flash-image is not found for API version v1beta, "
            "or is not supported for predict.', 'status': 'NOT_FOUND'}}"
        ),
        model="gemini-1.5-flash-image",
    )

    assert "GEMINI_IMAGE_MODEL" in detail
    assert "IMAGEN_MODEL" in detail
    assert "gemini-3.1-flash-image-preview" in detail
    assert "gemini-1.5-flash-image" in detail


def test_normalize_error_detail_for_auth_failure() -> None:
    detail = _normalize_error_detail(
        Exception("401 invalid API key"),
        model="gemini-3.1-flash-image-preview",
    )

    assert detail == (
        "Google GenAI authentication failed. "
        "Update GOOGLE_GENAI_API_KEY and restart the backend and worker."
    )


def test_settings_prefers_new_gemini_model_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
    monkeypatch.setenv("IMAGEN_MODEL", "imagen-4.0-generate-001")

    settings = Settings(_env_file=None)

    assert settings.resolved_gemini_image_model == "gemini-3.1-flash-image-preview"


def test_settings_accepts_legacy_imagen_model_env(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    monkeypatch.setenv("IMAGEN_MODEL", "imagen-4.0-generate-001")

    settings = Settings(_env_file=None)

    assert settings.resolved_gemini_image_model == "imagen-4.0-generate-001"
