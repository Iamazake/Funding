"""Fase 2F: autenticação, sessões e controle de acesso.

Revision ID: f2f000000001
Revises: f2e200000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2f000000001"
down_revision: str | None = "f2e200000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("role IN ('ADMIN', 'ANALYST')", name="ck_app_users_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_app_users_status"),
        sa.CheckConstraint(
            "email = lower(btrim(email))", name="ck_app_users_email_normalized"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_app_users_email_lower",
        "app_users",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.create_table(
        "app_auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_app_auth_sessions_token_hash"),
    )
    op.create_index("ix_app_auth_sessions_user_id", "app_auth_sessions", ["user_id"])
    op.create_index("ix_app_auth_sessions_expires_at", "app_auth_sessions", ["expires_at"])

    op.create_table(
        "app_user_audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["app_users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_app_user_audit_events_actor", "app_user_audit_events", ["actor_user_id"]
    )
    op.create_index(
        "ix_app_user_audit_events_target", "app_user_audit_events", ["target_user_id"]
    )
    op.create_index(
        "ix_app_user_audit_events_action", "app_user_audit_events", ["action"]
    )

    op.add_column("funding_audit_events", sa.Column("actor_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_funding_audit_events_actor_user_id",
        "funding_audit_events",
        "app_users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_funding_audit_events_actor_user_id",
        "funding_audit_events",
        ["actor_user_id"],
    )

    op.alter_column(
        "treasury_bank_validations",
        "validated_by",
        new_column_name="validated_by_legacy",
        existing_type=sa.String(length=120),
        existing_nullable=True,
    )
    op.add_column(
        "treasury_bank_validations", sa.Column("validated_by", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_treasury_bank_validations_validated_by",
        "treasury_bank_validations",
        "app_users",
        ["validated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_treasury_bank_validations_validated_by",
        "treasury_bank_validations",
        ["validated_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_treasury_bank_validations_validated_by",
        table_name="treasury_bank_validations",
    )
    op.drop_constraint(
        "fk_treasury_bank_validations_validated_by",
        "treasury_bank_validations",
        type_="foreignkey",
    )
    op.drop_column("treasury_bank_validations", "validated_by")
    op.alter_column(
        "treasury_bank_validations",
        "validated_by_legacy",
        new_column_name="validated_by",
        existing_type=sa.String(length=120),
        existing_nullable=True,
    )

    op.drop_index("ix_funding_audit_events_actor_user_id", table_name="funding_audit_events")
    op.drop_constraint(
        "fk_funding_audit_events_actor_user_id", "funding_audit_events", type_="foreignkey"
    )
    op.drop_column("funding_audit_events", "actor_user_id")

    op.drop_index("ix_app_user_audit_events_action", table_name="app_user_audit_events")
    op.drop_index("ix_app_user_audit_events_target", table_name="app_user_audit_events")
    op.drop_index("ix_app_user_audit_events_actor", table_name="app_user_audit_events")
    op.drop_table("app_user_audit_events")
    op.drop_index("ix_app_auth_sessions_expires_at", table_name="app_auth_sessions")
    op.drop_index("ix_app_auth_sessions_user_id", table_name="app_auth_sessions")
    op.drop_table("app_auth_sessions")
    op.drop_index("uq_app_users_email_lower", table_name="app_users")
    op.drop_table("app_users")
