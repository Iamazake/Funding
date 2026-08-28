from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.funding import DecimalString

ContinuityType = Literal["RENEGOTIATION", "ROLLOVER", "REFINANCING"]
ContinuityScope = Literal["SAME_CONTRACT", "NEW_CONTRACT"]
ContinuityStatus = Literal[
    "REVIEW_REQUIRED", "RENEGOTIATION_CONFIRMED", "REFIN_CONFIRMED", "REJECTED"
]


class DebtContinuityApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DebtContinuityReviewCreate(DebtContinuityApiModel):
    source_batch_id: int = Field(gt=0)
    successor_sale_identity_id: UUID
    candidate_predecessor_sale_identity_ids: list[UUID] = Field(min_length=1)
    continuity_type: Literal["RENEGOTIATION", "ROLLOVER"] = "RENEGOTIATION"
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
    predecessor_sale_identity_id: UUID | None = None
    predecessor_sale_identity_ids: list[UUID] = Field(default_factory=list)
    original_principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    principal_paid: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    principal_rolled: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    interest_paid: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    has_new_disbursement: bool
    effective_date: date
    evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_principal_equation(self) -> DebtContinuityConfirm:
        _validate_predecessor_references(
            self.predecessor_sale_identity_id, self.predecessor_sale_identity_ids
        )
        if self.original_principal != self.principal_paid + self.principal_rolled:
            raise ValueError(
                "principal original deve ser igual ao principal pago mais o rolado."
            )
        return self

    @property
    def resolved_predecessor_ids(self) -> list[UUID]:
        return _resolved_predecessor_ids(
            self.predecessor_sale_identity_id, self.predecessor_sale_identity_ids
        )


class DebtContinuityReject(DebtContinuityApiModel):
    reason: str = Field(min_length=3, max_length=255)
    evidence: dict[str, Any] = Field(default_factory=dict)


class RefinancingCreate(DebtContinuityApiModel):
    predecessor_sale_identity_id: UUID | None = None
    predecessor_sale_identity_ids: list[UUID] = Field(default_factory=list)
    successor_sale_identity_id: UUID | None = None
    successor_contract_code: str | None = Field(default=None, min_length=1, max_length=100)
    effective_date: date
    notes: str | None = Field(default=None, max_length=255)
    principal_rolled: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=2
    )

    @model_validator(mode="after")
    def validate_distinct_contracts(self):
        _validate_predecessor_references(
            self.predecessor_sale_identity_id, self.predecessor_sale_identity_ids
        )
        if (self.successor_sale_identity_id is None) == (self.successor_contract_code is None):
            raise ValueError("Informe o contrato sucessor por identidade ou código.")
        if self.successor_sale_identity_id in self.resolved_predecessor_ids:
            raise ValueError("REFIN exige contratos predecessor e sucessor distintos.")
        return self

    @property
    def resolved_predecessor_ids(self) -> list[UUID]:
        return _resolved_predecessor_ids(
            self.predecessor_sale_identity_id, self.predecessor_sale_identity_ids
        )


class RefinancingCorrection(DebtContinuityApiModel):
    predecessor_sale_identity_ids: list[UUID] | None = None
    successor_sale_identity_id: UUID | None = None
    successor_contract_code: str | None = Field(default=None, min_length=1, max_length=100)
    effective_date: date
    notes: str = Field(min_length=3, max_length=255)

    @model_validator(mode="after")
    def validate_successor_reference(self):
        if (self.successor_sale_identity_id is None) == (self.successor_contract_code is None):
            raise ValueError("Informe o contrato sucessor por identidade ou código.")
        if self.predecessor_sale_identity_ids is not None:
            _validate_predecessor_references(None, self.predecessor_sale_identity_ids)
        return self


class DebtFundingContinuityResponse(DebtContinuityApiModel):
    id: UUID
    origin_allocation_id: UUID
    source_id: UUID
    rolled_amount: DecimalString
    predecessor_sale_identity_id: UUID | None = None


class DebtContinuityResponse(DebtContinuityApiModel):
    id: UUID
    source_batch_id: int
    continuity_type: ContinuityType
    scope: ContinuityScope
    predecessor_sale_identity_id: UUID | None
    predecessor_sale_identity_ids: list[UUID] = Field(default_factory=list)
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
    predecessor_contract_code: str | None = None
    predecessor_contract_codes: list[str] = Field(default_factory=list)
    successor_contract_code: str | None = None
    refinanced_installment_count: int = 0
    operational_new_disbursement: DecimalString | None = None


def _resolved_predecessor_ids(
    singular: UUID | None, plural: list[UUID]
) -> list[UUID]:
    return list(plural) if plural else ([singular] if singular is not None else [])


def _validate_predecessor_references(singular: UUID | None, plural: list[UUID]) -> None:
    resolved = _resolved_predecessor_ids(singular, plural)
    if not resolved:
        raise ValueError("Informe ao menos um contrato predecessor.")
    if len(resolved) != len(set(resolved)):
        raise ValueError("Um contrato predecessor não pode ser selecionado mais de uma vez.")
    if singular is not None and plural and singular not in plural:
        raise ValueError(
            "A referência predecessora singular deve pertencer à lista informada."
        )


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
