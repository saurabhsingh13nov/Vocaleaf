"""Pydantic models for internal admin APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserResponse
from app.schemas.subscription import PlanSummaryResponse, UsageMetricResponse


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    monthly_story_limit: int | None = Field(default=None, ge=0)
    max_pages_per_story: int | None = Field(default=None, ge=0)
    image_quality_mode: str | None = Field(default=None, min_length=1, max_length=50)
    voice_clone_limit: int | None = Field(default=None, ge=0)
    monthly_audio_chars_limit: int | None = Field(default=None, ge=0)
    price_cents: int | None = Field(default=None, ge=0)
    active: bool | None = None


class AssignSubscriptionRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)


class SetUserRoleRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class CreateEntitlementOverrideRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)
    effective_to: datetime | None = None
    monthly_story_limit: int | None = Field(default=None, ge=0)
    max_pages_per_story: int | None = Field(default=None, ge=0)
    image_quality_mode: str | None = Field(default=None, min_length=1, max_length=50)
    voice_clone_limit: int | None = Field(default=None, ge=0)
    monthly_audio_chars_limit: int | None = Field(default=None, ge=0)


class CreateUsageCreditGrantRequest(BaseModel):
    usage_type: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=255)
    effective_to: datetime | None = None


class AdminPlanResponse(PlanSummaryResponse):
    active: bool


class EntitlementOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    revoked_by_user_id: uuid.UUID | None
    monthly_story_limit: int | None
    max_pages_per_story: int | None
    image_quality_mode: str | None
    voice_clone_limit: int | None
    monthly_audio_chars_limit: int | None
    reason: str
    effective_from: datetime
    effective_to: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UsageCreditGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    revoked_by_user_id: uuid.UUID | None
    usage_type: str
    quantity: int
    reason: str
    effective_from: datetime
    effective_to: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    event_type: str
    event_data_json: dict | None
    created_at: datetime


class AdminUserListItemResponse(UserResponse):
    current_period_start: datetime | None
    current_period_end: datetime | None
    plan: PlanSummaryResponse
    usage: dict[str, UsageMetricResponse]


class AdminUserDetailResponse(AdminUserListItemResponse):
    active_override: EntitlementOverrideResponse | None
    active_grants: list[UsageCreditGrantResponse]
    recent_audit_events: list[AuditEventResponse]
