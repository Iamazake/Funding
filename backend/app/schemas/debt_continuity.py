from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.funding import DecimalString

ContinuityType = Literal["RENEGOTIATION", "ROLLOVER"]
ContinuityScope = Literal["SAME_CONTRACT", "NEW_CONTRACT"]
ContinuityStatus = Literal[
    "REVIEW_REQUIRED", "RENEGOTIATION_CONFIRMED", "REJECTED"
]


class DebtContinuityApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DebtContinuityReviewCreate(DebtContinuityApiModel):
    source_batch_id: int = Field(gt=0)
    successor_sale_identity_id: UUID
    candidate_predecessor_sale_identity_ids: list[UUID] = Field(min_length=1)
    continuity_type: ContinuityType = "RENEGOTIATION"
    scope: ContinuityScope
    effective_date: date | None = None
    reason: str = Field(min_length=3, max_length=255)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scope(self) -> DebtContinuityReviewCreate:
        candidates = set(self.candidate_predecessor_sale_identity_ids)
        if self.scope == "SAME_CONTRACT" and candidates != {
            self.successor_sale_identity_id
        }:
            raise ValueError("SAME_CONTRACT exige a própria Venda como predecessora.")
        if self.scope == "NEW_CONTRACT" and self.successor_sale_identity_id in candidates:
            raise ValueError("NEW_CONTRACT exige Venda predecessora distinta.")
        return self


class DebtContinuityConfirm(DebtContinuityApiModel):
    predecessor_sale_identity_id: UUID
    original_principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    principal_paid: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    principal_rolled: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    interest_paid: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    has_new_disbursement: bool
    effective_date: date
    evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_principal_equation(self) -> DebtContinuityConfirm:
        if self.original_principal != self.principal_paid + self.principal_rolled:
            raise ValueError(
                "principal original deve ser igual ao principal pago mais o rolado."
            )
        return self


class DebtContinuityReject(DebtContinuityApiModel):
    reason: str = Field(min_length=3, max_length=255)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DebtFundingContinuityResponse(DebtContinuityApiModel):
    id: UUID
    origin_allocation_id: UUID
    source_id: UUID
    rolled_amount: DecimalString


class DebtContinuityResponse(DebtContinuityApiModel):
    id: UUID
    source_batch_id: int
    continuity_type: ContinuityType
    scope: ContinuityScope
    predecessor_sale_identity_id: UUID | None
    successor_sale_identity_id: UUID
    status: ContinuityStatus
    original_principal: DecimalString | None
    principal_paid: DecimalString | None
    principal_rolled: DecimalString | None
    interest_paid: DecimalString | None
    has_new_disbursement: bool | None
    effective_date: date | None
    reason: str
    evidence: dict[str, Any]
    created_by: UUID
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    created_at: datetime
    funding_sources: list[DebtFundingContinuityResponse] = Field(default_factory=list)


class DebtContinuityPreview(DebtContinuityApiModel):
    mode: Literal["PRE_MIGRATION", "APPLIED"]
    current_promotion_id: int
    current_source_batch_id: int
    candidate_same_contract_renegotiations: int
    deterministic_confirmations: int
    planned_backfill_rows: int
    existing_reviews: int
    existing_confirmed: int
    note: str
