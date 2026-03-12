"""User model — the app account that owns all product data."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.audit_event import AuditEvent
    from app.models.auth_identity import AuthIdentity
    from app.models.character_profile import CharacterProfile
    from app.models.child import Child
    from app.models.consent import Consent
    from app.models.subscription import Subscription
    from app.models.usage_record import UsageRecord
    from app.models.voice_profile import VoiceProfile


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    primary_email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048))
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.ACTIVE)
    email_verified_at: Mapped[Optional[datetime]]
    last_login_at: Mapped[Optional[datetime]]

    # Relationships
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    children: Mapped[list["Child"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    voice_profiles: Mapped[list["VoiceProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    consents: Mapped[list["Consent"]] = relationship(back_populates="user")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="user")
    usage_records: Mapped[list["UsageRecord"]] = relationship(back_populates="user")
    character_profiles: Mapped[list["CharacterProfile"]] = relationship(
        back_populates="user"
    )
