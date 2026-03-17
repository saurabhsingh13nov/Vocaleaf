"""Internal admin APIs for support operations and entitlement management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user as require_admin_user, get_staff_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminPlanResponse,
    AdminUserDetailResponse,
    AdminUserListItemResponse,
    AssignSubscriptionRequest,
    AuditEventResponse,
    CreateEntitlementOverrideRequest,
    CreateUsageCreditGrantRequest,
    EntitlementOverrideResponse,
    PlanUpdateRequest,
    SetUserRoleRequest,
    UsageCreditGrantResponse,
)
from app.schemas.auth import UserResponse
from app.schemas.subscription import SubscriptionSummaryResponse
from app.services.audit import list_recent_audit_events_for_user
from app.services.subscription import (
    SubscriptionError,
    assign_subscription_to_user,
    build_usage_metrics,
    create_entitlement_override,
    create_usage_credit_grant,
    effective_plan_payload,
    get_admin_user as get_admin_target_user,
    get_subscription_context,
    list_admin_users,
    list_plans,
    revoke_entitlement_override,
    revoke_usage_credit_grant,
    set_user_role,
    subscription_summary_payload,
    update_plan_definition,
)
from app.services.user_roles import get_user_role_by_code

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _normalize_user_role_code(db: AsyncSession, raw_role: str) -> str:
    normalized_role = raw_role.strip().lower()
    role = await get_user_role_by_code(db, code=normalized_role)
    if role is None:
        raise HTTPException(status_code=400, detail="Invalid role")
    return role.code


def _raise_subscription_error(exc: SubscriptionError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


async def _build_admin_user_response(user: User, db: AsyncSession) -> AdminUserListItemResponse:
    context = await get_subscription_context(db, user_id=user.id)
    return AdminUserListItemResponse(
        **UserResponse.model_validate(user).model_dump(),
        current_period_start=context.subscription.current_period_start,
        current_period_end=context.subscription.current_period_end,
        plan=effective_plan_payload(context),
        usage=build_usage_metrics(context),
    )


@router.get("/users", response_model=list[AdminUserListItemResponse])
async def list_users(
    q: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    users = await list_admin_users(db, query=q, limit=limit)
    items: list[AdminUserListItemResponse] = []
    for user in users:
        items.append(await _build_admin_user_response(user, db))
    return items


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: uuid.UUID,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    user = await get_admin_target_user(db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    summary = await _build_admin_user_response(user, db)
    context = await get_subscription_context(db, user_id=user.id)
    audit_events = await list_recent_audit_events_for_user(db, user_id=user.id)
    return AdminUserDetailResponse(
        **summary.model_dump(),
        active_override=context.active_override,
        active_grants=context.active_grants,
        recent_audit_events=[AuditEventResponse.model_validate(event) for event in audit_events],
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: SetUserRoleRequest,
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await set_user_role(
            db,
            target_user_id=user_id,
            role=await _normalize_user_role_code(db, body.role),
            actor_user_id=current_user.id,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/subscription", response_model=SubscriptionSummaryResponse)
async def reassign_user_subscription(
    user_id: uuid.UUID,
    body: AssignSubscriptionRequest,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await assign_subscription_to_user(
            db,
            user_id=user_id,
            plan_code=body.plan_code.strip().lower(),
            actor_user_id=current_user.id,
        )
        context = await get_subscription_context(db, user_id=user_id)
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return SubscriptionSummaryResponse.model_validate(subscription_summary_payload(context))


@router.post("/users/{user_id}/entitlement-overrides", response_model=EntitlementOverrideResponse)
async def create_user_entitlement_override(
    user_id: uuid.UUID,
    body: CreateEntitlementOverrideRequest,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        override = await create_entitlement_override(
            db,
            target_user_id=user_id,
            actor_user_id=current_user.id,
            reason=body.reason,
            effective_to=body.effective_to,
            monthly_story_limit=body.monthly_story_limit,
            max_pages_per_story=body.max_pages_per_story,
            image_quality_mode=body.image_quality_mode,
            voice_clone_limit=body.voice_clone_limit,
            monthly_audio_chars_limit=body.monthly_audio_chars_limit,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return EntitlementOverrideResponse.model_validate(override)


@router.post("/entitlement-overrides/{override_id}/revoke", response_model=EntitlementOverrideResponse)
async def revoke_user_entitlement_override(
    override_id: uuid.UUID,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        override = await revoke_entitlement_override(
            db,
            override_id=override_id,
            actor_user_id=current_user.id,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return EntitlementOverrideResponse.model_validate(override)


@router.post("/users/{user_id}/usage-grants", response_model=UsageCreditGrantResponse)
async def create_user_usage_grant(
    user_id: uuid.UUID,
    body: CreateUsageCreditGrantRequest,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        grant = await create_usage_credit_grant(
            db,
            target_user_id=user_id,
            actor_user_id=current_user.id,
            usage_type=body.usage_type.strip().lower(),
            quantity=body.quantity,
            reason=body.reason,
            effective_to=body.effective_to,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return UsageCreditGrantResponse.model_validate(grant)


@router.post("/usage-grants/{grant_id}/revoke", response_model=UsageCreditGrantResponse)
async def revoke_user_usage_grant(
    grant_id: uuid.UUID,
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        grant = await revoke_usage_credit_grant(
            db,
            grant_id=grant_id,
            actor_user_id=current_user.id,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return UsageCreditGrantResponse.model_validate(grant)


@router.get("/plans", response_model=list[AdminPlanResponse])
async def get_plans(
    current_user: User = Depends(get_staff_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    plans = await list_plans(db)
    return [AdminPlanResponse.model_validate(plan) for plan in plans]


@router.patch("/plans/{plan_code}", response_model=AdminPlanResponse)
async def patch_plan(
    plan_code: str,
    body: PlanUpdateRequest,
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No plan changes were provided")

    try:
        plan = await update_plan_definition(
            db,
            plan_code=plan_code.strip().lower(),
            actor_user_id=current_user.id,
            changes=changes,
        )
    except SubscriptionError as exc:
        _raise_subscription_error(exc)
    return AdminPlanResponse.model_validate(plan)
