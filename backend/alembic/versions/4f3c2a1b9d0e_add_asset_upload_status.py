"""add asset upload lifecycle fields

Revision ID: 4f3c2a1b9d0e
Revises: 9dc2fd55b5fd
Create Date: 2026-03-13 17:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f3c2a1b9d0e"
down_revision: Union[str, Sequence[str], None] = "9dc2fd55b5fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


asset_upload_status = sa.Enum(
    "PENDING",
    "READY",
    "FAILED",
    name="assetuploadstatus",
)


def upgrade() -> None:
    """Upgrade schema."""
    asset_upload_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "assets",
        sa.Column(
            "upload_status",
            asset_upload_status,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("assets", sa.Column("confirmed_at", sa.DateTime(), nullable=True))
    op.alter_column("assets", "upload_status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("assets", "confirmed_at")
    op.drop_column("assets", "upload_status")
    asset_upload_status.drop(op.get_bind(), checkfirst=True)
