from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.models.debt import OperationalDebtContinuityPredecessor
from app.models.funding import FundingAllocation
from app.schemas.debt_continuity import (
    DebtContinuityConfirm,
    DebtContinuityResponse,
    DebtContinuityReviewCreate,
    RefinancingCorrection,
    RefinancingCreate,
)
from app.schemas.operational import RevenueItem, SaleItem
from app.services.funding.ledger import FundingLedgerRepository
from app.services.funding.revenue import realized_revenue_components
from app.services.operational.debt_continuity import (
    DebtContinuityConflictError,
    DebtContinuityRepository,
    DebtContinuityTerms,
    _allocate_rollover,
    assess_predecessor_candidates,
    debt_economic_effects,
    is_refinancing_closure_candidate,
    operational_new_disbursement,
    require_refinancing_new_disbursement,
    validate_same_client_identity,
)
from app.services.operational.identity import RevenueEvidence, match_revenues
from app.services.operational.read import (
    OperationalReadRepository,
    calculate_revenue_kpis,
    operational_revenue_components_for_kpi,
)
from app.services.treasury import TreasuryRepository

SALE_ID = UUID("10000000-0000-0000-0000-000000000001")
ZERO = Decimal("0.00")


def revenue(
    source_id: int,
    installment: int,
    *,
    identity_id: UUID | None,
    row_hash: str,
) -> RevenueEvidence:
    return RevenueEvidence(
        source_record_id=source_id,
        identity_id=identity_id,
        sale_identity_id=SALE_ID,
        contract_code="240600833",
        installment_code=str(installment),
        source_row_hash=row_hash,
        due_date=date(2026, 1, 1),
        principal=Decimal("100.00"),
        interest=Decimal("10.00"),
        expected_amount=Decimal("110.00"),
        payment_date=None,
        paid_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
    )


def test_confirmed_240600833_schedule_is_distinct_without_overwriting_old_revenues() -> None:
    previous = [
        revenue(
            installment,
            installment,
            identity_id=UUID(f"00000000-0000-0000-0000-{installment:012d}"),
            row_hash=f"old-{installment}",
        )
        for installment in range(1, 66)
    ]
    current = [
        revenue(
            1000 + installment,
            installment,
            identity_id=None,
            row_hash=f"old-{installment}",
        )
        for installment in (*range(1, 33), *range(57, 66))
    ]
    current.extend(
        revenue(
            2000 + installment,
            installment,
            identity_id=None,
            row_hash=f"renegotiated-{installment}",
        )
        for installment in range(1, 25)
    )
    original_identity_ids = [item.identity_id for item in previous]

    decisions = match_revenues(
        previous,
        current,
        confirmed_renegotiation_sales={SALE_ID},
    )

    old_schedule = [item for item in decisions if item.source_record_id < 2000]
    new_schedule = [item for item in decisions if item.source_record_id >= 2000]
    assert len(old_schedule) == 41
    assert {item.status for item in old_schedule} == {"AUTO_MATCH"}
    assert len(new_schedule) == 24
    assert {item.status for item in new_schedule} == {"NEW_IDENTITY"}
    assert {item.reason for item in new_schedule} == {"CONFIRMED_NEW_SCHEDULE"}
    assert [item.identity_id for item in previous] == original_identity_ids


def test_interest_only_payment_returns_no_principal_and_keeps_full_exposure() -> None:
    effects = debt_economic_effects(
        DebtContinuityTerms(
            original_principal=Decimal("1200.00"),
            principal_paid=Decimal("0.00"),
            principal_rolled=Decimal("1200.00"),
            interest_paid=Decimal("400.00"),
            has_new_disbursement=False,
        )
    )
    components = realized_revenue_components(
        principal=Decimal("1200.00"),
        interest=Decimal("400.00"),
        discount=Decimal("0.00"),
        paid_amount=Decimal("400.00"),
    )

    assert components == {
        "principal": Decimal("0.00"),
        "interest": Decimal("400.00"),
        "discount": Decimal("0.00"),
    }
    assert effects.interest_revenue == Decimal("400.00")
    assert effects.principal_return == Decimal("0.00")
    assert effects.remaining_exposure == Decimal("1200.00")
    assert effects.treasury_outflow == Decimal("0.00")
    assert effects.inherits_funding is True
    assert effects.requires_new_allocation is False


