"""Tests for story creation endpoints and text generation worker."""

import uuid
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.child import Child
from app.models.enums import (
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


async def test_run_text_generation_success(db_session, monkeypatch):
    from app.integrations.anthropic import StoryPageOutput, StoryTextOutput

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
    assert refreshed_story.status == StoryStatus.READY
    assert refreshed_story.title == "Moon Garden"
    assert refreshed_job.status == JobStatus.COMPLETED
    assert len(pages) == 2
    assert pages[0].status == StoryPageStatus.TEXT_READY
    assert len(page_generations) == 2
    assert page_generations[0].generation_type == GenerationType.TEXT
    assert page_generations[0].status == JobStatus.COMPLETED


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
