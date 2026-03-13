"""Voice profile and voice sample orchestration."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.integrations.r2 import R2Error, R2ObjectNotFoundError, get_r2_client
from app.models.asset import Asset
from app.models.enums import AssetType, AssetUploadStatus, VoiceProfileStatus, VoiceSampleStatus
from app.models.voice_profile import VoiceProfile
from app.models.voice_sample import VoiceSample
from app.schemas.voice import VoiceProfileCreate, VoiceSampleUploadRequest

ALLOWED_VOICE_SAMPLE_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/aac",
    "audio/m4a",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
}


class VoiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _expiry(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _build_voice_sample_object_key(user_id: uuid.UUID, asset_id: uuid.UUID) -> str:
    return f"voice-samples/{user_id}/{asset_id}"


async def _get_owned_voice_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> VoiceProfile | None:
    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.id == profile_id, VoiceProfile.user_id == user_id)
        .options(selectinload(VoiceProfile.voice_samples).selectinload(VoiceSample.asset))
    )
    return result.scalar_one_or_none()


async def _get_owned_voice_sample(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    sample_id: uuid.UUID,
) -> VoiceSample | None:
    result = await db.execute(
        select(VoiceSample)
        .where(
            VoiceSample.id == sample_id,
            VoiceSample.user_id == user_id,
            VoiceSample.voice_profile_id == profile_id,
        )
        .options(selectinload(VoiceSample.asset))
    )
    return result.scalar_one_or_none()


def _normalize_voice_sample_mime_type(mime_type: str) -> str:
    normalized = mime_type.split(";", 1)[0].strip().lower()
    aliases = {
        "audio/wave": "audio/wav",
    }
    return aliases.get(normalized, normalized)


def _validate_voice_sample_request(data: VoiceSampleUploadRequest) -> None:
    normalized_mime_type = _normalize_voice_sample_mime_type(data.mime_type)

    if normalized_mime_type not in ALLOWED_VOICE_SAMPLE_MIME_TYPES:
        raise VoiceError("Unsupported voice sample MIME type", status_code=400)

    if data.file_size_bytes > settings.voice_sample_max_file_size_bytes:
        raise VoiceError("Voice sample file is too large", status_code=400)


async def create_voice_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: VoiceProfileCreate,
) -> VoiceProfile:
    if not data.consent_confirmed:
        raise VoiceError(
            "Voice cloning consent is required to create a voice profile",
            status_code=400,
        )

    if data.default_for_user:
        await db.execute(
            update(VoiceProfile)
            .where(VoiceProfile.user_id == user_id)
            .values(default_for_user=False)
        )

    profile = VoiceProfile(
        user_id=user_id,
        display_name=data.display_name.strip(),
        status=VoiceProfileStatus.PENDING,
        source_type="user_upload",
        consent_confirmed=True,
        default_for_user=data.default_for_user,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile, attribute_names=["voice_samples"])
    return profile


async def list_voice_profiles(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[VoiceProfile]:
    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.user_id == user_id)
        .order_by(VoiceProfile.created_at.desc())
        .options(selectinload(VoiceProfile.voice_samples).selectinload(VoiceSample.asset))
    )
    profiles = list(result.scalars().all())

    for profile in profiles:
        profile.voice_samples.sort(key=lambda sample: sample.created_at, reverse=True)

    return profiles


async def create_voice_sample_upload(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    data: VoiceSampleUploadRequest,
) -> tuple[VoiceSample, Asset, str, datetime]:
    _validate_voice_sample_request(data)

    profile = await _get_owned_voice_profile(db, user_id=user_id, profile_id=profile_id)
    if not profile:
        raise VoiceError("Voice profile not found", status_code=404)

    normalized_mime_type = _normalize_voice_sample_mime_type(data.mime_type)

    asset_id = uuid.uuid4()
    sample_id = uuid.uuid4()

    asset = Asset(
        id=asset_id,
        user_id=user_id,
        storage_provider="r2",
        bucket_name=settings.r2_bucket_name,
        object_key=_build_voice_sample_object_key(user_id, asset_id),
        asset_type=AssetType.VOICE_SAMPLE,
        mime_type=normalized_mime_type,
        file_size_bytes=data.file_size_bytes,
        duration_ms=int(data.duration_seconds * 1000),
        is_private=True,
        upload_status=AssetUploadStatus.PENDING,
    )
    sample = VoiceSample(
        id=sample_id,
        user_id=user_id,
        voice_profile_id=profile.id,
        asset_id=asset.id,
        duration_seconds=data.duration_seconds,
        status=VoiceSampleStatus.PENDING,
    )
    db.add(asset)
    db.add(sample)
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
        raise VoiceError(str(exc), status_code=500) from exc

    await db.commit()
    await db.refresh(sample)
    await db.refresh(asset)
    return sample, asset, upload_url, expires_at


async def confirm_voice_sample_upload(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    sample_id: uuid.UUID,
) -> VoiceSample:
    sample = await _get_owned_voice_sample(
        db,
        user_id=user_id,
        profile_id=profile_id,
        sample_id=sample_id,
    )
    if not sample:
        raise VoiceError("Voice sample not found", status_code=404)

    if not sample.asset_id or not sample.asset:
        raise VoiceError("Voice sample asset not found", status_code=400)

    if sample.status == VoiceSampleStatus.UPLOADED:
        raise VoiceError("Voice sample already confirmed", status_code=409)

    try:
        metadata = get_r2_client().head_object(object_key=sample.asset.object_key)
    except R2ObjectNotFoundError as exc:
        raise VoiceError("Uploaded object not found in storage", status_code=400) from exc
    except R2Error as exc:
        raise VoiceError(str(exc), status_code=500) from exc

    sample.asset.file_size_bytes = metadata.file_size_bytes or sample.asset.file_size_bytes
    sample.asset.checksum = metadata.checksum or sample.asset.checksum
    sample.asset.upload_status = AssetUploadStatus.READY
    sample.asset.confirmed_at = _utcnow_naive()
    sample.status = VoiceSampleStatus.UPLOADED

    await db.commit()
    await db.refresh(sample)
    return sample


def _voice_sample_assets(samples: list[VoiceSample]) -> list[Asset]:
    assets: list[Asset] = []

    for sample in samples:
        if sample.asset is not None:
            assets.append(sample.asset)

    return assets


def _unique_assets(assets: list[Asset]) -> list[Asset]:
    seen: set[uuid.UUID] = set()
    unique: list[Asset] = []

    for asset in assets:
        if asset.id in seen:
            continue
        seen.add(asset.id)
        unique.append(asset)

    return unique


def _delete_storage_object_if_present(asset: Asset | None) -> None:
    if asset is None:
        return

    try:
        get_r2_client().delete_object(object_key=asset.object_key)
    except R2ObjectNotFoundError:
        return
    except R2Error as exc:
        raise VoiceError(str(exc), status_code=500) from exc


async def delete_voice_sample(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    sample_id: uuid.UUID,
) -> bool:
    sample = await _get_owned_voice_sample(
        db,
        user_id=user_id,
        profile_id=profile_id,
        sample_id=sample_id,
    )
    if not sample:
        return False

    _delete_storage_object_if_present(sample.asset)

    asset = sample.asset
    await db.delete(sample)
    if asset is not None:
        await db.delete(asset)

    await db.commit()
    return True


async def delete_voice_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> bool:
    profile = await _get_owned_voice_profile(db, user_id=user_id, profile_id=profile_id)
    if not profile:
        return False

    assets = _unique_assets(_voice_sample_assets(list(profile.voice_samples)))
    for asset in assets:
        _delete_storage_object_if_present(asset)

    for sample in list(profile.voice_samples):
        await db.delete(sample)

    for asset in assets:
        await db.delete(asset)

    await db.delete(profile)
    await db.commit()
    return True
