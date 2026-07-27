"""Create the Phase 0 database baseline.

Revision ID: 20260724_0001
Revises:
Create Date: 2026-07-24

The domain tables begin in later phases. This migration deliberately creates
only the Alembic baseline so Phase 0 does not pre-implement business features.
"""

from collections.abc import Sequence

revision: str = "20260724_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

