"""Google Gemini image-generation integration helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

_EMPTY_IMAGE_RETRY_ATTEMPTS = 3


def _empty_image_error_message(kind: str) -> str:
    return (
        f"Gemini image generation returned {kind} after {_EMPTY_IMAGE_RETRY_ATTEMPTS} attempts. "
        "This is usually a transient provider response. Retry story or page generation."
    )


class GoogleGeminiImageError(Exception):
    """Raised when Gemini image generation rejects or returns an invalid response."""


@dataclass(frozen=True)
class GeneratedImage:
    """Raw image output from the Gemini image provider."""

    content: bytes
    mime_type: str


def _get_genai_module():
    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as exc:
        raise GoogleGeminiImageError("The google-genai package is not installed") from exc
    return genai


def _build_enriched_prompt(
    *,
    prompt: str,
    art_style: str | None,
    continuity_context: str | None,
    negative_prompt: str | None,
) -> str:
    enriched_parts = [prompt]
    if art_style:
        enriched_parts.append(f"Art style: {art_style}")
    if continuity_context:
        enriched_parts.append(f"Visual continuity: {continuity_context}")
    if negative_prompt:
        enriched_parts.append(f"Avoid the following in the image: {negative_prompt}")
    return ". ".join(enriched_parts)


def _iter_response_parts(response) -> list[object]:
    direct_parts = list(getattr(response, "parts", None) or [])
    if direct_parts:
        return direct_parts

    parts: list[object] = []
    for candidate in list(getattr(response, "candidates", None) or []):
        content = getattr(candidate, "content", None)
        parts.extend(list(getattr(content, "parts", None) or []))
    return parts


def _extract_generated_image(response) -> GeneratedImage | None:
    saw_inline_image_part = False
    empty_mime_type = "image/png"

    for part in _iter_response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if inline_data is None:
            continue

        saw_inline_image_part = True
        mime_type = getattr(inline_data, "mime_type", None) or "image/png"
        image_bytes = getattr(inline_data, "data", None) or getattr(inline_data, "image_bytes", None)
        if image_bytes:
            return GeneratedImage(content=image_bytes, mime_type=mime_type)
        empty_mime_type = mime_type

    if saw_inline_image_part:
        return GeneratedImage(content=b"", mime_type=empty_mime_type)
    return None


class GoogleGeminiImageClient:
    """Thin wrapper around the Google GenAI SDK for Gemini image generation."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate_image(
        self,
        *,
        prompt: str,
        art_style: str | None = None,
        continuity_context: str | None = None,
        aspect_ratio: str = "4:3",
        negative_prompt: str | None = None,
    ) -> GeneratedImage:
        if not self.api_key:
            raise GoogleGeminiImageError("Google GenAI is not configured")

        genai = _get_genai_module()
        client = genai.Client(api_key=self.api_key)
        enriched_prompt = _build_enriched_prompt(
            prompt=prompt,
            art_style=art_style,
            continuity_context=continuity_context,
            negative_prompt=negative_prompt,
        )

        from google.genai import types  # type: ignore[import-not-found]

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )

        last_empty_error = _empty_image_error_message("no images")
        for _attempt in range(_EMPTY_IMAGE_RETRY_ATTEMPTS):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=enriched_prompt,
                    config=config,
                )
            except GoogleGeminiImageError:
                raise
            except Exception as exc:
                detail = _normalize_error_detail(exc, model=self.model)
                raise GoogleGeminiImageError(detail) from exc

            image = _extract_generated_image(response)
            if image is None:
                last_empty_error = _empty_image_error_message("no images")
                continue
            if not image.content:
                last_empty_error = _empty_image_error_message("an empty image")
                continue
            return image

        raise GoogleGeminiImageError(last_empty_error)


def get_google_gemini_image_client() -> GoogleGeminiImageClient:
    """Build a Google Gemini image client from app settings."""
    return GoogleGeminiImageClient(
        api_key=settings.google_genai_api_key,
        model=settings.resolved_gemini_image_model,
    )


def _normalize_error_detail(exc: Exception, *, model: str) -> str:
    detail = str(exc).strip() or "Gemini image generation failed"
    lowered = detail.lower()

    if "401" in lowered or "authentication" in lowered or "api key" in lowered:
        return (
            "Google GenAI authentication failed. "
            "Update GOOGLE_GENAI_API_KEY and restart the backend and worker."
        )

    if "404" in lowered and "not_found" in lowered and "models/" in lowered:
        return (
            f"Google Gemini image model '{model}' is unavailable for the Gemini API. "
            "Set GEMINI_IMAGE_MODEL to a currently supported model such as "
            "'gemini-3.1-flash-image-preview' and restart the backend and worker. "
            "The backend still accepts IMAGEN_MODEL as a deprecated alias during migration. "
            f"Provider error: {detail}"
        )

    return detail
