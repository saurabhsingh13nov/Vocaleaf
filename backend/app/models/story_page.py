"""StoryPage model — one page within a story."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import StoryPageStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.story import Story
    from app.models.story_page_generation import StoryPageGeneration


class StoryPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_pages"
    __table_args__ = (
        UniqueConstraint("story_id", "page_number", name="uq_story_page_number"),
    )

    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    text_content: Mapped[Optional[str]] = mapped_column(Text)
    image_prompt: Mapped[Optional[str]] = mapped_column(Text)
    continuity_notes: Mapped[Optional[str]] = mapped_column(Text)
    image_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    audio_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    duration_ms: Mapped[Optional[int]]
    status: Mapped[StoryPageStatus] = mapped_column(default=StoryPageStatus.PENDING)

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="pages")
    image_asset: Mapped[Optional["Asset"]] = relationship(
        foreign_keys=[image_asset_id]
    )
    audio_asset: Mapped[Optional["Asset"]] = relationship(
        foreign_keys=[audio_asset_id]
    )
    page_generations: Mapped[list["StoryPageGeneration"]] = relationship(
        back_populates="story_page"
    )
