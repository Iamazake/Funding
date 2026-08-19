"""Phase 2E.2 manual Treasury bank validations.

Revision ID: f2e200000001
Revises: f2c000000001
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2e200000001"
down_revision: str | None = "f2c000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "treasury_bank_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("supersedes_validation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("system_amount_snapshot", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("system_date_snapshot", sa.Date(), nullable=True),
        sa.Column("observed_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("difference_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("bank_reference", sa.String(length=255), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("validated_by", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "movement_type IN ('CONTRIBUTION', 'SALE', 'REVENUE')",
            name="ck_treasury_bank_validations_movement_type",
        ),
        sa.CheckConstraint(
            "direction IN ('INFLOW', 'OUTFLOW')",
            name="ck_treasury_bank_validations_direction",
        ),
        sa.CheckConstraint(
            "status IN ('VALIDATED', 'DIVERGENT')",
            name="ck_treasury_bank_validations_status",
        ),
        sa.CheckConstraint(
            "system_amount_snapshot > 0 AND observed_amount >= 0",
            name="ck_treasury_bank_validations_amounts",
        ),
        sa.CheckConstraint(
            "difference_amount = observed_amount - system_amount_snapshot",
            name="ck_treasury_bank_validations_difference",
        ),
        sa.CheckConstraint(
            "(difference_amount = 0 AND status = 'VALIDATED') OR "
            "(difference_amount <> 0 AND status = 'DIVERGENT')",
            name="ck_treasury_bank_validations_status_difference",
        ),
        sa.CheckConstraint(
            "status <> 'DIVERGENT' OR "
            "(justification IS NOT NULL AND btrim(justification) <> '')",
            name="ck_treasury_bank_validations_divergent_justification",
        ),
        sa.CheckConstraint("version > 0", name="ck_treasury_bank_validations_version"),
        sa.ForeignKeyConstraint(
            ["supersedes_validation_id"],
            ["treasury_bank_validations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "movement_key",
            "version",
            name="uq_treasury_bank_validations_movement_version",
        ),
        sa.UniqueConstraint(
            "supersedes_validation_id",
            name="uq_treasury_bank_validations_supersedes",
        ),
    )
    op.create_index(
        "ix_treasury_bank_validations_movement_key",
        "treasury_bank_validations",
        ["movement_key"],
    )
    op.create_index(
        "ix_treasury_bank_validations_status",
        "treasury_bank_validations",
        ["status"],
    )
    op.create_index(
        "uq_treasury_bank_validations_current",
        "treasury_bank_validations",
        ["movement_key"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_treasury_bank_validations_current",
        table_name="treasury_bank_validations",
    )
    op.drop_index(
        "ix_treasury_bank_validations_status",
        table_name="treasury_bank_validations",
    )
    op.drop_index(
        "ix_treasury_bank_validations_movement_key",
        table_name="treasury_bank_validations",
    )
    op.drop_table("treasury_bank_validations")
