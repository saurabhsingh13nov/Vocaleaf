"""Pydantic models for voice profile and sample APIs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import VoiceProfileStatus, VoiceSampleStatus


class VoiceProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    consent_confirmed: bool
    default_for_user: bool = False


class VoiceSampleUploadRequest(BaseModel):
    mime_type: str = Field(min_length=1, max_length=100)
    file_size_bytes: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)


class VoiceSampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID | None
    duration_seconds: float | None
    status: VoiceSampleStatus
    created_at: datetime


class VoiceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    status: VoiceProfileStatus
    consent_confirmed: bool
    default_for_user: bool
    created_at: datetime
    updated_at: datetime
    samples: list[VoiceSampleResponse]

    @classmethod
    def from_model(cls, profile) -> "VoiceProfileResponse":
        return cls.model_validate(
            {
                **profile.__dict__,
                "samples": list(profile.voice_samples),
            }
        )


class VoiceSampleUploadResponse(BaseModel):
    sample_id: uuid.UUID
    asset_id: uuid.UUID
    upload_url: str
    expires_at: datetime
