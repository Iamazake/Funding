from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.operational import MONEY, utc_now


class TreasuryBankValidation(Base):
    __tablename__ = "treasury_bank_validations"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('CONTRIBUTION', 'SALE', 'REVENUE')",
            name="ck_treasury_bank_validations_movement_type",
        ),
        CheckConstraint(
            "direction IN ('INFLOW', 'OUTFLOW')",
            name="ck_treasury_bank_validations_direction",
        ),
        CheckConstraint(
            "status IN ('VALIDATED', 'DIVERGENT')",
            name="ck_treasury_bank_validations_status",
        ),
        CheckConstraint(
            "system_amount_snapshot > 0 AND observed_amount >= 0",
            name="ck_treasury_bank_validations_amounts",
        ),
        CheckConstraint(
            "difference_amount = observed_amount - system_amount_snapshot",
            name="ck_treasury_bank_validations_difference",
        ),
        CheckConstraint(
            "(difference_amount = 0 AND status = 'VALIDATED') OR "
            "(difference_amount <> 0 AND status = 'DIVERGENT')",
            name="ck_treasury_bank_validations_status_difference",
        ),
        CheckConstraint(
            "status <> 'DIVERGENT' OR "
            "(justification IS NOT NULL AND btrim(justification) <> '')",
            name="ck_treasury_bank_validations_divergent_justification",
        ),
        CheckConstraint("version > 0", name="ck_treasury_bank_validations_version"),
        UniqueConstraint(
            "movement_key",
            "version",
            name="uq_treasury_bank_validations_movement_version",
        ),
        UniqueConstraint(
            "supersedes_validation_id",
            name="uq_treasury_bank_validations_supersedes",
        ),
        Index("ix_treasury_bank_validations_movement_key", "movement_key"),
        Index("ix_treasury_bank_validations_status", "status"),
        Index(
            "uq_treasury_bank_validations_current",
            "movement_key",
            unique=True,
            postgresql_where=sa_text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    movement_key: Mapped[str] = mapped_column(String(128), nullable=False)
    legacy_movement_key: Mapped[str | None] = mapped_column(String(128), index=True)
    sale_identity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_sale_identities.id", ondelete="RESTRICT"),
        index=True,
    )
    revenue_identity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operational_revenue_identities.id", ondelete="RESTRICT"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_text("true")
    )
    supersedes_validation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("treasury_bank_validations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    system_amount_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    system_date_snapshot: Mapped[date | None] = mapped_column(Date)
    observed_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    difference_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    bank_reference: Mapped[str | None] = mapped_column(String(255))
    justification: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    validated_by_legacy: Mapped[str | None] = mapped_column(String(120))
    validated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
