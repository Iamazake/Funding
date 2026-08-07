from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.operational import MONEY, RATE, utc_now

QUALITY_VALUES = "'VALID', 'WARNING', 'DIVERGENT', 'INVALID'"


class OperationalPromotion(Base):
    __tablename__ = "operational_promotions"
    __table_args__ = (
        UniqueConstraint("source_batch_id", name="uq_operational_promotions_source_batch"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormalizedSnapshotMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("operational_promotions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_quality_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    current_source_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id"), nullable=False, index=True
    )
    first_seen_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id"), nullable=False
    )
    last_seen_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id"), nullable=False
    )
    active_in_source: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
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


class OperationalClient(NormalizedSnapshotMixin, Base):
    __tablename__ = "operational_clients"
    __table_args__ = (
        CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_clients_quality",
        ),
        UniqueConstraint(
            "promotion_id", "source_bcli_row_id", name="uq_operational_clients_source_row"
        ),
    )

    source_bcli_row_id: Mapped[int] = mapped_column(
        ForeignKey("excel_bcli_cadastro_rows.id"), nullable=False, index=True
    )
    source_client_code: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_original: Mapped[str | None] = mapped_column(Text)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    name: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)


class OperationalContract(NormalizedSnapshotMixin, Base):
    __tablename__ = "operational_contracts"
    __table_args__ = (
        CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_contracts_quality",
        ),
        UniqueConstraint(
            "promotion_id", "source_dfen_row_id", name="uq_operational_contracts_source_row"
        ),
        UniqueConstraint(
            "current_source_batch_id",
            "contract_code",
            name="uq_operational_contracts_batch_code",
        ),
    )

    source_dfen_row_id: Mapped[int] = mapped_column(
        ForeignKey("excel_dfen_contrato_rows.id"), nullable=False, index=True
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_clients.id"), index=True
    )
    contract_code: Mapped[str | None] = mapped_column(String(100), index=True)
    source_client_code: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    operation_date: Mapped[date | None] = mapped_column(Date)
    first_due_date: Mapped[date | None] = mapped_column(Date)
    term: Mapped[int | None] = mapped_column(Integer)
    principal: Mapped[Decimal | None] = mapped_column(MONEY)
    iof: Mapped[Decimal | None] = mapped_column(MONEY)
    financed_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    installment_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    released_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    released_amount_original: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date)
    operational_status: Mapped[str | None] = mapped_column(Text)


class OperationalLoan(NormalizedSnapshotMixin, Base):
    __tablename__ = "operational_loans"
    __table_args__ = (
        CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_loans_quality",
        ),
        UniqueConstraint(
            "promotion_id", "source_loan_row_id", name="uq_operational_loans_source_row"
        ),
    )

    source_loan_row_id: Mapped[int] = mapped_column(
        ForeignKey("excel_econ_emprestimos_rows.id"), nullable=False, index=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_contracts.id"), index=True
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_clients.id"), index=True
    )
    contract_code: Mapped[str | None] = mapped_column(String(100), index=True)
    source_client_code: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    operation_date: Mapped[date | None] = mapped_column(Date)
    first_due_date: Mapped[date | None] = mapped_column(Date)
    term: Mapped[int | None] = mapped_column(Integer)
    principal: Mapped[Decimal | None] = mapped_column(MONEY)
    iof: Mapped[Decimal | None] = mapped_column(MONEY)
    financed_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    installment_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    released_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    released_amount_original: Mapped[str | None] = mapped_column(Text)
    interest_rate: Mapped[Decimal | None] = mapped_column(RATE)
    irr_rate: Mapped[Decimal | None] = mapped_column(RATE)
    cet_monthly_rate: Mapped[Decimal | None] = mapped_column(RATE)
    operational_status: Mapped[str | None] = mapped_column(Text)


class OperationalInstallment(NormalizedSnapshotMixin, Base):
    __tablename__ = "operational_installments"
    __table_args__ = (
        CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_installments_quality",
        ),
        UniqueConstraint(
            "promotion_id",
            "source_amortization_row_id",
            name="uq_operational_installments_source_row",
        ),
    )

    source_amortization_row_id: Mapped[int] = mapped_column(
        ForeignKey("excel_econ_amortizacoes_rows.id"), nullable=False, index=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_contracts.id"), index=True
    )
    contract_code: Mapped[str | None] = mapped_column(String(100), index=True)
    installment_code: Mapped[str | None] = mapped_column(String(100), index=True)
    candidate_group_key: Mapped[str | None] = mapped_column(String(255), index=True)
    candidate_group_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_date: Mapped[date | None] = mapped_column(Date)
    expected_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    principal_component: Mapped[Decimal | None] = mapped_column(MONEY)
    interest_component: Mapped[Decimal | None] = mapped_column(MONEY)
    paid_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    payment_date: Mapped[date | None] = mapped_column(Date)
    discount_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    discount_amount_original: Mapped[str | None] = mapped_column(Text)
    payment_marker_original: Mapped[str | None] = mapped_column(Text)
    installment_status: Mapped[str | None] = mapped_column(Text)
    situation: Mapped[str | None] = mapped_column(Text)
    anticipation_marker: Mapped[str | None] = mapped_column(Text)
    source_key: Mapped[str | None] = mapped_column(Text)
    financial_product: Mapped[str | None] = mapped_column(Text)


class OperationalPaymentMovement(NormalizedSnapshotMixin, Base):
    __tablename__ = "operational_payment_movements"
    __table_args__ = (
        CheckConstraint(
            f"data_quality_status IN ({QUALITY_VALUES})",
            name="ck_operational_payment_movements_quality",
        ),
    )

    installment_id: Mapped[int] = mapped_column(
        ForeignKey("operational_installments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_amortization_row_id: Mapped[int] = mapped_column(
        ForeignKey("excel_econ_amortizacoes_rows.id"), nullable=False, index=True
    )
    paid_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    payment_date: Mapped[date | None] = mapped_column(Date)
    discount_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    payment_marker_original: Mapped[str | None] = mapped_column(Text)


class OperationalQualityLink(Base):
    __tablename__ = "operational_quality_links"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(client_id, contract_id, loan_id, installment_id, "
            "payment_movement_id) = 1",
            name="ck_operational_quality_links_one_record",
        ),
        CheckConstraint(
            "data_inconsistency_id IS NOT NULL OR "
            "(issue_type IS NOT NULL AND severity IS NOT NULL)",
            name="ck_operational_quality_links_issue_source",
        ),
        CheckConstraint(
            f"severity IS NULL OR severity IN ({QUALITY_VALUES})",
            name="ck_operational_quality_links_severity",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("operational_promotions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_inconsistency_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_inconsistencies.id"), index=True
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_clients.id", ondelete="CASCADE"), index=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_contracts.id", ondelete="CASCADE"), index=True
    )
    loan_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_loans.id", ondelete="CASCADE"), index=True
    )
    installment_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_installments.id", ondelete="CASCADE"), index=True
    )
    payment_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_payment_movements.id", ondelete="CASCADE"), index=True
    )
    issue_type: Mapped[str | None] = mapped_column(String(80))
    severity: Mapped[str | None] = mapped_column(String(24))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


Index(
    "uq_operational_promotions_one_current",
    OperationalPromotion.is_current,
    unique=True,
    postgresql_where=OperationalPromotion.is_current.is_(True),
)
Index(
    "ix_operational_installments_contract_code_installment_code",
    OperationalInstallment.contract_code,
    OperationalInstallment.installment_code,
)
