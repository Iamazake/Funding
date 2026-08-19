from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.operational import MONEY, utc_now

# Contractual monthly rates are stored as fractions: 2% a.m. == 0.0200000000.
MONTHLY_RATE = Numeric(12, 10)


class FundingInvestor(Base):
    __tablename__ = "funding_investors"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_funding_investors_status"),
        UniqueConstraint("code"),
        Index("ix_funding_investors_code", "code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
    )

    contributions: Mapped[list[FundingContribution]] = relationship(
        back_populates="investor", lazy="raise"
    )


class FundingContribution(Base):
    __tablename__ = "funding_contributions"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="ck_funding_contributions_amount_positive"),
        CheckConstraint(
            "monthly_rate >= 0 AND monthly_rate <= 1",
            name="ck_funding_contributions_monthly_rate",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'CLOSED')",
            name="ck_funding_contributions_status",
        ),
        UniqueConstraint("code"),
        Index("ix_funding_contributions_code", "code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    investor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_investors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contribution_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    monthly_rate: Mapped[Decimal] = mapped_column(MONTHLY_RATE, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # A future ledger/allocation transaction must set this before its first movement.
    # Once set, the API refuses direct changes to original_amount.
    original_amount_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
    )

    investor: Mapped[FundingInvestor] = relationship(back_populates="contributions", lazy="raise")


