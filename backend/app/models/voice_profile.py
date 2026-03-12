"""VoiceProfile model — a usable cloned narration voice."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VoiceProfileStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.story import Story
    from app.models.user import User
    from app.models.voice_sample import VoiceSample


class VoiceProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "voice_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    provider_voice_id: Mapped[Optional[str]] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    clone_type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[VoiceProfileStatus] = mapped_column(
        default=VoiceProfileStatus.PENDING
    )
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    consent_confirmed: Mapped[bool] = mapped_column(default=False)
    default_for_user: Mapped[bool] = mapped_column(default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="voice_profiles")
    voice_samples: Mapped[list["VoiceSample"]] = relationship(
        back_populates="voice_profile", cascade="all, delete-orphan"
    )
    stories: Mapped[list["Story"]] = relationship(back_populates="voice_profile")