def test_financial_realization_remains_strict_for_negative_components() -> None:
    with pytest.raises(ValueError, match="não podem ser negativos"):
        realized_revenue_components(
            principal=Decimal("-75.60"),
            interest=Decimal("298.60"),
            discount=Decimal("4.82"),
            paid_amount=Decimal("218.18"),
        )


def test_operational_kpi_classifies_negative_amortization_without_mutating_source() -> None:
    item = RevenueItem(
        id=500,
        contract_code="2406001207",
        client_name="Cliente",
        installment_code="1",
        due_date=date(2025, 4, 4),
        payment_date=date(2025, 4, 2),
        expected_amount=Decimal("223.00"),
        paid_amount=Decimal("218.18"),
        principal_component=Decimal("-75.60"),
        interest_component=Decimal("298.60"),
        discount_amount=Decimal("4.82"),
        installment_status="PAGO_ANTEC",
        situation=None,
        anticipation_marker=None,
        data_quality_status="VALID",
    )
    original = item.model_copy(deep=True)

    components = operational_revenue_components_for_kpi(item)
    kpis = calculate_revenue_kpis([item], date(2026, 8, 27))

    assert components.principal == ZERO
    assert components.interest == Decimal("298.60")
    assert components.realized_principal == ZERO
    assert components.realized_interest == Decimal("223.00")
    assert components.realized_discount == Decimal("4.82")
    assert [(issue.type, issue.severity) for issue in components.issues] == [
        ("negative_amortization", "WARNING")
    ]
    assert kpis["paid_total"] == Decimal("218.18")
    assert kpis["principal_received"] == ZERO
    assert kpis["principal_total"] == ZERO
    assert kpis["interest_total"] == Decimal("298.60")
    assert item == original


def test_operational_kpi_classifies_negative_interest_adjustment_locally() -> None:
    item = RevenueItem(
        id=501,
        contract_code="2406001224",
        client_name="Cliente",
        installment_code="1",
        due_date=date(2026, 3, 23),
        payment_date=date(2026, 3, 23),
        expected_amount=Decimal("512.73"),
        paid_amount=Decimal("909.92"),
        principal_component=Decimal("518.33"),
        interest_component=Decimal("-5.60"),
        discount_amount=ZERO,
        installment_status="LIQ REFIN",
        situation=None,
        anticipation_marker=None,
        data_quality_status="VALID",
    )

    components = operational_revenue_components_for_kpi(item)

    assert components.principal == Decimal("518.33")
    assert components.interest == ZERO
    assert components.realized_principal == Decimal("518.33")
    assert components.realized_interest == ZERO
    assert [(issue.type, issue.severity) for issue in components.issues] == [
        ("negative_interest_adjustment", "WARNING")
    ]


def test_partial_principal_rollover_keeps_original_funding_without_new_cash() -> None:
    effects = debt_economic_effects(
        DebtContinuityTerms(
            original_principal=Decimal("10000.00"),
            principal_paid=Decimal("3000.00"),
            principal_rolled=Decimal("7000.00"),
            interest_paid=Decimal("0.00"),
            has_new_disbursement=False,
        )
    )
    allocation = FundingAllocation(
        id=uuid4(),
        amount=Decimal("10000.00"),
        source_id=uuid4(),
        sale_id=f"sale:{uuid4()}",
        status="ACTIVE",
    )
    inherited = _allocate_rollover(Decimal("7000.00"), [(allocation, Decimal("7000.00"))])
    zero_liquidation = realized_revenue_components(
        principal=Decimal("1000.00"),
        interest=Decimal("100.00"),
        discount=Decimal("0.00"),
        paid_amount=Decimal("0.00"),
    )

    assert effects.principal_return == Decimal("3000.00")
    assert effects.remaining_exposure == Decimal("7000.00")
    assert effects.treasury_outflow == ZERO
    assert effects.requires_new_allocation is False
    assert inherited == {allocation.id: Decimal("7000.00")}
    assert zero_liquidation == {
        "principal": ZERO,
        "interest": ZERO,
        "discount": ZERO,
    }
    assert "nova allocation bloqueada" in inspect.getsource(
        FundingLedgerRepository.create_allocation
    )


