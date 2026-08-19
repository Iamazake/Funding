from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.operational import utc_now


class OperationalSourceConnection(Base):
    __tablename__ = "operational_source_connections"
    __table_args__ = (
        CheckConstraint("source_type IN ('ONEDRIVE')", name="ck_source_connection_type"),
        CheckConstraint(
            "status IN ('CONNECTED', 'DISCONNECTED', 'RECONNECT_REQUIRED', 'FILE_NOT_FOUND')",
            name="ck_source_connection_status",
        ),
        CheckConstraint(
            "update_status IN ('UNKNOWN', 'CURRENT', 'UPDATE_AVAILABLE', 'FILE_NOT_FOUND', "
            "'RECONNECT_REQUIRED', 'ERROR')",
            name="ck_source_connection_update_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    encrypted_token_cache: Mapped[str | None] = mapped_column(Text)
    drive_id: Mapped[str | None] = mapped_column(String(255))
    drive_item_id: Mapped[str | None] = mapped_column(String(255))
    canonical_file_name: Mapped[str | None] = mapped_column(String(255))
    canonical_file_path: Mapped[str | None] = mapped_column(Text)
    last_known_etag: Mapped[str | None] = mapped_column(Text)
    last_known_ctag: Mapped[str | None] = mapped_column(Text)
    last_known_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_known_size: Mapped[int | None] = mapped_column(BigInteger)
    last_checked_sha256: Mapped[str | None] = mapped_column(String(64))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DISCONNECTED")
    update_status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNKNOWN")


class OneDriveOAuthState(Base):
    __tablename__ = "onedrive_oauth_states"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    encrypted_auth_flow: Mapped[str] = mapped_column(Text, nullable=False)
    admin_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