class FundingAuditEvent(Base):
    __tablename__ = "funding_audit_events"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('INVESTOR', 'CONTRIBUTION', 'SOURCE', 'LEDGER', "
            "'ALLOCATION', 'DISTRIBUTION', 'IDENTITY_MIGRATION')",
            name="ck_funding_audit_events_entity_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class FundingSource(Base):
    __tablename__ = "funding_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('INVESTOR_CONTRIBUTION', 'REMO_CAPITAL')",
            name="ck_funding_sources_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_funding_sources_status",
        ),
        CheckConstraint(
            "(source_type = 'INVESTOR_CONTRIBUTION' AND contribution_id IS NOT NULL) OR "
            "(source_type = 'REMO_CAPITAL' AND contribution_id IS NULL)",
            name="ck_funding_sources_contribution_type",
        ),
        UniqueConstraint("contribution_id"),
        Index("ix_funding_sources_source_type", "source_type"),
        Index("ix_funding_sources_status", "status"),
        Index(
            "uq_funding_sources_one_remo_capital",
            "source_type",
            unique=True,
            postgresql_where=sa_text("source_type = 'REMO_CAPITAL'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contribution_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_contributions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class FundingAllocation(Base):
    __tablename__ = "funding_allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_funding_allocations_amount_positive"),
        CheckConstraint("status IN ('ACTIVE', 'REVERSED')", name="ck_funding_allocations_status"),
        CheckConstraint(
            "sale_id ~ '^sale:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            "[0-9a-f]{4}-[0-9a-f]{12}$'",
            name="ck_funding_allocations_sale_id",
        ),
        Index("ix_funding_allocations_sale_id", "sale_id"),
        Index("ix_funding_allocations_source_id", "source_id"),
        Index(
            "uq_funding_allocations_active_sale_source",
            "sale_id",
            "source_id",
            unique=True,
            postgresql_where=sa_text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sale_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    legacy_sale_id: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FundingLedgerEntry(Base):
    __tablename__ = "funding_ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_funding_ledger_amount_positive"),
        CheckConstraint("direction IN (-1, 1)", name="ck_funding_ledger_direction"),
        CheckConstraint(
            "entry_type IN ('CONTRIBUTION', 'ALLOCATION', 'PRINCIPAL_RETURN', "
            "'REINVESTMENT', 'CAPITAL_RETURN', 'REVERSAL', 'ADJUSTMENT')",
            name="ck_funding_ledger_entry_type",
        ),
        CheckConstraint(
            "origin_type IN ('CONTRIBUTION', 'SALE_ALLOCATION', 'REMO_ADMIN', "
            "'ALLOCATION_REVERSAL', 'REVENUE_DISTRIBUTION', "
            "'REVENUE_DISTRIBUTION_REVERSAL', 'FUTURE_FINANCIAL_EVENT')",
            name="ck_funding_ledger_origin_type",
        ),
        CheckConstraint(
            "(entry_type = 'CONTRIBUTION' AND contribution_id IS NOT NULL "
            "AND allocation_id IS NULL AND revenue_distribution_item_id IS NULL "
            "AND reversal_of_entry_id IS NULL AND direction = 1) OR "
            "(entry_type = 'ALLOCATION' AND contribution_id IS NULL "
            "AND allocation_id IS NOT NULL AND revenue_distribution_item_id IS NULL "
            "AND reversal_of_entry_id IS NULL AND direction = -1) OR "
            "(entry_type = 'REVERSAL' AND contribution_id IS NULL "
            "AND allocation_id IS NULL AND revenue_distribution_item_id IS NULL "
            "AND reversal_of_entry_id IS NOT NULL) OR "
            "(entry_type = 'PRINCIPAL_RETURN' AND contribution_id IS NULL "
            "AND allocation_id IS NULL AND revenue_distribution_item_id IS NOT NULL "
            "AND reversal_of_entry_id IS NULL AND direction = 1) OR "
            "(entry_type NOT IN ('CONTRIBUTION', 'ALLOCATION', 'REVERSAL', "
            "'PRINCIPAL_RETURN') "
            "AND contribution_id IS NULL AND allocation_id IS NULL "
            "AND revenue_distribution_item_id IS NULL AND reversal_of_entry_id IS NULL)",
            name="ck_funding_ledger_relationships",
        ),
        UniqueConstraint("contribution_id"),
        UniqueConstraint("allocation_id"),
        UniqueConstraint(
            "revenue_distribution_item_id",
            name="uq_funding_ledger_revenue_distribution_item",
        ),
        UniqueConstraint("reversal_of_entry_id"),
        Index("ix_funding_ledger_source_effective", "source_id", "effective_date", "id"),
        Index("ix_funding_ledger_entry_type", "entry_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    direction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    origin_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contribution_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_contributions.id", ondelete="RESTRICT"),
    )
    allocation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_allocations.id", ondelete="RESTRICT"),
    )
    revenue_distribution_item_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_revenue_distribution_items.id", ondelete="RESTRICT"),
    )
    reversal_of_entry_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("funding_ledger_entries.id", ondelete="RESTRICT"),
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class FundingRevenueDistribution(Base):
    __tablename__ = "funding_revenue_distributions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DISTRIBUTED', 'DIVERGENT', 'REVERSED')",
            name="ck_funding_revenue_distributions_status",
        ),
        CheckConstraint(
            "sale_id ~ '^sale:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            "[0-9a-f]{4}-[0-9a-f]{12}$'",
            name="ck_funding_revenue_distributions_sale_id",
        ),
        CheckConstraint("version > 0", name="ck_funding_revenue_distributions_version"),
        CheckConstraint("base_amount > 0", name="ck_funding_revenue_distributions_base"),
        CheckConstraint(
            "principal_amount >= 0 AND interest_amount >= 0 AND discount_amount >= 0",
            name="ck_funding_revenue_distributions_components",
        ),
        CheckConstraint(
            "identified_amount >= 0 AND distributed_principal >= 0 "
            "AND distributed_interest >= 0 "
            "AND distributed_discount >= 0 AND unidentified_principal >= 0 "
            "AND unidentified_interest >= 0 AND unidentified_discount >= 0",
            name="ck_funding_revenue_distributions_totals",
        ),
        UniqueConstraint(
            "revenue_identity_id",
            "version",
            name="uq_funding_revenue_distributions_version",
        ),
        Index(
            "ix_funding_revenue_distributions_revenue_identity_id",
            "revenue_identity_id",
        ),
        Index("ix_funding_revenue_distributions_revenue_id", "revenue_id"),
        Index(
            "ix_funding_revenue_distributions_sale_identity_id",
            "sale_identity_id",
        ),
        Index("ix_funding_revenue_distributions_sale_id", "sale_id"),
        Index(
            "uq_funding_revenue_distributions_divergent_snapshot",
            "revenue_identity_id",
            "composition_hash",
            unique=True,
            postgresql_where=sa_text("status = 'DIVERGENT'"),
        ),
        Index(
            "uq_funding_revenue_distributions_active",
            "revenue_identity_id",
            unique=True,
            postgresql_where=sa_text("status = 'DISTRIBUTED'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    revenue_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operational_installments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revenue_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_revenue_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sale_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legacy_sale_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    composition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    interest_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    identified_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    distributed_principal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    distributed_interest: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    distributed_discount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unidentified_principal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unidentified_interest: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unidentified_discount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    source_count: Mapped[int] = mapped_column(nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FundingRevenueDistributionItem(Base):
    __tablename__ = "funding_revenue_distribution_items"
    __table_args__ = (
        CheckConstraint(
            "participation_rate >= 0 AND participation_rate <= 1",
            name="ck_funding_revenue_distribution_items_rate",
        ),
        CheckConstraint(
            "allocation_amount > 0 AND base_amount > 0",
            name="ck_funding_revenue_distribution_items_base",
        ),
        CheckConstraint(
            "principal_amount >= 0 AND interest_amount >= 0 AND discount_amount >= 0",
            name="ck_funding_revenue_distribution_items_components",
        ),
        UniqueConstraint(
            "distribution_id",
            "allocation_id",
            name="uq_funding_revenue_distribution_items_allocation",
        ),
        Index(
            "ix_funding_revenue_distribution_items_distribution_id",
            "distribution_id",
        ),
        Index("ix_funding_revenue_distribution_items_source_id", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    distribution_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_revenue_distributions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    allocation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("funding_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    participation_rate: Mapped[Decimal] = mapped_column(Numeric(18, 12), nullable=False)
    allocation_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    interest_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
