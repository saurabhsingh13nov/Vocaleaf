"""Per-user additive usage credit grants."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UsageCreditGrant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_credit_grants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    usage_type: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[int]
    reason: Mapped[str] = mapped_column(String(255))
    effective_from: Mapped[datetime]
    effective_to: Mapped[Optional[datetime]]
    revoked_at: Mapped[Optional[datetime]]

    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        back_populates="usage_credit_grants",
    )
    created_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id],
        back_populates="created_usage_credit_grants",
    )
    revoked_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[revoked_by_user_id],
        back_populates="revoked_usage_credit_grants",
    )
