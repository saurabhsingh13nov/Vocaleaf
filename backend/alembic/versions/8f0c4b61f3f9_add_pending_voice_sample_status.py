"""add pending voice sample status

Revision ID: 8f0c4b61f3f9
Revises: 4f3c2a1b9d0e
Create Date: 2026-03-13 20:50:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8f0c4b61f3f9"
down_revision: Union[str, Sequence[str], None] = "4f3c2a1b9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE voicesamplestatus ADD VALUE IF NOT EXISTS 'PENDING'")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for enum value removals")
