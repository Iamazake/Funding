from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.funding import (
    ContributionResponse,
    ContributionStatus,
    DecimalString,
    InvestorResponse,
)
from app.schemas.funding_ledger import FundingStatus


class ContributionAnalysisApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ContributionAnalysisSummary(ContributionAnalysisApiModel):
    contribution_id: UUID
    contribution_code: str
    investor_id: UUID
    investor_name: str
    original_amount: DecimalString
    available_balance: DecimalString
    allocated_capital: DecimalString
    returned_principal: DecimalString
    exposed_capital: DecimalString
    utilization_percentage: DecimalString
    monthly_rate: DecimalString
    contribution_date: date
    status: ContributionStatus


class ContributionOperationAnalysis(ContributionAnalysisApiModel):
    allocation_id: UUID
    sale_id: str
    sale_kind: Literal["CONTRACT", "ORPHAN_LOAN"]
    contract_code: str | None
    loan_id: int | None
    client_name: str | None
    operation_date: date
    operation_amount: DecimalString | None
    allocated_amount: DecimalString
    operation_percentage: DecimalString | None
    returned_principal: DecimalString
    exposed_capital: DecimalString
    allocation_status: Literal["ACTIVE", "REVERSED"]
    funding_status: FundingStatus


class ContributionMovementAnalysis(ContributionAnalysisApiModel):
    id: int
    effective_date: date
    entry_type: str
    origin_type: str
    contribution_id: UUID | None
    allocation_id: UUID | None
    revenue_distribution_item_id: UUID | None
    reversal_of_entry_id: int | None
    inflow: DecimalString
    outflow: DecimalString
    running_balance: DecimalString
    actor: str
    notes: str | None
    created_at: datetime


class ContributionReturnAnalysis(ContributionAnalysisApiModel):
    distribution_id: UUID
    distribution_item_id: UUID
    revenue_id: UUID | int
    sale_id: str
    allocation_id: UUID
    effective_date: date
    status: Literal["DISTRIBUTED", "REVERSED"]
    principal_amount: DecimalString
    interest_amount: DecimalString
    discount_amount: DecimalString


class ContributionReturnTotals(ContributionAnalysisApiModel):
    principal_amount: DecimalString
    interest_amount: DecimalString
    discount_amount: DecimalString


class ContributionAnalysisResponse(ContributionAnalysisApiModel):
    source_id: UUID
    contribution: ContributionResponse
    investor: InvestorResponse
    summary: ContributionAnalysisSummary
    operations: list[ContributionOperationAnalysis]
    movements: list[ContributionMovementAnalysis]
    return_totals: ContributionReturnTotals
    returns: list[ContributionReturnAnalysis]
