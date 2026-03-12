"""Story model — the top-level story record."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import StoryStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.child import Child
    from app.models.story_character import StoryCharacter
    from app.models.story_generation_job import StoryGenerationJob
    from app.models.story_page import StoryPage
    from app.models.voice_profile import VoiceProfile


class Story(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stories"
    __table_args__ = (
        Index("ix_stories_user_child_status", "user_id", "child_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    voice_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("voice_profiles.id", ondelete="SET NULL")
    )
    cover_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    title: Mapped[Optional[str]] = mapped_column(String(500))
    prompt: Mapped[Optional[str]] = mapped_column(Text)
    theme: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[StoryStatus] = mapped_column(default=StoryStatus.DRAFT)
    target_page_count: Mapped[Optional[int]]
    reading_level: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="en")
    art_style: Mapped[Optional[str]] = mapped_column(String(100))
    generation_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    child: Mapped["Child"] = relationship(back_populates="stories")
    voice_profile: Mapped[Optional["VoiceProfile"]] = relationship(
        back_populates="stories"
    )
    cover_asset: Mapped[Optional["Asset"]] = relationship()
    pages: Mapped[list["StoryPage"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list["StoryGenerationJob"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    story_characters: Mapped[list["StoryCharacter"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
