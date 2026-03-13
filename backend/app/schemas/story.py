"""Pydantic request and response models for story APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StoryPageStatus, StoryStatus


class StoryCreate(BaseModel):
    child_id: uuid.UUID
    voice_profile_id: uuid.UUID | None = None
    prompt: str | None = Field(default=None, max_length=2000)
    theme: str | None = Field(default=None, max_length=100)
    target_page_count: int = Field(default=6, ge=4, le=12)
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
    duration_ms: int | None
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
    created_at: datetime
    updated_at: datetime
    pages: list[StoryPageResponse]

    @classmethod
    def from_model(
        cls,
        story,
        *,
        latest_error_message: str | None = None,
    ) -> "StoryResponse":
        pages = sorted(list(story.pages), key=lambda page: page.page_number)
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
