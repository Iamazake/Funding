"""Phase 2C revenue distributions and principal returns.

Revision ID: f2c000000001
Revises: f2b000000001
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2c000000001"
down_revision: str | None = "f2b000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', "
        "'ALLOCATION', 'DISTRIBUTION')",
    )

    op.create_table(
        "funding_revenue_distributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revenue_id", sa.BigInteger(), nullable=False),
        sa.Column("sale_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("composition_hash", sa.String(length=64), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("principal_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("identified_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("distributed_principal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("distributed_interest", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("distributed_discount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unidentified_principal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unidentified_interest", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unidentified_discount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DISTRIBUTED', 'DIVERGENT', 'REVERSED')",
            name="ck_funding_revenue_distributions_status",
        ),
        sa.CheckConstraint(
            "sale_id ~ '^(contract|loan):[1-9][0-9]*$'",
            name="ck_funding_revenue_distributions_sale_id",
        ),
        sa.CheckConstraint(
            "version > 0", name="ck_funding_revenue_distributions_version"
        ),
        sa.CheckConstraint(
            "base_amount > 0", name="ck_funding_revenue_distributions_base"
        ),
        sa.CheckConstraint(
            "principal_amount >= 0 AND interest_amount >= 0 AND discount_amount >= 0",
            name="ck_funding_revenue_distributions_components",
        ),
        sa.CheckConstraint(
            "identified_amount >= 0 AND distributed_principal >= 0 "
            "AND distributed_interest >= 0 "
            "AND distributed_discount >= 0 AND unidentified_principal >= 0 "
            "AND unidentified_interest >= 0 AND unidentified_discount >= 0",
            name="ck_funding_revenue_distributions_totals",
        ),
        sa.ForeignKeyConstraint(
            ["revenue_id"], ["operational_installments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revenue_id", "version", name="uq_funding_revenue_distributions_version"
        ),
    )
    op.create_index(
        "ix_funding_revenue_distributions_revenue_id",
        "funding_revenue_distributions",
        ["revenue_id"],
    )
    op.create_index(
        "ix_funding_revenue_distributions_sale_id",
        "funding_revenue_distributions",
        ["sale_id"],
    )
    op.create_index(
        "uq_funding_revenue_distributions_divergent_snapshot",
        "funding_revenue_distributions",
        ["revenue_id", "composition_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'DIVERGENT'"),
    )
    op.create_index(
        "uq_funding_revenue_distributions_active",
        "funding_revenue_distributions",
        ["revenue_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DISTRIBUTED'"),
    )

    op.create_table(
        "funding_revenue_distribution_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("distribution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participation_rate", sa.Numeric(precision=18, scale=12), nullable=False),
        sa.Column("allocation_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("principal_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "participation_rate >= 0 AND participation_rate <= 1",
            name="ck_funding_revenue_distribution_items_rate",
        ),
        sa.CheckConstraint(
            "allocation_amount > 0 AND base_amount > 0",
            name="ck_funding_revenue_distribution_items_base",
        ),
        sa.CheckConstraint(
            "principal_amount >= 0 AND interest_amount >= 0 AND discount_amount >= 0",
            name="ck_funding_revenue_distribution_items_components",
        ),
        sa.ForeignKeyConstraint(
            ["distribution_id"], ["funding_revenue_distributions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["funding_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["allocation_id"], ["funding_allocations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "distribution_id",
            "allocation_id",
            name="uq_funding_revenue_distribution_items_allocation",
        ),
    )
    op.create_index(
        "ix_funding_revenue_distribution_items_distribution_id",
        "funding_revenue_distribution_items",
        ["distribution_id"],
    )
    op.create_index(
        "ix_funding_revenue_distribution_items_source_id",
        "funding_revenue_distribution_items",
        ["source_id"],
    )

    op.drop_constraint(
        "ck_funding_ledger_origin_type", "funding_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_funding_ledger_relationships", "funding_ledger_entries", type_="check"
    )
    op.add_column(
        "funding_ledger_entries",
        sa.Column("revenue_distribution_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_funding_ledger_revenue_distribution_item",
        "funding_ledger_entries",
        "funding_revenue_distribution_items",
        ["revenue_distribution_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_funding_ledger_revenue_distribution_item",
        "funding_ledger_entries",
        ["revenue_distribution_item_id"],
    )
    op.create_check_constraint(
        "ck_funding_ledger_origin_type",
        "funding_ledger_entries",
        "origin_type IN ('CONTRIBUTION', 'SALE_ALLOCATION', 'REMO_ADMIN', "
        "'ALLOCATION_REVERSAL', 'REVENUE_DISTRIBUTION', "
        "'REVENUE_DISTRIBUTION_REVERSAL', 'FUTURE_FINANCIAL_EVENT')",
    )
    op.create_check_constraint(
        "ck_funding_ledger_relationships",
        "funding_ledger_entries",
        _ledger_relationship_check(with_revenue=True),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_funding_ledger_append_only ON funding_ledger_entries")
    op.execute(
        "DELETE FROM funding_ledger_entries "
        "WHERE origin_type = 'REVENUE_DISTRIBUTION_REVERSAL'"
    )
    op.execute(
        "DELETE FROM funding_ledger_entries WHERE origin_type = 'REVENUE_DISTRIBUTION'"
    )

    op.drop_constraint(
        "ck_funding_ledger_relationships", "funding_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_funding_ledger_origin_type", "funding_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "uq_funding_ledger_revenue_distribution_item",
        "funding_ledger_entries",
        type_="unique",
    )
    op.drop_constraint(
        "fk_funding_ledger_revenue_distribution_item",
        "funding_ledger_entries",
        type_="foreignkey",
    )
    op.drop_column("funding_ledger_entries", "revenue_distribution_item_id")
    op.create_check_constraint(
        "ck_funding_ledger_origin_type",
        "funding_ledger_entries",
        "origin_type IN ('CONTRIBUTION', 'SALE_ALLOCATION', 'REMO_ADMIN', "
        "'ALLOCATION_REVERSAL', 'FUTURE_FINANCIAL_EVENT')",
    )
    op.create_check_constraint(
        "ck_funding_ledger_relationships",
        "funding_ledger_entries",
        _ledger_relationship_check(with_revenue=False),
    )
    op.execute(
        """
        CREATE TRIGGER trg_funding_ledger_append_only
        BEFORE UPDATE OR DELETE ON funding_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_funding_ledger_mutation();
        """
    )

    op.execute(
        "DELETE FROM funding_audit_events WHERE entity_type = 'DISTRIBUTION'"
    )
    op.drop_index(
        "ix_funding_revenue_distribution_items_source_id",
        table_name="funding_revenue_distribution_items",
    )
    op.drop_index(
        "ix_funding_revenue_distribution_items_distribution_id",
        table_name="funding_revenue_distribution_items",
    )
    op.drop_table("funding_revenue_distribution_items")
    op.drop_index(
        "uq_funding_revenue_distributions_active",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "uq_funding_revenue_distributions_divergent_snapshot",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "ix_funding_revenue_distributions_sale_id",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "ix_funding_revenue_distributions_revenue_id",
        table_name="funding_revenue_distributions",
    )
    op.drop_table("funding_revenue_distributions")

    op.drop_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', 'ALLOCATION')",
    )


def _ledger_relationship_check(*, with_revenue: bool) -> str:
    if not with_revenue:
        return (
            "(entry_type = 'CONTRIBUTION' AND contribution_id IS NOT NULL "
            "AND allocation_id IS NULL AND reversal_of_entry_id IS NULL AND direction = 1) OR "
            "(entry_type = 'ALLOCATION' AND contribution_id IS NULL "
            "AND allocation_id IS NOT NULL AND reversal_of_entry_id IS NULL AND direction = -1) OR "
            "(entry_type = 'REVERSAL' AND contribution_id IS NULL "
            "AND allocation_id IS NULL AND reversal_of_entry_id IS NOT NULL) OR "
            "(entry_type NOT IN ('CONTRIBUTION', 'ALLOCATION', 'REVERSAL') "
            "AND contribution_id IS NULL AND allocation_id IS NULL "
            "AND reversal_of_entry_id IS NULL)"
        )
    return (
        "(entry_type = 'CONTRIBUTION' AND contribution_id IS NOT NULL "
        "AND allocation_id IS NULL AND revenue_distribution_item_id IS NULL "
        "AND reversal_of_entry_id IS NULL AND direction = 1) OR "
        "(entry_type = 'ALLOCATION' AND contribution_id IS NULL "
        "AND allocation_id IS NOT NULL AND revenue_distribution_item_id IS NULL "
        "AND reversal_of_entry_id IS NULL AND direction = -1) OR "
        "(entry_type = 'REVERSAL' AND contribution_id IS NULL "
        "AND allocation_id IS NULL AND revenue_distribution_item_id IS NULL "
        "AND reversal_of_entry_id IS NOT NULL) OR "
        "(entry_type = 'PRINCIPAL_RETURN' AND contribution_id IS NULL "
        "AND allocation_id IS NULL AND revenue_distribution_item_id IS NOT NULL "
        "AND reversal_of_entry_id IS NULL AND direction = 1) OR "
        "(entry_type NOT IN ('CONTRIBUTION', 'ALLOCATION', 'REVERSAL', "
        "'PRINCIPAL_RETURN') AND contribution_id IS NULL AND allocation_id IS NULL "
        "AND revenue_distribution_item_id IS NULL AND reversal_of_entry_id IS NULL)"
    )
