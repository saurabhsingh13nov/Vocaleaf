"""Child profile endpoints — CRUD for child profiles."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.child import ChildCreate, ChildResponse, ChildUpdate
from app.services.child import (
    create_child,
    delete_child,
    get_child,
    list_children,
    update_child,
)

router = APIRouter(prefix="/api/children", tags=["children"])


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
async def create(
    body: ChildCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    child = await create_child(db, current_user.id, body)
    return child


@router.get("", response_model=list[ChildResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_children(db, current_user.id)


@router.get("/{child_id}", response_model=ChildResponse)
async def get_one(
    child_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    child = await get_child(db, current_user.id, child_id)
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    return child


@router.put("/{child_id}", response_model=ChildResponse)
async def update(
    child_id: uuid.UUID,
    body: ChildUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    child = await update_child(db, current_user.id, child_id, body)
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    return child


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    child_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_child(db, current_user.id, child_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