def test_real_new_disbursement_remains_treasury_outflow_and_requires_funding() -> None:
    effects = debt_economic_effects(
        DebtContinuityTerms(
            original_principal=Decimal("10000.00"),
            principal_paid=Decimal("0.00"),
            principal_rolled=Decimal("10000.00"),
            interest_paid=Decimal("0.00"),
            has_new_disbursement=True,
            new_disbursement_amount=Decimal("10000.00"),
        )
    )

    assert effects.treasury_outflow == Decimal("10000.00")
    assert effects.requires_new_allocation is True
    assert effects.inherits_funding is False


def test_ambiguous_predecessors_never_transfer_funding_or_touch_ledger() -> None:
    assessment = assess_predecessor_candidates([uuid4(), uuid4()])

    assert assessment.status == "REVIEW_REQUIRED"
    assert assessment.predecessor_sale_identity_id is None
    assert assessment.funding_transfer_allowed is False
    assert assessment.ledger_mutation_allowed is False


def test_treasury_filters_confirmed_rollover_without_hiding_real_sales() -> None:
    source = inspect.getsource(TreasuryRepository._movement_union)
    assert 'OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED"' in source
    assert "OperationalDebtContinuity.has_new_disbursement.is_(False)" in source
    assert "predecessor_sale_identity_id" in source


def _revenue_item(
    *, status: str, paid: str | None, payment_date: date | None, due_date: date
) -> RevenueItem:
    return RevenueItem(
        id=1,
        contract_code="CTR-OLD",
        client_name="Cliente",
        installment_code="1",
        due_date=due_date,
        payment_date=payment_date,
        expected_amount=Decimal("200.00"),
        paid_amount=Decimal(paid) if paid is not None else None,
        principal_component=Decimal("150.00"),
        interest_component=Decimal("50.00"),
        discount_amount=ZERO,
        installment_status=status,
        situation=None,
        anticipation_marker=None,
        data_quality_status="VALID",
    )


def test_refin_preserves_paid_history_in_revenue_kpis() -> None:
    paid = _revenue_item(
        status="PAGO",
        paid="200.00",
        payment_date=date(2026, 1, 10),
        due_date=date(2026, 1, 10),
    )
    refin = _revenue_item(
        status="REFIN",
        paid=None,
        payment_date=None,
        due_date=date(2026, 2, 10),
    )

    kpis = calculate_revenue_kpis([paid, refin], date(2026, 8, 26))

    assert paid.paid_amount == Decimal("200.00")
    assert kpis["principal_total"] == Decimal("150.00")
    assert kpis["interest_total"] == Decimal("50.00")
    assert kpis["principal_open"] == ZERO
    assert kpis["overdue_principal"] == ZERO


def test_refin_closure_is_historical_not_payment_or_current_exposure() -> None:
    refin = _revenue_item(
        status="REFIN",
        paid=None,
        payment_date=None,
        due_date=date(2026, 1, 10),
    )
    kpis = calculate_revenue_kpis([refin], date(2026, 8, 26))
    source = inspect.getsource(DebtContinuityRepository.create_refinancing)

    assert refin.installment_status == "REFIN"
    assert refin.paid_amount is None
    assert kpis["principal_total"] == ZERO
    assert kpis["interest_total"] == ZERO
    assert kpis["overdue_pmt"] == ZERO
    assert "FundingLedgerEntry(" not in source
    assert "FundingAllocation(" not in source
    assert "automatic_allocation_created" in source


def test_refin_response_exposes_canonical_predecessor_and_successor() -> None:
    fields = DebtContinuityResponse.model_fields
    assert "predecessor_sale_identity_id" in fields
    assert "successor_sale_identity_id" in fields
    assert "predecessor_contract_code" in fields
    assert "successor_contract_code" in fields
    assert "refinanced_installment_count" in fields


def test_refin_uses_only_operational_release_and_never_contract_subtraction() -> None:
    old_remaining = Decimal("1000.00")
    successor_principal = Decimal("2000.00")
    operational_release = Decimal("325.00")

    result = operational_new_disbursement(operational_release)

    assert result == Decimal("325.00")
    assert result != successor_principal - old_remaining
    assert "-" not in inspect.getsource(operational_new_disbursement).split("return")[-1]


