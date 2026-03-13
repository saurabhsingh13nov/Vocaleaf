"""Asset model — metadata and upload lifecycle for stored objects."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AssetType, AssetUploadStatus
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Asset(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    storage_provider: Mapped[str] = mapped_column(String(50), default="r2")
    bucket_name: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    asset_type: Mapped[AssetType]
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]]
    checksum: Mapped[Optional[str]] = mapped_column(String(128))
    width: Mapped[Optional[int]]
    height: Mapped[Optional[int]]
    duration_ms: Mapped[Optional[int]]
    is_private: Mapped[bool] = mapped_column(default=True)
    upload_status: Mapped[AssetUploadStatus] = mapped_column(
        default=AssetUploadStatus.PENDING
    )
    confirmed_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    deleted_at: Mapped[Optional[datetime]]

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="assets")
