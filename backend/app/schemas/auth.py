"""Pydantic request/response models for auth endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    primary_email: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    status: str
    email_verified_at: Optional[datetime]
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
