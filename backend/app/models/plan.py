"""Plan model — product tier definitions for billing."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class Plan(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100))
    monthly_story_limit: Mapped[Optional[int]]
    max_pages_per_story: Mapped[Optional[int]]
    image_quality_mode: Mapped[Optional[str]] = mapped_column(String(50))
    voice_clone_limit: Mapped[Optional[int]]
    monthly_audio_chars_limit: Mapped[Optional[int]]
    price_cents: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default="now()"
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")
