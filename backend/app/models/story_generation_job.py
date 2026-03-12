"""StoryGenerationJob model — tracks async generation workflows."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import JobStatus
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.story import Story
    from app.models.story_page_generation import StoryPageGeneration


class StoryGenerationJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "story_generation_jobs"

    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)
    provider_text: Mapped[Optional[str]] = mapped_column(String(50))
    provider_image: Mapped[Optional[str]] = mapped_column(String(50))
    provider_audio: Mapped[Optional[str]] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]]
    completed_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    # Relationships
    story: Mapped["Story"] = relationship(back_populates="generation_jobs")
    page_generations: Mapped[list["StoryPageGeneration"]] = relationship(
        back_populates="generation_job"
    )
