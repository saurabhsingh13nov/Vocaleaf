"""Tests for voice profile and voice sample endpoints."""

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import get_db
from app.integrations.elevenlabs import ElevenLabsError
from app.integrations.r2 import R2ObjectData, R2ObjectMetadata, R2ObjectNotFoundError
from app.main import app as fastapi_app
from app.models.asset import Asset
from app.models.enums import AssetType, AssetUploadStatus, VoiceProfileStatus, VoiceSampleStatus
from app.models.voice_profile import VoiceProfile
from app.models.voice_sample import VoiceSample
from app.workers.voice_clone_worker import (
    clone_voice_profile_task,
    mark_voice_clone_failed_in_session,
    run_voice_clone,
    run_voice_clone_in_session,
)

REGISTER_URL = "/api/auth/register"
VOICE_PROFILE_URL = "/api/voice-profiles"


class FakeR2Client:
    def __init__(self) -> None:
        self.objects: dict[str, R2ObjectMetadata] = {}
        self.deleted_keys: list[str] = []

    def generate_upload_url(self, *, object_key: str, mime_type: str | None, expires_in: int) -> str:
        return f"https://storage.example/upload/{object_key}?expires={expires_in}"

    def head_object(self, *, object_key: str) -> R2ObjectMetadata:
        if object_key not in self.objects:
            raise R2ObjectNotFoundError("missing object")
        return self.objects[object_key]

    def delete_object(self, *, object_key: str) -> None:
        self.deleted_keys.append(object_key)
        self.objects.pop(object_key, None)

    def download_object(self, *, object_key: str) -> R2ObjectData:
        if object_key not in self.objects:
            raise R2ObjectNotFoundError("missing object")
        return R2ObjectData(content=b"voice-sample", content_type="audio/webm")


async def register_and_get_client(client: AsyncClient, suffix: str = "") -> AsyncClient:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"voice-user{suffix}@example.com",
            "password": "securepass123",
            "full_name": f"Voice User {suffix}",
        },
    )
    return client


async def create_additional_client(db_session) -> AsyncClient:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    return AsyncClient(transport=transport, base_url="https://test")


