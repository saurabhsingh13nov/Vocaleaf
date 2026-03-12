"""CharacterProfile model — reusable character definitions for visual continuity."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.child import Child
    from app.models.story_character import StoryCharacter
    from app.models.user import User


class CharacterProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "character_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    child_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("children.id", ondelete="SET NULL")
    )
    reference_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[Optional[str]] = mapped_column(String(100))
    visual_description: Mapped[Optional[str]] = mapped_column(Text)
    style_notes: Mapped[Optional[str]] = mapped_column(Text)
    canonical_traits_json: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="character_profiles")
    child: Mapped[Optional["Child"]] = relationship(back_populates="character_profiles")
    reference_asset: Mapped[Optional["Asset"]] = relationship()
    story_characters: Mapped[list["StoryCharacter"]] = relationship(
        back_populates="character_profile"
    )
