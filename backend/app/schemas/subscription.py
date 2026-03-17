"""Pydantic models for subscription and usage summary endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    monthly_story_limit: int | None
    max_pages_per_story: int | None
    image_quality_mode: str | None
    voice_clone_limit: int | None
    monthly_audio_chars_limit: int | None
    price_cents: int


class UsageMetricResponse(BaseModel):
    used: int
    limit: int | None
    remaining: int | None
    unit: str


class SubscriptionSummaryResponse(BaseModel):
    id: uuid.UUID
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    plan: PlanSummaryResponse
    usage: dict[str, UsageMetricResponse]
