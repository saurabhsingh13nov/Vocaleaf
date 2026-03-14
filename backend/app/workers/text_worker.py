"""Story text generation worker entrypoints."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.session import dispose_session_state, dispose_session_state_sync, get_async_session_factory
from app.integrations.anthropic import AnthropicError, StoryTextOutput, get_anthropic_client
from app.models.enums import GenerationType, JobStatus, StoryPageStatus, StoryStatus
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.story_page_generation import StoryPageGeneration
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _load_story_and_job(
    db: AsyncSession,
    *,
    story_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[Story | None, StoryGenerationJob | None]:
    story_result = await db.execute(
        select(Story)
        .where(Story.id == story_id)
        .options(selectinload(Story.child), selectinload(Story.pages))
        .execution_options(populate_existing=True)
    )
    job_result = await db.execute(
        select(StoryGenerationJob)
        .where(StoryGenerationJob.id == job_id)
        .execution_options(populate_existing=True)
    )
    return story_result.scalar_one_or_none(), job_result.scalar_one_or_none()


def _validate_story_output(output: StoryTextOutput, *, expected_page_count: int | None) -> None:
    if expected_page_count is not None and len(output.pages) != expected_page_count:
        raise AnthropicError("Anthropic response page count did not match target_page_count")

    page_numbers = [page.page_number for page in output.pages]
    expected_numbers = list(range(1, len(output.pages) + 1))
    if page_numbers != expected_numbers:
        raise AnthropicError("Anthropic response page numbers must start at 1 and be sequential")


async def run_text_generation(
    story_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await run_text_generation_in_session(db, story_id=story_id, job_id=job_id)
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def mark_text_generation_failed_in_session(
    db: AsyncSession,
    *,
    story_id: uuid.UUID,
    job_id: uuid.UUID,
    error_message: str = "Story generation failed",
) -> None:
    await db.rollback()
    story, job = await _load_story_and_job(db, story_id=story_id, job_id=job_id)
    if story is None or job is None:
        logger.warning(
            "Text generation cleanup skipped because story %s or job %s no longer exists",
            story_id,
            job_id,
        )
        return

    story.status = StoryStatus.FAILED
    job.status = JobStatus.FAILED
    job.error_message = error_message
    job.completed_at = _utcnow_naive()
    await db.commit()


async def mark_text_generation_failed(
    story_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    error_message: str = "Story generation failed",
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await mark_text_generation_failed_in_session(
                db,
                story_id=story_id,
                job_id=job_id,
                error_message=error_message,
            )
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def run_text_generation_in_session(
    db: AsyncSession,
    *,
    story_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    story, job = await _load_story_and_job(db, story_id=story_id, job_id=job_id)
    if story is None or job is None:
        logger.warning(
            "Text generation skipped because story %s or job %s no longer exists",
            story_id,
            job_id,
        )
        return

    job.status = JobStatus.RUNNING
    job.started_at = _utcnow_naive()
    story.status = StoryStatus.GENERATING
    await db.commit()

    child = story.child
    if child is None:
        await mark_text_generation_failed_in_session(
            db,
            story_id=story_id,
            job_id=job_id,
            error_message="Story child context is missing",
        )
        return

    request_payload = {
        "child_name": child.name,
        "child_age": child.age,
        "favorite_themes": child.favorite_themes,
        "favorite_characters": child.favorite_characters,
        "bedtime_preferences": child.bedtime_preferences,
        "prompt": story.prompt,
        "theme": story.theme,
        "art_style": story.art_style,
        "page_count": story.target_page_count,
        "reading_level": story.reading_level,
        "language": story.language,
    }

    try:
        output = get_anthropic_client().generate_story_text(**request_payload)
        _validate_story_output(output, expected_page_count=story.target_page_count)
    except AnthropicError as exc:
        await mark_text_generation_failed_in_session(
            db,
            story_id=story_id,
            job_id=job_id,
            error_message=str(exc),
        )
        logger.exception("Text generation failed for story %s", story_id, exc_info=exc)
        return

    db.add_all(
        [
            StoryPage(
                story_id=story.id,
                page_number=page.page_number,
                text_content=page.text_content,
                image_prompt=page.image_prompt,
                continuity_notes=page.continuity_notes,
                status=StoryPageStatus.TEXT_READY,
            )
            for page in output.pages
        ]
    )
    await db.flush()

    pages_result = await db.execute(
        select(StoryPage)
        .where(StoryPage.story_id == story.id)
        .order_by(StoryPage.page_number.asc())
        .execution_options(populate_existing=True)
    )
    pages = list(pages_result.scalars().all())

    db.add_all(
        [
            StoryPageGeneration(
                story_page_id=page_model.id,
                generation_job_id=job.id,
                generation_type=GenerationType.TEXT,
                provider=job.provider_text,
                request_payload_json={**request_payload, "page_number": page_output.page_number},
                response_payload_json={
                    "page_number": page_output.page_number,
                    "text_content": page_output.text_content,
                    "image_prompt": page_output.image_prompt,
                    "continuity_notes": page_output.continuity_notes,
                },
                prompt_version=story.generation_version,
                status=JobStatus.COMPLETED,
                completed_at=_utcnow_naive(),
            )
            for page_model, page_output in zip(pages, output.pages, strict=True)
        ]
    )

    story.title = output.title
    story.status = StoryStatus.GENERATING
    job.provider_image = "google_imagen"
    job.error_message = None
    await db.commit()

    from app.workers.image_worker import generate_page_image_task

    for page_model in pages:
        generate_page_image_task.delay(str(page_model.id), str(job.id))


@celery_app.task(name="app.workers.text_worker.generate_story_text_task")
def generate_story_text_task(story_id: str, job_id: str) -> None:
    """Celery wrapper that bridges synchronous workers to async DB code."""
    story_uuid = uuid.UUID(story_id)
    job_uuid = uuid.UUID(job_id)

    try:
        asyncio.run(run_text_generation(story_uuid, job_uuid))
    except Exception as exc:
        logger.exception("Text generation task crashed for story %s", story_id)
        try:
            dispose_session_state_sync()
            asyncio.run(
                mark_text_generation_failed(
                    story_uuid,
                    job_uuid,
                    error_message=str(exc).strip() or "Story generation crashed",
                )
            )
        except Exception:
            logger.exception("Text generation crash cleanup failed for story %s", story_id)
        raise
