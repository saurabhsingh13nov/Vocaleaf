"""Pydantic models for asset upload and read endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AssetType, AssetUploadStatus


class AssetUploadUrlRequest(BaseModel):
    asset_type: AssetType
    mime_type: str = Field(min_length=1, max_length=100)
    file_size_bytes: int | None = Field(default=None, gt=0)


class AssetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    storage_provider: str
    bucket_name: str
    object_key: str
    asset_type: AssetType
    mime_type: str | None
    file_size_bytes: int | None
    checksum: str | None
    width: int | None
    height: int | None
    duration_ms: int | None
    is_private: bool
    upload_status: AssetUploadStatus
    confirmed_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None


class AssetUploadUrlResponse(BaseModel):
    asset_id: uuid.UUID
    upload_url: str
    expires_at: datetime


class AssetConfirmResponse(AssetResponse):
    pass


class AssetReadUrlResponse(BaseModel):
    url: str
    expires_at: datetime
