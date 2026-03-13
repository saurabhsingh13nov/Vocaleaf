"""Tests for asset signed upload and read endpoints."""

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.integrations.r2 import R2ObjectMetadata, R2ObjectNotFoundError
from app.main import app as fastapi_app
from app.db.session import get_db
from app.models.asset import Asset
from app.models.enums import AssetType, AssetUploadStatus

REGISTER_URL = "/api/auth/register"
UPLOAD_URL = "/api/assets/upload-url"


class FakeR2Client:
    def __init__(self) -> None:
        self.objects: dict[str, R2ObjectMetadata] = {}

    def generate_upload_url(self, *, object_key: str, mime_type: str | None, expires_in: int) -> str:
        return f"https://storage.example/upload/{object_key}?expires={expires_in}"

    def generate_download_url(self, *, object_key: str, expires_in: int) -> str:
        return f"https://storage.example/download/{object_key}?expires={expires_in}"

    def head_object(self, *, object_key: str) -> R2ObjectMetadata:
        if object_key not in self.objects:
            raise R2ObjectNotFoundError("missing object")
        return self.objects[object_key]


async def register_and_get_client(client: AsyncClient, suffix: str = "") -> AsyncClient:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"asset-user{suffix}@example.com",
            "password": "securepass123",
            "full_name": f"Asset User {suffix}",
        },
    )
    return client


async def create_additional_client(db_session) -> AsyncClient:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    return AsyncClient(transport=transport, base_url="https://test")


async def get_asset(db_session, asset_id: str) -> Asset:
    result = await db_session.execute(select(Asset).where(Asset.id == uuid.UUID(asset_id)))
    return result.scalar_one()


async def test_create_upload_url_creates_pending_asset(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "page_image",
            "mime_type": "image/png",
            "file_size_bytes": 1234,
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["upload_url"].startswith("https://storage.example/upload/")

    asset = await get_asset(db_session, data["asset_id"])
    assert asset.asset_type == AssetType.PAGE_IMAGE
    assert asset.upload_status == AssetUploadStatus.PENDING
    assert asset.mime_type == "image/png"
    assert asset.file_size_bytes == 1234
    assert asset.object_key.startswith("stories/")


async def test_create_upload_url_requires_auth(client: AsyncClient, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "page_image",
            "mime_type": "image/png",
        },
    )
    assert resp.status_code == 401


async def test_confirm_asset_upload_marks_asset_ready(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "page_audio",
            "mime_type": "audio/mpeg",
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=2048, checksum="abc123")

    confirm_resp = await client.post(f"/api/assets/{asset.id}/confirm")
    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["upload_status"] == "ready"
    assert body["file_size_bytes"] == 2048
    assert body["checksum"] == "abc123"
    assert body["confirmed_at"] is not None


async def test_confirm_asset_upload_requires_existing_object(client: AsyncClient, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "page_image",
            "mime_type": "image/png",
        },
    )

    confirm_resp = await client.post(f"/api/assets/{upload_resp.json()['asset_id']}/confirm")
    assert confirm_resp.status_code == 400
    assert "not found in storage" in confirm_resp.json()["detail"].lower()


async def test_asset_read_url_requires_ready_asset(client: AsyncClient, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "cover_image",
            "mime_type": "image/webp",
        },
    )

    read_resp = await client.get(f"/api/assets/{upload_resp.json()['asset_id']}/url")
    assert read_resp.status_code == 409


async def test_asset_read_url_returns_signed_url_for_ready_asset(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "thumbnail",
            "mime_type": "image/webp",
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=512, checksum="etag-1")
    await client.post(f"/api/assets/{asset.id}/confirm")

    read_resp = await client.get(f"/api/assets/{asset.id}/url")
    assert read_resp.status_code == 200
    assert read_resp.json()["url"].startswith("https://storage.example/download/")


async def test_voice_sample_read_url_is_forbidden(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client)
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "voice_sample",
            "mime_type": "audio/wav",
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=4096, checksum="etag-2")
    await client.post(f"/api/assets/{asset.id}/confirm")

    read_resp = await client.get(f"/api/assets/{asset.id}/url")
    assert read_resp.status_code == 403


async def test_only_owner_can_confirm_and_read(client: AsyncClient, db_session, monkeypatch):
    fake_r2 = FakeR2Client()
    monkeypatch.setattr("app.services.asset.get_r2_client", lambda: fake_r2)

    await register_and_get_client(client, suffix="A")
    upload_resp = await client.post(
        UPLOAD_URL,
        json={
            "asset_type": "page_image",
            "mime_type": "image/png",
        },
    )
    asset = await get_asset(db_session, upload_resp.json()["asset_id"])
    fake_r2.objects[asset.object_key] = R2ObjectMetadata(file_size_bytes=100, checksum="etag-3")

    client_b = await create_additional_client(db_session)
    try:
        await register_and_get_client(client_b, suffix="B")

        confirm_resp = await client_b.post(f"/api/assets/{asset.id}/confirm")
        assert confirm_resp.status_code == 404

        read_resp = await client_b.get(f"/api/assets/{asset.id}/url")
        assert read_resp.status_code == 404
    finally:
        await client_b.aclose()
        fastapi_app.dependency_overrides.clear()
