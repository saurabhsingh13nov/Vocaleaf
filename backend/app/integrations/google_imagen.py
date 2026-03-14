"""Backward-compatible aliases for the Gemini image integration."""

from app.integrations.google_gemini_image import (
    GeneratedImage,
    GoogleGeminiImageClient,
    GoogleGeminiImageError,
    _get_genai_module,
    _normalize_error_detail,
    get_google_gemini_image_client,
)

GoogleImagenClient = GoogleGeminiImageClient
GoogleImagenError = GoogleGeminiImageError


def get_google_imagen_client() -> GoogleGeminiImageClient:
    """Backward-compatible wrapper for older imports."""
    return get_google_gemini_image_client()
