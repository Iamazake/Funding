"""refinancing, investor profile, contribution maturity and bank code

Revision ID: f2k000000001
Revises: f2j000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2k000000001"
down_revision: str | None = "f2j000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("funding_investors", sa.Column("tax_id", sa.String(20), nullable=True))
    op.add_column("funding_investors", sa.Column("phone", sa.String(32), nullable=True))
    op.create_index("ix_funding_investors_tax_id", "funding_investors", ["tax_id"])
    op.add_column("funding_contributions", sa.Column("end_date", sa.Date(), nullable=True))
    op.create_index("ix_funding_contributions_end_date", "funding_contributions", ["end_date"])
    op.add_column(
        "treasury_bank_validations", sa.Column("bank_code", sa.String(16), nullable=True)
    )
    op.create_index(
        "ix_treasury_bank_validations_bank_code", "treasury_bank_validations", ["bank_code"]
    )
    op.create_check_constraint(
        "ck_treasury_bank_validations_bank_code",
        "treasury_bank_validations",
        "bank_code IS NULL OR bank_code IN "
        "('INTER', 'BTG', 'PICPAY', 'NUBANK', 'C6', 'CASH')",
    )

    op.drop_constraint(
        "ck_operational_debt_continuities_type",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_type",
        "operational_debt_continuities",
        "continuity_type IN ('RENEGOTIATION', 'ROLLOVER', 'REFINANCING')",
    )
    op.drop_constraint(
        "ck_operational_debt_continuities_status",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_status",
        "operational_debt_continuities",
        "status IN ('REVIEW_REQUIRED', 'RENEGOTIATION_CONFIRMED', "
        "'REFIN_CONFIRMED', 'REJECTED')",
    )
    op.drop_constraint(
        "ck_operational_debt_continuities_confirmation",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_confirmation",
        "operational_debt_continuities",
        "status NOT IN ('RENEGOTIATION_CONFIRMED', 'REFIN_CONFIRMED') OR "
        "(predecessor_sale_identity_id IS NOT NULL AND has_new_disbursement IS NOT NULL "
        "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
    )
    op.drop_constraint(
        "ck_operational_debt_continuity_audit_action",
        "operational_debt_continuity_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuity_audit_action",
        "operational_debt_continuity_audit_events",
        "action IN ('REVIEW_CREATED', 'RENEGOTIATION_CONFIRMED', "
        "'REFIN_CONFIRMED', 'REFIN_CORRECTED', 'REJECTED')",
    )
    op.create_table(
        "operational_debt_refinanced_installments",
        sa.Column("id", UUID, nullable=False),
        sa.Column("continuity_id", UUID, nullable=False),
        sa.Column("revenue_identity_id", UUID, nullable=False),
        sa.Column("original_status", sa.String(100), nullable=True),
        sa.Column("classified_by", UUID, nullable=False),
        sa.Column(
            "classified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["continuity_id"], ["operational_debt_continuities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revenue_identity_id"],
            ["operational_revenue_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["classified_by"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "continuity_id",
            "revenue_identity_id",
            name="uq_operational_debt_refinanced_installments_continuity_revenue",
        ),
    )
    op.create_index(
        "ix_operational_debt_refinanced_installments_continuity_id",
        "operational_debt_refinanced_installments",
        ["continuity_id"],
    )
    op.create_index(
        "ix_operational_debt_refinanced_installments_revenue",
        "operational_debt_refinanced_installments",
        ["revenue_identity_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_treasury_bank_validations_bank_code",
        "treasury_bank_validations",
        type_="check",
    )
    op.drop_index(
        "ix_operational_debt_refinanced_installments_revenue",
        table_name="operational_debt_refinanced_installments",
    )
    op.drop_index(
        "ix_operational_debt_refinanced_installments_continuity_id",
        table_name="operational_debt_refinanced_installments",
    )
    op.drop_table("operational_debt_refinanced_installments")
    op.drop_constraint(
        "ck_operational_debt_continuities_confirmation",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_confirmation",
        "operational_debt_continuities",
        "status <> 'RENEGOTIATION_CONFIRMED' OR "
        "(predecessor_sale_identity_id IS NOT NULL AND has_new_disbursement IS NOT NULL "
        "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
    )
    op.drop_constraint(
        "ck_operational_debt_continuity_audit_action",
        "operational_debt_continuity_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuity_audit_action",
        "operational_debt_continuity_audit_events",
        "action IN ('REVIEW_CREATED', 'RENEGOTIATION_CONFIRMED', 'REJECTED')",
    )
    op.drop_constraint(
        "ck_operational_debt_continuities_status",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_status",
        "operational_debt_continuities",
        "status IN ('REVIEW_REQUIRED', 'RENEGOTIATION_CONFIRMED', 'REJECTED')",
    )
    op.drop_constraint(
        "ck_operational_debt_continuities_type",
        "operational_debt_continuities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operational_debt_continuities_type",
        "operational_debt_continuities",
        "continuity_type IN ('RENEGOTIATION', 'ROLLOVER')",
    )
    op.drop_index(
        "ix_treasury_bank_validations_bank_code", table_name="treasury_bank_validations"
    )
    op.drop_column("treasury_bank_validations", "bank_code")
    op.drop_index("ix_funding_contributions_end_date", table_name="funding_contributions")
    op.drop_column("funding_contributions", "end_date")
    op.drop_index("ix_funding_investors_tax_id", table_name="funding_investors")
    op.drop_column("funding_investors", "phone")
    op.drop_column("funding_investors", "tax_id")
