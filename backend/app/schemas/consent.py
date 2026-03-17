"""Pydantic models for consent capture and status endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ConsentType


class ConsentAcceptItem(BaseModel):
    consent_type: ConsentType
    accepted_version: str = Field(min_length=1, max_length=50)


class ConsentAcceptRequest(BaseModel):
    consents: list[ConsentAcceptItem]


class ConsentStatusItem(BaseModel):
    consent_type: ConsentType
    required_version: str
    accepted_version: str | None
    accepted_at: datetime | None
    is_current: bool


class ConsentStatusResponse(BaseModel):
    items: list[ConsentStatusItem]
    requires_legal_consent: bool
    has_voice_cloning_consent: bool
