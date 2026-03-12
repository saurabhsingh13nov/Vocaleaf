"""Subscription model — user's active or historical subscription state."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SubscriptionStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.user import User


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id"), index=True
    )
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[SubscriptionStatus] = mapped_column(
        default=SubscriptionStatus.ACTIVE
    )
    current_period_start: Mapped[Optional[datetime]]
    current_period_end: Mapped[Optional[datetime]]
    cancel_at: Mapped[Optional[datetime]]

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
