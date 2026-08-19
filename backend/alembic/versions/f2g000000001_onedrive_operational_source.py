"""Fase 2G: OneDrive Personal como fonte operacional.

Revision ID: f2g000000001
Revises: f2f000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2g000000001"
down_revision: str | None = "f2f000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_source_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("encrypted_token_cache", sa.Text(), nullable=True),
        sa.Column("drive_id", sa.String(length=255), nullable=True),
        sa.Column("drive_item_id", sa.String(length=255), nullable=True),
        sa.Column("canonical_file_name", sa.String(length=255), nullable=True),
        sa.Column("canonical_file_path", sa.Text(), nullable=True),
        sa.Column("last_known_etag", sa.Text(), nullable=True),
        sa.Column("last_known_ctag", sa.Text(), nullable=True),
        sa.Column("last_known_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_known_size", sa.BigInteger(), nullable=True),
        sa.Column("last_checked_sha256", sa.String(length=64), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("update_status", sa.String(length=24), nullable=False),
        sa.CheckConstraint("source_type IN ('ONEDRIVE')", name="ck_source_connection_type"),
        sa.CheckConstraint(
            "status IN ('CONNECTED', 'DISCONNECTED', 'RECONNECT_REQUIRED', 'FILE_NOT_FOUND')",
            name="ck_source_connection_status",
        ),
        sa.CheckConstraint(
            "update_status IN ('UNKNOWN', 'CURRENT', 'UPDATE_AVAILABLE', 'FILE_NOT_FOUND', "
            "'RECONNECT_REQUIRED', 'ERROR')",
            name="ck_source_connection_update_status",
        ),
        sa.ForeignKeyConstraint(["connected_by_user_id"], ["app_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", name="uq_operational_source_connections_type"),
    )
    op.create_table(
        "onedrive_oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_auth_flow", sa.Text(), nullable=False),
        sa.Column("admin_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["admin_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index("ix_onedrive_oauth_states_expires_at", "onedrive_oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_onedrive_oauth_states_expires_at", table_name="onedrive_oauth_states")
    op.drop_table("onedrive_oauth_states")
    op.drop_table("operational_source_connections")
