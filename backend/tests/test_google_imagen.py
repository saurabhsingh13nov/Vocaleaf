"""Tests for Google Imagen integration helpers."""

from app.integrations.google_imagen import _normalize_error_detail


def test_normalize_error_detail_for_invalid_model() -> None:
    detail = _normalize_error_detail(
        Exception(
            "404 NOT_FOUND. {'error': {'code': 404, 'message': "
            "'models/imagen-3.0-generate-002 is not found for API version v1beta, "
            "or is not supported for predict.', 'status': 'NOT_FOUND'}}"
        ),
        model="imagen-3.0-generate-002",
    )

    assert "IMAGEN_MODEL" in detail
    assert "imagen-4.0-generate-001" in detail
    assert "imagen-3.0-generate-002" in detail


def test_normalize_error_detail_for_auth_failure() -> None:
    detail = _normalize_error_detail(
        Exception("401 invalid API key"),
        model="imagen-4.0-generate-001",
    )

    assert detail == (
        "Google GenAI authentication failed. "
        "Update GOOGLE_GENAI_API_KEY and restart the backend and worker."
    )


def test_normalize_error_detail_for_invalid_safety_setting() -> None:
    detail = _normalize_error_detail(
        Exception(
            "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': "
            "'Only block_low_and_above is supported for safetySetting.', "
            "'status': 'INVALID_ARGUMENT'}}"
        ),
        model="imagen-4.0-generate-001",
    )

    assert "BLOCK_LOW_AND_ABOVE" in detail
    assert "Restart the backend and worker" in detail
