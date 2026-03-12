"""Pydantic request/response models for child profile endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=17)
    favorite_themes: Optional[dict] = None
    favorite_characters: Optional[dict] = None
    bedtime_preferences: Optional[dict] = None


class ChildUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=17)
    favorite_themes: Optional[dict] = None
    favorite_characters: Optional[dict] = None
    bedtime_preferences: Optional[dict] = None


class ChildResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: Optional[int]
    favorite_themes: Optional[dict]
    favorite_characters: Optional[dict]
    bedtime_preferences: Optional[dict]
    created_at: datetime
    updated_at: datetime
