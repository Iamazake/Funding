from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.operational import utc_now


class OperationalSaleIdentity(Base):
    __tablename__ = "operational_sale_identities"
    __table_args__ = (
        CheckConstraint(
            "origin_kind IN ('CONTRACT', 'ORPHAN_LOAN')",
            name="ck_operational_sale_identities_origin_kind",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'REVIEW_REQUIRED', 'RETIRED')",
            name="ck_operational_sale_identities_status",
        ),
        UniqueConstraint(
            "source_system",
            "source_contract_code",
            name="uq_operational_sale_identities_source_contract",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_system: Mapped[str] = mapped_column(
        String(40), nullable=False, default="CADASTRO_CLIENTES"
    )
    source_contract_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    origin_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalSaleSnapshot(Base):
    __tablename__ = "operational_sale_snapshots"
    __table_args__ = (
        CheckConstraint(
            "contract_id IS NOT NULL OR loan_id IS NOT NULL",
            name="ck_operational_sale_snapshots_source",
        ),
        CheckConstraint(
            "match_status IN ('BASELINE', 'AUTO_MATCH', 'MANUAL_MATCH', 'NEW_IDENTITY')",
            name="ck_operational_sale_snapshots_match_status",
        ),
        UniqueConstraint(
            "promotion_id", "sale_identity_id", name="uq_operational_sale_snapshots_identity"
        ),
        UniqueConstraint("contract_id", name="uq_operational_sale_snapshots_contract"),
        UniqueConstraint("loan_id", name="uq_operational_sale_snapshots_loan"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("operational_promotions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_contracts.id", ondelete="CASCADE")
    )
    loan_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_loans.id", ondelete="CASCADE")
    )
    match_status: Mapped[str] = mapped_column(String(24), nullable=False)
    match_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalRevenueIdentity(Base):
    __tablename__ = "operational_revenue_identities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'REVIEW_REQUIRED', 'RETIRED')",
            name="ck_operational_revenue_identities_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sale_identity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        index=True,
    )
    unresolved_contract_code: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalRevenueSnapshot(Base):
    __tablename__ = "operational_revenue_snapshots"
    __table_args__ = (
        CheckConstraint(
            "match_status IN ('BASELINE', 'AUTO_MATCH', 'MANUAL_MATCH', 'NEW_IDENTITY')",
            name="ck_operational_revenue_snapshots_match_status",
        ),
        UniqueConstraint(
            "promotion_id",
            "revenue_identity_id",
            name="uq_operational_revenue_snapshots_identity",
        ),
        UniqueConstraint("installment_id", name="uq_operational_revenue_snapshots_installment"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revenue_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_revenue_identities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("operational_promotions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    installment_id: Mapped[int] = mapped_column(
        ForeignKey("operational_installments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_status: Mapped[str] = mapped_column(String(24), nullable=False)
    match_score: Mapped[int | None] = mapped_column()
    match_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalIdentityMatchReview(Base):
    __tablename__ = "operational_identity_match_reviews"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('SALE', 'REVENUE')",
            name="ck_operational_identity_match_reviews_entity_type",
        ),
        CheckConstraint(
            "status IN ('REVIEW_REQUIRED', 'RESOLVED', 'REJECTED')",
            name="ck_operational_identity_match_reviews_status",
        ),
        UniqueConstraint(
            "source_batch_id",
            "entity_type",
            "source_record_id",
            name="uq_operational_identity_match_reviews_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_promotions.id", ondelete="SET NULL"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    candidate_identity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="REVIEW_REQUIRED", server_default="REVIEW_REQUIRED"
    )
    critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalIdentityMigrationManifest(Base):
    __tablename__ = "operational_identity_migration_manifest"
    __table_args__ = (
        CheckConstraint(
            "reference_type IN ('SALE', 'REVENUE', 'TREASURY_MOVEMENT')",
            name="ck_operational_identity_migration_manifest_type",
        ),
        UniqueConstraint(
            "reference_type",
            "legacy_reference",
            name="uq_operational_identity_migration_manifest_reference",
        ),
        Index(
            "ix_operational_identity_migration_manifest_canonical",
            "canonical_identity_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    legacy_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_identity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
