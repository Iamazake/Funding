from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.funding import FundingAllocation, FundingLedgerEntry
from app.schemas.contribution_analysis import ContributionOperationAnalysis
from app.services.funding.analysis import (
    ContributionAnalysisRepository,
    OperationIdentity,
    analysis_amounts,
    valid_principal_returns,
)

SOURCE_ID = UUID("30000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


def ledger_entry(
    entry_id: int,
    entry_type: str,
    amount: str,
    direction: int,
    effective_date: date,
    *,
    item_id: UUID | None = None,
    reversal_of: int | None = None,
) -> FundingLedgerEntry:
    return FundingLedgerEntry(
        id=entry_id,
        source_id=SOURCE_ID,
        entry_type=entry_type,
        amount=Decimal(amount),
        direction=direction,
        effective_date=effective_date,
        origin_type="REVENUE_DISTRIBUTION" if item_id else "REMO_ADMIN",
        revenue_distribution_item_id=item_id,
        reversal_of_entry_id=reversal_of,
        actor="Teste",
        created_at=NOW,
    )


def operation(
    amount: str,
    returned: str = "0.00",
    status: str = "ACTIVE",
    *,
    sale_id: str = "contract:10",
) -> ContributionOperationAnalysis:
    allocated = Decimal(amount)
    returned_amount = Decimal(returned)
    return ContributionOperationAnalysis(
        allocation_id=uuid4(),
        sale_id=sale_id,
        sale_kind="CONTRACT",
        contract_code="CTR-10",
        loan_id=None,
        client_name="Cliente",
        operation_date=date(2026, 1, 2),
        operation_amount=Decimal("10000.00"),
        allocated_amount=allocated,
        operation_percentage=allocated / Decimal("100"),
        returned_principal=returned_amount,
        exposed_capital=max(allocated - returned_amount, Decimal("0.00")),
        allocation_status=status,
        funding_status="COMPLETE",
    )


@pytest.mark.parametrize(
    ("operations", "allocated", "exposed", "utilization"),
    [
        ([], "0.00", "0.00", "0.0000"),
        ([operation("4000.00")], "4000.00", "4000.00", "40.0000"),
        (
            [operation("4000.00", "1000.00"), operation("2500.00", sale_id="loan:40")],
            "6500.00",
            "5500.00",
            "55.0000",
        ),
    ],
)
def test_no_one_and_multiple_allocations_derive_exposure_and_utilization(
    operations, allocated, exposed, utilization
) -> None:
    result = analysis_amounts(Decimal("10000.00"), [], operations, {})
    assert result.allocated_capital == Decimal(allocated)
    assert result.exposed_capital == Decimal(exposed)
    assert result.utilization_percentage == Decimal(utilization)


def test_reversed_allocation_is_not_active_capital() -> None:
    result = analysis_amounts(
        Decimal("10000.00"),
        [],
        [operation("4000.00"), operation("3000.00", status="REVERSED")],
        {},
    )
    assert result.allocated_capital == Decimal("4000.00")
    assert result.exposed_capital == Decimal("4000.00")


def test_principal_return_and_its_reversal_are_not_double_counted() -> None:
    active_item = uuid4()
    reversed_item = uuid4()
    entries = [
        ledger_entry(1, "CONTRIBUTION", "10000.00", 1, date(2026, 1, 1)),
        ledger_entry(2, "PRINCIPAL_RETURN", "1000.00", 1, date(2026, 2, 1), item_id=active_item),
        ledger_entry(3, "PRINCIPAL_RETURN", "500.00", 1, date(2026, 2, 2), item_id=reversed_item),
        ledger_entry(4, "REVERSAL", "500.00", -1, date(2026, 2, 2), reversal_of=3),
    ]
    valid = valid_principal_returns(entries)
    result = analysis_amounts(Decimal("10000.00"), entries, [], valid)
    assert valid == {active_item: Decimal("1000.00")}
    assert result.returned_principal == Decimal("1000.00")
    assert result.available_balance == Decimal("11000.00")


def test_interest_is_economic_and_does_not_increase_available_balance() -> None:
    item_id = uuid4()
    entries = [
        ledger_entry(1, "CONTRIBUTION", "10000.00", 1, date(2026, 1, 1)),
        ledger_entry(2, "ALLOCATION", "4000.00", -1, date(2026, 1, 2)),
        ledger_entry(3, "PRINCIPAL_RETURN", "1000.00", 1, date(2026, 2, 1), item_id=item_id),
    ]
    result = analysis_amounts(
        Decimal("10000.00"),
        entries,
        [operation("4000.00", "1000.00")],
        {item_id: Decimal("1000.00")},
    )
    assert result.available_balance == Decimal("7000.00")
    assert result.returned_principal == Decimal("1000.00")


def test_ledger_running_balance_uses_effective_date_then_id_order() -> None:
    entries = [
        ledger_entry(1, "CONTRIBUTION", "10000.00", 1, date(2026, 1, 1)),
        ledger_entry(2, "ALLOCATION", "4000.00", -1, date(2026, 1, 2)),
        ledger_entry(3, "PRINCIPAL_RETURN", "750.00", 1, date(2026, 1, 2), item_id=uuid4()),
    ]
    movements = ContributionAnalysisRepository._movement_responses(entries)
    assert [item.running_balance for item in movements] == [
        Decimal("10000.00"), Decimal("6000.00"), Decimal("6750.00")
    ]


@pytest.mark.parametrize(
    ("sale_id", "kind", "loan_id"),
    [("contract:10", "CONTRACT", None), ("loan:40", "ORPHAN_LOAN", 40)],
)
def test_normal_contract_and_orphan_loan_keep_sale_identity(sale_id, kind, loan_id) -> None:
    allocation = FundingAllocation(
        id=uuid4(), sale_id=sale_id, source_id=SOURCE_ID, amount=Decimal("4000.00"),
        effective_date=date(2026, 1, 2), status="ACTIVE", actor="Teste", created_at=NOW,
    )
    identity = OperationIdentity(
        kind, "CTR-10" if loan_id is None else None, loan_id, "Cliente",
        date(2026, 1, 2), Decimal("10000.00"),
    )
    response = ContributionAnalysisRepository._operation_response(
        allocation, identity, Decimal("10000.00"), Decimal("1000.00")
    )
    assert response.sale_id == sale_id
    assert response.sale_kind == kind
    assert response.loan_id == loan_id
    assert response.operation_percentage == Decimal("40.0000")
    assert response.exposed_capital == Decimal("3000.00")
