"""Voice cloning worker entrypoints."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.session import dispose_session_state, dispose_session_state_sync, get_async_session_factory
from app.integrations.elevenlabs import ElevenLabsError, ElevenLabsSample, get_elevenlabs_client
from app.integrations.r2 import R2Error, R2ObjectNotFoundError, get_r2_client
from app.models.enums import AssetUploadStatus, VoiceProfileStatus, VoiceSampleStatus
from app.models.voice_profile import VoiceProfile
from app.models.voice_sample import VoiceSample
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def run_voice_clone(
    profile_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await run_voice_clone_in_session(db, profile_id)
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def _load_profile_for_status_update(db: AsyncSession, profile_id: uuid.UUID) -> VoiceProfile | None:
    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.id == profile_id)
        .options(selectinload(VoiceProfile.voice_samples))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def mark_voice_clone_failed_in_session(db: AsyncSession, profile_id: uuid.UUID) -> None:
    await db.rollback()
    profile = await _load_profile_for_status_update(db, profile_id)
    if profile is None:
        logger.warning("Voice clone cleanup skipped because profile %s no longer exists", profile_id)
        return

    for sample in profile.voice_samples:
        if sample.status == VoiceSampleStatus.PROCESSING:
            sample.status = VoiceSampleStatus.UPLOADED
    profile.status = VoiceProfileStatus.FAILED
    await db.commit()


async def mark_voice_clone_failed(
    profile_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Restore a stuck clone request to a failed state after an unexpected worker crash."""
    owns_session_factory = session_factory is None
    session_factory = session_factory or get_async_session_factory()
    try:
        async with session_factory() as db:
            await mark_voice_clone_failed_in_session(db, profile_id)
    finally:
        if owns_session_factory:
            await dispose_session_state()


async def run_voice_clone_in_session(db: AsyncSession, profile_id: uuid.UUID) -> None:
    """Clone a voice profile from uploaded samples and persist its provider state."""
    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.id == profile_id)
        .options(selectinload(VoiceProfile.voice_samples).selectinload(VoiceSample.asset))
        .execution_options(populate_existing=True)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.warning("Voice clone skipped because profile %s no longer exists", profile_id)
        return

    samples = [
        sample
        for sample in profile.voice_samples
        if sample.status == VoiceSampleStatus.UPLOADED
        and sample.asset is not None
        and sample.asset.upload_status == AssetUploadStatus.READY
    ]
    if not samples:
        profile.status = VoiceProfileStatus.FAILED
        await db.commit()
        logger.warning("Voice clone failed because profile %s has no eligible samples", profile_id)
        return

    for sample in samples:
        sample.status = VoiceSampleStatus.PROCESSING
    await db.commit()

    try:
        payload_samples: list[ElevenLabsSample] = []
        for index, sample in enumerate(samples, start=1):
            asset = sample.asset
            if asset is None:
                raise R2Error("Voice sample asset is missing")
            object_data = get_r2_client().download_object(object_key=asset.object_key)
            payload_samples.append(
                ElevenLabsSample(
                    file_name=f"{profile.id}-sample-{index}",
                    content=object_data.content,
                    content_type=object_data.content_type or asset.mime_type,
                )
            )

        cloned_voice = get_elevenlabs_client().clone_voice(
            display_name=profile.display_name,
            samples=payload_samples,
        )
    except (ElevenLabsError, R2Error, R2ObjectNotFoundError) as exc:
        await mark_voice_clone_failed_in_session(db, profile_id)
        logger.exception("Voice clone failed for profile %s", profile_id, exc_info=exc)
        return

    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.id == profile_id)
        .options(selectinload(VoiceProfile.voice_samples))
        .execution_options(populate_existing=True)
    )
    profile = result.scalar_one()
    profile.provider = "elevenlabs"
    profile.provider_voice_id = cloned_voice.voice_id
    profile.clone_type = profile.clone_type or "instant"
    profile.status = VoiceProfileStatus.READY

    for sample in profile.voice_samples:
        if sample.status == VoiceSampleStatus.PROCESSING:
            sample.status = VoiceSampleStatus.ACCEPTED

    await db.commit()


@celery_app.task(name="app.workers.voice_clone_worker.clone_voice_profile_task")
def clone_voice_profile_task(profile_id: str) -> None:
    """Celery wrapper that bridges synchronous workers to async DB code."""
    profile_uuid = uuid.UUID(profile_id)

    try:
        asyncio.run(run_voice_clone(profile_uuid))
    except Exception:
        logger.exception("Voice clone task crashed for profile %s", profile_id)
        try:
            dispose_session_state_sync()
            asyncio.run(mark_voice_clone_failed(profile_uuid))
        except Exception:
            logger.exception("Voice clone crash cleanup failed for profile %s", profile_id)
        raise
