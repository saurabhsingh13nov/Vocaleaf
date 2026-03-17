"""Per-user absolute entitlement overrides."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserEntitlementOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_entitlement_overrides"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    monthly_story_limit: Mapped[Optional[int]]
    max_pages_per_story: Mapped[Optional[int]]
    image_quality_mode: Mapped[Optional[str]] = mapped_column(String(50))
    voice_clone_limit: Mapped[Optional[int]]
    monthly_audio_chars_limit: Mapped[Optional[int]]
    reason: Mapped[str] = mapped_column(String(255))
    effective_from: Mapped[datetime]
    effective_to: Mapped[Optional[datetime]]
    revoked_at: Mapped[Optional[datetime]]

    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        back_populates="entitlement_overrides",
    )
    created_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id],
        back_populates="created_entitlement_overrides",
    )
    revoked_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[revoked_by_user_id],
        back_populates="revoked_entitlement_overrides",
    )
