"""UsageRecord model — metered usage and cost data."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UsageRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_user_type_created", "user_id", "usage_type", "created_at"),
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL")
    )
    story_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_pages.id", ondelete="SET NULL")
    )
    usage_type: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[float]
    unit: Mapped[str] = mapped_column(String(50))
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    provider_cost_micros: Mapped[Optional[int]]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="usage_records")
