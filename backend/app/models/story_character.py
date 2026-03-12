"""StoryCharacter model — join table connecting stories to character profiles."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.character_profile import CharacterProfile
    from app.models.story import Story


class StoryCharacter(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "story_characters"
    __table_args__ = (
        UniqueConstraint(
            "story_id", "character_profile_id", name="uq_story_character"
        ),
    )

    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    character_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character_profiles.id", ondelete="CASCADE"), index=True
    )
    role_in_story: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="story_characters")
    character_profile: Mapped["CharacterProfile"] = relationship(
        back_populates="story_characters"
    )
