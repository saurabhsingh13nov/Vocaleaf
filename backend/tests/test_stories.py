"""Tests for story creation endpoints and text generation worker."""

import uuid
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app as fastapi_app
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
from app.models.user import User
from app.models.voice_profile import VoiceProfile
from app.workers.text_worker import run_text_generation_in_session

REGISTER_URL = "/api/auth/register"
CHILDREN_URL = "/api/children"
STORIES_URL = "/api/stories"


class FakeAnthropicClient:
    def __init__(self, output):
        self.output = output
        self.calls: list[dict] = []

    def generate_story_text(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class FakeDownloadClient:
    def generate_download_url(self, *, object_key: str, expires_in: int) -> str:
        return f"https://storage.example/download/{object_key}?expires={expires_in}"


async def register_and_get_client(client: AsyncClient, suffix: str = "") -> AsyncClient:
    response = await client.post(
        REGISTER_URL,
        json={
            "email": f"story-user{suffix}@example.com",
            "password": "securepass123",
            "full_name": f"Story User {suffix}",
        },
    )
    assert response.status_code == 201
    return client


async def create_child(client: AsyncClient, name: str = "Luna", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    response = await client.post(CHILDREN_URL, json=payload)
    assert response.status_code == 201
    return response.json()


async def create_additional_client(db_session) -> AsyncClient:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    return AsyncClient(transport=transport, base_url="https://test")


async def get_user_by_email(db_session, email: str) -> User:
    result = await db_session.execute(select(User).where(User.primary_email == email))
    return result.scalar_one()


async def get_story(db_session, story_id: str) -> Story:
    result = await db_session.execute(
        select(Story)
        .where(Story.id == uuid.UUID(story_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_job_for_story(db_session, story_id: str) -> StoryGenerationJob:
    result = await db_session.execute(
        select(StoryGenerationJob)
        .where(StoryGenerationJob.story_id == uuid.UUID(story_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def test_create_story_success(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client)
    child = await create_child(client, name="Luna", age=5)

    response = await client.post(
        STORIES_URL,
        json={
            "child_id": child["id"],
            "prompt": "A lantern walk through the moonlit woods",
            "theme": "Bedtime",
            "target_page_count": 6,
            "reading_level": "Preschool",
            "art_style": "Dreamy",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "generating"
    assert body["child_id"] == child["id"]
    assert body["pages"] == []

    story = await get_story(db_session, body["id"])
    job = await get_job_for_story(db_session, body["id"])
    assert story.status == StoryStatus.GENERATING
    assert job.status == JobStatus.PENDING
    assert job.provider_text == "anthropic"


async def test_create_story_requires_prompt_or_theme(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client)
    child = await create_child(client, name="Luna")

    response = await client.post(
        STORIES_URL,
        json={
            "child_id": child["id"],
            "prompt": "   ",
            "theme": "   ",
        },
    )

    assert response.status_code == 400
    assert "prompt or theme" in response.json()["detail"].lower()


async def test_create_story_validates_page_count_bounds(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client)
    child = await create_child(client, name="Luna")

    too_small = await client.post(
        STORIES_URL,
        json={
            "child_id": child["id"],
            "prompt": "A mountain picnic",
            "target_page_count": 1,
        },
    )
    assert too_small.status_code == 422

    too_large = await client.post(
        STORIES_URL,
        json={
            "child_id": child["id"],
            "prompt": "A mountain picnic",
            "target_page_count": 11,
        },
    )
    assert too_large.status_code == 422


async def test_create_story_rejects_other_users_child(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client, suffix="A")
    child = await create_child(client, name="Luna")

    async with await create_additional_client(db_session) as client_b:
        await register_and_get_client(client_b, suffix="B")
        response = await client_b.post(
            STORIES_URL,
            json={
                "child_id": child["id"],
                "prompt": "A mountain picnic",
            },
        )

    assert response.status_code == 404


async def test_create_story_rejects_non_ready_voice_profile(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client)
    child = await create_child(client, name="Luna")
    user = await get_user_by_email(db_session, "story-user@example.com")

    profile = VoiceProfile(
        user_id=user.id,
        display_name="Not Ready",
        status=VoiceProfileStatus.PENDING,
        consent_confirmed=True,
        source_type="user_upload",
    )
    db_session.add(profile)
    await db_session.commit()

    response = await client.post(
        STORIES_URL,
        json={
            "child_id": child["id"],
            "prompt": "A mountain picnic",
            "voice_profile_id": str(profile.id),
        },
    )

    assert response.status_code == 400
    assert "must be ready" in response.json()["detail"].lower()


async def test_list_stories_only_returns_current_user(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.workers.text_worker.generate_story_text_task.delay",
        lambda story_id, job_id: None,
    )

    await register_and_get_client(client, suffix="A")
    child_a = await create_child(client, name="Luna")
    await client.post(STORIES_URL, json={"child_id": child_a["id"], "prompt": "Story A"})

    async with await create_additional_client(db_session) as client_b:
        await register_and_get_client(client_b, suffix="B")
        child_b = await create_child(client_b, name="Max")
        await client_b.post(STORIES_URL, json={"child_id": child_b["id"], "prompt": "Story B"})

        response_b = await client_b.get(STORIES_URL)
        assert response_b.status_code == 200
        assert len(response_b.json()) == 1
        assert response_b.json()[0]["child_id"] == child_b["id"]

    response_a = await client.get(STORIES_URL)
    assert response_a.status_code == 200
    assert len(response_a.json()) == 1
    assert response_a.json()[0]["child_id"] == child_a["id"]


async def test_get_story_detail_returns_pages_in_order(client: AsyncClient, db_session):
    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(
        user_id=user.id,
        name="Luna",
        age=5,
    )
    story = Story(
        user_id=user.id,
        child=child,
        title="Moonlight Lantern",
        prompt="A lantern walk",
        status=StoryStatus.READY,
        target_page_count=2,
        language="en",
    )
    page_two = StoryPage(
        story=story,
        page_number=2,
        text_content="Second page",
        image_prompt="Second prompt",
        continuity_notes="Second notes",
        status=StoryPageStatus.TEXT_READY,
    )
    page_one = StoryPage(
        story=story,
        page_number=1,
        text_content="First page",
        image_prompt="First prompt",
        continuity_notes="First notes",
        status=StoryPageStatus.TEXT_READY,
    )
    db_session.add_all([user, child, story, page_two, page_one])
    await db_session.commit()

    response = await client.get(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 200
    body = response.json()
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert body["title"] == "Moonlight Lantern"
    assert body["pages"][0]["image_url"] is None
    assert body["pages"][0]["audio_url"] is None


async def test_get_story_detail_include_urls_inlines_signed_media(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: FakeDownloadClient())

    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    image_asset = Asset(
        user_id=user.id,
        storage_provider="r2",
        bucket_name="bucket",
        object_key=f"stories/{user.id}/page-images/image-asset",
        asset_type=AssetType.PAGE_IMAGE,
        upload_status=AssetUploadStatus.READY,
        is_private=True,
    )
    audio_asset = Asset(
        user_id=user.id,
        storage_provider="r2",
        bucket_name="bucket",
        object_key=f"stories/{user.id}/page-audio/audio-asset",
        asset_type=AssetType.PAGE_AUDIO,
        upload_status=AssetUploadStatus.READY,
        is_private=True,
    )
    story = Story(
        user_id=user.id,
        child=child,
        title="Moonlight Lantern",
        prompt="A lantern walk",
        status=StoryStatus.READY,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user, child, image_asset, audio_asset, story])
    await db_session.flush()

    page = StoryPage(
        story=story,
        page_number=1,
        text_content="First page",
        image_prompt="First prompt",
        continuity_notes="First notes",
        status=StoryPageStatus.COMPLETE,
        image_asset_id=image_asset.id,
        audio_asset_id=audio_asset.id,
    )
    db_session.add(page)
    await db_session.commit()

    response = await client.get(f"{STORIES_URL}/{story.id}?include_urls=true")

    assert response.status_code == 200
    body = response.json()
    assert body["pages"][0]["image_url"].startswith("https://storage.example/download/")
    assert body["pages"][0]["audio_url"].startswith("https://storage.example/download/")
    assert body["pages"][0]["image_url_expires_at"] is not None
    assert body["pages"][0]["audio_url_expires_at"] is not None


async def test_get_story_detail_returns_404_for_other_user(client: AsyncClient, db_session):
    await register_and_get_client(client, suffix="a")
    user_a = await get_user_by_email(db_session, "story-usera@example.com")
    child = Child(user_id=user_a.id, name="Luna", age=5)
    story = Story(
        user_id=user_a.id,
        child=child,
        title="Secret Story",
        prompt="A quiet night",
        status=StoryStatus.READY,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user_a, child, story])
    await db_session.commit()

    async with await create_additional_client(db_session) as client_b:
        await register_and_get_client(client_b, suffix="b")
        response = await client_b.get(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 404


async def test_delete_failed_story_success(client: AsyncClient, db_session):
    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    story = Story(
        user_id=user.id,
        child=child,
        title="Broken Story",
        prompt="A quiet night",
        status=StoryStatus.FAILED,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user, child, story])
    await db_session.commit()

    response = await client.delete(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 204

    list_response = await client.get(STORIES_URL)
    assert list_response.status_code == 200
    assert list_response.json() == []

    detail_response = await client.get(f"{STORIES_URL}/{story.id}")
    assert detail_response.status_code == 404

    refreshed_story = await get_story(db_session, str(story.id))
    assert refreshed_story.status == StoryStatus.DELETED


async def test_delete_failed_story_returns_404_for_other_user(client: AsyncClient, db_session):
    await register_and_get_client(client, suffix="a")
    user_a = await get_user_by_email(db_session, "story-usera@example.com")
    child = Child(user_id=user_a.id, name="Luna", age=5)
    story = Story(
        user_id=user_a.id,
        child=child,
        title="Secret Story",
        prompt="A quiet night",
        status=StoryStatus.FAILED,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user_a, child, story])
    await db_session.commit()

    async with await create_additional_client(db_session) as client_b:
        await register_and_get_client(client_b, suffix="b")
        response = await client_b.delete(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 404


async def test_delete_ready_story_success(client: AsyncClient, db_session):
    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    story = Story(
        user_id=user.id,
        child=child,
        title="Ready Story",
        prompt="A quiet night",
        status=StoryStatus.READY,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user, child, story])
    await db_session.commit()

    response = await client.delete(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 204

    detail_response = await client.get(f"{STORIES_URL}/{story.id}")
    assert detail_response.status_code == 404


async def test_delete_generating_story_success(client: AsyncClient, db_session):
    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    story = Story(
        user_id=user.id,
        child=child,
        title="In Progress Story",
        prompt="A quiet night",
        status=StoryStatus.GENERATING,
        target_page_count=1,
        language="en",
    )
    db_session.add_all([user, child, story])
    await db_session.commit()

    response = await client.delete(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 204

    detail_response = await client.get(f"{STORIES_URL}/{story.id}")
    assert detail_response.status_code == 404


async def test_story_detail_includes_retry_metadata_for_failed_outputs(client: AsyncClient, db_session):
    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    voice_profile = VoiceProfile(
        user_id=user.id,
        display_name="Story Voice",
        status=VoiceProfileStatus.READY,
        consent_confirmed=True,
        source_type="user_upload",
        provider="elevenlabs",
        provider_voice_id="voice_123",
    )
    story = Story(
        user_id=user.id,
        child=child,
        voice_profile=voice_profile,
        title="Broken Story",
        prompt="A quiet night",
        status=StoryStatus.FAILED,
        target_page_count=2,
        language="en",
    )
    job = StoryGenerationJob(
        story=story,
        job_type="full_generation",
        status=JobStatus.FAILED,
        provider_text="anthropic",
        provider_image="google_gemini_image",
        provider_audio="elevenlabs",
        error_message="Generation failed",
    )
    page = StoryPage(
        story=story,
        page_number=1,
        text_content="The lantern glowed softly.",
        image_prompt="A glowing lantern by a forest path",
        continuity_notes="Keep the fox scarf visible.",
        status=StoryPageStatus.FAILED,
    )
    image_generation = StoryPageGeneration(
        story_page=page,
        generation_job=job,
        generation_type=GenerationType.IMAGE,
        provider="google_gemini_image",
        status=JobStatus.FAILED,
        response_payload_json={"error_message": "Gemini image generation returned no images."},
    )
    db_session.add_all([user, child, voice_profile, story, job, page, image_generation])
    await db_session.commit()

    response = await client.get(f"{STORIES_URL}/{story.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["can_resume_missing_outputs"] is True
    assert body["pages"][0]["retryable_outputs"] == ["image"]
    assert body["pages"][0]["output_errors"] == {"image": "Gemini image generation returned no images."}


async def test_retry_story_missing_outputs_enqueues_only_missing_work(client: AsyncClient, db_session, monkeypatch):
    image_task_calls: list[tuple[str, str]] = []
    audio_task_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.workers.image_worker.generate_page_image_task.delay",
        lambda page_id, job_id: image_task_calls.append((page_id, job_id)),
    )
    monkeypatch.setattr(
        "app.workers.audio_worker.generate_page_audio_task.delay",
        lambda page_id, job_id: audio_task_calls.append((page_id, job_id)),
    )

    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    voice_profile = VoiceProfile(
        user_id=user.id,
        display_name="Story Voice",
        status=VoiceProfileStatus.READY,
        consent_confirmed=True,
        source_type="user_upload",
        provider="elevenlabs",
        provider_voice_id="voice_123",
    )
    story = Story(
        user_id=user.id,
        child=child,
        voice_profile=voice_profile,
        title="Broken Story",
        prompt="A quiet night",
        status=StoryStatus.FAILED,
        target_page_count=2,
        language="en",
    )
    original_job = StoryGenerationJob(
        story=story,
        job_type="full_generation",
        status=JobStatus.FAILED,
        provider_text="anthropic",
        provider_image="google_gemini_image",
        provider_audio="elevenlabs",
        error_message="Generation failed",
    )
    image_asset = Asset(
        user_id=user.id,
        storage_provider="r2",
        bucket_name="storybook",
        object_key=f"stories/{user.id}/existing-page-2.png",
        asset_type=AssetType.PAGE_IMAGE,
        mime_type="image/png",
        file_size_bytes=2048,
        checksum="existing-page-2",
        is_private=True,
        upload_status=AssetUploadStatus.READY,
    )
    image_failed_page = StoryPage(
        story=story,
        page_number=1,
        text_content="The lantern glowed softly.",
        image_prompt="A glowing lantern by a forest path",
        continuity_notes="Keep the fox scarf visible.",
        status=StoryPageStatus.FAILED,
    )
    audio_failed_page = StoryPage(
        story=story,
        page_number=2,
        text_content="The owl listened to the wind.",
        image_prompt="A sleepy owl beside a silver pond",
        continuity_notes="Keep the silver pond visible.",
        status=StoryPageStatus.FAILED,
        image_asset=image_asset,
    )
    db_session.add_all([user, child, voice_profile, story, original_job, image_asset, image_failed_page, audio_failed_page])
    await db_session.commit()

    response = await client.post(f"{STORIES_URL}/{story.id}/retry-missing")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "generating"
    assert body["can_resume_missing_outputs"] is False
    assert len(image_task_calls) == 1
    assert len(audio_task_calls) == 1
    assert image_task_calls[0][0] == str(image_failed_page.id)
    assert audio_task_calls[0][0] == str(audio_failed_page.id)
    assert image_task_calls[0][1] == audio_task_calls[0][1]

    refreshed_story = await get_story(db_session, str(story.id))
    retry_jobs = (
        await db_session.execute(
            select(StoryGenerationJob)
            .where(StoryGenerationJob.story_id == story.id)
            .order_by(StoryGenerationJob.created_at.asc())
        )
    ).scalars().all()
    assert refreshed_story.status == StoryStatus.GENERATING
    assert len(retry_jobs) == 2
    assert retry_jobs[-1].job_type == "retry_missing_outputs"
    assert retry_jobs[-1].provider_image == "google_gemini_image"
    assert retry_jobs[-1].provider_audio == "elevenlabs"

    refreshed_pages = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.story_id == story.id)
            .order_by(StoryPage.page_number.asc())
        )
    ).scalars().all()
    assert refreshed_pages[0].status == StoryPageStatus.TEXT_READY
    assert refreshed_pages[1].status == StoryPageStatus.IMAGE_READY


async def test_retry_story_page_missing_outputs_only_affects_selected_page(client: AsyncClient, db_session, monkeypatch):
    image_task_calls: list[tuple[str, str]] = []
    audio_task_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.workers.image_worker.generate_page_image_task.delay",
        lambda page_id, job_id: image_task_calls.append((page_id, job_id)),
    )
    monkeypatch.setattr(
        "app.workers.audio_worker.generate_page_audio_task.delay",
        lambda page_id, job_id: audio_task_calls.append((page_id, job_id)),
    )

    await register_and_get_client(client)
    user = await get_user_by_email(db_session, "story-user@example.com")
    child = Child(user_id=user.id, name="Luna", age=5)
    voice_profile = VoiceProfile(
        user_id=user.id,
        display_name="Story Voice",
        status=VoiceProfileStatus.READY,
        consent_confirmed=True,
        source_type="user_upload",
        provider="elevenlabs",
        provider_voice_id="voice_123",
    )
    story = Story(
        user_id=user.id,
        child=child,
        voice_profile=voice_profile,
        title="Broken Story",
        prompt="A quiet night",
        status=StoryStatus.FAILED,
        target_page_count=2,
        language="en",
    )
    original_job = StoryGenerationJob(
        story=story,
        job_type="full_generation",
        status=JobStatus.FAILED,
        provider_text="anthropic",
        provider_image="google_gemini_image",
        provider_audio="elevenlabs",
        error_message="Generation failed",
    )
    image_asset = Asset(
        user_id=user.id,
        storage_provider="r2",
        bucket_name="storybook",
        object_key=f"stories/{user.id}/existing-page-1.png",
        asset_type=AssetType.PAGE_IMAGE,
        mime_type="image/png",
        file_size_bytes=2048,
        checksum="existing-page-1",
        is_private=True,
        upload_status=AssetUploadStatus.READY,
    )
    page_one = StoryPage(
        story=story,
        page_number=1,
        text_content="The lantern glowed softly.",
        image_prompt="A glowing lantern by a forest path",
        continuity_notes="Keep the fox scarf visible.",
        status=StoryPageStatus.FAILED,
        image_asset=image_asset,
    )
    page_two = StoryPage(
        story=story,
        page_number=2,
        text_content="The owl listened to the wind.",
        image_prompt="A sleepy owl beside a silver pond",
        continuity_notes="Keep the silver pond visible.",
        status=StoryPageStatus.FAILED,
    )
    db_session.add_all([user, child, voice_profile, story, original_job, image_asset, page_one, page_two])
    await db_session.commit()

    response = await client.post(f"{STORIES_URL}/{story.id}/pages/{page_one.id}/retry-missing")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "generating"
    assert len(audio_task_calls) == 1
    assert audio_task_calls[0][0] == str(page_one.id)
    assert image_task_calls == []

    refreshed_pages = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.story_id == story.id)
            .order_by(StoryPage.page_number.asc())
        )
    ).scalars().all()
    assert refreshed_pages[0].status == StoryPageStatus.IMAGE_READY
    assert refreshed_pages[1].status == StoryPageStatus.FAILED


async def test_run_text_generation_success(db_session, monkeypatch):
    from app.integrations.anthropic import StoryPageOutput, StoryTextOutput

    # Mock image task dispatch so it doesn't actually run
    image_task_calls = []
    monkeypatch.setattr(
        "app.workers.image_worker.generate_page_image_task.delay",
        lambda page_id, job_id: image_task_calls.append((page_id, job_id)),
    )

    user = User(
        id=uuid.uuid4(),
        primary_email="worker@example.com",
        full_name="Worker User",
        status=UserStatus.ACTIVE,
    )
    child = Child(
        id=uuid.uuid4(),
        user=user,
        name="Luna",
        age=5,
        favorite_themes={"favorite": "space"},
        favorite_characters={"hero": "Milo"},
        bedtime_preferences={"pace": "calm"},
    )
    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        child=child,
        prompt="A moon garden adventure",
        theme="Bedtime",
        status=StoryStatus.GENERATING,
        target_page_count=2,
        reading_level="Preschool",
        language="en",
        art_style="Dreamy",
        generation_version="phase-9-text-v1",
    )
    job = StoryGenerationJob(
        id=uuid.uuid4(),
        story=story,
        job_type="full_generation",
        status=JobStatus.PENDING,
        provider_text="anthropic",
    )
    db_session.add_all([user, child, story, job])
    await db_session.commit()

    fake_client = FakeAnthropicClient(
        StoryTextOutput(
            title="Moon Garden",
            pages=[
                StoryPageOutput(
                    page_number=1,
                    text_content="Luna tiptoed into the moon garden.",
                    image_prompt="A moonlit garden with silver flowers",
                    continuity_notes="Keep the lantern and silver flowers on later pages.",
                ),
                StoryPageOutput(
                    page_number=2,
                    text_content="She followed the glow to a sleepy owl.",
                    image_prompt="A sleepy owl beside a glowing pond",
                    continuity_notes="The owl should appear gentle and glowing.",
                ),
            ],
        )
    )
    monkeypatch.setattr("app.workers.text_worker.get_anthropic_client", lambda: fake_client)

    await run_text_generation_in_session(
        db_session,
        story_id=story.id,
        job_id=job.id,
    )

    refreshed_story = await get_story(db_session, str(story.id))
    refreshed_job = await get_job_for_story(db_session, str(story.id))
    pages = (
        await db_session.execute(
            select(StoryPage)
            .where(StoryPage.story_id == story.id)
            .order_by(StoryPage.page_number.asc())
        )
    ).scalars().all()
    page_generations = (
        await db_session.execute(
            select(StoryPageGeneration).where(StoryPageGeneration.generation_job_id == job.id)
        )
    ).scalars().all()

    assert fake_client.calls
    # Story stays GENERATING while images are being generated
    assert refreshed_story.status == StoryStatus.GENERATING
    assert refreshed_story.title == "Moon Garden"
    assert refreshed_job.provider_image == "google_gemini_image"
    assert len(pages) == 2
    assert pages[0].status == StoryPageStatus.TEXT_READY
    assert len(page_generations) == 2
    assert page_generations[0].generation_type == GenerationType.TEXT
    assert page_generations[0].status == JobStatus.COMPLETED
    # Image tasks were enqueued for each page
    assert len(image_task_calls) == 2


async def test_run_text_generation_marks_story_failed(db_session, monkeypatch):
    from app.integrations.anthropic import AnthropicError

    user = User(
        id=uuid.uuid4(),
        primary_email="worker-failure@example.com",
        full_name="Worker Failure",
        status=UserStatus.ACTIVE,
    )
    child = Child(id=uuid.uuid4(), user=user, name="Luna", age=5)
    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        child=child,
        prompt="A moon garden adventure",
        status=StoryStatus.GENERATING,
        target_page_count=2,
        language="en",
    )
    job = StoryGenerationJob(
        id=uuid.uuid4(),
        story=story,
        job_type="full_generation",
        status=JobStatus.PENDING,
        provider_text="anthropic",
    )
    db_session.add_all([user, child, story, job])
    await db_session.commit()

    monkeypatch.setattr(
        "app.workers.text_worker.get_anthropic_client",
        lambda: FakeAnthropicClient(AnthropicError("Claude request failed")),
    )

    await run_text_generation_in_session(
        db_session,
        story_id=story.id,
        job_id=job.id,
    )

    refreshed_story = await get_story(db_session, str(story.id))
    refreshed_job = await get_job_for_story(db_session, str(story.id))
    pages = (
        await db_session.execute(select(StoryPage).where(StoryPage.story_id == story.id))
    ).scalars().all()

    assert refreshed_story.status == StoryStatus.FAILED
    assert refreshed_job.status == JobStatus.FAILED
    assert refreshed_job.error_message == "Claude request failed"
    assert pages == []


async def test_run_text_generation_missing_story_is_graceful(db_session, monkeypatch):
    fake_client = FakeAnthropicClient(
        SimpleNamespace(
            title="Unused",
            pages=[],
        )
    )
    monkeypatch.setattr("app.workers.text_worker.get_anthropic_client", lambda: fake_client)

    await run_text_generation_in_session(
        db_session,
        story_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
    )

    assert fake_client.calls == []


def test_anthropic_client_normalizes_authentication_failures(monkeypatch):
    from app.integrations.anthropic import AnthropicClient, AnthropicError

    class FakeMessages:
        def create(self, **kwargs):
            raise Exception(
                "Error code: 401 - {'type': 'error', 'error': "
                "{'type': 'authentication_error', 'message': 'invalid x-api-key'}}"
            )

    class FakeSdkClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr("app.integrations.anthropic._get_sdk_client_class", lambda: FakeSdkClient)

    client = AnthropicClient(api_key="bad-key", model="test-model")

    try:
        client.generate_story_text(
            child_name="Luna",
            child_age=5,
            favorite_themes=None,
            favorite_characters=None,
            bedtime_preferences=None,
            prompt="A moon garden adventure",
            theme="Bedtime",
            art_style="Dreamy",
            page_count=2,
            reading_level="Preschool",
            language="en",
        )
    except AnthropicError as exc:
        assert str(exc) == (
            "Anthropic authentication failed. "
            "Update ANTHROPIC_API_KEY and restart the backend and worker."
        )
    else:  # pragma: no cover - defensive failure path
        raise AssertionError("Expected AnthropicError")
