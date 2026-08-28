from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.operational import MONEY, utc_now


class OperationalDebtContinuity(Base):
    __tablename__ = "operational_debt_continuities"
    __table_args__ = (
        CheckConstraint(
            "continuity_type IN ('RENEGOTIATION', 'ROLLOVER', 'REFINANCING')",
            name="ck_operational_debt_continuities_type",
        ),
        CheckConstraint(
            "scope IN ('SAME_CONTRACT', 'NEW_CONTRACT')",
            name="ck_operational_debt_continuities_scope",
        ),
        CheckConstraint(
            "status IN ('REVIEW_REQUIRED', 'RENEGOTIATION_CONFIRMED', "
            "'REFIN_CONFIRMED', 'REJECTED')",
            name="ck_operational_debt_continuities_status",
        ),
        CheckConstraint(
            "original_principal IS NULL OR original_principal >= 0",
            name="ck_operational_debt_continuities_original_principal",
        ),
        CheckConstraint(
            "principal_paid IS NULL OR principal_paid >= 0",
            name="ck_operational_debt_continuities_principal_paid",
        ),
        CheckConstraint(
            "principal_rolled IS NULL OR principal_rolled >= 0",
            name="ck_operational_debt_continuities_principal_rolled",
        ),
        CheckConstraint(
            "interest_paid IS NULL OR interest_paid >= 0",
            name="ck_operational_debt_continuities_interest_paid",
        ),
        CheckConstraint(
            "original_principal IS NULL OR principal_paid IS NULL OR principal_rolled IS NULL "
            "OR original_principal = principal_paid + principal_rolled",
            name="ck_operational_debt_continuities_principal_equation",
        ),
        CheckConstraint(
            "status NOT IN ('RENEGOTIATION_CONFIRMED', 'REFIN_CONFIRMED') OR "
            "(predecessor_sale_identity_id IS NOT NULL AND has_new_disbursement IS NOT NULL "
            "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_operational_debt_continuities_confirmation",
        ),
        CheckConstraint(
            "predecessor_sale_identity_id IS NULL OR "
            "(scope = 'SAME_CONTRACT') = "
            "(predecessor_sale_identity_id = successor_sale_identity_id)",
            name="ck_operational_debt_continuities_scope_identity",
        ),
        UniqueConstraint(
            "source_batch_id",
            "successor_sale_identity_id",
            name="uq_operational_debt_continuities_batch_successor",
        ),
        Index(
            "ix_operational_debt_continuities_predecessor",
            "predecessor_sale_identity_id",
        ),
        Index(
            "ix_operational_debt_continuities_successor_status",
            "successor_sale_identity_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    continuity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    predecessor_sale_identity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
    )
    successor_sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="REVIEW_REQUIRED", server_default="REVIEW_REQUIRED"
    )
    original_principal: Mapped[Decimal | None] = mapped_column(MONEY)
    principal_paid: Mapped[Decimal | None] = mapped_column(MONEY)
    principal_rolled: Mapped[Decimal | None] = mapped_column(MONEY)
    interest_paid: Mapped[Decimal | None] = mapped_column(MONEY)
    has_new_disbursement: Mapped[bool | None] = mapped_column(Boolean)
    effective_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalDebtContinuityPredecessor(Base):
    """Append-only membership history for the canonical N -> 1 relationship."""

    __tablename__ = "operational_debt_continuity_predecessors"
    __table_args__ = (
        CheckConstraint(
            "(is_current AND removed_at IS NULL AND removed_by IS NULL) OR "
            "(NOT is_current AND removed_at IS NOT NULL AND removed_by IS NOT NULL)",
            name="ck_operational_debt_continuity_predecessors_lifecycle",
        ),
        Index(
            "uq_operational_debt_continuity_predecessors_current",
            "continuity_id",
            "sale_identity_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index(
            "ix_operational_debt_continuity_predecessors_sale_current",
            "sale_identity_id",
            "is_current",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    continuity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_debt_continuities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    added_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False
    )
    removed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalDebtFundingContinuity(Base):
    __tablename__ = "operational_debt_funding_continuities"
    __table_args__ = (
        CheckConstraint(
            "rolled_amount > 0",
            name="ck_operational_debt_funding_continuities_amount",
        ),
        UniqueConstraint(
            "continuity_id",
            "origin_allocation_id",
            name="uq_operational_debt_funding_continuities_allocation",
        ),
        Index(
            "ix_operational_debt_funding_continuities_successor",
            "successor_sale_identity_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    continuity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_debt_continuities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    successor_sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    origin_allocation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rolled_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalDebtContinuityAuditEvent(Base):
    __tablename__ = "operational_debt_continuity_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('REVIEW_CREATED', 'RENEGOTIATION_CONFIRMED', "
            "'REFIN_CONFIRMED', 'REFIN_CORRECTED', 'PREDECESSORS_CORRECTED', "
            "'REJECTED')",
            name="ck_operational_debt_continuity_audit_action",
        ),
        Index(
            "ix_operational_debt_continuity_audit_continuity_created",
            "continuity_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    continuity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_debt_continuities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class OperationalDebtRefinancedInstallment(Base):
    """Append-only classification of unpaid debt closed by a confirmed refinancing."""

    __tablename__ = "operational_debt_refinanced_installments"
    __table_args__ = (
        UniqueConstraint(
            "continuity_id",
            "revenue_identity_id",
            name="uq_operational_debt_refinanced_installments_continuity_revenue",
        ),
        Index(
            "ix_operational_debt_refinanced_installments_revenue",
            "revenue_identity_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    continuity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_debt_continuities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revenue_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_revenue_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_status: Mapped[str | None] = mapped_column(String(100))
    classified_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False
    )
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
