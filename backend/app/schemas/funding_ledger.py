from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.funding import DecimalString

FundingSourceType = Literal["INVESTOR_CONTRIBUTION", "REMO_CAPITAL"]
FundingSourceStatus = Literal["ACTIVE", "INACTIVE"]
FundingStatus = Literal[
    "NOT_INFORMED", "INCOMPLETE", "COMPLETE", "OVERFUNDED", "BASE_AMOUNT_UNAVAILABLE"
]


class FundingLedgerApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FundingSourceResponse(FundingLedgerApiModel):
    id: UUID
    source_type: FundingSourceType
    contribution_id: UUID | None
    status: FundingSourceStatus
    investor_id: UUID | None = None
    investor_name: str | None = None
    contribution_code: str | None = None
    contribution_date: date | None = None
    original_amount: DecimalString | None = None
    monthly_rate: DecimalString | None = None
    current_balance: DecimalString
    created_at: datetime
    updated_at: datetime


class LedgerEntryResponse(FundingLedgerApiModel):
    id: int
    source_id: UUID
    entry_type: str
    amount: DecimalString
    direction: int
    signed_amount: DecimalString
    effective_date: date
    origin_type: str
    contribution_id: UUID | None
    allocation_id: UUID | None
    revenue_distribution_item_id: UUID | None = None
    reversal_of_entry_id: int | None
    actor: str
    notes: str | None
    created_at: datetime


class SourceBalanceResponse(FundingLedgerApiModel):
    source_id: UUID
    as_of: date | None
    balance: DecimalString


class RemoCapitalEntryCreate(FundingLedgerApiModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    effective_date: date
    direction: Literal["CREDIT", "DEBIT"] = "CREDIT"
    actor: str | None = Field(default=None, min_length=2, max_length=120)
    notes: str = Field(min_length=3, max_length=4000)


class AllocationCreate(FundingLedgerApiModel):
    source_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    actor: str | None = Field(default=None, min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


class AllocationReverse(FundingLedgerApiModel):
    actor: str | None = Field(default=None, min_length=2, max_length=120)
    reason: str = Field(min_length=3, max_length=4000)


class AllocationResponse(FundingLedgerApiModel):
    id: UUID
    sale_id: str
    source_id: UUID
    source_type: FundingSourceType
    contribution_id: UUID | None
    contribution_code: str | None
    investor_id: UUID | None
    investor_name: str | None
    amount: DecimalString
    percentage: DecimalString | None
    effective_date: date
    status: Literal["ACTIVE", "REVERSED"]
    actor: str
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None
    inherited_from_predecessor: bool = False
    origin_sale_id: str | None = None


class SaleCompositionResponse(FundingLedgerApiModel):
    sale_id: str
    operation_date: date
    base_field: Literal["released_amount"] = "released_amount"
    operation_amount: DecimalString | None
    identified_amount: DecimalString
    difference: DecimalString | None
    funding_status: FundingStatus
    source_count: int
    allocations: list[AllocationResponse]
    has_new_disbursement: bool = True
    funding_origin_sale_id: str | None = None
