"""Tests for page audio generation worker."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.models.asset import Asset
from app.models.child import Child
from app.models.enums import (
    AssetType,
    AssetUploadStatus,
    GenerationType,
    JobStatus,
    StoryPageStatus,
    StoryStatus,
    UserStatus,
    VoiceProfileStatus,
)
from app.models.story import Story
from app.models.story_generation_job import StoryGenerationJob
from app.models.story_page import StoryPage
from app.models.story_page_generation import StoryPageGeneration
from app.models.voice_profile import VoiceProfile
from app.workers.audio_worker import (
    mark_audio_generation_failed_in_session,
    run_audio_generation_in_session,
)


@dataclass(frozen=True)
class FakeR2ObjectMetadata:
    file_size_bytes: int | None
    checksum: str | None


class FakeElevenLabsClient:
    def __init__(self, output):
        self.output = output
        self.calls: list[dict] = []

    def generate_narration(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class FakeR2Client:
    def __init__(self):
        self.uploads: list[dict] = []

    def put_object(self, *, object_key, body, content_type):
        self.uploads.append({"object_key": object_key, "body": body, "content_type": content_type})
        return FakeR2ObjectMetadata(file_size_bytes=len(body), checksum="audio123")


async def _setup_narrated_story_with_pages(db_session, *, page_count=1):
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        primary_email=f"audio-worker-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Audio Worker User",
        status=UserStatus.ACTIVE,
    )
    child = Child(id=uuid.uuid4(), user=user, name="Luna", age=5)
    voice_profile = VoiceProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="elevenlabs",
        provider_voice_id="voice_123",
        display_name="Bedtime Voice",
        clone_type="instant",
        status=VoiceProfileStatus.READY,
        source_type="user_upload",
        consent_confirmed=True,
    )
    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        child=child,
        voice_profile=voice_profile,
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
        provider_image="google_gemini_image",
    )
    image_assets = []
    pages = []
    for i in range(1, page_count + 1):
        image_asset = Asset(
            id=uuid.uuid4(),
            user_id=user.id,
            storage_provider="r2",
            bucket_name="storybook",
            object_key=f"stories/{user.id}/{i}.png",
            asset_type=AssetType.PAGE_IMAGE,
            mime_type="image/png",
            file_size_bytes=2048,
            checksum=f"image-{i}",
            is_private=True,
            upload_status=AssetUploadStatus.READY,
        )
        image_assets.append(image_asset)
        page = StoryPage(
            id=uuid.uuid4(),
            story=story,
            page_number=i,
            text_content=f"Page {i} text",
            image_prompt=f"Prompt {i}",
            continuity_notes=f"Continuity {i}",
            image_asset=image_asset,
            status=StoryPageStatus.IMAGE_READY,
        )
        pages.append(page)

    db_session.add_all([user, child, voice_profile, story, job, *image_assets, *pages])
    await db_session.commit()
    return story, job, pages, voice_profile


async def test_audio_generation_success_marks_page_complete(db_session, monkeypatch):
    from app.integrations.elevenlabs import ElevenLabsNarrationAudio

    story, job, pages, _voice_profile = await _setup_narrated_story_with_pages(db_session, page_count=1)

    fake_elevenlabs = FakeElevenLabsClient(
        ElevenLabsNarrationAudio(
            content=b"FAKE_MP3_AUDIO",
            mime_type="audio/mpeg",
            duration_ms=3210,
        )
    )
    fake_r2 = FakeR2Client()

    monkeypatch.setattr("app.workers.audio_worker.get_elevenlabs_client", lambda: fake_elevenlabs)
    monkeypatch.setattr("app.workers.audio_worker.get_r2_client", lambda: fake_r2)

    await run_audio_generation_in_session(
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
    assert refreshed_page.status == StoryPageStatus.COMPLETE
    assert refreshed_page.audio_asset_id is not None
    assert refreshed_page.duration_ms == 3210

    asset = (
        await db_session.execute(
            select(Asset).where(Asset.id == refreshed_page.audio_asset_id)
        )
    ).scalar_one()
    assert asset.asset_type == AssetType.PAGE_AUDIO
    assert asset.mime_type == "audio/mpeg"
    assert asset.upload_status == AssetUploadStatus.READY
    assert asset.duration_ms == 3210

    generation = (
        await db_session.execute(
            select(StoryPageGeneration)
            .where(StoryPageGeneration.story_page_id == pages[0].id)
            .where(StoryPageGeneration.generation_type == GenerationType.AUDIO)
        )
    ).scalar_one()
    assert generation.provider == "elevenlabs"
    assert generation.status == JobStatus.COMPLETED

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
    assert refreshed_job.provider_audio == "elevenlabs"
    assert len(fake_r2.uploads) == 1
    assert fake_r2.uploads[0]["content_type"] == "audio/mpeg"
    assert len(fake_elevenlabs.calls) == 1


async def test_audio_generation_keeps_story_generating_until_all_pages_done(db_session, monkeypatch):
    from app.integrations.elevenlabs import ElevenLabsNarrationAudio

    story, job, pages, _voice_profile = await _setup_narrated_story_with_pages(db_session, page_count=2)

    fake_elevenlabs = FakeElevenLabsClient(
        ElevenLabsNarrationAudio(
            content=b"FAKE_MP3_AUDIO",
            mime_type="audio/mpeg",
            duration_ms=2100,
        )
    )
    fake_r2 = FakeR2Client()

    monkeypatch.setattr("app.workers.audio_worker.get_elevenlabs_client", lambda: fake_elevenlabs)
    monkeypatch.setattr("app.workers.audio_worker.get_r2_client", lambda: fake_r2)

    await run_audio_generation_in_session(
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
    refreshed_job = (
        await db_session.execute(
            select(StoryGenerationJob)
            .where(StoryGenerationJob.id == job.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    other_page = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.id == pages[1].id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()

    assert refreshed_story.status == StoryStatus.GENERATING
    assert refreshed_job.status == JobStatus.RUNNING
    assert other_page.status == StoryPageStatus.IMAGE_READY


async def test_audio_generation_provider_error_marks_story_failed(db_session, monkeypatch):
    from app.integrations.elevenlabs import ElevenLabsError

    story, job, pages, _voice_profile = await _setup_narrated_story_with_pages(db_session, page_count=1)

    fake_elevenlabs = FakeElevenLabsClient(ElevenLabsError("TTS request failed"))
    monkeypatch.setattr("app.workers.audio_worker.get_elevenlabs_client", lambda: fake_elevenlabs)

    await run_audio_generation_in_session(
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

    assert refreshed_page.status == StoryPageStatus.FAILED
    assert refreshed_story.status == StoryStatus.FAILED
    assert refreshed_job.status == JobStatus.FAILED
    assert refreshed_job.error_message == "TTS request failed"


async def test_audio_generation_skips_non_image_ready_page(db_session, monkeypatch):
    from app.integrations.elevenlabs import ElevenLabsNarrationAudio

    story, job, pages, _voice_profile = await _setup_narrated_story_with_pages(db_session, page_count=1)
    pages[0].status = StoryPageStatus.COMPLETE
    await db_session.commit()

    fake_elevenlabs = FakeElevenLabsClient(
        ElevenLabsNarrationAudio(
            content=b"unused",
            mime_type="audio/mpeg",
            duration_ms=1000,
        )
    )
    monkeypatch.setattr("app.workers.audio_worker.get_elevenlabs_client", lambda: fake_elevenlabs)

    await run_audio_generation_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
    )

    assert fake_elevenlabs.calls == []


async def test_audio_generation_failure_cleanup_updates_story_without_relationship_access(db_session):
    story, job, pages, _voice_profile = await _setup_narrated_story_with_pages(db_session, page_count=1)

    await mark_audio_generation_failed_in_session(
        db_session,
        story_page_id=pages[0].id,
        job_id=job.id,
        error_message="cleanup test",
    )

    refreshed_page = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.id == pages[0].id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
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

    assert refreshed_page.status == StoryPageStatus.FAILED
    assert refreshed_story.status == StoryStatus.FAILED
    assert refreshed_job.status == JobStatus.FAILED
    assert refreshed_job.error_message == "cleanup test"
