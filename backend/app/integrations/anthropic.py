"""Anthropic text-generation integration helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import settings


class AnthropicError(Exception):
    """Raised when Anthropic rejects or returns an invalid story response."""


@dataclass(frozen=True)
class StoryPageOutput:
    """Structured page payload returned by the text provider."""

    page_number: int
    text_content: str
    image_prompt: str
    continuity_notes: str


@dataclass(frozen=True)
class StoryTextOutput:
    """Structured full-story payload returned by the text provider."""

    title: str
    pages: list[StoryPageOutput]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "pages": [asdict(page) for page in self.pages],
        }


def _get_sdk_client_class():
    try:
        from anthropic import Anthropic  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised in environments missing the SDK
        raise AnthropicError("The anthropic package is not installed") from exc

    return Anthropic


def _extract_text_block(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        raise AnthropicError("Anthropic response did not include content blocks")

    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

    raise AnthropicError("Anthropic response did not include a text block")


def _strip_markdown_fences(payload: str) -> str:
    stripped = payload.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()

    return stripped


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnthropicError(f"Anthropic response field '{field_name}' must be a non-empty string")
    return value.strip()


def _normalize_optional_context(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _validate_story_payload(payload: Any) -> StoryTextOutput:
    if not isinstance(payload, dict):
        raise AnthropicError("Anthropic response JSON must be an object")

    title = _require_string(payload.get("title"), "title")
    pages_payload = payload.get("pages")
    if not isinstance(pages_payload, list) or not pages_payload:
        raise AnthropicError("Anthropic response must include a non-empty 'pages' list")

    pages: list[StoryPageOutput] = []
    for index, page_payload in enumerate(pages_payload, start=1):
        if not isinstance(page_payload, dict):
            raise AnthropicError(f"Anthropic response page {index} must be an object")

        page_number = page_payload.get("page_number")
        if not isinstance(page_number, int) or page_number < 1:
            raise AnthropicError(f"Anthropic response page {index} has an invalid page_number")

        pages.append(
            StoryPageOutput(
                page_number=page_number,
                text_content=_require_string(page_payload.get("text_content"), "text_content"),
                image_prompt=_require_string(page_payload.get("image_prompt"), "image_prompt"),
                continuity_notes=_require_string(
                    page_payload.get("continuity_notes"),
                    "continuity_notes",
                ),
            )
        )

    return StoryTextOutput(title=title, pages=pages)


class AnthropicClient:
    """Small SDK-backed wrapper for structured story generation."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.model = model

    def generate_story_text(
        self,
        *,
        child_name: str,
        child_age: int | None,
        favorite_themes: Any,
        favorite_characters: Any,
        bedtime_preferences: Any,
        prompt: str | None,
        theme: str | None,
        art_style: str | None,
        page_count: int,
        reading_level: str | None,
        language: str,
    ) -> StoryTextOutput:
        if not self.api_key:
            raise AnthropicError("Anthropic is not configured")

        sdk_client_class = _get_sdk_client_class()
        client = sdk_client_class(api_key=self.api_key)

        child_age_text = str(child_age) if child_age is not None else "unknown"
        system_prompt = (
            "You write warm, age-appropriate children's bedtime stories. "
            "Return only valid JSON with the exact schema requested. "
            "Do not wrap the JSON in markdown fences."
        )
        user_prompt = "\n".join(
            [
                "Create a personalized children's story with this JSON shape:",
                '{',
                '  "title": "string",',
                '  "pages": [',
                "    {",
                '      "page_number": 1,',
                '      "text_content": "2-4 sentences of narration",',
                '      "image_prompt": "illustration prompt",',
                '      "continuity_notes": "story continuity notes"',
                "    }",
                "  ]",
                "}",
                "",
                f"Child name: {child_name}",
                f"Child age: {child_age_text}",
                f"Favorite themes: {_normalize_optional_context(favorite_themes) or 'none provided'}",
                f"Favorite characters: {_normalize_optional_context(favorite_characters) or 'none provided'}",
                f"Bedtime preferences: {_normalize_optional_context(bedtime_preferences) or 'none provided'}",
                f"Story prompt: {prompt.strip() if prompt else 'none provided'}",
                f"Theme: {theme.strip() if theme else 'none provided'}",
                f"Art style: {art_style.strip() if art_style else 'none provided'}",
                f"Reading level: {reading_level.strip() if reading_level else 'none provided'}",
                f"Language: {language}",
                f"Required page count: {page_count}",
                "",
                "Requirements:",
                "- Keep the tone gentle and imaginative.",
                "- Keep each page self-contained but continuous with the rest of the story.",
                "- Make illustration prompts visually specific and consistent.",
                "- The pages array must contain exactly the required number of pages.",
                "- Page numbers must start at 1 and increase by 1.",
            ]
        )

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )
        except AnthropicError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via mocks in tests
            detail = str(exc).strip() or "Anthropic story generation failed"
            raise AnthropicError(detail) from exc

        response_text = _extract_text_block(response)
        try:
            payload = json.loads(_strip_markdown_fences(response_text))
        except json.JSONDecodeError as exc:
            raise AnthropicError("Anthropic response was not valid JSON") from exc

        return _validate_story_payload(payload)


def get_anthropic_client() -> AnthropicClient:
    """Build an Anthropic client from app settings."""
    return AnthropicClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )
