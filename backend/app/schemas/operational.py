from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

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
    funding_status: str = "NOT_INFORMED"
    bank_validation_status: str = "NOT_RECORDED"


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


class RevenueItem(OperationalApiModel):
    id: int
    contract_code: str | None
    client_name: str | None
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


class RevenueDetail(RevenueItem):
    payment_marker: str | None
    source_reference: str | None
    warnings: list[QualityMessage] = Field(default_factory=list)
    divergences: list[QualityMessage] = Field(default_factory=list)
    funding_status: str = "NOT_INFORMED"
    bank_validation_status: str = "NOT_RECORDED"


class RevenuePage(OperationalApiModel):
    items: list[RevenueItem]
    pagination: PageMeta
    summary: RevenueSummary
