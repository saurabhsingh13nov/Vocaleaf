"""Asset service — create upload URLs, confirm uploads, and issue read URLs."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.r2 import R2Error, R2ObjectNotFoundError, get_r2_client
from app.models.asset import Asset
from app.models.enums import AssetType, AssetUploadStatus
from app.schemas.asset import AssetUploadUrlRequest


class AssetError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _expiry(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _build_object_key(user_id: uuid.UUID, asset_id: uuid.UUID, asset_type: AssetType) -> str:
    key_roots = {
        AssetType.VOICE_SAMPLE: "voice-samples",
        AssetType.PAGE_IMAGE: "stories",
        AssetType.PAGE_AUDIO: "stories",
        AssetType.COVER_IMAGE: "stories",
        AssetType.THUMBNAIL: "derived",
    }
    key_suffixes = {
        AssetType.VOICE_SAMPLE: f"{user_id}/{asset_id}",
        AssetType.PAGE_IMAGE: f"{user_id}/page-images/{asset_id}",
        AssetType.PAGE_AUDIO: f"{user_id}/page-audio/{asset_id}",
        AssetType.COVER_IMAGE: f"{user_id}/cover-images/{asset_id}",
        AssetType.THUMBNAIL: f"{user_id}/thumbnails/{asset_id}",
    }
    return f"{key_roots[asset_type]}/{key_suffixes[asset_type]}"


async def _get_owned_asset(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> Asset | None:
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.user_id == user_id,
            Asset.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def create_upload_asset(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: AssetUploadUrlRequest,
) -> tuple[Asset, str, datetime]:
    asset_id = uuid.uuid4()
    asset = Asset(
        id=asset_id,
        user_id=user_id,
        storage_provider="r2",
        bucket_name=settings.r2_bucket_name,
        object_key=_build_object_key(user_id, asset_id, data.asset_type),
        asset_type=data.asset_type,
        mime_type=data.mime_type,
        file_size_bytes=data.file_size_bytes,
        is_private=True,
        upload_status=AssetUploadStatus.PENDING,
    )
    db.add(asset)
    await db.flush()

    expires_at = _expiry(settings.asset_upload_url_expire_seconds)
    try:
        upload_url = get_r2_client().generate_upload_url(
            object_key=asset.object_key,
            mime_type=asset.mime_type,
            expires_in=settings.asset_upload_url_expire_seconds,
        )
    except R2Error as exc:
        await db.rollback()
        raise AssetError(str(exc), status_code=500) from exc

    await db.commit()
    await db.refresh(asset)
    return asset, upload_url, expires_at


async def confirm_asset_upload(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> Asset:
    asset = await _get_owned_asset(db, user_id=user_id, asset_id=asset_id)
    if not asset:
        raise AssetError("Asset not found", status_code=404)

    if asset.upload_status == AssetUploadStatus.READY:
        raise AssetError("Asset already confirmed", status_code=409)

    try:
        metadata = get_r2_client().head_object(object_key=asset.object_key)
    except R2ObjectNotFoundError as exc:
        raise AssetError("Uploaded object not found in storage", status_code=400) from exc
    except R2Error as exc:
        raise AssetError(str(exc), status_code=500) from exc

    asset.file_size_bytes = metadata.file_size_bytes or asset.file_size_bytes
    asset.checksum = metadata.checksum or asset.checksum
    asset.upload_status = AssetUploadStatus.READY
    asset.confirmed_at = _utcnow_naive()
    await db.commit()
    await db.refresh(asset)
    return asset


async def get_asset_download_url(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> tuple[str, datetime]:
    asset = await _get_owned_asset(db, user_id=user_id, asset_id=asset_id)
    if not asset:
        raise AssetError("Asset not found", status_code=404)

    if asset.asset_type == AssetType.VOICE_SAMPLE:
        raise AssetError("Raw voice sample assets cannot be downloaded here", status_code=403)

    if asset.upload_status != AssetUploadStatus.READY:
        raise AssetError("Asset is not ready", status_code=409)

    expires_at = _expiry(settings.asset_read_url_expire_seconds)
    try:
        url = get_r2_client().generate_download_url(
            object_key=asset.object_key,
            expires_in=settings.asset_read_url_expire_seconds,
        )
    except R2Error as exc:
        raise AssetError(str(exc), status_code=500) from exc

    return url, expires_at