def test_partial_payment_remains_real_revenue_and_is_never_refin() -> None:
    partial = RevenueItem(
        id=2,
        contract_code="CTR-A",
        client_name="Cliente",
        installment_code="1",
        due_date=date(2026, 8, 10),
        payment_date=date(2026, 8, 10),
        expected_amount=Decimal("300.00"),
        paid_amount=Decimal("200.00"),
        principal_component=Decimal("250.00"),
        interest_component=Decimal("50.00"),
        discount_amount=ZERO,
        installment_status="PARCIAL",
        situation=None,
        anticipation_marker=None,
        data_quality_status="VALID",
    )

    kpis = calculate_revenue_kpis([partial], date(2026, 8, 27))

    assert partial.installment_status == "PARCIAL"
    assert partial.paid_amount == Decimal("200.00")
    assert kpis["paid_total"] == Decimal("200.00")
    assert kpis["principal_received"] == Decimal("150.00")
    assert kpis["interest_total"] == Decimal("50.00")
    assert not is_refinancing_closure_candidate(None, Decimal("200.00"))
    assert not is_refinancing_closure_candidate(date(2026, 8, 10), Decimal("200.00"))
    assert is_refinancing_closure_candidate(None, ZERO)
    treasury_source = inspect.getsource(TreasuryRepository._movement_union)
    assert 'OperationalInstallment.paid_amount.label("inflow")' in treasury_source
    assert "OperationalInstallment.paid_amount > ZERO" in treasury_source


def test_partial_payment_then_renegotiation_rolls_only_remaining_exposure() -> None:
    predecessor_id = uuid4()
    successor_id = uuid4()
    relationship = DebtContinuityReviewCreate(
        source_batch_id=4,
        successor_sale_identity_id=successor_id,
        candidate_predecessor_sale_identity_ids=[predecessor_id],
        continuity_type="RENEGOTIATION",
        scope="NEW_CONTRACT",
        reason="Reprogramação humana confirmada.",
    )
    effects = debt_economic_effects(
        DebtContinuityTerms(
            original_principal=Decimal("250.00"),
            principal_paid=Decimal("150.00"),
            principal_rolled=Decimal("100.00"),
            interest_paid=Decimal("50.00"),
            has_new_disbursement=False,
        )
    )
    source = inspect.getsource(DebtContinuityRepository.confirm)

    assert effects.interest_revenue == Decimal("50.00")
    assert effects.principal_return == Decimal("150.00")
    assert effects.remaining_exposure == Decimal("100.00")
    assert effects.treasury_outflow == ZERO
    assert effects.inherits_funding is True
    assert effects.requires_new_allocation is False
    assert relationship.candidate_predecessor_sale_identity_ids == [predecessor_id]
    assert relationship.successor_sale_identity_id == successor_id
    assert relationship.continuity_type == "RENEGOTIATION"
    assert "FundingAllocation(" not in source
    assert "FundingLedgerEntry(" not in source
    assert "TreasuryBankValidation(" not in source
    assert "RENEGOTIATION_CONFIRMED" in source


def test_refinancing_is_reserved_for_positive_operational_release() -> None:
    with pytest.raises(DebtContinuityConflictError):
        require_refinancing_new_disbursement(None)
    with pytest.raises(DebtContinuityConflictError):
        require_refinancing_new_disbursement(ZERO)

    assert require_refinancing_new_disbursement(Decimal("100.00")) == Decimal("100.00")


def test_sale_details_expose_refinancing_and_renegotiation_relationship_types() -> None:
    fields = SaleItem.model_fields
    source = inspect.getsource(OperationalReadRepository._continuity_relationships)

    assert "continuity_type" in fields
    assert "predecessor_sale_ids" in fields
    assert "predecessor_contract_codes" in fields
    assert '"REFIN_CONFIRMED"' in source
    assert '"RENEGOTIATION_CONFIRMED"' in source
    assert "continuity_type" in source
    assert "OperationalDebtContinuity.updated_at" in source
    assert "OperationalDebtContinuityPredecessor" in source
    assert '"successor_sale_id": successor_key' in source


