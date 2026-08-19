"""debt renegotiation and funding continuity

Revision ID: f2i000000001
Revises: f2h000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2i000000001"
down_revision: str | None = "f2h000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    op.create_table(
        "operational_debt_continuities",
        sa.Column("id", UUID, nullable=False),
        sa.Column("source_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("continuity_type", sa.String(length=24), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("predecessor_sale_identity_id", UUID, nullable=True),
        sa.Column("successor_sale_identity_id", UUID, nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="REVIEW_REQUIRED",
            nullable=False,
        ),
        sa.Column("original_principal", MONEY, nullable=True),
        sa.Column("principal_paid", MONEY, nullable=True),
        sa.Column("principal_rolled", MONEY, nullable=True),
        sa.Column("interest_paid", MONEY, nullable=True),
        sa.Column("has_new_disbursement", sa.Boolean(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("confirmed_by", UUID, nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "continuity_type IN ('RENEGOTIATION', 'ROLLOVER')",
            name="ck_operational_debt_continuities_type",
        ),
        sa.CheckConstraint(
            "scope IN ('SAME_CONTRACT', 'NEW_CONTRACT')",
            name="ck_operational_debt_continuities_scope",
        ),
        sa.CheckConstraint(
            "status IN ('REVIEW_REQUIRED', 'RENEGOTIATION_CONFIRMED', 'REJECTED')",
            name="ck_operational_debt_continuities_status",
        ),
        sa.CheckConstraint(
            "original_principal IS NULL OR original_principal >= 0",
            name="ck_operational_debt_continuities_original_principal",
        ),
        sa.CheckConstraint(
            "principal_paid IS NULL OR principal_paid >= 0",
            name="ck_operational_debt_continuities_principal_paid",
        ),
        sa.CheckConstraint(
            "principal_rolled IS NULL OR principal_rolled >= 0",
            name="ck_operational_debt_continuities_principal_rolled",
        ),
        sa.CheckConstraint(
            "interest_paid IS NULL OR interest_paid >= 0",
            name="ck_operational_debt_continuities_interest_paid",
        ),
        sa.CheckConstraint(
            "original_principal IS NULL OR principal_paid IS NULL OR principal_rolled IS NULL "
            "OR original_principal = principal_paid + principal_rolled",
            name="ck_operational_debt_continuities_principal_equation",
        ),
        sa.CheckConstraint(
            "status <> 'RENEGOTIATION_CONFIRMED' OR "
            "(predecessor_sale_identity_id IS NOT NULL AND has_new_disbursement IS NOT NULL "
            "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_operational_debt_continuities_confirmation",
        ),
        sa.CheckConstraint(
            "predecessor_sale_identity_id IS NULL OR "
            "(scope = 'SAME_CONTRACT') = "
            "(predecessor_sale_identity_id = successor_sale_identity_id)",
            name="ck_operational_debt_continuities_scope_identity",
        ),
        sa.ForeignKeyConstraint(
            ["source_batch_id"],
            ["operational_import_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_sale_identity_id"],
            ["operational_sale_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_sale_identity_id"],
            ["operational_sale_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_batch_id",
            "successor_sale_identity_id",
            name="uq_operational_debt_continuities_batch_successor",
        ),
    )
    op.create_index(
        "ix_operational_debt_continuities_source_batch_id",
        "operational_debt_continuities",
        ["source_batch_id"],
    )
    op.create_index(
        "ix_operational_debt_continuities_predecessor",
        "operational_debt_continuities",
        ["predecessor_sale_identity_id"],
    )
    op.create_index(
        "ix_operational_debt_continuities_successor_status",
        "operational_debt_continuities",
        ["successor_sale_identity_id", "status"],
    )

    op.create_table(
        "operational_debt_funding_continuities",
        sa.Column("id", UUID, nullable=False),
        sa.Column("continuity_id", UUID, nullable=False),
        sa.Column("successor_sale_identity_id", UUID, nullable=False),
        sa.Column("origin_allocation_id", UUID, nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("rolled_amount", MONEY, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rolled_amount > 0",
            name="ck_operational_debt_funding_continuities_amount",
        ),
        sa.ForeignKeyConstraint(
            ["continuity_id"],
            ["operational_debt_continuities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_sale_identity_id"],
            ["operational_sale_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["origin_allocation_id"],
            ["funding_allocations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["funding_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "continuity_id",
            "origin_allocation_id",
            name="uq_operational_debt_funding_continuities_allocation",
        ),
    )
    op.create_index(
        "ix_operational_debt_funding_continuities_continuity_id",
        "operational_debt_funding_continuities",
        ["continuity_id"],
    )
    op.create_index(
        "ix_operational_debt_funding_continuities_source_id",
        "operational_debt_funding_continuities",
        ["source_id"],
    )
    op.create_index(
        "ix_operational_debt_funding_continuities_successor",
        "operational_debt_funding_continuities",
        ["successor_sale_identity_id"],
    )

    op.create_table(
        "operational_debt_continuity_audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("continuity_id", UUID, nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('REVIEW_CREATED', 'RENEGOTIATION_CONFIRMED', 'REJECTED')",
            name="ck_operational_debt_continuity_audit_action",
        ),
        sa.ForeignKeyConstraint(
            ["continuity_id"],
            ["operational_debt_continuities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_debt_continuity_audit_continuity_created",
        "operational_debt_continuity_audit_events",
        ["continuity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_debt_continuity_audit_continuity_created",
        table_name="operational_debt_continuity_audit_events",
    )
    op.drop_table("operational_debt_continuity_audit_events")
    op.drop_index(
        "ix_operational_debt_funding_continuities_successor",
        table_name="operational_debt_funding_continuities",
    )
    op.drop_index(
        "ix_operational_debt_funding_continuities_source_id",
        table_name="operational_debt_funding_continuities",
    )
    op.drop_index(
        "ix_operational_debt_funding_continuities_continuity_id",
        table_name="operational_debt_funding_continuities",
    )
    op.drop_table("operational_debt_funding_continuities")
    op.drop_index(
        "ix_operational_debt_continuities_successor_status",
        table_name="operational_debt_continuities",
    )
    op.drop_index(
        "ix_operational_debt_continuities_predecessor",
        table_name="operational_debt_continuities",
    )
    op.drop_index(
        "ix_operational_debt_continuities_source_batch_id",
        table_name="operational_debt_continuities",
    )
    op.drop_table("operational_debt_continuities")
