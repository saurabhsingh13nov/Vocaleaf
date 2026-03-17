"""Append-only audit helpers for compliance and support workflows."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


def record_audit_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        actor_user_id=actor_user_id if actor_user_id is not None else user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        event_data_json=event_data,
    )
    db.add(event)
    return event


async def list_recent_audit_events_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 25,
) -> list[AuditEvent]:
    result = await db.execute(
        select(AuditEvent)
        .where(
            or_(
                AuditEvent.user_id == user_id,
                AuditEvent.actor_user_id == user_id,
            )
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(result.scalars())
