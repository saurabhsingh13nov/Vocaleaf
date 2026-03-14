"""Google Imagen image-generation integration helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


class GoogleImagenError(Exception):
    """Raised when Imagen rejects or returns an invalid image response."""


@dataclass(frozen=True)
class GeneratedImage:
    """Raw image output from the Imagen provider."""

    content: bytes
    mime_type: str


def _get_genai_module():
    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as exc:
        raise GoogleImagenError("The google-genai package is not installed") from exc
    return genai


class GoogleImagenClient:
    """Thin wrapper around the Google GenAI SDK for image generation."""

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
            raise GoogleImagenError("Google GenAI is not configured")

        genai = _get_genai_module()
        client = genai.Client(api_key=self.api_key)

        enriched_parts = [prompt]
        if art_style:
            enriched_parts.append(f"Art style: {art_style}")
        if continuity_context:
            enriched_parts.append(f"Visual continuity: {continuity_context}")
        enriched_prompt = ". ".join(enriched_parts)

        from google.genai import types  # type: ignore[import-not-found]

        config_kwargs: dict = {
            "number_of_images": 1,
            "aspect_ratio": aspect_ratio,
            "output_mime_type": "image/png",
            "safety_filter_level": types.SafetyFilterLevel.BLOCK_LOW_AND_ABOVE,
            "person_generation": types.PersonGeneration.ALLOW_ADULT,
        }
        if negative_prompt:
            config_kwargs["negative_prompt"] = negative_prompt

        try:
            config = types.GenerateImagesConfig(**config_kwargs)
            response = client.models.generate_images(
                model=self.model,
                prompt=enriched_prompt,
                config=config,
            )
        except GoogleImagenError:
            raise
        except Exception as exc:
            detail = _normalize_error_detail(exc, model=self.model)
            raise GoogleImagenError(detail) from exc

        if not response.generated_images:
            raise GoogleImagenError("Imagen returned no images")

        image = response.generated_images[0].image
        if image is None or not image.image_bytes:
            raise GoogleImagenError("Imagen returned an empty image")

        return GeneratedImage(
            content=image.image_bytes,
            mime_type="image/png",
        )


def get_google_imagen_client() -> GoogleImagenClient:
    """Build a Google Imagen client from app settings."""
    return GoogleImagenClient(
        api_key=settings.google_genai_api_key,
        model=settings.imagen_model,
    )


def _normalize_error_detail(exc: Exception, *, model: str) -> str:
    detail = str(exc).strip() or "Imagen image generation failed"
    lowered = detail.lower()

    if "401" in lowered or "authentication" in lowered or "api key" in lowered:
        return (
            "Google GenAI authentication failed. "
            "Update GOOGLE_GENAI_API_KEY and restart the backend and worker."
        )

    if "400" in lowered and "safetysetting" in lowered and "block_low_and_above" in lowered:
        return (
            "Google Imagen rejected the configured safety filter level for this model. "
            "The backend now defaults to BLOCK_LOW_AND_ABOVE for Imagen 4. "
            f"Restart the backend and worker. Provider error: {detail}"
        )

    if "404" in lowered and "not_found" in lowered and "models/" in lowered:
        return (
            f"Google Imagen model '{model}' is unavailable for the Gemini API. "
            "Set IMAGEN_MODEL to a currently supported model such as "
            "'imagen-4.0-generate-001' and restart the backend and worker. "
            f"Provider error: {detail}"
        )

    return detail
