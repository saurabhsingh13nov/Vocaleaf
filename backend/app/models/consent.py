"""Consent model — explicit user consent for legal/sensitive actions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ConsentType
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Consent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "consents"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    consent_type: Mapped[ConsentType]
    accepted_version: Mapped[str] = mapped_column(String(50))
    accepted_at: Mapped[datetime] = mapped_column(server_default="now()")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="consents")
