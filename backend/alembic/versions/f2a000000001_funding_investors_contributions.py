"""Phase 2A real funding investors and contributions.

Revision ID: f2a000000001
Revises: f1c000000001
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a000000001"
down_revision: str | None = "f1c000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "funding_investors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_funding_investors_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_funding_investors_code", "funding_investors", ["code"])
    op.create_index("ix_funding_investors_name", "funding_investors", ["name"])
    op.create_index("ix_funding_investors_status", "funding_investors", ["status"])

    op.create_table(
        "funding_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("investor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contribution_date", sa.Date(), nullable=False),
        sa.Column("original_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("monthly_rate", sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("original_amount_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("original_amount > 0", name="ck_funding_contributions_amount_positive"),
        sa.CheckConstraint("monthly_rate >= 0 AND monthly_rate <= 1", name="ck_funding_contributions_monthly_rate"),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE', 'CLOSED')", name="ck_funding_contributions_status"),
        sa.ForeignKeyConstraint(["investor_id"], ["funding_investors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_funding_contributions_code", "funding_contributions", ["code"])
    op.create_index("ix_funding_contributions_investor_id", "funding_contributions", ["investor_id"])
    op.create_index("ix_funding_contributions_contribution_date", "funding_contributions", ["contribution_date"])
    op.create_index("ix_funding_contributions_status", "funding_contributions", ["status"])

    op.create_table(
        "funding_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("entity_type IN ('INVESTOR', 'CONTRIBUTION')", name="ck_funding_audit_events_entity_type"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funding_audit_events_entity_type", "funding_audit_events", ["entity_type"])
    op.create_index("ix_funding_audit_events_entity_id", "funding_audit_events", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_funding_audit_events_entity_id", table_name="funding_audit_events")
    op.drop_index("ix_funding_audit_events_entity_type", table_name="funding_audit_events")
    op.drop_table("funding_audit_events")
    op.drop_index("ix_funding_contributions_status", table_name="funding_contributions")
    op.drop_index("ix_funding_contributions_contribution_date", table_name="funding_contributions")
    op.drop_index("ix_funding_contributions_investor_id", table_name="funding_contributions")
    op.drop_index("ix_funding_contributions_code", table_name="funding_contributions")
    op.drop_table("funding_contributions")
    op.drop_index("ix_funding_investors_status", table_name="funding_investors")
    op.drop_index("ix_funding_investors_name", table_name="funding_investors")
    op.drop_index("ix_funding_investors_code", table_name="funding_investors")
    op.drop_table("funding_investors")
