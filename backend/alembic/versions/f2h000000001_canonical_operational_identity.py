# ruff: noqa: E501
"""canonical operational sale and revenue identity

Revision ID: f2h000000001
Revises: f2g000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2h000000001"
down_revision: str | None = "f2g000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "operational_sale_identities",
        sa.Column("id", UUID, nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_contract_code", sa.String(length=100), nullable=False),
        sa.Column("origin_kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "origin_kind IN ('CONTRACT', 'ORPHAN_LOAN')",
            name="ck_operational_sale_identities_origin_kind",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVIEW_REQUIRED', 'RETIRED')",
            name="ck_operational_sale_identities_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "source_contract_code",
            name="uq_operational_sale_identities_source_contract",
        ),
    )
    op.create_index(
        "ix_operational_sale_identities_source_contract_code",
        "operational_sale_identities",
        ["source_contract_code"],
    )
    op.create_table(
        "operational_sale_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sale_identity_id", UUID, nullable=False),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("loan_id", sa.BigInteger(), nullable=True),
        sa.Column("match_status", sa.String(length=24), nullable=False),
        sa.Column("match_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "contract_id IS NOT NULL OR loan_id IS NOT NULL",
            name="ck_operational_sale_snapshots_source",
        ),
        sa.CheckConstraint(
            "match_status IN ('BASELINE', 'AUTO_MATCH', 'MANUAL_MATCH', 'NEW_IDENTITY')",
            name="ck_operational_sale_snapshots_match_status",
        ),
        sa.ForeignKeyConstraint(
            ["sale_identity_id"], ["operational_sale_identities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["operational_promotions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["operational_contracts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["loan_id"], ["operational_loans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "promotion_id", "sale_identity_id", name="uq_operational_sale_snapshots_identity"
        ),
        sa.UniqueConstraint("contract_id", name="uq_operational_sale_snapshots_contract"),
        sa.UniqueConstraint("loan_id", name="uq_operational_sale_snapshots_loan"),
    )
    op.create_index(
        "ix_operational_sale_snapshots_sale_identity_id",
        "operational_sale_snapshots",
        ["sale_identity_id"],
    )
    op.create_index(
        "ix_operational_sale_snapshots_promotion_id",
        "operational_sale_snapshots",
        ["promotion_id"],
    )
    op.create_table(
        "operational_revenue_identities",
        sa.Column("id", UUID, nullable=False),
        sa.Column("sale_identity_id", UUID, nullable=True),
        sa.Column("unresolved_contract_code", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVIEW_REQUIRED', 'RETIRED')",
            name="ck_operational_revenue_identities_status",
        ),
        sa.ForeignKeyConstraint(
            ["sale_identity_id"], ["operational_sale_identities.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_revenue_identities_sale_identity_id",
        "operational_revenue_identities",
        ["sale_identity_id"],
    )
    op.create_index(
        "ix_operational_revenue_identities_unresolved_contract_code",
        "operational_revenue_identities",
        ["unresolved_contract_code"],
    )
    op.create_table(
        "operational_revenue_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("revenue_identity_id", UUID, nullable=False),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("installment_id", sa.BigInteger(), nullable=False),
        sa.Column("match_status", sa.String(length=24), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "match_status IN ('BASELINE', 'AUTO_MATCH', 'MANUAL_MATCH', 'NEW_IDENTITY')",
            name="ck_operational_revenue_snapshots_match_status",
        ),
        sa.ForeignKeyConstraint(
            ["revenue_identity_id"],
            ["operational_revenue_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["operational_promotions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["installment_id"], ["operational_installments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "promotion_id",
            "revenue_identity_id",
            name="uq_operational_revenue_snapshots_identity",
        ),
        sa.UniqueConstraint(
            "installment_id", name="uq_operational_revenue_snapshots_installment"
        ),
    )
    op.create_index(
        "ix_operational_revenue_snapshots_revenue_identity_id",
        "operational_revenue_snapshots",
        ["revenue_identity_id"],
    )
    op.create_index(
        "ix_operational_revenue_snapshots_promotion_id",
        "operational_revenue_snapshots",
        ["promotion_id"],
    )
    op.create_index(
        "ix_operational_revenue_snapshots_installment_id",
        "operational_revenue_snapshots",
        ["installment_id"],
    )
    op.create_table(
        "operational_identity_match_reviews",
        sa.Column("id", UUID, nullable=False),
        sa.Column("source_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("promotion_id", sa.BigInteger(), nullable=True),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("source_record_id", sa.BigInteger(), nullable=False),
        sa.Column("candidate_identity_id", UUID, nullable=True),
        sa.Column("status", sa.String(length=24), server_default="REVIEW_REQUIRED", nullable=False),
        sa.Column("critical", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("resolved_by", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "entity_type IN ('SALE', 'REVENUE')",
            name="ck_operational_identity_match_reviews_entity_type",
        ),
        sa.CheckConstraint(
            "status IN ('REVIEW_REQUIRED', 'RESOLVED', 'REJECTED')",
            name="ck_operational_identity_match_reviews_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_batch_id"], ["operational_import_batches.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["operational_promotions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["resolved_by"], ["app_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_batch_id",
            "entity_type",
            "source_record_id",
            name="uq_operational_identity_match_reviews_source",
        ),
    )
    for column in ("source_batch_id", "promotion_id", "candidate_identity_id", "resolved_by"):
        op.create_index(
            f"ix_operational_identity_match_reviews_{column}",
            "operational_identity_match_reviews",
            [column],
        )
    op.create_table(
        "operational_identity_migration_manifest",
        sa.Column("id", UUID, nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=False),
        sa.Column("legacy_reference", sa.String(length=128), nullable=False),
        sa.Column("canonical_identity_id", UUID, nullable=False),
        sa.Column("canonical_reference", sa.String(length=128), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "reference_type IN ('SALE', 'REVENUE', 'TREASURY_MOVEMENT')",
            name="ck_operational_identity_migration_manifest_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_type",
            "legacy_reference",
            name="uq_operational_identity_migration_manifest_reference",
        ),
    )
    op.create_index(
        "ix_operational_identity_migration_manifest_canonical",
        "operational_identity_migration_manifest",
        ["canonical_identity_id"],
    )

    _backfill_current_snapshot()
    _add_canonical_domain_references()


def _backfill_current_snapshot() -> None:
    op.execute(
        """
        INSERT INTO operational_sale_identities
            (id, source_system, source_contract_code, origin_kind, status)
        SELECT (
                 substr(md5('sale:CADASTRO_CLIENTES:' || c.contract_code), 1, 8) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || c.contract_code), 9, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || c.contract_code), 13, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || c.contract_code), 17, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || c.contract_code), 21, 12)
               )::uuid,
               'CADASTRO_CLIENTES', c.contract_code, 'CONTRACT', 'ACTIVE'
        FROM operational_contracts c
        JOIN operational_promotions p ON p.id = c.promotion_id
        WHERE p.is_current AND p.status = 'succeeded'
        ON CONFLICT (source_system, source_contract_code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO operational_sale_identities
            (id, source_system, source_contract_code, origin_kind, status)
        SELECT (
                 substr(md5('sale:CADASTRO_CLIENTES:' || l.contract_code), 1, 8) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || l.contract_code), 9, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || l.contract_code), 13, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || l.contract_code), 17, 4) || '-' ||
                 substr(md5('sale:CADASTRO_CLIENTES:' || l.contract_code), 21, 12)
               )::uuid,
               'CADASTRO_CLIENTES', l.contract_code, 'ORPHAN_LOAN', 'ACTIVE'
        FROM operational_loans l
        JOIN operational_promotions p ON p.id = l.promotion_id
        WHERE p.is_current AND p.status = 'succeeded' AND l.contract_id IS NULL
        ON CONFLICT (source_system, source_contract_code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO operational_sale_snapshots
            (sale_identity_id, promotion_id, contract_id, loan_id, match_status, match_evidence)
        SELECT si.id, c.promotion_id, c.id,
               (SELECT min(l.id) FROM operational_loans l
                WHERE l.promotion_id = c.promotion_id AND l.contract_id = c.id),
               'BASELINE',
               jsonb_build_object('method', 'CURRENT_PROMOTION_BASELINE',
                                  'source_batch_id', p.source_batch_id,
                                  'contract_code', c.contract_code)
        FROM operational_contracts c
        JOIN operational_promotions p ON p.id = c.promotion_id
        JOIN operational_sale_identities si
          ON si.source_system = 'CADASTRO_CLIENTES'
         AND si.source_contract_code = c.contract_code
        WHERE p.is_current AND p.status = 'succeeded'
        """
    )
    op.execute(
        """
        INSERT INTO operational_sale_snapshots
            (sale_identity_id, promotion_id, contract_id, loan_id, match_status, match_evidence)
        SELECT si.id, l.promotion_id, NULL, l.id, 'BASELINE',
               jsonb_build_object('method', 'CURRENT_PROMOTION_BASELINE_ORPHAN_LOAN',
                                  'source_batch_id', p.source_batch_id,
                                  'contract_code', l.contract_code)
        FROM operational_loans l
        JOIN operational_promotions p ON p.id = l.promotion_id
        JOIN operational_sale_identities si
          ON si.source_system = 'CADASTRO_CLIENTES'
         AND si.source_contract_code = l.contract_code
        WHERE p.is_current AND p.status = 'succeeded' AND l.contract_id IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO operational_revenue_identities
            (id, sale_identity_id, unresolved_contract_code, status)
        SELECT (
                 substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 1, 8) || '-' ||
                 substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 9, 4) || '-' ||
                 substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 13, 4) || '-' ||
                 substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 17, 4) || '-' ||
                 substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 21, 12)
               )::uuid,
               coalesce(ss.sale_identity_id, orphan_sale.id),
               CASE WHEN coalesce(ss.sale_identity_id, orphan_sale.id) IS NULL
                    THEN i.contract_code ELSE NULL END,
               'ACTIVE'
        FROM operational_installments i
        JOIN operational_promotions p ON p.id = i.promotion_id
        LEFT JOIN operational_sale_snapshots ss
          ON ss.promotion_id = i.promotion_id AND ss.contract_id = i.contract_id
        LEFT JOIN operational_sale_identities orphan_sale
          ON i.contract_id IS NULL
         AND orphan_sale.source_system = 'CADASTRO_CLIENTES'
         AND orphan_sale.source_contract_code = i.contract_code
         AND orphan_sale.origin_kind = 'ORPHAN_LOAN'
        WHERE p.is_current AND p.status = 'succeeded'
        """
    )
    op.execute(
        """
        INSERT INTO operational_revenue_snapshots
            (revenue_identity_id, promotion_id, installment_id,
             match_status, match_score, match_evidence)
        SELECT ri.id, i.promotion_id, i.id, 'BASELINE', NULL,
               jsonb_build_object('method', 'CURRENT_PROMOTION_BASELINE',
                                  'source_batch_id', p.source_batch_id,
                                  'source_amortization_row_id', i.source_amortization_row_id)
        FROM operational_installments i
        JOIN operational_promotions p ON p.id = i.promotion_id
        JOIN operational_revenue_identities ri
          ON ri.id = (
               substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 1, 8) || '-' ||
               substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 9, 4) || '-' ||
               substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 13, 4) || '-' ||
               substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 17, 4) || '-' ||
               substr(md5('revenue:' || i.promotion_id::text || ':' || i.id::text), 21, 12)
             )::uuid
        WHERE p.is_current AND p.status = 'succeeded'
        """
    )


def _add_canonical_domain_references() -> None:
    op.add_column("funding_allocations", sa.Column("sale_identity_id", UUID, nullable=True))
    op.add_column("funding_allocations", sa.Column("legacy_sale_id", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_funding_allocations_sale_identity",
        "funding_allocations",
        "operational_sale_identities",
        ["sale_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_funding_allocations_sale_identity_id", "funding_allocations", ["sale_identity_id"]
    )
    op.add_column(
        "funding_revenue_distributions", sa.Column("revenue_identity_id", UUID, nullable=True)
    )
    op.add_column(
        "funding_revenue_distributions", sa.Column("sale_identity_id", UUID, nullable=True)
    )
    op.add_column(
        "funding_revenue_distributions", sa.Column("legacy_sale_id", sa.String(64), nullable=True)
    )
    op.create_foreign_key(
        "fk_funding_revenue_distributions_revenue_identity",
        "funding_revenue_distributions",
        "operational_revenue_identities",
        ["revenue_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_funding_revenue_distributions_sale_identity",
        "funding_revenue_distributions",
        "operational_sale_identities",
        ["sale_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_funding_revenue_distributions_sale_identity_id",
        "funding_revenue_distributions",
        ["sale_identity_id"],
    )
    op.add_column(
        "treasury_bank_validations", sa.Column("legacy_movement_key", sa.String(128), nullable=True)
    )
    op.add_column("treasury_bank_validations", sa.Column("sale_identity_id", UUID, nullable=True))
    op.add_column(
        "treasury_bank_validations", sa.Column("revenue_identity_id", UUID, nullable=True)
    )
    op.create_foreign_key(
        "fk_treasury_bank_validations_sale_identity",
        "treasury_bank_validations",
        "operational_sale_identities",
        ["sale_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_treasury_bank_validations_revenue_identity",
        "treasury_bank_validations",
        "operational_revenue_identities",
        ["revenue_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_treasury_bank_validations_legacy_movement_key",
        "treasury_bank_validations",
        ["legacy_movement_key"],
    )
    op.create_index(
        "ix_treasury_bank_validations_sale_identity_id",
        "treasury_bank_validations",
        ["sale_identity_id"],
    )
    op.create_index(
        "ix_treasury_bank_validations_revenue_identity_id",
        "treasury_bank_validations",
        ["revenue_identity_id"],
    )

    # Replace the legacy-only checks after data conversion. PostgreSQL validates
    # checks on every UPDATE, so they must be removed before canonical keys are written.
    op.drop_constraint("ck_funding_allocations_sale_id", "funding_allocations", type_="check")
    op.drop_constraint(
        "ck_funding_revenue_distributions_sale_id",
        "funding_revenue_distributions",
        type_="check",
    )

    op.execute(
        """
        UPDATE funding_allocations a
        SET legacy_sale_id = a.sale_id,
            sale_identity_id = ss.sale_identity_id,
            sale_id = 'sale:' || ss.sale_identity_id::text
        FROM operational_sale_snapshots ss
        JOIN operational_promotions p ON p.id = ss.promotion_id AND p.is_current
        WHERE (a.sale_id LIKE 'contract:%' AND ss.contract_id = split_part(a.sale_id, ':', 2)::bigint)
           OR (a.sale_id LIKE 'loan:%' AND ss.loan_id = split_part(a.sale_id, ':', 2)::bigint)
        """
    )
    op.execute(
        """
        UPDATE funding_revenue_distributions d
        SET revenue_identity_id = rs.revenue_identity_id,
            sale_identity_id = ri.sale_identity_id,
            legacy_sale_id = d.sale_id,
            sale_id = 'sale:' || ri.sale_identity_id::text
        FROM operational_revenue_snapshots rs
        JOIN operational_revenue_identities ri ON ri.id = rs.revenue_identity_id
        WHERE rs.installment_id = d.revenue_id
        """
    )
    op.execute(
        """
        UPDATE treasury_bank_validations v
        SET legacy_movement_key = v.movement_key,
            sale_identity_id = ss.sale_identity_id,
            movement_key = 'sale:' || ss.sale_identity_id::text
        FROM operational_sale_snapshots ss
        JOIN operational_promotions p ON p.id = ss.promotion_id AND p.is_current
        WHERE v.movement_type = 'SALE'
          AND ((v.movement_key LIKE 'sale:contract:%'
                AND ss.contract_id = split_part(v.movement_key, ':', 3)::bigint)
            OR (v.movement_key LIKE 'sale:loan:%'
                AND ss.loan_id = split_part(v.movement_key, ':', 3)::bigint))
        """
    )
    op.execute(
        """
        UPDATE treasury_bank_validations v
        SET legacy_movement_key = v.movement_key,
            revenue_identity_id = rs.revenue_identity_id,
            movement_key = 'revenue:' || rs.revenue_identity_id::text
        FROM operational_revenue_snapshots rs
        WHERE v.movement_type = 'REVENUE'
          AND v.movement_key LIKE 'revenue:%'
          AND rs.installment_id = split_part(v.movement_key, ':', 2)::bigint
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM funding_allocations WHERE sale_identity_id IS NULL) THEN
            RAISE EXCEPTION 'canonical identity backfill left funding allocations unresolved';
          END IF;
          IF EXISTS (SELECT 1 FROM funding_revenue_distributions
                     WHERE revenue_identity_id IS NULL OR sale_identity_id IS NULL) THEN
            RAISE EXCEPTION 'canonical identity backfill left revenue distributions unresolved';
          END IF;
          IF EXISTS (SELECT 1 FROM treasury_bank_validations
                     WHERE movement_type = 'SALE' AND sale_identity_id IS NULL) THEN
            RAISE EXCEPTION 'canonical identity backfill left sale validations unresolved';
          END IF;
          IF EXISTS (SELECT 1 FROM treasury_bank_validations
                     WHERE movement_type = 'REVENUE' AND revenue_identity_id IS NULL) THEN
            RAISE EXCEPTION 'canonical identity backfill left revenue validations unresolved';
          END IF;
        END $$;
        """
    )

    op.alter_column("funding_allocations", "sale_identity_id", nullable=False)
    op.alter_column("funding_revenue_distributions", "revenue_identity_id", nullable=False)
    op.alter_column("funding_revenue_distributions", "sale_identity_id", nullable=False)
    op.create_check_constraint(
        "ck_funding_allocations_sale_id",
        "funding_allocations",
        "sale_id ~ '^sale:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
    )
    op.create_check_constraint(
        "ck_funding_revenue_distributions_sale_id",
        "funding_revenue_distributions",
        "sale_id ~ '^sale:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
    )
    op.drop_constraint(
        "uq_funding_revenue_distributions_version",
        "funding_revenue_distributions",
        type_="unique",
    )
    op.drop_index(
        "uq_funding_revenue_distributions_divergent_snapshot",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "uq_funding_revenue_distributions_active",
        table_name="funding_revenue_distributions",
    )
    op.create_unique_constraint(
        "uq_funding_revenue_distributions_version",
        "funding_revenue_distributions",
        ["revenue_identity_id", "version"],
    )
    op.create_index(
        "ix_funding_revenue_distributions_revenue_identity_id",
        "funding_revenue_distributions",
        ["revenue_identity_id"],
    )
    op.create_index(
        "uq_funding_revenue_distributions_divergent_snapshot",
        "funding_revenue_distributions",
        ["revenue_identity_id", "composition_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'DIVERGENT'"),
    )
    op.create_index(
        "uq_funding_revenue_distributions_active",
        "funding_revenue_distributions",
        ["revenue_identity_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DISTRIBUTED'"),
    )

    op.drop_constraint("ck_funding_audit_events_entity_type", "funding_audit_events", type_="check")
    op.create_check_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', "
        "'ALLOCATION', 'DISTRIBUTION', 'IDENTITY_MIGRATION')",
    )
    _write_manifest_and_audit()


def _write_manifest_and_audit() -> None:
    op.execute(
        """
        INSERT INTO operational_identity_migration_manifest
          (id, reference_type, legacy_reference, canonical_identity_id,
           canonical_reference, evidence)
        SELECT (
                 substr(md5('manifest:sale:' || a.legacy_sale_id), 1, 8) || '-' ||
                 substr(md5('manifest:sale:' || a.legacy_sale_id), 9, 4) || '-' ||
                 substr(md5('manifest:sale:' || a.legacy_sale_id), 13, 4) || '-' ||
                 substr(md5('manifest:sale:' || a.legacy_sale_id), 17, 4) || '-' ||
                 substr(md5('manifest:sale:' || a.legacy_sale_id), 21, 12)
               )::uuid,
               'SALE', a.legacy_sale_id, a.sale_identity_id, a.sale_id,
               jsonb_build_object('method', 'CURRENT_PROMOTION_DIRECT_SNAPSHOT_REFERENCE',
                                  'funding_allocation_id', a.id,
                                  'amount', a.amount)
        FROM funding_allocations a
        WHERE a.legacy_sale_id IS NOT NULL
        ON CONFLICT (reference_type, legacy_reference) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO operational_identity_migration_manifest
          (id, reference_type, legacy_reference, canonical_identity_id,
           canonical_reference, evidence)
        SELECT (
                 substr(md5('manifest:revenue:' || d.revenue_id::text), 1, 8) || '-' ||
                 substr(md5('manifest:revenue:' || d.revenue_id::text), 9, 4) || '-' ||
                 substr(md5('manifest:revenue:' || d.revenue_id::text), 13, 4) || '-' ||
                 substr(md5('manifest:revenue:' || d.revenue_id::text), 17, 4) || '-' ||
                 substr(md5('manifest:revenue:' || d.revenue_id::text), 21, 12)
               )::uuid,
               'REVENUE', 'revenue:' || d.revenue_id::text,
               d.revenue_identity_id,
               'revenue:' || d.revenue_identity_id::text,
               jsonb_build_object('method', 'CURRENT_PROMOTION_DIRECT_INSTALLMENT_FK',
                                  'distribution_id', d.id,
                                  'source_installment_id', d.revenue_id)
        FROM funding_revenue_distributions d
        ON CONFLICT (reference_type, legacy_reference) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO operational_identity_migration_manifest
          (id, reference_type, legacy_reference, canonical_identity_id,
           canonical_reference, evidence)
        SELECT (
                 substr(md5('manifest:treasury:' || v.legacy_movement_key), 1, 8) || '-' ||
                 substr(md5('manifest:treasury:' || v.legacy_movement_key), 9, 4) || '-' ||
                 substr(md5('manifest:treasury:' || v.legacy_movement_key), 13, 4) || '-' ||
                 substr(md5('manifest:treasury:' || v.legacy_movement_key), 17, 4) || '-' ||
                 substr(md5('manifest:treasury:' || v.legacy_movement_key), 21, 12)
               )::uuid,
               'TREASURY_MOVEMENT', v.legacy_movement_key,
               coalesce(v.sale_identity_id, v.revenue_identity_id), v.movement_key,
               jsonb_build_object('method', 'CURRENT_PROMOTION_DIRECT_MOVEMENT_REFERENCE',
                                  'treasury_validation_id', v.id,
                                  'status', v.status)
        FROM treasury_bank_validations v
        WHERE v.legacy_movement_key IS NOT NULL
        ON CONFLICT (reference_type, legacy_reference) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO funding_audit_events
          (entity_type, entity_id, action, changes, actor_user_id)
        SELECT 'IDENTITY_MIGRATION', m.canonical_identity_id,
               'CANONICAL_IDENTITY_MIGRATED',
               jsonb_build_object('phase', '2G.1',
                                  'reference_type', m.reference_type,
                                  'legacy_reference', m.legacy_reference,
                                  'canonical_reference', m.canonical_reference,
                                  'manifest_id', m.id),
               NULL
        FROM operational_identity_migration_manifest m
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM funding_audit_events "
        "WHERE entity_type = 'IDENTITY_MIGRATION' AND action = 'CANONICAL_IDENTITY_MIGRATED'"
    )
    op.execute(
        "UPDATE funding_allocations SET sale_id = legacy_sale_id "
        "WHERE legacy_sale_id IS NOT NULL"
    )
    op.execute(
        "UPDATE funding_revenue_distributions SET sale_id = legacy_sale_id "
        "WHERE legacy_sale_id IS NOT NULL"
    )
    op.execute(
        "UPDATE treasury_bank_validations SET movement_key = legacy_movement_key "
        "WHERE legacy_movement_key IS NOT NULL"
    )

    op.drop_constraint("ck_funding_allocations_sale_id", "funding_allocations", type_="check")
    op.create_check_constraint(
        "ck_funding_allocations_sale_id",
        "funding_allocations",
        "sale_id ~ '^(contract|loan):[1-9][0-9]*$'",
    )
    op.drop_constraint(
        "ck_funding_revenue_distributions_sale_id",
        "funding_revenue_distributions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_funding_revenue_distributions_sale_id",
        "funding_revenue_distributions",
        "sale_id ~ '^(contract|loan):[1-9][0-9]*$'",
    )
    op.drop_constraint(
        "uq_funding_revenue_distributions_version",
        "funding_revenue_distributions",
        type_="unique",
    )
    op.drop_index(
        "uq_funding_revenue_distributions_divergent_snapshot",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "uq_funding_revenue_distributions_active",
        table_name="funding_revenue_distributions",
    )
    op.drop_index(
        "ix_funding_revenue_distributions_revenue_identity_id",
        table_name="funding_revenue_distributions",
    )
    op.create_unique_constraint(
        "uq_funding_revenue_distributions_version",
        "funding_revenue_distributions",
        ["revenue_id", "version"],
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
    op.drop_constraint("ck_funding_audit_events_entity_type", "funding_audit_events", type_="check")
    op.create_check_constraint(
        "ck_funding_audit_events_entity_type",
        "funding_audit_events",
        "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', "
        "'ALLOCATION', 'DISTRIBUTION')",
    )

    for table, columns in (
        ("treasury_bank_validations", ("revenue_identity_id", "sale_identity_id", "legacy_movement_key")),
        ("funding_revenue_distributions", ("legacy_sale_id", "sale_identity_id", "revenue_identity_id")),
        ("funding_allocations", ("legacy_sale_id", "sale_identity_id")),
    ):
        for column in columns:
            index = f"ix_{table}_{column}"
            if column != "legacy_sale_id":
                op.drop_index(index, table_name=table)
        for column in columns:
            op.drop_column(table, column)

    op.drop_table("operational_identity_migration_manifest")
    op.drop_table("operational_identity_match_reviews")
    op.drop_table("operational_revenue_snapshots")
    op.drop_table("operational_revenue_identities")
    op.drop_table("operational_sale_snapshots")
    op.drop_table("operational_sale_identities")
