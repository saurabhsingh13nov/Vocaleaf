"""Child model — child profile used for story personalization."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.character_profile import CharacterProfile
    from app.models.story import Story
    from app.models.user import User


class Child(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "children"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[Optional[int]]
    favorite_themes: Mapped[Optional[dict]] = mapped_column(JSONB)
    favorite_characters: Mapped[Optional[dict]] = mapped_column(JSONB)
    bedtime_preferences: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="children")
    stories: Mapped[list["Story"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    character_profiles: Mapped[list["CharacterProfile"]] = relationship(
        back_populates="child"
    )
