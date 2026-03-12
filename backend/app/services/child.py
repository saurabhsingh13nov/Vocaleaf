"""Child profile business logic — CRUD with ownership enforcement."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.child import Child
from app.schemas.child import ChildCreate, ChildUpdate


async def create_child(
    db: AsyncSession, user_id: uuid.UUID, data: ChildCreate
) -> Child:
    child = Child(user_id=user_id, **data.model_dump())
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


async def list_children(db: AsyncSession, user_id: uuid.UUID) -> list[Child]:
    result = await db.execute(
        select(Child).where(Child.user_id == user_id).order_by(Child.created_at)
    )
    return list(result.scalars().all())


async def get_child(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> Child | None:
    result = await db.execute(
        select(Child).where(Child.id == child_id, Child.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_child(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID, data: ChildUpdate
) -> Child | None:
    child = await get_child(db, user_id, child_id)
    if not child:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(child, field, value)

    await db.commit()
    await db.refresh(child)
    return child


async def delete_child(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> bool:
    child = await get_child(db, user_id, child_id)
    if not child:
        return False

    await db.delete(child)
    await db.commit()
    return True
