from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.funding import DecimalString

TreasuryMovementType = Literal[
    "CONTRIBUTION",
    "SALE",
    "REVENUE",
    "CAPITAL_REMUNERATION",
]
TreasuryDirection = Literal["INFLOW", "OUTFLOW"]
TreasuryValidationStatus = Literal[
    "PENDING",
    "VALIDATED",
    "DIVERGENT",
]


class TreasuryApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TreasuryMovementResponse(TreasuryApiModel):
    id: str
    movement_type: TreasuryMovementType
    direction: TreasuryDirection
    movement_date: date | None
    reference: str
    description: str
    contract_code: str | None
    client_name: str | None = None
    installment_code: str | None = None
    data_quality_status: str | None = None
    funding_status: str | None = None
    investor_id: UUID | None
    investor_name: str | None
    inflow: DecimalString | None
    outflow: DecimalString | None
    amount: DecimalString | None
    origin: str
    source_record_id: str
    detail_path: str
    status: str
    financial_operator: str | None = None
    financial_account: str | None = None
    validation_status: TreasuryValidationStatus = "PENDING"
    validation_id: UUID | None = None
    observed_amount: DecimalString | None = None
    observed_date: date | None = None
    difference_amount: DecimalString | None = None
    bank_reference: str | None = None
    validated_at: datetime | None = None
    validated_by: UUID | None = None
    validation_justification: str | None = None


class TreasurySummaryResponse(TreasuryApiModel):
    period_from: date | None
    period_to: date | None
    total_inflows: DecimalString
    total_outflows: DecimalString
    known_net_flow: DecimalString
    contributions: DecimalString
    revenues: DecimalString
    sales: DecimalString
    contribution_count: int
    revenue_count: int
    sale_count: int
    undated_movement_count: int
    unknown_amount_count: int
    pending_validation_count: int
    validated_count: int
    divergent_count: int
    net_difference_amount: DecimalString


class TreasuryPageMeta(TreasuryApiModel):
    page: int
    page_size: int
    total: int
    pages: int


class TreasuryMovementsResponse(TreasuryApiModel):
    items: list[TreasuryMovementResponse]
    pagination: TreasuryPageMeta


class TreasuryValidationCreate(TreasuryApiModel):
    observed_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    observed_date: date
    bank_reference: str | None = Field(default=None, max_length=255)
    justification: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize_optional_text(self):
        for field_name in ("bank_reference", "justification"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class TreasuryValidationResponse(TreasuryApiModel):
    id: UUID
    movement_key: str
    version: int
    is_current: bool
    supersedes_validation_id: UUID | None
    movement_type: Literal["CONTRIBUTION", "SALE", "REVENUE"]
    direction: TreasuryDirection
    system_amount_snapshot: DecimalString
    system_date_snapshot: date | None
    observed_amount: DecimalString
    observed_date: date
    difference_amount: DecimalString
    status: Literal["VALIDATED", "DIVERGENT"]
    bank_reference: str | None
    justification: str | None
    validated_at: datetime
    validated_by: UUID | None
    created_at: datetime


class TreasuryValidationState(TreasuryApiModel):
    movement_key: str
    status: TreasuryValidationStatus
    current: TreasuryValidationResponse | None


class TreasuryValidationHistory(TreasuryApiModel):
    movement_key: str
    items: list[TreasuryValidationResponse]
