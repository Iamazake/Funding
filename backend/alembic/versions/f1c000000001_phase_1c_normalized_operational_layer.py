"""phase 1c normalized operational layer

Revision ID: f1c000000001
Revises: ecacd0239c1a
Create Date: 2026-08-07

Prepared only. Do not apply without express authorization.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f1c000000001"
down_revision: str | None = "ecacd0239c1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUALITY_VALUES = "'VALID', 'WARNING', 'DIVERGENT', 'INVALID'"


def _snapshot_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("data_quality_status", sa.String(length=24), nullable=False),
        sa.Column("current_source_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("first_seen_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("last_seen_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("active_in_source", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["operational_promotions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["current_source_batch_id"], ["operational_import_batches.id"]
        ),
        sa.ForeignKeyConstraint(["first_seen_batch_id"], ["operational_import_batches.id"]),
        sa.ForeignKeyConstraint(["last_seen_batch_id"], ["operational_import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    ]


def _snapshot_indexes(table: str) -> None:
    for column in (
        "promotion_id",
        "data_quality_status",
        "current_source_batch_id",
        "active_in_source",
    ):
        op.create_index(f"ix_{table}_{column}", table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "operational_promotions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_batch_id"], ["operational_import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_batch_id", name="uq_operational_promotions_source_batch"
        ),
    )
    op.create_index(
        "ix_operational_promotions_source_batch_id",
        "operational_promotions",
        ["source_batch_id"],
    )
    op.create_index(
        "ix_operational_promotions_status", "operational_promotions", ["status"]
    )
    op.create_index(
        "ix_operational_promotions_is_current", "operational_promotions", ["is_current"]
    )
    op.create_index(
        "uq_operational_promotions_one_current",
        "operational_promotions",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current IS true"),
    )

    op.create_table(
        "operational_clients",
        sa.Column("source_bcli_row_id", sa.BigInteger(), nullable=False),
        sa.Column("source_client_code", sa.String(length=100), nullable=True),
        sa.Column("cpf_original", sa.Text(), nullable=True),
        sa.Column("cpf_normalized", sa.String(length=11), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        *_snapshot_columns(),
        sa.CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_clients_quality",
        ),
        sa.ForeignKeyConstraint(["source_bcli_row_id"], ["excel_bcli_cadastro_rows.id"]),
        sa.UniqueConstraint(
            "promotion_id", "source_bcli_row_id", name="uq_operational_clients_source_row"
        ),
    )
    _snapshot_indexes("operational_clients")
    for column in ("source_bcli_row_id", "source_client_code", "cpf_normalized"):
        op.create_index(f"ix_operational_clients_{column}", "operational_clients", [column])

    op.create_table(
        "operational_contracts",
        sa.Column("source_dfen_row_id", sa.BigInteger(), nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=True),
        sa.Column("contract_code", sa.String(length=100), nullable=True),
        sa.Column("source_client_code", sa.String(length=100), nullable=True),
        sa.Column("cpf_normalized", sa.String(length=11), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=True),
        sa.Column("first_due_date", sa.Date(), nullable=True),
        sa.Column("term", sa.Integer(), nullable=True),
        sa.Column("principal", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("iof", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("financed_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("installment_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("released_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("released_amount_original", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("operational_status", sa.Text(), nullable=True),
        *_snapshot_columns(),
        sa.CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_contracts_quality",
        ),
        sa.ForeignKeyConstraint(["source_dfen_row_id"], ["excel_dfen_contrato_rows.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["operational_clients.id"]),
        sa.UniqueConstraint(
            "promotion_id", "source_dfen_row_id", name="uq_operational_contracts_source_row"
        ),
        sa.UniqueConstraint(
            "current_source_batch_id",
            "contract_code",
            name="uq_operational_contracts_batch_code",
        ),
    )
    _snapshot_indexes("operational_contracts")
    for column in (
        "source_dfen_row_id",
        "client_id",
        "contract_code",
        "source_client_code",
        "cpf_normalized",
    ):
        op.create_index(f"ix_operational_contracts_{column}", "operational_contracts", [column])

    op.create_table(
        "operational_loans",
        sa.Column("source_loan_row_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("client_id", sa.BigInteger(), nullable=True),
        sa.Column("contract_code", sa.String(length=100), nullable=True),
        sa.Column("source_client_code", sa.String(length=100), nullable=True),
        sa.Column("cpf_normalized", sa.String(length=11), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=True),
        sa.Column("first_due_date", sa.Date(), nullable=True),
        sa.Column("term", sa.Integer(), nullable=True),
        sa.Column("principal", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("iof", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("financed_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("installment_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("released_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("released_amount_original", sa.Text(), nullable=True),
        sa.Column("interest_rate", sa.Numeric(precision=18, scale=10), nullable=True),
        sa.Column("irr_rate", sa.Numeric(precision=18, scale=10), nullable=True),
        sa.Column("cet_monthly_rate", sa.Numeric(precision=18, scale=10), nullable=True),
        sa.Column("operational_status", sa.Text(), nullable=True),
        *_snapshot_columns(),
        sa.CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_loans_quality",
        ),
        sa.ForeignKeyConstraint(["source_loan_row_id"], ["excel_econ_emprestimos_rows.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["operational_contracts.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["operational_clients.id"]),
        sa.UniqueConstraint(
            "promotion_id", "source_loan_row_id", name="uq_operational_loans_source_row"
        ),
    )
    _snapshot_indexes("operational_loans")
    for column in (
        "source_loan_row_id",
        "contract_id",
        "client_id",
        "contract_code",
        "source_client_code",
        "cpf_normalized",
    ):
        op.create_index(f"ix_operational_loans_{column}", "operational_loans", [column])

    op.create_table(
        "operational_installments",
        sa.Column("source_amortization_row_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("contract_code", sa.String(length=100), nullable=True),
        sa.Column("installment_code", sa.String(length=100), nullable=True),
        sa.Column("candidate_group_key", sa.String(length=255), nullable=True),
        sa.Column("candidate_group_size", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("expected_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("principal_component", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("interest_component", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("paid_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("discount_amount_original", sa.Text(), nullable=True),
        sa.Column("payment_marker_original", sa.Text(), nullable=True),
        sa.Column("installment_status", sa.Text(), nullable=True),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("anticipation_marker", sa.Text(), nullable=True),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("financial_product", sa.Text(), nullable=True),
        *_snapshot_columns(),
        sa.CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_installments_quality",
        ),
        sa.ForeignKeyConstraint(
            ["source_amortization_row_id"], ["excel_econ_amortizacoes_rows.id"]
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["operational_contracts.id"]),
        sa.UniqueConstraint(
            "promotion_id",
            "source_amortization_row_id",
            name="uq_operational_installments_source_row",
        ),
    )
    _snapshot_indexes("operational_installments")
    for column in (
        "source_amortization_row_id",
        "contract_id",
        "contract_code",
        "installment_code",
        "candidate_group_key",
    ):
        op.create_index(
            f"ix_operational_installments_{column}", "operational_installments", [column]
        )
    op.create_index(
        "ix_operational_installments_contract_code_installment_code",
        "operational_installments",
        ["contract_code", "installment_code"],
    )

    op.create_table(
        "operational_payment_movements",
        sa.Column("installment_id", sa.BigInteger(), nullable=False),
        sa.Column("source_amortization_row_id", sa.BigInteger(), nullable=False),
        sa.Column("paid_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("payment_marker_original", sa.Text(), nullable=True),
        *_snapshot_columns(),
        sa.CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_payment_movements_quality",
        ),
        sa.ForeignKeyConstraint(
            ["installment_id"], ["operational_installments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_amortization_row_id"], ["excel_econ_amortizacoes_rows.id"]
        ),
    )
    _snapshot_indexes("operational_payment_movements")
    op.create_index(
        "ix_operational_payment_movements_installment_id",
        "operational_payment_movements",
        ["installment_id"],
    )
    op.create_index(
        "ix_operational_payment_movements_source_amortization_row_id",
        "operational_payment_movements",
        ["source_amortization_row_id"],
    )

    op.create_table(
        "operational_quality_links",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("data_inconsistency_id", sa.BigInteger(), nullable=True),
        sa.Column("client_id", sa.BigInteger(), nullable=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("loan_id", sa.BigInteger(), nullable=True),
        sa.Column("installment_id", sa.BigInteger(), nullable=True),
        sa.Column("payment_movement_id", sa.BigInteger(), nullable=True),
        sa.Column("issue_type", sa.String(length=80), nullable=True),
        sa.Column("severity", sa.String(length=24), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(client_id, contract_id, loan_id, installment_id, "
            "payment_movement_id) = 1",
            name="ck_operational_quality_links_one_record",
        ),
        sa.CheckConstraint(
            "data_inconsistency_id IS NOT NULL OR "
            "(issue_type IS NOT NULL AND severity IS NOT NULL)",
            name="ck_operational_quality_links_issue_source",
        ),
        sa.CheckConstraint(
            f"severity IS NULL OR severity IN ({QUALITY_VALUES})",
            name="ck_operational_quality_links_severity",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["operational_promotions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["data_inconsistency_id"], ["data_inconsistencies.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["operational_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["operational_contracts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["loan_id"], ["operational_loans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["installment_id"], ["operational_installments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["payment_movement_id"],
            ["operational_payment_movements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "promotion_id",
        "data_inconsistency_id",
        "client_id",
        "contract_id",
        "loan_id",
        "installment_id",
        "payment_movement_id",
    ):
        op.create_index(
            f"ix_operational_quality_links_{column}", "operational_quality_links", [column]
        )


def downgrade() -> None:
    op.drop_table("operational_quality_links")
    op.drop_table("operational_payment_movements")
    op.drop_table("operational_installments")
    op.drop_table("operational_loans")
    op.drop_table("operational_contracts")
    op.drop_table("operational_clients")
    op.drop_table("operational_promotions")
