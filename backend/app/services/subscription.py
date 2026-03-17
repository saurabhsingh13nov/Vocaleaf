"""Plan bootstrap, entitlement resolution, and admin subscription helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_credit_grant import UsageCreditGrant
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.user_entitlement_override import UserEntitlementOverride
from app.services.audit import record_audit_event
from app.services.user_roles import get_user_role_by_code
from app.services.usage import (
    USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED,
    USAGE_TYPE_IMAGES_GENERATED,
    USAGE_TYPE_STORIES_CREATED,
    USAGE_TYPE_VOICE_CLONES_CREATED,
)

FREE_PLAN_CODE = "free"
PREMIUM_PLAN_CODE = "premium"
DEFAULT_SUBSCRIPTION_PERIOD_DAYS = 30

PLAN_SEED_DATA = (
    {
        "code": FREE_PLAN_CODE,
        "name": "free",
        "monthly_story_limit": 3,
        "max_pages_per_story": 6,
        "image_quality_mode": "standard",
        "voice_clone_limit": 1,
        "monthly_audio_chars_limit": 15000,
        "price_cents": 0,
        "active": True,
    },
    {
        "code": PREMIUM_PLAN_CODE,
        "name": "premium",
        "monthly_story_limit": 30,
        "max_pages_per_story": 10,
        "image_quality_mode": "premium",
        "voice_clone_limit": 5,
        "monthly_audio_chars_limit": 300000,
        "price_cents": 1299,
        "active": True,
    },
)

USAGE_UNITS = {
    USAGE_TYPE_STORIES_CREATED: "story",
    USAGE_TYPE_IMAGES_GENERATED: "page_image",
    USAGE_TYPE_VOICE_CLONES_CREATED: "voice_clone",
    USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED: "character",
}

OVERRIDABLE_LIMIT_FIELDS = (
    "monthly_story_limit",
    "max_pages_per_story",
    "image_quality_mode",
    "voice_clone_limit",
    "monthly_audio_chars_limit",
)

USAGE_TO_LIMIT_FIELD = {
    USAGE_TYPE_STORIES_CREATED: "monthly_story_limit",
    USAGE_TYPE_VOICE_CLONES_CREATED: "voice_clone_limit",
    USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED: "monthly_audio_chars_limit",
}


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SubscriptionError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class EffectivePlan:
    id: uuid.UUID
    code: str
    name: str
    monthly_story_limit: int | None
    max_pages_per_story: int | None
    image_quality_mode: str | None
    voice_clone_limit: int | None
    monthly_audio_chars_limit: int | None
    price_cents: int


@dataclass
class SubscriptionContext:
    subscription: Subscription
    plan: Plan
    effective_plan: EffectivePlan
    period_start: datetime
    period_end: datetime
    usage_totals: dict[str, float]
    active_override: UserEntitlementOverride | None
    active_grants: list[UsageCreditGrant]


def _active_window_clause(model) -> Any:
    now = _utcnow_naive()
    return (
        model.effective_from <= now,
        or_(model.effective_to.is_(None), model.effective_to > now),
        model.revoked_at.is_(None),
    )


def _normalize_user_identifier(email: str | None = None, user_id: uuid.UUID | None = None) -> tuple[str | None, uuid.UUID | None]:
    normalized_email = email.strip().lower() if email is not None else None
    return normalized_email, user_id


def _with_grants(base_limit: int | None, grants: list[UsageCreditGrant], usage_type: str) -> int | None:
    if base_limit is None:
        return None
    added = sum(grant.quantity for grant in grants if grant.usage_type == usage_type)
    return base_limit + added


def _remaining(limit: int | None, used: float) -> int | None:
    if limit is None:
        return None
    return max(int(limit - used), 0)


async def ensure_seeded_plans(db: AsyncSession) -> tuple[dict[str, Plan], bool]:
    result = await db.execute(select(Plan))
    plans = list(result.scalars())
    existing_by_code = {plan.code: plan for plan in plans if getattr(plan, "code", None)}
    existing_by_name = {plan.name: plan for plan in plans}

    changed = False
    for payload in PLAN_SEED_DATA:
        if payload["code"] in existing_by_code:
            continue

        legacy = existing_by_name.get(payload["name"])
        if legacy is not None and not getattr(legacy, "code", None):
            legacy.code = payload["code"]
            existing_by_code[legacy.code] = legacy
            changed = True
            continue

        plan = Plan(**payload)
        db.add(plan)
        existing_by_code[plan.code] = plan
        changed = True

    if changed:
        await db.flush()

    return existing_by_code, changed


async def list_plans(db: AsyncSession) -> list[Plan]:
    await ensure_seeded_plans(db)
    result = await db.execute(select(Plan).order_by(Plan.code.asc()))
    return list(result.scalars())


async def _get_plan_by_code(db: AsyncSession, *, code: str) -> Plan:
    plans, _ = await ensure_seeded_plans(db)
    plan = plans.get(code)
    if plan is not None:
        return plan

    result = await db.execute(select(Plan).where(Plan.code == code))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise SubscriptionError(f"Plan '{code}' was not found", status_code=404)
    return plan


async def _get_user_by_identifier(
    db: AsyncSession,
    *,
    email: str | None = None,
    user_id: uuid.UUID | None = None,
) -> User | None:
    normalized_email, user_uuid = _normalize_user_identifier(email=email, user_id=user_id)
    if normalized_email is not None:
        result = await db.execute(select(User).where(User.primary_email == normalized_email))
        return result.scalar_one_or_none()
    if user_uuid is not None:
        result = await db.execute(select(User).where(User.id == user_uuid))
        return result.scalar_one_or_none()
    return None


async def _require_user_by_id(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> User:
    user = await _get_user_by_identifier(db, user_id=user_id)
    if user is None:
        raise SubscriptionError("User not found", status_code=404)
    return user


async def _find_current_subscription(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> Subscription | None:
    now = _utcnow_naive()
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.current_period_end.desc(), Subscription.created_at.desc())
    )
    subscriptions = list(result.scalars())

    active: Subscription | None = None
    for subscription in subscriptions:
        if (
            subscription.current_period_start is not None
            and subscription.current_period_start > now
        ):
            continue
        if (
            subscription.current_period_end is not None
            and subscription.current_period_end <= now
        ):
            subscription.status = SubscriptionStatus.EXPIRED
            continue
        active = subscription
        break

    if active is None and subscriptions:
        await db.flush()

    return active


async def _usage_totals_for_period(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, float]:
    result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.created_at >= period_start,
            UsageRecord.created_at < period_end,
        )
    )
    totals = {
        USAGE_TYPE_STORIES_CREATED: 0.0,
        USAGE_TYPE_IMAGES_GENERATED: 0.0,
        USAGE_TYPE_VOICE_CLONES_CREATED: 0.0,
        USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED: 0.0,
    }
    for record in result.scalars():
        totals[record.usage_type] = totals.get(record.usage_type, 0.0) + float(record.quantity)
    return totals


async def _get_active_override(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> UserEntitlementOverride | None:
    result = await db.execute(
        select(UserEntitlementOverride)
        .where(
            UserEntitlementOverride.user_id == user_id,
            *_active_window_clause(UserEntitlementOverride),
        )
        .order_by(
            UserEntitlementOverride.created_at.desc(),
            UserEntitlementOverride.id.desc(),
        )
    )
    return result.scalars().first()


async def _get_active_grants(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[UsageCreditGrant]:
    result = await db.execute(
        select(UsageCreditGrant)
        .where(
            UsageCreditGrant.user_id == user_id,
            *_active_window_clause(UsageCreditGrant),
        )
        .order_by(UsageCreditGrant.created_at.desc(), UsageCreditGrant.id.desc())
    )
    return list(result.scalars())


def _build_effective_plan(
    plan: Plan,
    *,
    active_override: UserEntitlementOverride | None,
    active_grants: list[UsageCreditGrant],
) -> EffectivePlan:
    effective_values = {
        "monthly_story_limit": plan.monthly_story_limit,
        "max_pages_per_story": plan.max_pages_per_story,
        "image_quality_mode": plan.image_quality_mode,
        "voice_clone_limit": plan.voice_clone_limit,
        "monthly_audio_chars_limit": plan.monthly_audio_chars_limit,
    }

    if active_override is not None:
        for field_name in OVERRIDABLE_LIMIT_FIELDS:
            override_value = getattr(active_override, field_name)
            if override_value is not None:
                effective_values[field_name] = override_value

    effective_values["monthly_story_limit"] = _with_grants(
        effective_values["monthly_story_limit"],
        active_grants,
        USAGE_TYPE_STORIES_CREATED,
    )
    effective_values["voice_clone_limit"] = _with_grants(
        effective_values["voice_clone_limit"],
        active_grants,
        USAGE_TYPE_VOICE_CLONES_CREATED,
    )
    effective_values["monthly_audio_chars_limit"] = _with_grants(
        effective_values["monthly_audio_chars_limit"],
        active_grants,
        USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED,
    )

    return EffectivePlan(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        monthly_story_limit=effective_values["monthly_story_limit"],
        max_pages_per_story=effective_values["max_pages_per_story"],
        image_quality_mode=effective_values["image_quality_mode"],
        voice_clone_limit=effective_values["voice_clone_limit"],
        monthly_audio_chars_limit=effective_values["monthly_audio_chars_limit"],
        price_cents=plan.price_cents,
    )


async def create_subscription(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    plan_code: str,
    provider: str | None,
    event_type: str,
    actor_user_id: uuid.UUID | None = None,
) -> Subscription:
    plan = await _get_plan_by_code(db, code=plan_code)
    now = _utcnow_naive()
    current = await _find_current_subscription(db, user_id=user_id)
    if current is not None:
        current.status = SubscriptionStatus.CANCELLED
        current.cancel_at = now
        current.current_period_end = now

    subscription = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        provider=provider,
        provider_subscription_id=None,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=DEFAULT_SUBSCRIPTION_PERIOD_DAYS),
        cancel_at=None,
    )
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription, attribute_names=["plan"])
    record_audit_event(
        db,
        user_id=user_id,
        actor_user_id=actor_user_id,
        entity_type="subscription",
        entity_id=subscription.id,
        event_type=event_type,
        event_data={
            "plan_code": plan.code,
            "plan_name": plan.name,
            "provider": provider,
        },
    )
    return subscription


async def ensure_user_has_free_subscription(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> tuple[Subscription, bool]:
    subscription = await _find_current_subscription(db, user_id=user_id)
    if subscription is not None:
        return subscription, False

    created = await create_subscription(
        db,
        user_id=user_id,
        plan_code=FREE_PLAN_CODE,
        provider="system",
        event_type="subscription.auto_assigned_free",
    )
    return created, True


async def get_subscription_context(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> SubscriptionContext:
    _plans, seeded = await ensure_seeded_plans(db)
    subscription, created = await ensure_user_has_free_subscription(db, user_id=user_id)
    if seeded or created:
        await db.commit()
    await db.flush()
    await db.refresh(subscription, attribute_names=["plan"])

    period_start = subscription.current_period_start or _utcnow_naive()
    period_end = subscription.current_period_end or (period_start + timedelta(days=DEFAULT_SUBSCRIPTION_PERIOD_DAYS))
    usage_totals = await _usage_totals_for_period(
        db,
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    )
    active_override = await _get_active_override(db, user_id=user_id)
    active_grants = await _get_active_grants(db, user_id=user_id)
    effective_plan = _build_effective_plan(
        subscription.plan,
        active_override=active_override,
        active_grants=active_grants,
    )
    return SubscriptionContext(
        subscription=subscription,
        plan=subscription.plan,
        effective_plan=effective_plan,
        period_start=period_start,
        period_end=period_end,
        usage_totals=usage_totals,
        active_override=active_override,
        active_grants=active_grants,
    )


def build_usage_metrics(context: SubscriptionContext) -> dict[str, dict[str, int | None | str]]:
    totals = context.usage_totals
    plan = context.effective_plan
    return {
        USAGE_TYPE_STORIES_CREATED: {
            "used": int(totals.get(USAGE_TYPE_STORIES_CREATED, 0)),
            "limit": plan.monthly_story_limit,
            "remaining": _remaining(plan.monthly_story_limit, totals.get(USAGE_TYPE_STORIES_CREATED, 0)),
            "unit": USAGE_UNITS[USAGE_TYPE_STORIES_CREATED],
        },
        USAGE_TYPE_IMAGES_GENERATED: {
            "used": int(totals.get(USAGE_TYPE_IMAGES_GENERATED, 0)),
            "limit": None,
            "remaining": None,
            "unit": USAGE_UNITS[USAGE_TYPE_IMAGES_GENERATED],
        },
        USAGE_TYPE_VOICE_CLONES_CREATED: {
            "used": int(totals.get(USAGE_TYPE_VOICE_CLONES_CREATED, 0)),
            "limit": plan.voice_clone_limit,
            "remaining": _remaining(plan.voice_clone_limit, totals.get(USAGE_TYPE_VOICE_CLONES_CREATED, 0)),
            "unit": USAGE_UNITS[USAGE_TYPE_VOICE_CLONES_CREATED],
        },
        USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED: {
            "used": int(totals.get(USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED, 0)),
            "limit": plan.monthly_audio_chars_limit,
            "remaining": _remaining(plan.monthly_audio_chars_limit, totals.get(USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED, 0)),
            "unit": USAGE_UNITS[USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED],
        },
    }


def effective_plan_payload(context: SubscriptionContext) -> dict[str, Any]:
    return {
        "id": context.effective_plan.id,
        "code": context.effective_plan.code,
        "name": context.effective_plan.name,
        "monthly_story_limit": context.effective_plan.monthly_story_limit,
        "max_pages_per_story": context.effective_plan.max_pages_per_story,
        "image_quality_mode": context.effective_plan.image_quality_mode,
        "voice_clone_limit": context.effective_plan.voice_clone_limit,
        "monthly_audio_chars_limit": context.effective_plan.monthly_audio_chars_limit,
        "price_cents": context.effective_plan.price_cents,
    }


def subscription_summary_payload(context: SubscriptionContext) -> dict[str, Any]:
    return {
        "id": context.subscription.id,
        "status": context.subscription.status.value,
        "current_period_start": context.subscription.current_period_start,
        "current_period_end": context.subscription.current_period_end,
        "plan": effective_plan_payload(context),
        "usage": build_usage_metrics(context),
    }


async def enforce_story_creation_allowed(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    target_page_count: int,
) -> SubscriptionContext:
    context = await get_subscription_context(db, user_id=user_id)
    metrics = build_usage_metrics(context)

    page_limit = context.effective_plan.max_pages_per_story
    if page_limit is not None and target_page_count > page_limit:
        raise SubscriptionError(
            f"Your {context.effective_plan.name} plan allows up to {page_limit} pages per story.",
            status_code=403,
        )

    remaining_stories = metrics[USAGE_TYPE_STORIES_CREATED]["remaining"]
    if remaining_stories is not None and int(remaining_stories) < 1:
        raise SubscriptionError(
            f"Your {context.effective_plan.name} plan has no story credits remaining this period.",
            status_code=403,
        )

    return context


async def enforce_voice_clone_allowed(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> SubscriptionContext:
    context = await get_subscription_context(db, user_id=user_id)
    metrics = build_usage_metrics(context)
    remaining = metrics[USAGE_TYPE_VOICE_CLONES_CREATED]["remaining"]
    if remaining is not None and int(remaining) < 1:
        raise SubscriptionError(
            f"Your {context.effective_plan.name} plan has no voice clone credits remaining this period.",
            status_code=403,
        )
    return context


async def ensure_audio_quota_available(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    required_characters: int,
) -> SubscriptionContext:
    context = await get_subscription_context(db, user_id=user_id)
    limit = context.effective_plan.monthly_audio_chars_limit
    used = int(context.usage_totals.get(USAGE_TYPE_AUDIO_CHARS_SYNTHESIZED, 0))
    remaining = None if limit is None else max(limit - used, 0)

    if remaining is not None and required_characters > remaining:
        raise SubscriptionError(
            f"Your {context.effective_plan.name} plan has {remaining} narration characters remaining this period, "
            f"but this story needs {required_characters}.",
            status_code=403,
        )

    return context


async def assign_subscription_to_user(
    db: AsyncSession,
    *,
    plan_code: str,
    email: str | None = None,
    user_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> Subscription:
    user = await _get_user_by_identifier(db, email=email, user_id=user_id)
    if user is None:
        raise SubscriptionError("User not found", status_code=404)

    _plans, seeded = await ensure_seeded_plans(db)
    subscription = await create_subscription(
        db,
        user_id=user.id,
        plan_code=plan_code,
        provider="manual",
        event_type="subscription.assigned",
        actor_user_id=actor_user_id,
    )
    if seeded:
        await db.flush()
    await db.commit()
    await db.refresh(subscription, attribute_names=["plan"])
    return subscription


async def update_plan_definition(
    db: AsyncSession,
    *,
    plan_code: str,
    actor_user_id: uuid.UUID,
    changes: dict[str, Any],
) -> Plan:
    plan = await _get_plan_by_code(db, code=plan_code)
    for field_name, value in changes.items():
        setattr(plan, field_name, value)

    record_audit_event(
        db,
        user_id=None,
        actor_user_id=actor_user_id,
        entity_type="plan",
        entity_id=plan.id,
        event_type="plan.updated",
        event_data={
            "plan_code": plan.code,
            "changes": changes,
        },
    )
    await db.commit()
    await db.refresh(plan)
    return plan


async def set_user_role(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    role: str,
    actor_user_id: uuid.UUID,
) -> User:
    user = await _require_user_by_id(db, user_id=target_user_id)
    role_definition = await get_user_role_by_code(db, code=role)
    if role_definition is None:
        raise SubscriptionError("Role not found", status_code=404)

    user.role = role_definition.code
    record_audit_event(
        db,
        user_id=user.id,
        actor_user_id=actor_user_id,
        entity_type="user",
        entity_id=user.id,
        event_type="user.role_updated",
        event_data={"role": role_definition.code},
    )
    await db.commit()
    await db.refresh(user)
    return user


async def create_entitlement_override(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str,
    effective_to: datetime | None,
    monthly_story_limit: int | None,
    max_pages_per_story: int | None,
    image_quality_mode: str | None,
    voice_clone_limit: int | None,
    monthly_audio_chars_limit: int | None,
) -> UserEntitlementOverride:
    await _require_user_by_id(db, user_id=target_user_id)
    if all(
        value is None
        for value in (
            monthly_story_limit,
            max_pages_per_story,
            image_quality_mode,
            voice_clone_limit,
            monthly_audio_chars_limit,
        )
    ):
        raise SubscriptionError("At least one entitlement override field is required", status_code=400)

    override = UserEntitlementOverride(
        user_id=target_user_id,
        created_by_user_id=actor_user_id,
        monthly_story_limit=monthly_story_limit,
        max_pages_per_story=max_pages_per_story,
        image_quality_mode=image_quality_mode,
        voice_clone_limit=voice_clone_limit,
        monthly_audio_chars_limit=monthly_audio_chars_limit,
        reason=reason,
        effective_from=_utcnow_naive(),
        effective_to=effective_to,
        revoked_at=None,
    )
    db.add(override)
    await db.flush()
    record_audit_event(
        db,
        user_id=target_user_id,
        actor_user_id=actor_user_id,
        entity_type="user_entitlement_override",
        entity_id=override.id,
        event_type="entitlement_override.created",
        event_data={"reason": reason},
    )
    await db.commit()
    await db.refresh(override)
    return override


async def revoke_entitlement_override(
    db: AsyncSession,
    *,
    override_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> UserEntitlementOverride:
    result = await db.execute(select(UserEntitlementOverride).where(UserEntitlementOverride.id == override_id))
    override = result.scalar_one_or_none()
    if override is None:
        raise SubscriptionError("Override not found", status_code=404)

    override.revoked_at = _utcnow_naive()
    override.revoked_by_user_id = actor_user_id
    record_audit_event(
        db,
        user_id=override.user_id,
        actor_user_id=actor_user_id,
        entity_type="user_entitlement_override",
        entity_id=override.id,
        event_type="entitlement_override.revoked",
    )
    await db.commit()
    await db.refresh(override)
    return override


async def create_usage_credit_grant(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    usage_type: str,
    quantity: int,
    reason: str,
    effective_to: datetime | None,
) -> UsageCreditGrant:
    await _require_user_by_id(db, user_id=target_user_id)
    if usage_type not in USAGE_TO_LIMIT_FIELD:
        raise SubscriptionError("Unsupported usage type for grants", status_code=400)

    grant = UsageCreditGrant(
        user_id=target_user_id,
        created_by_user_id=actor_user_id,
        usage_type=usage_type,
        quantity=quantity,
        reason=reason,
        effective_from=_utcnow_naive(),
        effective_to=effective_to,
        revoked_at=None,
    )
    db.add(grant)
    await db.flush()
    record_audit_event(
        db,
        user_id=target_user_id,
        actor_user_id=actor_user_id,
        entity_type="usage_credit_grant",
        entity_id=grant.id,
        event_type="usage_credit_grant.created",
        event_data={"usage_type": usage_type, "quantity": quantity, "reason": reason},
    )
    await db.commit()
    await db.refresh(grant)
    return grant


async def revoke_usage_credit_grant(
    db: AsyncSession,
    *,
    grant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> UsageCreditGrant:
    result = await db.execute(select(UsageCreditGrant).where(UsageCreditGrant.id == grant_id))
    grant = result.scalar_one_or_none()
    if grant is None:
        raise SubscriptionError("Usage credit grant not found", status_code=404)

    grant.revoked_at = _utcnow_naive()
    grant.revoked_by_user_id = actor_user_id
    record_audit_event(
        db,
        user_id=grant.user_id,
        actor_user_id=actor_user_id,
        entity_type="usage_credit_grant",
        entity_id=grant.id,
        event_type="usage_credit_grant.revoked",
    )
    await db.commit()
    await db.refresh(grant)
    return grant


async def list_admin_users(
    db: AsyncSession,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if query:
        pattern = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                User.primary_email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars())


async def get_admin_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
