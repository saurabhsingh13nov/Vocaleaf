"""normalize user roles into a table-backed catalog

Revision ID: c4f7d2e9a1b6
Revises: b7e1c3f4a9d2
Create Date: 2026-03-17 15:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4f7d2e9a1b6"
down_revision: Union[str, Sequence[str], None] = "b7e1c3f4a9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


legacy_user_role = postgresql.ENUM(
    "CUSTOMER",
    "STAFF",
    "ADMIN",
    name="userrole",
)


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.execute(
        """
        INSERT INTO user_roles (code, display_name, description)
        VALUES
            ('customer', 'Customer', 'Standard customer account with no internal admin access.'),
            ('staff', 'Staff', 'Internal support role with access to support tooling.'),
            ('admin', 'Admin', 'Internal admin role with access to plan and role management.')
        """
    )

    op.alter_column(
        "users",
        "role",
        existing_type=legacy_user_role,
        type_=sa.String(length=50),
        postgresql_using="lower(role::text)",
        existing_nullable=False,
    )
    op.create_foreign_key(
        "fk_users_role_user_roles",
        "users",
        "user_roles",
        ["role"],
        ["code"],
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    legacy_user_role.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()

    legacy_user_role.create(bind, checkfirst=True)

    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_constraint("fk_users_role_user_roles", "users", type_="foreignkey")
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=50),
        type_=legacy_user_role,
        postgresql_using="upper(role)::userrole",
        existing_nullable=False,
    )

    op.drop_table("user_roles")
