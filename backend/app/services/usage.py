"""Usage metering helpers."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_record import UsageRecord

USAGE_TYPE_STORIES_CREATED = "stories_created"
USAGE_TYPE_IMAGES_GENERATED = "images_generated"
USAGE_TYPE_VOICE_CLONES_CREATED = "voice_clones_created"
USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED = "audio_chars_synthesized"


def record_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    usage_type: str,
    quantity: float,
    unit: str,
    provider: str | None = None,
    provider_cost_micros: int | None = None,
    story_id: uuid.UUID | None = None,
    story_page_id: uuid.UUID | None = None,
) -> UsageRecord:
    record = UsageRecord(
        user_id=user_id,
        story_id=story_id,
        story_page_id=story_page_id,
        usage_type=usage_type,
        quantity=quantity,
        unit=unit,
        provider=provider,
        provider_cost_micros=provider_cost_micros,
    )
    db.add(record)
    return record


def record_story_created_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
) -> UsageRecord:
    return record_usage(
        db,
        user_id=user_id,
        story_id=story_id,
        usage_type=USAGE_TYPE_STORIES_CREATED,
        quantity=1,
        unit="story",
    )


def record_image_generated_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
    story_page_id: uuid.UUID,
    provider: str,
) -> UsageRecord:
    return record_usage(
        db,
        user_id=user_id,
        story_id=story_id,
        story_page_id=story_page_id,
        usage_type=USAGE_TYPE_IMAGES_GENERATED,
        quantity=1,
        unit="page_image",
        provider=provider,
    )


def record_voice_clone_created_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
) -> UsageRecord:
    return record_usage(
        db,
        user_id=user_id,
        usage_type=USAGE_TYPE_VOICE_CLONES_CREATED,
        quantity=1,
        unit="voice_clone",
        provider=provider,
    )


def record_audio_chars_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
    story_page_id: uuid.UUID,
    quantity: int,
    provider: str,
) -> UsageRecord:
    return record_usage(
        db,
        user_id=user_id,
        story_id=story_id,
        story_page_id=story_page_id,
        usage_type=USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED,
        quantity=quantity,
        unit="character",
        provider=provider,
    )
