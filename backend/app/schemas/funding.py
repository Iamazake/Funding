from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

DecimalString = Annotated[
    Decimal, PlainSerializer(lambda value: format(value, "f"), return_type=str)
]
InvestorStatus = Literal["ACTIVE", "INACTIVE"]
ContributionStatus = Literal["ACTIVE", "INACTIVE", "CLOSED"]


class FundingApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InvestorCreate(FundingApiModel):
    name: str = Field(min_length=3, max_length=200)
    tax_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=32)
    status: InvestorStatus = "ACTIVE"
    notes: str | None = Field(default=None, max_length=4000)


class InvestorUpdate(FundingApiModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    tax_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=32)
    status: InvestorStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class InvestorResponse(FundingApiModel):
    id: UUID
    code: str
    name: str
    tax_id_masked: str | None = None
    phone: str | None = None
    status: InvestorStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ContributionCreate(FundingApiModel):
    investor_id: UUID
    contribution_date: date
    end_date: date | None = None
    original_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    monthly_rate: Decimal = Field(ge=0, le=1, max_digits=12, decimal_places=10)
    status: ContributionStatus = "ACTIVE"
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_end_date(self):
        if self.end_date is not None and self.end_date < self.contribution_date:
            raise ValueError("Data fim não pode ser anterior à data do aporte.")
        return self


class ContributionUpdate(FundingApiModel):
    investor_id: UUID | None = None
    contribution_date: date | None = None
    end_date: date | None = None
    original_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    monthly_rate: Decimal | None = Field(default=None, ge=0, le=1, max_digits=12, decimal_places=10)
    status: ContributionStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class ContributionResponse(FundingApiModel):
    id: UUID
    code: str
    investor_id: UUID
    contribution_date: date
    end_date: date | None = None
    original_amount: DecimalString
    monthly_rate: DecimalString
    status: ContributionStatus
    notes: str | None
    original_amount_editable: bool
    created_at: datetime
    updated_at: datetime
