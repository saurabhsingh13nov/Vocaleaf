"""Tests for page image generation worker."""

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

from sqlalchemy import select

from app.models.child import Child
from app.models.enums import (
    AssetType,
    AssetUploadStatus,
    GenerationType,
    JobStatus,
    StoryPageStatus,
    StoryStatus,
    UserStatus,
)
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.story_page_generation import StoryPageGeneration
from app.models.asset import Asset
from app.workers.image_worker import run_image_generation_in_session


@dataclass(frozen=True)
class FakeR2ObjectMetadata:
    file_size_bytes: int | None
    checksum: str | None


class FakeGoogleImagenClient:
    def __init__(self, output):
        self.output = output
        self.calls: list[dict] = []

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class FakeR2Client:
    def __init__(self):
        self.uploads: list[dict] = []

    def put_object(self, *, object_key, body, content_type):
        self.uploads.append({"object_key": object_key, "body": body, "content_type": content_type})
        return FakeR2ObjectMetadata(file_size_bytes=len(body), checksum="abc123")


async def _setup_story_with_pages(db_session, *, page_count=2, page_status=StoryPageStatus.TEXT_READY):
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        primary_email=f"img-worker-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Image Worker User",
        status=UserStatus.ACTIVE,
    )
    child = Child(id=uuid.uuid4(), user=user, name="Luna", age=5)
    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        child=child,
        prompt="A moon garden adventure",
        status=StoryStatus.GENERATING,
        target_page_count=page_count,
        language="en",
        art_style="Dreamy watercolor",
    )
    job = StoryGenerationJob(
        id=uuid.uuid4(),
        story=story,
        job_type="full_generation",
        status=JobStatus.RUNNING,
        provider_text="anthropic",
        provider_image="google_imagen",
    )
    pages = []
    for i in range(1, page_count + 1):
        page = StoryPage(
            id=uuid.uuid4(),
            story=story,
            page_number=i,
            text_content=f"Page {i} text",
            image_prompt=f"A moonlit garden scene, page {i}",
            continuity_notes=f"Keep silver flowers consistent, page {i}",
            status=page_status,
        )
        pages.append(page)

    db_session.add_all([user, child, story, job, *pages])
    await db_session.commit()
    return story, job, pages


async def test_image_generation_success(db_session, monkeypatch):
    from app.integrations.google_imagen import GeneratedImage

    story, job, pages = await _setup_story_with_pages(db_session, page_count=1)

    fake_image = GeneratedImage(content=b"\x89PNG_FAKE_IMAGE_DATA", mime_type="image/png")
    fake_imagen = FakeGoogleImagenClient(fake_image)
    fake_r2 = FakeR2Client()

    monkeypatch.setattr("app.workers.image_worker.get_google_imagen_client", lambda: fake_imagen)
    monkeypatch.setattr("app.workers.image_worker.get_r2_client", lambda: fake_r2)

    await run_image_generation_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
    )

    # Verify page status
    refreshed_page = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.id == pages[0].id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_page.status == StoryPageStatus.IMAGE_READY
    assert refreshed_page.image_asset_id is not None

    # Verify asset created
    asset = (
        await db_session.execute(
            select(Asset).where(Asset.id == refreshed_page.image_asset_id)
        )
    ).scalar_one()
    assert asset.asset_type == AssetType.PAGE_IMAGE
    assert asset.mime_type == "image/png"
    assert asset.upload_status == AssetUploadStatus.READY
    assert asset.file_size_bytes == len(b"\x89PNG_FAKE_IMAGE_DATA")

    # Verify page generation record
    gen = (
        await db_session.execute(
            select(StoryPageGeneration)
            .where(StoryPageGeneration.story_page_id == pages[0].id)
            .where(StoryPageGeneration.generation_type == GenerationType.IMAGE)
        )
    ).scalar_one()
    assert gen.provider == "google_imagen"
    assert gen.status == JobStatus.COMPLETED

    # Verify R2 upload
    assert len(fake_r2.uploads) == 1
    assert fake_r2.uploads[0]["content_type"] == "image/png"

    # Verify Imagen client was called with correct params
    assert len(fake_imagen.calls) == 1
    assert fake_imagen.calls[0]["art_style"] == "Dreamy watercolor"

    # Single page story — job should be completed, story READY
    refreshed_story = (
        await db_session.execute(
            select(Story)
            .where(Story.id == story.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    refreshed_job = (
        await db_session.execute(
            select(StoryGenerationJob)
            .where(StoryGenerationJob.id == job.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_story.status == StoryStatus.READY
    assert refreshed_job.status == JobStatus.COMPLETED


async def test_image_generation_api_error_marks_page_failed(db_session, monkeypatch):
    from app.integrations.google_imagen import GoogleImagenError

    story, job, pages = await _setup_story_with_pages(db_session, page_count=1)

    fake_imagen = FakeGoogleImagenClient(GoogleImagenError("Imagen request failed"))
    monkeypatch.setattr("app.workers.image_worker.get_google_imagen_client", lambda: fake_imagen)

    await run_image_generation_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
    )

    refreshed_page = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.id == pages[0].id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_page.status == StoryPageStatus.FAILED
    assert refreshed_page.image_asset_id is None

    refreshed_story = (
        await db_session.execute(
            select(Story)
            .where(Story.id == story.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_story.status == StoryStatus.FAILED

    refreshed_job = (
        await db_session.execute(
            select(StoryGenerationJob)
            .where(StoryGenerationJob.id == job.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_job.error_message == "Imagen request failed"
    assert refreshed_job.status == JobStatus.FAILED
    assert refreshed_job.completed_at is not None


async def test_image_generation_missing_page_is_graceful(db_session, monkeypatch):
    from app.integrations.google_imagen import GeneratedImage

    fake_imagen = FakeGoogleImagenClient(
        GeneratedImage(content=b"unused", mime_type="image/png")
    )
    monkeypatch.setattr("app.workers.image_worker.get_google_imagen_client", lambda: fake_imagen)

    await run_image_generation_in_session(
        db_session,
        story_page_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
    )

    assert fake_imagen.calls == []


async def test_image_generation_skips_non_text_ready_page(db_session, monkeypatch):
    from app.integrations.google_imagen import GeneratedImage

    story, job, pages = await _setup_story_with_pages(
        db_session, page_count=1, page_status=StoryPageStatus.IMAGE_READY
    )

    fake_imagen = FakeGoogleImagenClient(
        GeneratedImage(content=b"unused", mime_type="image/png")
    )
    monkeypatch.setattr("app.workers.image_worker.get_google_imagen_client", lambda: fake_imagen)

    await run_image_generation_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
    )

    assert fake_imagen.calls == []


async def test_story_stays_generating_when_not_all_pages_done(db_session, monkeypatch):
    from app.integrations.google_imagen import GeneratedImage

    story, job, pages = await _setup_story_with_pages(db_session, page_count=2)

    fake_image = GeneratedImage(content=b"\x89PNG_FAKE", mime_type="image/png")
    fake_imagen = FakeGoogleImagenClient(fake_image)
    fake_r2 = FakeR2Client()

    monkeypatch.setattr("app.workers.image_worker.get_google_imagen_client", lambda: fake_imagen)
    monkeypatch.setattr("app.workers.image_worker.get_r2_client", lambda: fake_r2)

    # Generate image for first page only
    await run_image_generation_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
    )

    refreshed_story = (
        await db_session.execute(
            select(Story)
            .where(Story.id == story.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    # Story should still be GENERATING since page 2 is still TEXT_READY
    assert refreshed_story.status == StoryStatus.GENERATING
