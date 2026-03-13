"""VoiceSample model — raw uploaded recordings for voice cloning."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VoiceSampleStatus
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.voice_profile import VoiceProfile


class VoiceSample(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "voice_samples"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    voice_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voice_profiles.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    duration_seconds: Mapped[Optional[float]]
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    sample_quality_score: Mapped[Optional[float]]
    status: Mapped[VoiceSampleStatus] = mapped_column(
        default=VoiceSampleStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    # Relationships
    voice_profile: Mapped["VoiceProfile"] = relationship(
        back_populates="voice_samples"
    )
    asset: Mapped[Optional["Asset"]] = relationship()