async def get_voice_profile(db_session, profile_id: str) -> VoiceProfile:
    result = await db_session.execute(
        select(VoiceProfile)
        .where(VoiceProfile.id == uuid.UUID(profile_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_voice_sample(db_session, sample_id: str) -> VoiceSample:
    result = await db_session.execute(
        select(VoiceSample)
        .where(VoiceSample.id == uuid.UUID(sample_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_asset(db_session, asset_id: str) -> Asset:
    result = await db_session.execute(
        select(Asset)
        .where(Asset.id == uuid.UUID(asset_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def create_profile(client: AsyncClient, *, name: str = "Bedtime Voice", default_for_user: bool = False) -> dict:
    resp = await client.post(
        VOICE_PROFILE_URL,
        json={
            "display_name": name,
            "consent_confirmed": True,
            "default_for_user": default_for_user,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_voice_profile_requires_consent(client: AsyncClient):
    await register_and_get_client(client)

    resp = await client.post(
        VOICE_PROFILE_URL,
        json={
            "display_name": "Story Voice",
            "consent_confirmed": False,
        },
    )

    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"].lower()


async def test_create_voice_profile_sets_pending_status(client: AsyncClient, db_session):
    await register_and_get_client(client)

    resp = await client.post(
        VOICE_PROFILE_URL,
        json={
            "display_name": "Story Voice",
            "consent_confirmed": True,
            "default_for_user": True,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["consent_confirmed"] is True
    assert body["default_for_user"] is True
    assert body["samples"] == []

    profile = await get_voice_profile(db_session, body["id"])
    assert profile.status == VoiceProfileStatus.PENDING
    assert profile.source_type == "user_upload"


async def test_create_voice_profile_clears_previous_default(client: AsyncClient, db_session):
    await register_and_get_client(client)
    first = await create_profile(client, name="First Voice", default_for_user=True)
    second = await create_profile(client, name="Second Voice", default_for_user=True)

    first_profile = await get_voice_profile(db_session, first["id"])
    second_profile = await get_voice_profile(db_session, second["id"])

    assert first_profile.default_for_user is False
    assert second_profile.default_for_user is True


async def test_list_voice_profiles_returns_nested_samples(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 2048,
            "duration_seconds": 12.5,
        },
    )
    sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=2048, checksum="sample-1")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample.id}/confirm")

    list_resp = await client.get(VOICE_PROFILE_URL)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]["samples"][0]["status"] == "uploaded"
    assert data[0]["samples"][0]["duration_seconds"] == 12.5


async def test_get_voice_profile_returns_owned_profile(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 2048,
            "duration_seconds": 9.5,
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=2048, checksum="sample-1")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{upload_resp.json()['sample_id']}/confirm")

    resp = await client.get(f"{VOICE_PROFILE_URL}/{profile['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == profile["id"]
    assert body["samples"][0]["status"] == "uploaded"


async def test_create_voice_sample_upload_creates_pending_records(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)

    resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 4096,
            "duration_seconds": 8.2,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["upload_url"].startswith("https://storage.example/upload/")

    sample = await get_voice_sample(db_session, body["sample_id"])
    asset = await get_asset(db_session, body["asset_id"])
    assert sample.status == VoiceSampleStatus.PENDING
    assert sample.duration_seconds == 8.2
    assert asset.asset_type == AssetType.VOICE_SAMPLE
    assert asset.upload_status == AssetUploadStatus.PENDING
    assert asset.duration_ms == 8200
    assert asset.object_key.startswith("voice-samples/")


async def test_create_voice_sample_upload_rejects_invalid_mime_type(client: AsyncClient, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)

    resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "image/png",
            "file_size_bytes": 4096,
            "duration_seconds": 8.2,
        },
    )

    assert resp.status_code == 400


async def test_create_voice_sample_upload_accepts_codec_parameterized_webm(
    client: AsyncClient, db_session, monkeypatch
):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)

    resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm;codecs=opus",
            "file_size_bytes": 4096,
            "duration_seconds": 8.2,
        },
    )

    assert resp.status_code == 201
    asset = await get_asset(db_session, resp.json()["asset_id"])
    assert asset.mime_type == "audio/webm"


async def test_confirm_voice_sample_upload_marks_sample_uploaded(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.4,
        },
    )
    body = upload_resp.json()
    sample = await get_voice_sample(db_session, body["sample_id"])
    asset = await get_asset(db_session, body["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1111, checksum="etag-voice")

    confirm_resp = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample.id}/confirm")
    assert confirm_resp.status_code == 200
    confirm_body = confirm_resp.json()
    assert confirm_body["status"] == "uploaded"

    refreshed_sample = await get_voice_sample(db_session, body["sample_id"])
    refreshed_asset = await get_asset(db_session, body["asset_id"])
    assert refreshed_sample.status == VoiceSampleStatus.UPLOADED
    assert refreshed_asset.upload_status == AssetUploadStatus.READY
    assert refreshed_asset.file_size_bytes == 1111
    assert refreshed_asset.checksum == "etag-voice"


async def test_only_owner_can_create_and_confirm_voice_samples(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client, suffix="A")
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 4096,
            "duration_seconds": 4.0,
        },
    )
    sample_id = upload_resp.json()["sample_id"]
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=100, checksum="etag-2")

    client_b = await create_additional_client(db_session)
    try:
        await register_and_get_client(client_b, suffix="B")

        create_resp = await client_b.post(
            f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
            json={
                "mime_type": "audio/webm",
                "file_size_bytes": 4096,
                "duration_seconds": 4.0,
            },
        )
        assert create_resp.status_code == 404

        confirm_resp = await client_b.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample_id}/confirm")
        assert confirm_resp.status_code == 404
    finally:
        await client_b.aclose()
        fastapi_app.dependency_overrides.clear()


async def test_delete_pending_voice_sample_removes_sample_and_asset(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 4096,
            "duration_seconds": 4.0,
        },
    )

    sample_id = upload_resp.json()["sample_id"]
    asset_id = upload_resp.json()["asset_id"]
    asset = await get_asset(db_session, asset_id)

    resp = await client.delete(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample_id}")
    assert resp.status_code == 204
    assert asset.object_key in fake_r2.deleted_keys

    sample_result = await db_session.execute(select(VoiceSample).where(VoiceSample.id == uuid.UUID(sample_id)))
    asset_result = await db_session.execute(select(Asset).where(Asset.id == uuid.UUID(asset_id)))
    assert sample_result.scalar_one_or_none() is None
    assert asset_result.scalar_one_or_none() is None


