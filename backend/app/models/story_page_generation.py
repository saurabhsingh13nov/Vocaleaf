"""StoryPageGeneration model — tracks one generation attempt for one page/modality."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import GenerationType, JobStatus
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.story_generation_job import StoryGenerationJob
    from app.models.story_page import StoryPage


class StoryPageGeneration(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "story_page_generations"

    story_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_pages.id", ondelete="CASCADE"), index=True
    )
    generation_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_generation_jobs.id", ondelete="CASCADE"), index=True
    )
    generation_type: Mapped[GenerationType]
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    request_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    completed_at: Mapped[Optional[datetime]]

    # Relationships
    story_page: Mapped["StoryPage"] = relationship(back_populates="page_generations")
    generation_job: Mapped["StoryGenerationJob"] = relationship(
        back_populates="page_generations"
    )
