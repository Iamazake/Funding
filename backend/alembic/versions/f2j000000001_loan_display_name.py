"""preserve ECON_EMPRESTIMOS display name provenance

Revision ID: f2j000000001
Revises: f2i000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2j000000001"
down_revision: str | None = "f2i000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "excel_econ_emprestimos_rows",
        sa.Column("nome_cliente_original", sa.Text(), nullable=True),
    )
    op.add_column(
        "excel_econ_emprestimos_rows",
        sa.Column("nome_cliente", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("excel_econ_emprestimos_rows", "nome_cliente")
    op.drop_column("excel_econ_emprestimos_rows", "nome_cliente_original")