async def test_clone_voice_profile_marks_processing_and_enqueues_task(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    task_calls: list[str] = []
    monkeypatch.setattr(
        "app.workers.voice_clone_worker.clone_voice_profile_task.delay",
        lambda profile_id: task_calls.append(profile_id),
    )

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.1,
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-clone")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{upload_resp.json()['sample_id']}/confirm")

    resp = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/clone")

    assert resp.status_code == 202
    assert resp.json()["status"] == "processing"
    assert task_calls == [profile["id"]]

    refreshed_profile = await get_voice_profile(db_session, profile["id"])
    assert refreshed_profile.status == VoiceProfileStatus.PROCESSING


async def test_clone_voice_profile_requires_uploaded_sample(client: AsyncClient, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)
    monkeypatch.setattr(
        "app.workers.voice_clone_worker.clone_voice_profile_task.delay",
        lambda profile_id: None,
    )

    await register_and_get_client(client)
    profile = await create_profile(client)

    resp = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/clone")

    assert resp.status_code == 400
    assert "confirmed voice sample" in resp.json()["detail"].lower()


async def test_clone_voice_profile_is_idempotent_while_processing(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    task_calls: list[str] = []
    monkeypatch.setattr(
        "app.workers.voice_clone_worker.clone_voice_profile_task.delay",
        lambda profile_id: task_calls.append(profile_id),
    )

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.1,
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-clone")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{upload_resp.json()['sample_id']}/confirm")

    first = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/clone")
    second = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/clone")

    assert first.status_code == 202
    assert second.status_code == 202
    assert task_calls == [profile["id"]]


async def test_clone_voice_profile_rejects_ready_profile(client: AsyncClient, db_session, monkeypatch):
    await register_and_get_client(client)
    profile = await create_profile(client)

    voice_profile = await get_voice_profile(db_session, profile["id"])
    voice_profile.status = VoiceProfileStatus.READY
    voice_profile.provider = "elevenlabs"
    voice_profile.provider_voice_id = "voice_ready_123"
    await db_session.commit()

    resp = await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/clone")

    assert resp.status_code == 409


async def test_run_voice_clone_sets_profile_ready_and_marks_samples_accepted(
    client: AsyncClient, db_session, monkeypatch
):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.workers.voice_clone_worker.get_r2_client", lambda: fake_r2)
    monkeypatch.setattr(
        "app.workers.voice_clone_worker.get_elevenlabs_client",
        lambda: SimpleNamespace(clone_voice=lambda display_name, samples: SimpleNamespace(voice_id="voice_123")),
    )

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.1,
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-clone")
    sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    asset.upload_status = AssetUploadStatus.READY
    sample.status = VoiceSampleStatus.UPLOADED
    await db_session.commit()

    await run_voice_clone_in_session(db_session, uuid.UUID(profile["id"]))

    refreshed_profile = await get_voice_profile(db_session, profile["id"])
    refreshed_sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    assert refreshed_profile.status == VoiceProfileStatus.READY
    assert refreshed_profile.provider == "elevenlabs"
    assert refreshed_profile.provider_voice_id == "voice_123"
    assert refreshed_sample.status == VoiceSampleStatus.ACCEPTED


async def test_run_voice_clone_marks_failed_and_restores_samples_on_provider_error(
    client: AsyncClient, db_session, monkeypatch
):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.workers.voice_clone_worker.get_r2_client", lambda: fake_r2)

    def raise_clone_error(*, display_name, samples):
        raise ElevenLabsError("provider unavailable")

    monkeypatch.setattr(
        "app.workers.voice_clone_worker.get_elevenlabs_client",
        lambda: SimpleNamespace(clone_voice=raise_clone_error),
    )

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.1,
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-clone")
    sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    asset.upload_status = AssetUploadStatus.READY
    sample.status = VoiceSampleStatus.UPLOADED
    await db_session.commit()

    await run_voice_clone_in_session(db_session, uuid.UUID(profile["id"]))

    refreshed_profile = await get_voice_profile(db_session, profile["id"])
    refreshed_sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    assert refreshed_profile.status == VoiceProfileStatus.FAILED
    assert refreshed_sample.status == VoiceSampleStatus.UPLOADED


async def test_mark_voice_clone_failed_in_session_restores_processing_samples(
    client: AsyncClient, db_session, monkeypatch
):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 5.1,
        },
    )
    sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])

    profile_model = await get_voice_profile(db_session, profile["id"])
    profile_model.status = VoiceProfileStatus.PROCESSING
    sample.status = VoiceSampleStatus.PROCESSING
    await db_session.commit()

    await mark_voice_clone_failed_in_session(db_session, uuid.UUID(profile["id"]))

    refreshed_profile = await get_voice_profile(db_session, profile["id"])
    refreshed_sample = await get_voice_sample(db_session, upload_resp.json()["sample_id"])
    assert refreshed_profile.status == VoiceProfileStatus.FAILED
    assert refreshed_sample.status == VoiceSampleStatus.UPLOADED


