from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

Money = Annotated[Decimal, PlainSerializer(lambda value: format(value, "f"), return_type=str)]
Quality = Literal["VALID", "WARNING", "DIVERGENT", "INVALID"]


class OperationalApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageMeta(OperationalApiModel):
    page: int
    page_size: int
    total: int
    pages: int


class QualityMessage(OperationalApiModel):
    type: str
    severity: str
    message: str


class SaleSummary(OperationalApiModel):
    total_contracts: int
    principal: Money
    released_amount: Money
    financed_amount: Money
    warning_contracts: int
    divergent_contracts: int


class SaleItem(OperationalApiModel):
    id: str
    contract_code: str | None
    client_name: str | None
    client_identity_id: int | None = None
    client_name_source: Literal["CLIENT_CANONICAL", "ECON_EMPRESTIMOS"] | None = None
    client_name_divergent: bool = False
    source_client_code: str | None
    operation_date: date | None
    release_date: date | None
    first_due_date: date | None
    term: int | None
    principal: Money | None
    iof: Money | None
    financed_amount: Money | None
    installment_amount: Money | None
    released_amount: Money | None
    interest_rate: Money | None
    irr_rate: Money | None
    cet_monthly_rate: Money | None
    status: str | None
    data_quality_status: Quality
    warning_count: int = 0
    divergence_count: int = 0
    funding_status: Literal[
        "NOT_INFORMED",
        "INCOMPLETE",
        "COMPLETE",
        "OVERFUNDED",
        "BASE_AMOUNT_UNAVAILABLE",
    ] = "NOT_INFORMED"
    funding_identified_amount: Money = Decimal("0.00")
    funding_difference: Money | None = None
    funding_source_count: int = 0
    bank_validation_status: str = "NOT_RECORDED"
    continuity_id: str | None = None
    continuity_type: Literal["REFINANCING", "RENEGOTIATION", "ROLLOVER"] | None = None
    continuity_role: Literal["PREDECESSOR", "SUCCESSOR"] | None = None
    predecessor_sale_id: str | None = None
    predecessor_contract_code: str | None = None
    predecessor_sale_ids: list[str] = Field(default_factory=list)
    predecessor_contract_codes: list[str] = Field(default_factory=list)
    successor_sale_id: str | None = None
    successor_contract_code: str | None = None
    continuity_effective_date: date | None = None
    continuity_notes: str | None = None


class SaleDetail(SaleItem):
    warnings: list[QualityMessage] = Field(default_factory=list)
    divergences: list[QualityMessage] = Field(default_factory=list)


class SalesPage(OperationalApiModel):
    items: list[SaleItem]
    pagination: PageMeta
    summary: SaleSummary


class RevenueSummary(OperationalApiModel):
    total_records: int
    expected_amount: Money
    paid_amount: Money
    principal_received: Money
    interest_amount: Money
    discount_amount: Money
    pending_records: int
    warning_records: int
    divergent_records: int
    principal_total: Money = Decimal("0.00")
    principal_open: Money = Decimal("0.00")
    average_pmt: Money = Decimal("0.00")
    overdue_principal: Money = Decimal("0.00")
    overdue_pmt: Money = Decimal("0.00")
    delinquency_percentage: Money = Decimal("0.00")


class RevenueItem(OperationalApiModel):
    id: int
    revenue_identity_id: UUID | None = None
    contract_code: str | None
    client_name: str | None
    client_name_source: Literal["CLIENT_CANONICAL", "ECON_EMPRESTIMOS"] | None = None
    client_name_divergent: bool = False
    installment_code: str | None
    due_date: date | None
    payment_date: date | None
    expected_amount: Money | None
    paid_amount: Money | None
    principal_component: Money | None
    interest_component: Money | None
    discount_amount: Money | None
    installment_status: str | None
    situation: str | None
    anticipation_marker: str | None
    data_quality_status: Quality
    warning_count: int = 0
    divergence_count: int = 0
    sale_id: str | None = None
    funding_status: (
        Literal[
            "NOT_INFORMED",
            "INCOMPLETE",
            "COMPLETE",
            "OVERFUNDED",
            "BASE_AMOUNT_UNAVAILABLE",
        ]
        | None
    ) = None
    distribution_status: Literal[
        "PENDING_FUNDING",
        "READY",
        "DISTRIBUTED",
        "DIVERGENT",
        "REVERSED",
    ] = "PENDING_FUNDING"
    primary_source_name: str | None = None
    bank_validation_status: str = "NOT_RECORDED"
    refinanced_to_contract_code: str | None = None


class RevenueDetail(RevenueItem):
    payment_marker: str | None
    source_reference: str | None
    warnings: list[QualityMessage] = Field(default_factory=list)
    divergences: list[QualityMessage] = Field(default_factory=list)
    bank_validation_status: str = "NOT_RECORDED"


class RevenuePage(OperationalApiModel):
    items: list[RevenueItem]
    pagination: PageMeta
    summary: RevenueSummary
