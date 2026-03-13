"""Voice profile and sample endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.voice import (
    VoiceProfileCreate,
    VoiceProfileResponse,
    VoiceSampleResponse,
    VoiceSampleUploadRequest,
    VoiceSampleUploadResponse,
)
from app.services.voice import (
    VoiceError,
    confirm_voice_sample_upload,
    create_voice_profile,
    create_voice_sample_upload,
    delete_voice_profile,
    delete_voice_sample,
    list_voice_profiles,
)

router = APIRouter(prefix="/api/voice-profiles", tags=["voice"])


@router.post("", response_model=VoiceProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: VoiceProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        profile = await create_voice_profile(db, user_id=current_user.id, data=body)
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return VoiceProfileResponse.from_model(profile)


@router.get("", response_model=list[VoiceProfileResponse])
async def list_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles = await list_voice_profiles(db, user_id=current_user.id)
    return [VoiceProfileResponse.from_model(profile) for profile in profiles]


@router.post(
    "/{profile_id}/samples",
    response_model=VoiceSampleUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sample_upload(
    profile_id: uuid.UUID,
    body: VoiceSampleUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        sample, asset, upload_url, expires_at = await create_voice_sample_upload(
            db,
            user_id=current_user.id,
            profile_id=profile_id,
            data=body,
        )
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return VoiceSampleUploadResponse(
        sample_id=sample.id,
        asset_id=asset.id,
        upload_url=upload_url,
        expires_at=expires_at,
    )


@router.post(
    "/{profile_id}/samples/{sample_id}/confirm",
    response_model=VoiceSampleResponse,
)
async def confirm_sample_upload(
    profile_id: uuid.UUID,
    sample_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        sample = await confirm_voice_sample_upload(
            db,
            user_id=current_user.id,
            profile_id=profile_id,
            sample_id=sample_id,
        )
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return sample


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        deleted = await delete_voice_profile(
            db,
            user_id=current_user.id,
            profile_id=profile_id,
        )
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice profile not found")


@router.delete("/{profile_id}/samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    profile_id: uuid.UUID,
    sample_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        deleted = await delete_voice_sample(
            db,
            user_id=current_user.id,
            profile_id=profile_id,
            sample_id=sample_id,
        )
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice sample not found")
