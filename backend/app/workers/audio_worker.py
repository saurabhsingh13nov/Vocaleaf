"""Page audio generation worker entrypoints."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.session import dispose_session_state, dispose_session_state_sync, get_async_session_factory
from app.integrations.elevenlabs import ElevenLabsError, get_elevenlabs_client
from app.integrations.r2 import get_r2_client
from app.models.asset import Asset
from app.models.enums import (
    AssetType,
    AssetUploadStatus,
    GenerationType,
    JobStatus,
    StoryPageStatus,
    VoiceProfileStatus,
)
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.story_page_generation import StoryPageGeneration
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _page_context_text(story: Story, page: StoryPage, *, offset: int) -> str | None:
    target_number = page.page_number + offset
    for candidate in story.pages:
        if candidate.page_number == target_number and candidate.text_content:
            return candidate.text_content
    return None


async def _load_page_and_job(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[StoryPage | None, Story | None, StoryGenerationJob | None]:
    page_result = await db.execute(
        select(StoryPage)
        .where(StoryPage.id == story_page_id)
        .execution_options(populate_existing=True)
    )
    page = page_result.scalar_one_or_none()

    story = None
    if page is not None:
        story_result = await db.execute(
            select(Story)
            .where(Story.id == page.story_id)
            .options(
                selectinload(Story.pages),
                selectinload(Story.voice_profile),
            )
            .execution_options(populate_existing=True)
        )
        story = story_result.scalar_one_or_none()

    job_result = await db.execute(
        select(StoryGenerationJob)
        .where(StoryGenerationJob.id == job_id)
        .execution_options(populate_existing=True)
    )
    return page, story, job_result.scalar_one_or_none()


async def run_audio_generation(
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await run_audio_generation_in_session(db, story_page_id=story_page_id, job_id=job_id)
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def mark_audio_generation_failed_in_session(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    error_message: str = "Audio generation failed",
    request_payload: dict | None = None,
    response_payload: dict | None = None,
) -> None:
    await db.rollback()
    page, story, job = await _load_page_and_job(db, story_page_id=story_page_id, job_id=job_id)
    if page is None or story is None or job is None:
        logger.warning(
            "Audio generation cleanup skipped because page %s, story, or job %s no longer exists",
            story_page_id,
            job_id,
        )
        return

    from app.models.enums import StoryStatus

    db.add(
        StoryPageGeneration(
            story_page_id=page.id,
            generation_job_id=job.id,
            generation_type=GenerationType.AUDIO,
            provider="elevenlabs",
            request_payload_json=request_payload,
            response_payload_json=response_payload or {"error_message": error_message},
            status=JobStatus.FAILED,
            completed_at=_utcnow_naive(),
        )
    )
    page.status = StoryPageStatus.FAILED
    story.status = StoryStatus.FAILED
    job.status = JobStatus.FAILED
    job.completed_at = _utcnow_naive()
    job.error_message = error_message
    await db.commit()


async def mark_audio_generation_failed(
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    error_message: str = "Audio generation failed",
    request_payload: dict | None = None,
    response_payload: dict | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await mark_audio_generation_failed_in_session(
                db,
                story_page_id=story_page_id,
                job_id=job_id,
                error_message=error_message,
                request_payload=request_payload,
                response_payload=response_payload,
            )
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def run_audio_generation_in_session(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    page, story, job = await _load_page_and_job(db, story_page_id=story_page_id, job_id=job_id)
    if page is None or story is None or job is None:
        logger.warning(
            "Audio generation skipped because page %s, story, or job %s no longer exists",
            story_page_id,
            job_id,
        )
        return

    if page.status != StoryPageStatus.IMAGE_READY:
        logger.info(
            "Audio generation skipped for page %s — status is %s, not IMAGE_READY",
            story_page_id,
            page.status.value,
        )
        return

    voice_profile = story.voice_profile
    if (
        voice_profile is None
        or voice_profile.status != VoiceProfileStatus.READY
        or not voice_profile.provider_voice_id
    ):
        await mark_audio_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message="Narration voice is not available for this story",
            response_payload={"error_message": "Narration voice is not available for this story"},
        )
        return

    request_payload = {
        "text": page.text_content or "",
        "voice_id": voice_profile.provider_voice_id,
        "language_code": story.language or None,
        "previous_text": _page_context_text(story, page, offset=-1),
        "next_text": _page_context_text(story, page, offset=1),
    }

    try:
        result = get_elevenlabs_client().generate_narration(**request_payload)
    except ElevenLabsError as exc:
        await mark_audio_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message=str(exc),
            request_payload=request_payload,
        )
        logger.exception("Audio generation failed for page %s", story_page_id, exc_info=exc)
        return

    audio_uuid = uuid.uuid4()
    object_key = (
        f"stories/{story.user_id}/{story.id}"
        f"/pages/{page.page_number}/audio/{audio_uuid}.mp3"
    )

    try:
        r2_meta = get_r2_client().put_object(
            object_key=object_key,
            body=result.content,
            content_type=result.mime_type,
        )
    except Exception as exc:
        await mark_audio_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message=f"Failed to upload audio to storage: {exc}",
            request_payload=request_payload,
            response_payload={"error_message": f"Failed to upload audio to storage: {exc}"},
        )
        logger.exception("R2 upload failed for narrated page %s", story_page_id, exc_info=exc)
        return

    from app.core.config import settings
    from app.models.enums import StoryStatus

    asset = Asset(
        user_id=story.user_id,
        storage_provider="r2",
        bucket_name=settings.r2_bucket_name,
        object_key=object_key,
        asset_type=AssetType.PAGE_AUDIO,
        mime_type=result.mime_type,
        file_size_bytes=r2_meta.file_size_bytes,
        checksum=r2_meta.checksum,
        duration_ms=result.duration_ms,
        is_private=True,
        upload_status=AssetUploadStatus.READY,
        confirmed_at=_utcnow_naive(),
    )
    db.add(asset)
    await db.flush()

    page_generation = StoryPageGeneration(
        story_page_id=page.id,
        generation_job_id=job.id,
        generation_type=GenerationType.AUDIO,
        provider="elevenlabs",
        request_payload_json=request_payload,
        response_payload_json={
            "object_key": object_key,
            "file_size_bytes": r2_meta.file_size_bytes,
            "mime_type": result.mime_type,
            "duration_ms": result.duration_ms,
        },
        status=JobStatus.COMPLETED,
        completed_at=_utcnow_naive(),
    )
    db.add(page_generation)

    page.audio_asset_id = asset.id
    page.duration_ms = result.duration_ms
    page.status = StoryPageStatus.COMPLETE if page.image_asset_id else StoryPageStatus.AUDIO_READY
    job.provider_audio = "elevenlabs"
    job.error_message = None
    await db.flush()

    all_pages_result = await db.execute(
        select(StoryPage)
        .where(StoryPage.story_id == story.id)
        .execution_options(populate_existing=True)
    )
    all_pages = list(all_pages_result.scalars().all())
    all_audio_done = all(p.status == StoryPageStatus.COMPLETE for p in all_pages)

    if all_audio_done:
        story.status = StoryStatus.READY
        job.status = JobStatus.COMPLETED
        job.completed_at = _utcnow_naive()

    await db.commit()


@celery_app.task(name="app.workers.audio_worker.generate_page_audio_task")
def generate_page_audio_task(story_page_id: str, job_id: str) -> None:
    """Celery wrapper that bridges synchronous workers to async DB code."""
    page_uuid = uuid.UUID(story_page_id)
    job_uuid = uuid.UUID(job_id)

    try:
        asyncio.run(run_audio_generation(page_uuid, job_uuid))
    except Exception as exc:
        logger.exception("Audio generation task crashed for page %s", story_page_id)
        try:
            dispose_session_state_sync()
            asyncio.run(
                mark_audio_generation_failed(
                    page_uuid,
                    job_uuid,
                    error_message=str(exc).strip() or "Audio generation crashed",
                )
            )
        except Exception:
            logger.exception("Audio generation crash cleanup failed for page %s", story_page_id)
        raise
