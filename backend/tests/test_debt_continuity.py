from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.funding import FundingAllocation
from app.services.funding.ledger import FundingLedgerRepository
from app.services.funding.revenue import realized_revenue_components
from app.services.operational.debt_continuity import (
    DebtContinuityTerms,
    _allocate_rollover,
    assess_predecessor_candidates,
    debt_economic_effects,
)
from app.services.operational.identity import RevenueEvidence, match_revenues
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
    inherited = _allocate_rollover(
        Decimal("7000.00"), [(allocation, Decimal("7000.00"))]
    )
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
