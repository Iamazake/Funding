from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.funding import DecimalString
from app.schemas.funding_ledger import FundingStatus

RevenueDistributionStatus = Literal[
    "PENDING_FUNDING",
    "READY",
    "DISTRIBUTED",
    "DIVERGENT",
    "REVERSED",
]


class RevenueDistributionApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RevenueDistributionProcess(RevenueDistributionApiModel):
    actor: str | None = Field(default=None, min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


class RevenueDistributionReverse(RevenueDistributionApiModel):
    actor: str | None = Field(default=None, min_length=2, max_length=120)
    reason: str = Field(min_length=3, max_length=4000)


class RevenueDistributionItemResponse(RevenueDistributionApiModel):
    id: UUID
    source_id: UUID
    source_type: Literal["INVESTOR_CONTRIBUTION", "REMO_CAPITAL"]
    allocation_id: UUID
    contribution_id: UUID | None
    contribution_code: str | None
    investor_id: UUID | None
    investor_name: str | None
    participation_rate: DecimalString
    percentage: DecimalString
    allocation_amount: DecimalString
    principal_amount: DecimalString
    interest_amount: DecimalString
    discount_amount: DecimalString
    total_amount: DecimalString


class RevenueDistributionResponse(RevenueDistributionApiModel):
    id: UUID | None
    revenue_id: UUID | int
    sale_id: str | None
    version: int | None
    status: RevenueDistributionStatus
    funding_status: FundingStatus | None
    reason: str | None
    effective_date: date | None
    base_amount: DecimalString | None
    principal_amount: DecimalString
    interest_amount: DecimalString
    discount_amount: DecimalString
    identified_amount: DecimalString
    distributed_principal: DecimalString
    distributed_interest: DecimalString
    distributed_discount: DecimalString
    unidentified_principal: DecimalString
    unidentified_interest: DecimalString
    unidentified_discount: DecimalString
    distributed_total: DecimalString
    unidentified_total: DecimalString
    primary_source_name: str | None
    source_count: int
    items: list[RevenueDistributionItemResponse]
    created_at: datetime | None
    reversed_at: datetime | None