@pytest.mark.parametrize("predecessor_count", [1, 3])
def test_refinancing_and_renegotiation_accept_one_or_many_predecessors(
    predecessor_count: int,
) -> None:
    predecessor_ids = [uuid4() for _ in range(predecessor_count)]
    successor_id = uuid4()
    refin = RefinancingCreate(
        predecessor_sale_identity_ids=predecessor_ids,
        successor_sale_identity_id=successor_id,
        effective_date=date(2026, 8, 27),
    )
    reneg = DebtContinuityConfirm(
        predecessor_sale_identity_ids=predecessor_ids,
        original_principal=Decimal("300.00"),
        principal_paid=Decimal("100.00"),
        principal_rolled=Decimal("200.00"),
        interest_paid=Decimal("20.00"),
        has_new_disbursement=False,
        effective_date=date(2026, 8, 27),
    )

    assert refin.resolved_predecessor_ids == predecessor_ids
    assert reneg.resolved_predecessor_ids == predecessor_ids


def test_duplicate_predecessor_and_different_canonical_client_are_blocked() -> None:
    predecessor_id = uuid4()
    with pytest.raises(ValueError, match="mais de uma vez"):
        RefinancingCreate(
            predecessor_sale_identity_ids=[predecessor_id, predecessor_id],
            successor_sale_identity_id=uuid4(),
            effective_date=date(2026, 8, 27),
        )

    validate_same_client_identity(10, {uuid4(): 10, uuid4(): 10})
    with pytest.raises(DebtContinuityConflictError, match="mesmo cliente canônico"):
        validate_same_client_identity(10, {uuid4(): 10, uuid4(): 11})
    with pytest.raises(DebtContinuityConflictError, match="identidade canônica"):
        validate_same_client_identity(10, {uuid4(): None})


def test_n_to_one_relation_is_unbounded_current_unique_and_backfilled_by_new_migration() -> None:
    table = OperationalDebtContinuityPredecessor.__table__
    indexes = {item.name: item for item in table.indexes}
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "f2l000000001_debt_continuity_predecessors.py"
    ).read_text(encoding="utf-8")

    assert "predecessor_2" not in migration
    assert "predecessor_3" not in migration
    assert indexes["uq_operational_debt_continuity_predecessors_current"].unique
    assert 'down_revision: str | None = "f2k000000001"' in migration
    assert "INSERT INTO operational_debt_continuity_predecessors" in migration
    assert "predecessor_sale_identity_id IS NOT NULL" in migration


def test_multiple_predecessors_preserve_payments_funding_origins_and_cash_rules() -> None:
    create_source = inspect.getsource(DebtContinuityRepository.create_refinancing)
    confirm_source = inspect.getsource(DebtContinuityRepository.confirm)
    funding_source = inspect.getsource(DebtContinuityRepository._inherit_funding)
    response_source = inspect.getsource(DebtContinuityRepository._response)

    assert "for predecessor_id in predecessor_ids" in create_source
    assert "_classify_unpaid_installments" in create_source
    assert "_operational_released_amount" in create_source
    assert "paid_amount" not in create_source
    assert "FundingAllocation(" not in create_source
    assert "FundingLedgerEntry(" not in create_source
    assert "predecessor_ids" in confirm_source
    assert "has_new_disbursement" in confirm_source
    assert "FundingAllocation.sale_identity_id.in_(predecessor_ids)" in funding_source
    assert "origin_allocation_id" in response_source
    assert "predecessor_sale_identity_id" in response_source


def test_predecessor_list_correction_is_append_only_and_audited() -> None:
    ids = [uuid4(), uuid4(), uuid4()]
    correction = RefinancingCorrection(
        predecessor_sale_identity_ids=[ids[0], ids[2]],
        successor_sale_identity_id=uuid4(),
        effective_date=date(2026, 8, 27),
        notes="Retirada auditada do contrato intermediário.",
    )
    source = inspect.getsource(DebtContinuityRepository.correct_refinancing)
    replace_source = inspect.getsource(DebtContinuityRepository._replace_predecessors)

    assert correction.predecessor_sale_identity_ids == [ids[0], ids[2]]
    assert '"before"' in source and '"after"' in source
    assert '"PREDECESSORS_CORRECTED"' in source
    assert "item.is_current = False" in replace_source
    assert "item.removed_at" in replace_source
    assert "OperationalDebtContinuityPredecessor(" in replace_source
