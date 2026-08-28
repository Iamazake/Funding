from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.funding import FundingInvestor
from app.schemas.debt_continuity import RefinancingCorrection
from app.schemas.funding import ContributionCreate, InvestorCreate
from app.schemas.treasury import TreasuryValidationCreate
from app.services.excel.mapping import WorkbookMapper
from app.services.funding.repository import FundingRepository
from app.services.operational.debt_continuity import DebtContinuityRepository
from app.services.operational.read import _display_client_name


def test_investor_accepts_new_fields_but_response_masks_tax_id() -> None:
    data = InvestorCreate(
        name="Pessoa Investidora",
        tax_id="123.456.789-01",
        phone="(11) 99999-0000",
        notes="Contato preferencial por telefone.",
    )
    now = datetime(2026, 8, 26, tzinfo=UTC)
    row = FundingInvestor(
        id=uuid4(),
        code="INV-TESTE",
        name=data.name,
        tax_id=data.tax_id,
        phone=data.phone,
        status=data.status,
        notes=data.notes,
        created_at=now,
        updated_at=now,
    )

    response = FundingRepository._investor_response(row)

    assert response.tax_id_masked == "123.***.***-01"
    assert response.phone == "(11) 99999-0000"
    assert "tax_id" not in response.model_dump()


def test_contribution_end_date_is_contractual_and_never_creates_ledger_by_schema() -> None:
    contribution = ContributionCreate(
        investor_id=uuid4(),
        contribution_date=date(2026, 8, 1),
        end_date=date(2027, 8, 1),
        original_amount=Decimal("100000.00"),
        monthly_rate=Decimal("0.0200000000"),
    )
    assert contribution.end_date == date(2027, 8, 1)

    with pytest.raises(ValidationError):
        ContributionCreate(
            investor_id=uuid4(),
            contribution_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
            original_amount=Decimal("1.00"),
            monthly_rate=Decimal("0"),
        )


@pytest.mark.parametrize("bank_code", ["INTER", "BTG", "PICPAY", "NUBANK", "C6", "CASH"])
def test_bank_validation_accepts_stable_codes(bank_code: str) -> None:
    result = TreasuryValidationCreate(
        observed_amount=Decimal("10.00"),
        observed_date=date(2026, 8, 26),
        bank_code=bank_code,
    )
    assert result.bank_code == bank_code


def test_bol_antecip_is_preserved_as_observation_not_financial_rule() -> None:
    source = inspect.getsource(WorkbookMapper._map_row)
    assert 'values["BOL_ANTECIP"]' in source
    assert '"bol_antecip"' in source


def test_client_name_fallback_never_overwrites_ambiguous_source() -> None:
    assert _display_client_name(None, ("Nome Operacional", False)) == (
        "Nome Operacional",
        "ECON_EMPRESTIMOS",
        False,
    )
    assert _display_client_name(None, ("Nome Ambíguo", True)) == (None, None, True)


def test_refin_correction_requires_audit_reason_and_never_mutates_ledger() -> None:
    with pytest.raises(ValidationError):
        RefinancingCorrection(
            successor_contract_code="CTR-NEW",
            effective_date=date(2026, 8, 26),
            notes="",
        )
    source = inspect.getsource(DebtContinuityRepository.correct_refinancing)
    assert '"REFIN_CORRECTED"' in source
    assert '"previous_state"' in source
    assert '"new_state"' in source
    assert "FundingLedgerEntry(" not in source
    assert "FundingAllocation(" not in source
