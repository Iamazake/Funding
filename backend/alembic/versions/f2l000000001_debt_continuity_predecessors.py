"""canonical N-to-1 debt continuity predecessors

Revision ID: f2l000000001
Revises: f2k000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2l000000001"
down_revision: str | None = "f2k000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "operational_debt_continuity_predecessors",
        sa.Column("id", UUID, nullable=False),
        sa.Column("continuity_id", UUID, nullable=False),
        sa.Column("sale_identity_id", UUID, nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("added_by", UUID, nullable=False),
        sa.Column("removed_by", UUID, nullable=True),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(is_current AND removed_at IS NULL AND removed_by IS NULL) OR "
            "(NOT is_current AND removed_at IS NOT NULL AND removed_by IS NOT NULL)",
            name="ck_operational_debt_continuity_predecessors_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["continuity_id"], ["operational_debt_continuities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sale_identity_id"], ["operational_sale_identities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["added_by"], ["app_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["removed_by"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_debt_continuity_predecessors_continuity_id",
        "operational_debt_continuity_predecessors",
        ["continuity_id"],
    )
    op.create_index(
        "ix_operational_debt_continuity_predecessors_sale_current",
        "operational_debt_continuity_predecessors",
        ["sale_identity_id", "is_current"],
    )
    op.create_index(
        "uq_operational_debt_continuity_predecessors_current",
        "operational_debt_continuity_predecessors",
        ["continuity_id", "sale_identity_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO operational_debt_continuity_predecessors
                (id, continuity_id, sale_identity_id, is_current, added_by, added_at)
            SELECT
                gen_random_uuid(), id, predecessor_sale_identity_id, true, created_by, created_at
            FROM operational_debt_continuities
            WHERE predecessor_sale_identity_id IS NOT NULL
            """
        )
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
        "'REFIN_CONFIRMED', 'REFIN_CORRECTED', 'PREDECESSORS_CORRECTED', "
        "'REJECTED')",
    )


def downgrade() -> None:
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
    op.drop_index(
        "uq_operational_debt_continuity_predecessors_current",
        table_name="operational_debt_continuity_predecessors",
    )
    op.drop_index(
        "ix_operational_debt_continuity_predecessors_sale_current",
        table_name="operational_debt_continuity_predecessors",
    )
    op.drop_index(
        "ix_operational_debt_continuity_predecessors_continuity_id",
        table_name="operational_debt_continuity_predecessors",
    )
    op.drop_table("operational_debt_continuity_predecessors")
