"""Pydantic request and response models for story APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GenerationType, JobStatus, StoryPageStatus, StoryStatus


class StoryCreate(BaseModel):
    child_id: uuid.UUID
    voice_profile_id: uuid.UUID | None = None
    prompt: str | None = Field(default=None, max_length=2000)
    theme: str | None = Field(default=None, max_length=100)
    target_page_count: int = Field(default=6, ge=2)
    reading_level: str | None = Field(default=None, max_length=50)
    art_style: str | None = Field(default=None, max_length=100)
    language: str = Field(default="en", min_length=2, max_length=10)


class StoryPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_number: int
    text_content: str | None
    image_prompt: str | None
    continuity_notes: str | None
    status: StoryPageStatus
    image_asset_id: uuid.UUID | None
    audio_asset_id: uuid.UUID | None
    image_url: str | None = None
    image_url_expires_at: datetime | None = None
    audio_url: str | None = None
    audio_url_expires_at: datetime | None = None
    duration_ms: int | None
    retryable_outputs: list[str] = Field(default_factory=list)
    output_errors: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    child_id: uuid.UUID
    voice_profile_id: uuid.UUID | None
    title: str | None
    prompt: str | None
    theme: str | None
    status: StoryStatus
    target_page_count: int | None
    reading_level: str | None
    language: str
    art_style: str | None
    latest_error_message: str | None = None
    can_resume_missing_outputs: bool = False
    created_at: datetime
    updated_at: datetime
    pages: list[StoryPageResponse]

    @classmethod
    def from_model(
        cls,
        story,
        *,
        latest_error_message: str | None = None,
        asset_urls_by_id: dict[uuid.UUID, tuple[str, datetime]] | None = None,
    ) -> "StoryResponse":
        story_requires_narration = story.voice_profile_id is not None
        pages = [
            _page_response_payload(
                page,
                story_requires_narration=story_requires_narration,
                story_status=story.status,
                asset_urls_by_id=asset_urls_by_id or {},
            )
            for page in sorted(list(story.pages), key=lambda page: page.page_number)
        ]
        return cls.model_validate(
            {
                "id": story.id,
                "user_id": story.user_id,
                "child_id": story.child_id,
                "voice_profile_id": story.voice_profile_id,
                "title": story.title,
                "prompt": story.prompt,
                "theme": story.theme,
                "status": story.status,
                "target_page_count": story.target_page_count,
                "reading_level": story.reading_level,
                "language": story.language,
                "art_style": story.art_style,
                "latest_error_message": latest_error_message,
                "can_resume_missing_outputs": any(page["retryable_outputs"] for page in pages),
                "created_at": story.created_at,
                "updated_at": story.updated_at,
                "pages": pages,
            }
        )


class StoryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    child_id: uuid.UUID
    title: str | None
    theme: str | None
    status: StoryStatus
    target_page_count: int | None
    art_style: str | None
    latest_error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        story,
        *,
        latest_error_message: str | None = None,
    ) -> "StoryListItem":
        return cls.model_validate(
            {
                "id": story.id,
                "child_id": story.child_id,
                "title": story.title,
                "theme": story.theme,
                "status": story.status,
                "target_page_count": story.target_page_count,
                "art_style": story.art_style,
                "latest_error_message": latest_error_message,
                "created_at": story.created_at,
                "updated_at": story.updated_at,
            }
        )


def _page_response_payload(
    page,
    *,
    story_requires_narration: bool,
    story_status: StoryStatus,
    asset_urls_by_id: dict[uuid.UUID, tuple[str, datetime]],
) -> dict:
    retryable_outputs = _retryable_outputs_for_page(
        page,
        story_requires_narration=story_requires_narration,
        story_status=story_status,
    )
    image_url, image_url_expires_at = _asset_url_payload(asset_urls_by_id, page.image_asset_id)
    audio_url, audio_url_expires_at = _asset_url_payload(asset_urls_by_id, page.audio_asset_id)
    return {
        "id": page.id,
        "page_number": page.page_number,
        "text_content": page.text_content,
        "image_prompt": page.image_prompt,
        "continuity_notes": page.continuity_notes,
        "status": page.status,
        "image_asset_id": page.image_asset_id,
        "audio_asset_id": page.audio_asset_id,
        "image_url": image_url,
        "image_url_expires_at": image_url_expires_at,
        "audio_url": audio_url,
        "audio_url_expires_at": audio_url_expires_at,
        "duration_ms": page.duration_ms,
        "retryable_outputs": retryable_outputs,
        "output_errors": _output_errors_for_page(page),
        "created_at": page.created_at,
        "updated_at": page.updated_at,
    }


def _retryable_outputs_for_page(
    page,
    *,
    story_requires_narration: bool,
    story_status: StoryStatus,
) -> list[str]:
    outputs: list[str] = []
    failed_story = story_status == StoryStatus.FAILED
    failed_page = page.status == StoryPageStatus.FAILED

    image_retryable = (
        page.image_asset_id is None
        and page.text_content is not None
        and (failed_story or failed_page)
    )
    if image_retryable:
        outputs.append(GenerationType.IMAGE.value)

    audio_retryable = (
        story_requires_narration
        and page.image_asset_id is not None
        and page.audio_asset_id is None
        and (failed_story or failed_page)
    )
    if audio_retryable:
        outputs.append(GenerationType.AUDIO.value)

    return outputs


def _output_errors_for_page(page) -> dict[str, str]:
    latest_by_type: dict[str, object] = {}
    for generation in sorted(
        list(getattr(page, "page_generations", [])),
        key=lambda entry: (entry.completed_at or entry.created_at, entry.created_at),
    ):
        latest_by_type[generation.generation_type.value] = generation

    errors: dict[str, str] = {}
    for generation_type, generation in latest_by_type.items():
        if generation.status != JobStatus.FAILED:
            continue
        response_payload = generation.response_payload_json or {}
        error_message = response_payload.get("error_message")
        if isinstance(error_message, str) and error_message.strip():
            errors[generation_type] = error_message

    return errors


def _asset_url_payload(
    asset_urls_by_id: dict[uuid.UUID, tuple[str, datetime]],
    asset_id: uuid.UUID | None,
) -> tuple[str | None, datetime | None]:
    if asset_id is None:
        return None, None
    return asset_urls_by_id.get(asset_id, (None, None))