def test_clone_voice_profile_task_marks_failed_on_unexpected_error(monkeypatch):
    cleanup_calls: list[uuid.UUID] = []

    async def raise_unexpected(profile_id: uuid.UUID) -> None:
        raise RuntimeError("unexpected failure")

    async def record_cleanup(profile_id: uuid.UUID) -> None:
        cleanup_calls.append(profile_id)

    monkeypatch.setattr("app.workers.voice_clone_worker.run_voice_clone", raise_unexpected)
    monkeypatch.setattr("app.workers.voice_clone_worker.mark_voice_clone_failed", record_cleanup)

    profile_id = str(uuid.uuid4())
    with pytest.raises(RuntimeError, match="unexpected failure"):
        clone_voice_profile_task(profile_id)

    assert cleanup_calls == [uuid.UUID(profile_id)]


async def test_delete_uploaded_voice_sample_succeeds_when_object_missing(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 3.5,
        },
    )
    sample_id = upload_resp.json()["sample_id"]
    asset_id = upload_resp.json()["asset_id"]
    asset = await get_asset(db_session, asset_id)
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-delete")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample_id}/confirm")

    fake_r2.objects.pop(asset.object_key, None)
    resp = await client.delete(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{sample_id}")
    assert resp.status_code == 204

    sample_result = await db_session.execute(select(VoiceSample).where(VoiceSample.id == uuid.UUID(sample_id)))
    asset_result = await db_session.execute(select(Asset).where(Asset.id == uuid.UUID(asset_id)))
    assert sample_result.scalar_one_or_none() is None
    assert asset_result.scalar_one_or_none() is None


async def test_delete_voice_profile_cascades_samples_and_assets(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    profile = await create_profile(client)

    first_upload = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 1024,
            "duration_seconds": 3.7,
        },
    )
    second_upload = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 2048,
            "duration_seconds": 3.9,
        },
    )

    first_asset = await get_asset(db_session, first_upload.json()["asset_id"])
    second_asset = await get_asset(db_session, second_upload.json()["asset_id"])
    fake_r2.objects[first_asset.object_key] = R2ObjectMetadata(file_size_bytes=1024, checksum="etag-1")
    fake_r2.objects[second_asset.object_key] = R2ObjectMetadata(file_size_bytes=2048, checksum="etag-2")
    await client.post(f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{first_upload.json()['sample_id']}/confirm")

    resp = await client.delete(f"{VOICE_PROFILE_URL}/{profile['id']}")
    assert resp.status_code == 204
    assert first_asset.object_key in fake_r2.deleted_keys
    assert second_asset.object_key in fake_r2.deleted_keys

    profile_result = await db_session.execute(select(VoiceProfile).where(VoiceProfile.id == uuid.UUID(profile["id"])))
    sample_result = await db_session.execute(
        select(VoiceSample).where(VoiceSample.voice_profile_id == uuid.UUID(profile["id"]))
    )
    asset_result = await db_session.execute(
        select(Asset).where(Asset.id.in_([uuid.UUID(first_upload.json()["asset_id"]), uuid.UUID(second_upload.json()["asset_id"])]))
    )
    assert profile_result.scalar_one_or_none() is None
    assert list(sample_result.scalars().all()) == []
    assert list(asset_result.scalars().all()) == []


async def test_only_owner_can_delete_voice_profile_and_sample(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.voice.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client, suffix="A")
    profile = await create_profile(client)
    upload_resp = await client.post(
        f"{VOICE_PROFILE_URL}/{profile['id']}/samples",
        json={
            "mime_type": "audio/webm",
            "file_size_bytes": 4096,
            "duration_seconds": 4.0,
        },
    )

    client_b = await create_additional_client(db_session)
    try:
        await register_and_get_client(client_b, suffix="B")

        sample_delete_resp = await client_b.delete(
            f"{VOICE_PROFILE_URL}/{profile['id']}/samples/{upload_resp.json()['sample_id']}"
        )
        profile_delete_resp = await client_b.delete(f"{VOICE_PROFILE_URL}/{profile['id']}")

        assert sample_delete_resp.status_code == 404
        assert profile_delete_resp.status_code == 404
    finally:
        await client_b.aclose()
        fastapi_app.dependency_overrides.clear()
