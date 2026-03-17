"""add admin roles and entitlement support schema

Revision ID: b7e1c3f4a9d2
Revises: 8f0c4b61f3f9
Create Date: 2026-03-17 09:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e1c3f4a9d2"
down_revision: Union[str, Sequence[str], None] = "8f0c4b61f3f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role = sa.Enum(
    "CUSTOMER",
    "STAFF",
    "ADMIN",
    name="userrole",
)


def upgrade() -> None:
    bind = op.get_bind()

    user_role.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role,
            nullable=False,
            server_default="CUSTOMER",
        ),
    )
    op.alter_column("users", "role", server_default=None)

    op.add_column("plans", sa.Column("code", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE plans
        SET code = CASE
            WHEN lower(name) = 'free' THEN 'free'
            WHEN lower(name) = 'premium' THEN 'premium'
            ELSE lower(regexp_replace(name, '[^a-zA-Z0-9]+', '_', 'g'))
        END
        WHERE code IS NULL
        """
    )
    op.alter_column("plans", "code", nullable=False)
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)

    op.add_column("audit_events", sa.Column("actor_user_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE audit_events
        SET actor_user_id = user_id
        WHERE actor_user_id IS NULL
        """
    )
    op.create_foreign_key(
        "fk_audit_events_actor_user_id_users",
        "audit_events",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_id"),
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )

    op.create_table(
        "user_entitlement_overrides",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("monthly_story_limit", sa.Integer(), nullable=True),
        sa.Column("max_pages_per_story", sa.Integer(), nullable=True),
        sa.Column("image_quality_mode", sa.String(length=50), nullable=True),
        sa.Column("voice_clone_limit", sa.Integer(), nullable=True),
        sa.Column("monthly_audio_chars_limit", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_entitlement_overrides_user_id"),
        "user_entitlement_overrides",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "usage_credit_grants",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("usage_type", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_usage_credit_grants_user_id"),
        "usage_credit_grants",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f("ix_usage_credit_grants_user_id"), table_name="usage_credit_grants")
    op.drop_table("usage_credit_grants")

    op.drop_index(op.f("ix_user_entitlement_overrides_user_id"), table_name="user_entitlement_overrides")
    op.drop_table("user_entitlement_overrides")

    op.drop_index(op.f("ix_audit_events_actor_user_id"), table_name="audit_events")
    op.drop_constraint("fk_audit_events_actor_user_id_users", "audit_events", type_="foreignkey")
    op.drop_column("audit_events", "actor_user_id")

    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_column("plans", "code")

    op.drop_column("users", "role")
    user_role.drop(bind, checkfirst=True)
