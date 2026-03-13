"""Story orchestration and retrieval helpers."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.child import Child
from app.models.enums import JobStatus, StoryStatus, VoiceProfileStatus
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.voice_profile import VoiceProfile
from app.schemas.story import StoryCreate


class StoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _story_detail_load():
    return (
        selectinload(Story.pages),
        selectinload(Story.generation_jobs),
    )


def _latest_error_message(story: Story) -> str | None:
    latest_job = max(story.generation_jobs, key=lambda job: job.created_at, default=None)
    return latest_job.error_message if latest_job else None


async def _get_owned_child(db: AsyncSession, *, user_id: uuid.UUID, child_id: uuid.UUID) -> Child | None:
    result = await db.execute(
        select(Child).where(Child.id == child_id, Child.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_owned_voice_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    voice_profile_id: uuid.UUID,
) -> VoiceProfile | None:
    result = await db.execute(
        select(VoiceProfile).where(
            VoiceProfile.id == voice_profile_id,
            VoiceProfile.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_story(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: StoryCreate,
) -> Story:
    child = await _get_owned_child(db, user_id=user_id, child_id=data.child_id)
    if child is None:
        raise StoryError("Child not found", status_code=404)

    if not (data.prompt and data.prompt.strip()) and not (data.theme and data.theme.strip()):
        raise StoryError("Provide a prompt or theme to create a story", status_code=400)

    if data.voice_profile_id is not None:
        voice_profile = await _get_owned_voice_profile(
            db,
            user_id=user_id,
            voice_profile_id=data.voice_profile_id,
        )
        if voice_profile is None:
            raise StoryError("Voice profile not found", status_code=404)
        if voice_profile.status != VoiceProfileStatus.READY:
            raise StoryError("Voice profile must be ready before story creation", status_code=400)

    story = Story(
        user_id=user_id,
        child_id=data.child_id,
        voice_profile_id=data.voice_profile_id,
        prompt=data.prompt.strip() if data.prompt else None,
        theme=data.theme.strip() if data.theme else None,
        status=StoryStatus.DRAFT,
        target_page_count=data.target_page_count,
        reading_level=data.reading_level.strip() if data.reading_level else None,
        language=data.language.strip().lower(),
        art_style=data.art_style.strip() if data.art_style else None,
        generation_version="phase-9-text-v1",
    )
    db.add(story)
    await db.flush()

    job = StoryGenerationJob(
        story_id=story.id,
        job_type="full_generation",
        status=JobStatus.PENDING,
        provider_text="anthropic",
    )
    db.add(job)
    await db.commit()

    from app.workers.text_worker import generate_story_text_task

    generate_story_text_task.delay(str(story.id), str(job.id))

    story.status = StoryStatus.GENERATING
    await db.commit()

    result = await db.execute(
        select(Story)
        .where(Story.id == story.id)
        .options(*_story_detail_load())
    )
    return result.scalar_one()


async def list_stories(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[Story]:
    result = await db.execute(
        select(Story)
        .where(Story.user_id == user_id, Story.status != StoryStatus.DELETED)
        .order_by(Story.created_at.desc())
        .limit(limit)
        .offset(offset)
        .options(selectinload(Story.generation_jobs))
    )
    return list(result.scalars().all())


async def get_story(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
) -> Story | None:
    result = await db.execute(
        select(Story)
        .where(
            Story.id == story_id,
            Story.user_id == user_id,
            Story.status != StoryStatus.DELETED,
        )
        .options(*_story_detail_load())
    )
    return result.scalar_one_or_none()


async def delete_story(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
) -> None:
    story = await get_story(db, user_id=user_id, story_id=story_id)
    if story is None:
        raise StoryError("Story not found", status_code=404)

    story.status = StoryStatus.DELETED
    await db.commit()


def story_latest_error_message(story: Story) -> str | None:
    return _latest_error_message(story)
