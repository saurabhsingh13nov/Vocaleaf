"""Asset endpoints — signed uploads, upload confirmation, and signed reads."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.asset import (
    AssetConfirmResponse,
    AssetReadUrlResponse,
    AssetUploadUrlRequest,
    AssetUploadUrlResponse,
)
from app.services.asset import (
    AssetError,
    confirm_asset_upload,
    create_upload_asset,
    get_asset_download_url,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/upload-url", response_model=AssetUploadUrlResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_url(
    body: AssetUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        asset, upload_url, expires_at = await create_upload_asset(
            db,
            user_id=current_user.id,
            data=body,
        )
    except AssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return AssetUploadUrlResponse(
        asset_id=asset.id,
        upload_url=upload_url,
        expires_at=expires_at,
    )


@router.post("/{asset_id}/confirm", response_model=AssetConfirmResponse)
async def confirm_upload(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        asset = await confirm_asset_upload(db, user_id=current_user.id, asset_id=asset_id)
    except AssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return asset


@router.get("/{asset_id}/url", response_model=AssetReadUrlResponse)
async def read_url(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        url, expires_at = await get_asset_download_url(
            db,
            user_id=current_user.id,
            asset_id=asset_id,
        )
    except AssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return AssetReadUrlResponse(url=url, expires_at=expires_at)
