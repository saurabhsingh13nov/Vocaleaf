"""Story orchestration and retrieval helpers."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.child import Child
from app.models.enums import GenerationType, JobStatus, StoryPageStatus, StoryStatus, VoiceProfileStatus
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.voice_profile import VoiceProfile
from app.schemas.story import StoryCreate
from app.services.audit import record_audit_event
from app.services.subscription import SubscriptionError, enforce_story_creation_allowed
from app.services.usage import record_story_created_usage


class StoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _story_detail_load():
    return (
        selectinload(Story.pages).selectinload(StoryPage.page_generations),
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

    try:
        await enforce_story_creation_allowed(
            db,
            user_id=user_id,
            target_page_count=data.target_page_count,
        )
    except SubscriptionError as exc:
        raise StoryError(exc.message, status_code=exc.status_code) from exc

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
        generation_version="phase-11-audio-v1",
    )
    db.add(story)
    await db.flush()
    record_story_created_usage(db, user_id=user_id, story_id=story.id)
    record_audit_event(
        db,
        user_id=user_id,
        entity_type="story",
        entity_id=story.id,
        event_type="story.created",
        event_data={
            "target_page_count": data.target_page_count,
            "voice_profile_id": str(data.voice_profile_id) if data.voice_profile_id else None,
        },
    )

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


def _story_requires_narration(story: Story) -> bool:
    return story.voice_profile_id is not None


def _page_retryable_outputs(story: Story, page: StoryPage) -> list[GenerationType]:
    outputs: list[GenerationType] = []
    failed_story = story.status == StoryStatus.FAILED
    failed_page = page.status == StoryPageStatus.FAILED

    if (
        page.image_asset_id is None
        and page.text_content is not None
        and (failed_story or failed_page)
    ):
        outputs.append(GenerationType.IMAGE)

    if (
        _story_requires_narration(story)
        and page.image_asset_id is not None
        and page.audio_asset_id is None
        and (failed_story or failed_page)
    ):
        outputs.append(GenerationType.AUDIO)

    return outputs


async def _create_retry_job(
    db: AsyncSession,
    *,
    story: Story,
    job_type: str,
    outputs: set[GenerationType],
) -> StoryGenerationJob:
    job = StoryGenerationJob(
        story_id=story.id,
        job_type=job_type,
        status=JobStatus.PENDING,
        provider_image="google_gemini_image" if GenerationType.IMAGE in outputs else None,
        provider_audio="elevenlabs" if GenerationType.AUDIO in outputs else None,
    )
    db.add(job)
    await db.flush()
    return job


async def _load_story_page(
    db: AsyncSession,
    *,
    story_id: uuid.UUID,
    page_id: uuid.UUID,
) -> StoryPage | None:
    result = await db.execute(
        select(StoryPage)
        .where(StoryPage.id == page_id, StoryPage.story_id == story_id)
        .options(selectinload(StoryPage.page_generations))
    )
    return result.scalar_one_or_none()


async def _enqueue_retry_tasks(
    *,
    page_outputs: list[tuple[StoryPage, list[GenerationType]]],
    job_id: uuid.UUID,
) -> None:
    from app.workers.audio_worker import generate_page_audio_task
    from app.workers.image_worker import generate_page_image_task

    for page, outputs in page_outputs:
        if GenerationType.IMAGE in outputs:
            generate_page_image_task.delay(str(page.id), str(job_id))
        elif GenerationType.AUDIO in outputs:
            generate_page_audio_task.delay(str(page.id), str(job_id))


async def retry_story_missing_outputs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
) -> Story:
    story = await get_story(db, user_id=user_id, story_id=story_id)
    if story is None:
        raise StoryError("Story not found", status_code=404)

    page_outputs = [
        (page, _page_retryable_outputs(story, page))
        for page in sorted(list(story.pages), key=lambda entry: entry.page_number)
    ]
    page_outputs = [(page, outputs) for page, outputs in page_outputs if outputs]
    if not page_outputs:
        raise StoryError("There are no missing outputs to retry for this story", status_code=400)

    outputs = {output for _page, retryable in page_outputs for output in retryable}
    job = await _create_retry_job(
        db,
        story=story,
        job_type="retry_missing_outputs",
        outputs=outputs,
    )

    story.status = StoryStatus.GENERATING
    for page, retryable in page_outputs:
        if GenerationType.IMAGE in retryable:
            page.status = StoryPageStatus.TEXT_READY
        elif GenerationType.AUDIO in retryable:
            page.status = StoryPageStatus.IMAGE_READY

    await db.commit()
    await _enqueue_retry_tasks(page_outputs=page_outputs, job_id=job.id)

    refreshed_story = await get_story(db, user_id=user_id, story_id=story_id)
    if refreshed_story is None:
        raise StoryError("Story not found", status_code=404)
    return refreshed_story


async def retry_story_page_missing_outputs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
    page_id: uuid.UUID,
) -> Story:
    story = await get_story(db, user_id=user_id, story_id=story_id)
    if story is None:
        raise StoryError("Story not found", status_code=404)

    page = await _load_story_page(db, story_id=story.id, page_id=page_id)
    if page is None:
        raise StoryError("Story page not found", status_code=404)

    retryable = _page_retryable_outputs(story, page)
    if not retryable:
        raise StoryError("There are no missing outputs to retry for this page", status_code=400)

    job = await _create_retry_job(
        db,
        story=story,
        job_type="page_retry",
        outputs=set(retryable),
    )

    story.status = StoryStatus.GENERATING
    if GenerationType.IMAGE in retryable:
        page.status = StoryPageStatus.TEXT_READY
    elif GenerationType.AUDIO in retryable:
        page.status = StoryPageStatus.IMAGE_READY

    await db.commit()
    await _enqueue_retry_tasks(page_outputs=[(page, retryable)], job_id=job.id)

    refreshed_story = await get_story(db, user_id=user_id, story_id=story_id)
    if refreshed_story is None:
        raise StoryError("Story not found", status_code=404)
    return refreshed_story


async def delete_story(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
) -> None:
    story = await get_story(db, user_id=user_id, story_id=story_id)
    if story is None:
        raise StoryError("Story not found", status_code=404)

    record_audit_event(
        db,
        user_id=user_id,
        entity_type="story",
        entity_id=story.id,
        event_type="story.deleted",
        event_data={"previous_status": story.status.value},
    )
    story.status = StoryStatus.DELETED
    await db.commit()


def story_latest_error_message(story: Story) -> str | None:
    return _latest_error_message(story)
