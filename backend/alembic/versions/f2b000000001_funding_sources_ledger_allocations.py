"""Phase 2B funding sources, append-only ledger, and sale allocations.

Revision ID: f2b000000001
Revises: f2a000000001
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2b000000001"
down_revision: str | None = "f2a000000001"
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
        "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', 'ALLOCATION')",
    )

    op.create_table(
        "funding_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("contribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
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
            "source_type IN ('INVESTOR_CONTRIBUTION', 'REMO_CAPITAL')",
            name="ck_funding_sources_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_funding_sources_status",
        ),
        sa.CheckConstraint(
            "(source_type = 'INVESTOR_CONTRIBUTION' AND contribution_id IS NOT NULL) OR "
            "(source_type = 'REMO_CAPITAL' AND contribution_id IS NULL)",
            name="ck_funding_sources_contribution_type",
        ),
        sa.ForeignKeyConstraint(
            ["contribution_id"], ["funding_contributions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contribution_id"),
    )
    op.create_index("ix_funding_sources_source_type", "funding_sources", ["source_type"])
    op.create_index("ix_funding_sources_status", "funding_sources", ["status"])
    op.create_index(
        "uq_funding_sources_one_remo_capital",
        "funding_sources",
        ["source_type"],
        unique=True,
        postgresql_where=sa.text("source_type = 'REMO_CAPITAL'"),
    )

    op.create_table(
        "funding_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_funding_allocations_amount_positive"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVERSED')",
            name="ck_funding_allocations_status",
        ),
        sa.CheckConstraint(
            "sale_id ~ '^(contract|loan):[1-9][0-9]*$'",
            name="ck_funding_allocations_sale_id",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["funding_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funding_allocations_sale_id", "funding_allocations", ["sale_id"])
    op.create_index("ix_funding_allocations_source_id", "funding_allocations", ["source_id"])
    op.create_index(
        "ix_funding_allocations_effective_date",
        "funding_allocations",
        ["effective_date"],
    )
    op.create_index(
        "uq_funding_allocations_active_sale_source",
        "funding_allocations",
        ["sale_id", "source_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "funding_ledger_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("direction", sa.SmallInteger(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("origin_type", sa.String(length=32), nullable=False),
        sa.Column("contribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversal_of_entry_id", sa.BigInteger(), nullable=True),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_funding_ledger_amount_positive"),
        sa.CheckConstraint("direction IN (-1, 1)", name="ck_funding_ledger_direction"),
        sa.CheckConstraint(
            "entry_type IN ('CONTRIBUTION', 'ALLOCATION', 'PRINCIPAL_RETURN', "
            "'REINVESTMENT', 'CAPITAL_RETURN', 'REVERSAL', 'ADJUSTMENT')",
            name="ck_funding_ledger_entry_type",
        ),
        sa.CheckConstraint(
            "origin_type IN ('CONTRIBUTION', 'SALE_ALLOCATION', 'REMO_ADMIN', "
            "'ALLOCATION_REVERSAL', 'FUTURE_FINANCIAL_EVENT')",
            name="ck_funding_ledger_origin_type",
        ),
        sa.CheckConstraint(
            "(entry_type = 'CONTRIBUTION' AND contribution_id IS NOT NULL "
            "AND allocation_id IS NULL AND reversal_of_entry_id IS NULL AND direction = 1) OR "
            "(entry_type = 'ALLOCATION' AND contribution_id IS NULL "
            "AND allocation_id IS NOT NULL AND reversal_of_entry_id IS NULL AND direction = -1) OR "
            "(entry_type = 'REVERSAL' AND contribution_id IS NULL "
            "AND allocation_id IS NULL AND reversal_of_entry_id IS NOT NULL) OR "
            "(entry_type NOT IN ('CONTRIBUTION', 'ALLOCATION', 'REVERSAL') "
            "AND contribution_id IS NULL AND allocation_id IS NULL "
            "AND reversal_of_entry_id IS NULL)",
            name="ck_funding_ledger_relationships",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["funding_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["contribution_id"], ["funding_contributions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["allocation_id"], ["funding_allocations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_entry_id"], ["funding_ledger_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contribution_id"),
        sa.UniqueConstraint("allocation_id"),
        sa.UniqueConstraint("reversal_of_entry_id"),
    )
    op.create_index(
        "ix_funding_ledger_source_effective",
        "funding_ledger_entries",
        ["source_id", "effective_date", "id"],
    )
    op.create_index(
        "ix_funding_ledger_entry_type", "funding_ledger_entries", ["entry_type"]
    )

    op.execute(
        """
        CREATE FUNCTION prevent_funding_ledger_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'funding_ledger_entries is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_funding_ledger_append_only
        BEFORE UPDATE OR DELETE ON funding_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_funding_ledger_mutation();
        """
    )

    _bootstrap_sources_and_contributions()


def _bootstrap_sources_and_contributions() -> None:
    op.execute(
        """
        INSERT INTO funding_sources
            (id, source_type, contribution_id, status, created_at, updated_at)
        VALUES
            ('00000000-0000-0000-0000-00000000f2b0', 'REMO_CAPITAL', NULL,
             'ACTIVE', now(), now());
        """
    )
    op.execute(
        """
        INSERT INTO funding_audit_events
            (entity_type, entity_id, action, changes, created_at)
        VALUES
            ('SOURCE', '00000000-0000-0000-0000-00000000f2b0', 'CREATED',
             '{"source_type":"REMO_CAPITAL","initial_balance":"0.00"}'::jsonb, now());
        """
    )
    op.execute(
        """
        INSERT INTO funding_sources
            (id, source_type, contribution_id, status, created_at, updated_at)
        SELECT
            md5('funding-source:' || contribution.id::text)::uuid,
            'INVESTOR_CONTRIBUTION', contribution.id, 'ACTIVE', now(), now()
        FROM funding_contributions AS contribution
        ORDER BY contribution.created_at, contribution.id;
        """
    )
    op.execute(
        """
        INSERT INTO funding_audit_events
            (entity_type, entity_id, action, changes, created_at)
        SELECT
            'SOURCE', source.id, 'CREATED',
            jsonb_build_object(
                'source_type', 'INVESTOR_CONTRIBUTION',
                'contribution_id', source.contribution_id::text
            ),
            now()
        FROM funding_sources AS source
        WHERE source.source_type = 'INVESTOR_CONTRIBUTION';
        """
    )
    op.execute(
        """
        INSERT INTO funding_audit_events
            (entity_type, entity_id, action, changes, created_at)
        SELECT
            'CONTRIBUTION', contribution.id, 'F2B_LEDGER_BOOTSTRAP',
            jsonb_build_object(
                'source_id', source.id::text,
                'previous_original_amount_locked_at',
                contribution.original_amount_locked_at
            ),
            now()
        FROM funding_contributions AS contribution
        JOIN funding_sources AS source ON source.contribution_id = contribution.id;
        """
    )
    op.execute(
        """
        INSERT INTO funding_ledger_entries
            (source_id, entry_type, amount, direction, effective_date, origin_type,
             contribution_id, allocation_id, reversal_of_entry_id, actor, notes, created_at)
        SELECT
            source.id, 'CONTRIBUTION', contribution.original_amount, 1,
            contribution.contribution_date, 'CONTRIBUTION', contribution.id,
            NULL, NULL, 'MIGRATION_F2B',
            'Entrada inicial idempotente do aporte existente.', now()
        FROM funding_contributions AS contribution
        JOIN funding_sources AS source ON source.contribution_id = contribution.id
        ORDER BY contribution.created_at, contribution.id;
        """
    )
    op.execute(
        """
        UPDATE funding_contributions
        SET original_amount_locked_at = COALESCE(original_amount_locked_at, now()),
            updated_at = now();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE funding_contributions AS contribution
        SET original_amount_locked_at = CASE
            WHEN audit.changes->>'previous_original_amount_locked_at' IS NULL THEN NULL
            ELSE (audit.changes->>'previous_original_amount_locked_at')::timestamptz
        END
        FROM funding_audit_events AS audit
        WHERE audit.action = 'F2B_LEDGER_BOOTSTRAP'
          AND audit.entity_id = contribution.id;
        """
    )
    op.execute(
        """
        DELETE FROM funding_audit_events
        WHERE entity_type IN ('SOURCE', 'LEDGER', 'ALLOCATION')
           OR action = 'F2B_LEDGER_BOOTSTRAP';
        """
    )

    op.execute("DROP TRIGGER trg_funding_ledger_append_only ON funding_ledger_entries")
    op.execute("DROP FUNCTION prevent_funding_ledger_mutation()")
    op.drop_index("ix_funding_ledger_entry_type", table_name="funding_ledger_entries")
    op.drop_index("ix_funding_ledger_source_effective", table_name="funding_ledger_entries")
    op.drop_table("funding_ledger_entries")
    op.drop_index(
        "uq_funding_allocations_active_sale_source", table_name="funding_allocations"
    )
    op.drop_index("ix_funding_allocations_effective_date", table_name="funding_allocations")
    op.drop_index("ix_funding_allocations_source_id", table_name="funding_allocations")
    op.drop_index("ix_funding_allocations_sale_id", table_name="funding_allocations")
    op.drop_table("funding_allocations")
    op.drop_index("uq_funding_sources_one_remo_capital", table_name="funding_sources")
    op.drop_index("ix_funding_sources_status", table_name="funding_sources")
    op.drop_index("ix_funding_sources_source_type", table_name="funding_sources")
    op.drop_table("funding_sources")

    op.drop_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        "entity_type IN ('INVESTOR', 'CONTRIBUTION')",
    )
