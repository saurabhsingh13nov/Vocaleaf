"""Story endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.story import StoryCreate, StoryListItem, StoryResponse
from app.services.story import (
    StoryError,
    create_story,
    delete_story,
    get_story,
    list_stories,
    story_latest_error_message,
)

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.post("", response_model=StoryResponse, status_code=status.HTTP_202_ACCEPTED)
async def create(
    body: StoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        story = await create_story(db, user_id=current_user.id, data=body)
    except StoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return StoryResponse.from_model(
        story,
        latest_error_message=story_latest_error_message(story),
    )


@router.get("", response_model=list[StoryListItem])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stories = await list_stories(db, user_id=current_user.id, limit=limit, offset=offset)
    return [
        StoryListItem.from_model(story, latest_error_message=story_latest_error_message(story))
        for story in stories
    ]


@router.get("/{story_id}", response_model=StoryResponse)
async def get_one(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await get_story(db, user_id=current_user.id, story_id=story_id)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    return StoryResponse.from_model(
        story,
        latest_error_message=story_latest_error_message(story),
    )


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_one(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_story(db, user_id=current_user.id, story_id=story_id)
    except StoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
