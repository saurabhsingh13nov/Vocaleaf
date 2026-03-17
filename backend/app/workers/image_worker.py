"""Page image generation worker entrypoints."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.session import dispose_session_state, dispose_session_state_sync, get_async_session_factory
from app.integrations.google_gemini_image import (
    GoogleGeminiImageError,
    get_google_gemini_image_client,
)
from app.integrations.r2 import get_r2_client
from app.models.asset import Asset
from app.models.enums import (
    AssetType,
    AssetUploadStatus,
    GenerationType,
    JobStatus,
    StoryPageStatus,
)
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.story_page_generation import StoryPageGeneration
from app.services.usage import record_image_generated_usage
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _story_requires_narration(story: Story) -> bool:
    return story.voice_profile_id is not None


def _extension_for_image_mime_type(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "jpg"

    guessed = mimetypes.guess_extension(mime_type) or ".bin"
    return guessed.lstrip(".")


async def _load_page_and_job(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[StoryPage | None, StoryGenerationJob | None]:
    page_result = await db.execute(
        select(StoryPage)
        .where(StoryPage.id == story_page_id)
        .options(selectinload(StoryPage.story).selectinload(Story.voice_profile))
        .execution_options(populate_existing=True)
    )
    job_result = await db.execute(
        select(StoryGenerationJob)
        .where(StoryGenerationJob.id == job_id)
        .execution_options(populate_existing=True)
    )
    return page_result.scalar_one_or_none(), job_result.scalar_one_or_none()


async def run_image_generation(
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await run_image_generation_in_session(db, story_page_id=story_page_id, job_id=job_id)
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def mark_image_generation_failed_in_session(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    error_message: str = "Image generation failed",
    request_payload: dict | None = None,
    response_payload: dict | None = None,
) -> None:
    await db.rollback()
    page, job = await _load_page_and_job(db, story_page_id=story_page_id, job_id=job_id)
    if page is None or job is None:
        logger.warning(
            "Image generation cleanup skipped because page %s or job %s no longer exists",
            story_page_id,
            job_id,
        )
        return

    from app.models.enums import StoryStatus

    db.add(
        StoryPageGeneration(
            story_page_id=page.id,
            generation_job_id=job.id,
            generation_type=GenerationType.IMAGE,
            provider="google_gemini_image",
            request_payload_json=request_payload,
            response_payload_json=response_payload or {"error_message": error_message},
            status=JobStatus.FAILED,
            completed_at=_utcnow_naive(),
        )
    )
    page.status = StoryPageStatus.FAILED
    page.story.status = StoryStatus.FAILED
    job.status = JobStatus.FAILED
    job.completed_at = _utcnow_naive()
    job.error_message = error_message
    await db.commit()


async def mark_image_generation_failed(
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    error_message: str = "Image generation failed",
    request_payload: dict | None = None,
    response_payload: dict | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await mark_image_generation_failed_in_session(
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


async def run_image_generation_in_session(
    db: AsyncSession,
    *,
    story_page_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    page, job = await _load_page_and_job(db, story_page_id=story_page_id, job_id=job_id)
    if page is None or job is None:
        logger.warning(
            "Image generation skipped because page %s or job %s no longer exists",
            story_page_id,
            job_id,
        )
        return

    if page.status != StoryPageStatus.TEXT_READY:
        logger.info(
            "Image generation skipped for page %s — status is %s, not TEXT_READY",
            story_page_id,
            page.status.value,
        )
        return

    story = page.story
    if story is None:
        await mark_image_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message="Story context is missing for page",
        )
        return

    request_payload = {
        "prompt": page.image_prompt or "",
        "art_style": story.art_style,
        "continuity_context": page.continuity_notes,
    }

    try:
        result = get_google_gemini_image_client().generate_image(**request_payload)
    except GoogleGeminiImageError as exc:
        await mark_image_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message=str(exc),
            request_payload=request_payload,
        )
        logger.exception("Image generation failed for page %s", story_page_id, exc_info=exc)
        return

    image_uuid = uuid.uuid4()
    file_extension = _extension_for_image_mime_type(result.mime_type)
    object_key = (
        f"stories/{story.user_id}/{story.id}"
        f"/pages/{page.page_number}/image/{image_uuid}.{file_extension}"
    )

    try:
        r2_meta = get_r2_client().put_object(
            object_key=object_key,
            body=result.content,
            content_type=result.mime_type,
        )
    except Exception as exc:
        await mark_image_generation_failed_in_session(
            db,
            story_page_id=story_page_id,
            job_id=job_id,
            error_message=f"Failed to upload image to storage: {exc}",
            request_payload=request_payload,
            response_payload={"error_message": f"Failed to upload image to storage: {exc}"},
        )
        logger.exception("R2 upload failed for page %s", story_page_id, exc_info=exc)
        return

    from app.core.config import settings

    asset = Asset(
        user_id=story.user_id,
        storage_provider="r2",
        bucket_name=settings.r2_bucket_name,
        object_key=object_key,
        asset_type=AssetType.PAGE_IMAGE,
        mime_type=result.mime_type,
        file_size_bytes=r2_meta.file_size_bytes,
        checksum=r2_meta.checksum,
        is_private=True,
        upload_status=AssetUploadStatus.READY,
        confirmed_at=_utcnow_naive(),
    )
    db.add(asset)
    await db.flush()

    page_generation = StoryPageGeneration(
        story_page_id=page.id,
        generation_job_id=job.id,
        generation_type=GenerationType.IMAGE,
        provider="google_gemini_image",
        request_payload_json=request_payload,
        response_payload_json={
            "object_key": object_key,
            "file_size_bytes": r2_meta.file_size_bytes,
            "mime_type": result.mime_type,
        },
        status=JobStatus.COMPLETED,
        completed_at=_utcnow_naive(),
    )
    db.add(page_generation)
    record_image_generated_usage(
        db,
        user_id=story.user_id,
        story_id=story.id,
        story_page_id=page.id,
        provider="google_gemini_image",
    )

    page.image_asset_id = asset.id
    page.status = StoryPageStatus.COMPLETE if page.audio_asset_id else StoryPageStatus.IMAGE_READY
    await db.flush()

    should_generate_audio = _story_requires_narration(story)

    # Check if all pages for this story now have the required outputs.
    all_pages_result = await db.execute(
        select(StoryPage)
        .where(StoryPage.story_id == story.id)
        .execution_options(populate_existing=True)
    )
    all_pages = list(all_pages_result.scalars().all())
    all_images_done = all(
        p.status in (StoryPageStatus.IMAGE_READY, StoryPageStatus.COMPLETE)
        for p in all_pages
    )

    if all_images_done and not should_generate_audio:
        from app.models.enums import StoryStatus

        story.status = StoryStatus.READY
        job.status = JobStatus.COMPLETED
        job.completed_at = _utcnow_naive()

    await db.commit()

    if should_generate_audio:
        from app.workers.audio_worker import generate_page_audio_task

        generate_page_audio_task.delay(str(page.id), str(job.id))


@celery_app.task(name="app.workers.image_worker.generate_page_image_task")
def generate_page_image_task(story_page_id: str, job_id: str) -> None:
    """Celery wrapper that bridges synchronous workers to async DB code."""
    page_uuid = uuid.UUID(story_page_id)
    job_uuid = uuid.UUID(job_id)

    try:
        asyncio.run(run_image_generation(page_uuid, job_uuid))
    except Exception as exc:
        logger.exception("Image generation task crashed for page %s", story_page_id)
        try:
            dispose_session_state_sync()
            asyncio.run(
                mark_image_generation_failed(
                    page_uuid,
                    job_uuid,
                    error_message=str(exc).strip() or "Image generation crashed",
                )
            )
        except Exception:
            logger.exception("Image generation crash cleanup failed for page %s", story_page_id)
        raise
