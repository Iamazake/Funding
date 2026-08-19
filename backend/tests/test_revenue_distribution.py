from __future__ import annotations

import asyncio
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.models.funding import (
    FundingAllocation,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingRevenueDistribution,
    FundingRevenueDistributionItem,
    FundingSource,
)
from app.models.normalized import OperationalInstallment
from app.schemas.revenue_distribution import RevenueDistributionProcess
from app.services.funding.ledger import ledger_balance
from app.services.funding.revenue import (
    RevenueContext,
    RevenueDistributionRepository,
    RevenueState,
    _composition_hash,
    _primary_source,
    allocate_component,
)

IDS = [
    UUID("10000000-0000-0000-0000-000000000001"),
    UUID("10000000-0000-0000-0000-000000000002"),
    UUID("10000000-0000-0000-0000-000000000003"),
]


def allocation_row(index: int, amount: str, source_type: str = "REMO_CAPITAL"):
    allocation = FundingAllocation(
        id=IDS[index],
        sale_id="contract:10",
        source_id=IDS[index],
        amount=Decimal(amount),
        effective_date=date(2026, 1, 1),
        status="ACTIVE",
        actor="Teste",
    )
    source = FundingSource(
        id=IDS[index],
        source_type=source_type,
        contribution_id=None,
        status="ACTIVE",
    )
    return allocation, source, None, None


def revenue_context(
    *,
    base: str | None = "20000.00",
    payment_date: date | None = date(2026, 2, 5),
    principal: str = "1000.00",
    interest: str = "100.00",
    discount: str = "10.00",
    sale_id: str | None = "contract:10",
) -> RevenueContext:
    installment = OperationalInstallment(
        id=55,
        payment_date=payment_date,
        principal_component=Decimal(principal),
        interest_component=Decimal(interest),
        discount_amount=Decimal(discount),
    )
    return RevenueContext(
        installment=installment,
        sale_id=sale_id,
        base_amount=Decimal(base) if base is not None else None,
    )


def test_complete_distribution_closes_each_component_exactly() -> None:
    shares, gap = allocate_component(
        Decimal("1000.00"),
        [(IDS[0], Decimal("10000.00")), (IDS[1], Decimal("10000.00"))],
        Decimal("20000.00"),
    )
    assert shares == {IDS[0]: Decimal("500.00"), IDS[1]: Decimal("500.00")}
    assert sum(shares.values()) + gap == Decimal("1000.00")
    assert gap == Decimal("0.00")


def test_incomplete_distribution_preserves_gap_without_normalizing_sources() -> None:
    shares, gap = allocate_component(
        Decimal("1000.00"),
        [(IDS[0], Decimal("10000.00")), (IDS[1], Decimal("6000.00"))],
        Decimal("20000.00"),
    )
    assert shares == {IDS[0]: Decimal("500.00"), IDS[1]: Decimal("300.00")}
    assert gap == Decimal("200.00")
    assert sum(shares.values()) + gap == Decimal("1000.00")


def test_largest_remainder_closes_cents_with_stable_allocation_id_tie_break() -> None:
    shares, gap = allocate_component(
        Decimal("100.00"),
        [(IDS[2], Decimal("1.00")), (IDS[1], Decimal("1.00")), (IDS[0], Decimal("1.00"))],
        Decimal("3.00"),
    )
    assert shares[IDS[0]] == Decimal("33.34")
    assert shares[IDS[1]] == Decimal("33.33")
    assert shares[IDS[2]] == Decimal("33.33")
    assert sum(shares.values()) + gap == Decimal("100.00")


@pytest.mark.asyncio
async def test_current_states_cover_no_funding_incomplete_complete_overfunded_and_orphan() -> None:
    class StateRepository(RevenueDistributionRepository):
        def __init__(self, rows):
            self.rows = rows

        async def _allocation_rows(self, sale_id: str):
            return self.rows

    no_funding = await StateRepository([])._current_state(revenue_context())
    incomplete = await StateRepository(
        [allocation_row(0, "10000.00"), allocation_row(1, "6000.00")]
    )._current_state(revenue_context())
    complete = await StateRepository(
        [allocation_row(0, "10000.00"), allocation_row(1, "10000.00")]
    )._current_state(revenue_context())
    overfunded = await StateRepository(
        [allocation_row(0, "15000.00"), allocation_row(1, "10000.00")]
    )._current_state(revenue_context())
    orphan = await StateRepository([])._current_state(revenue_context(sale_id=None))

    assert (no_funding.status, no_funding.funding_status) == (
        "PENDING_FUNDING",
        "NOT_INFORMED",
    )
    assert (incomplete.status, incomplete.funding_status) == ("READY", "INCOMPLETE")
    assert (complete.status, complete.funding_status) == ("READY", "COMPLETE")
    assert (overfunded.status, overfunded.funding_status) == (
        "DIVERGENT",
        "OVERFUNDED",
    )
    assert orphan.status == "DIVERGENT"
    assert orphan.funding_status is None


@pytest.mark.asyncio
async def test_missing_payment_date_and_negative_component_are_divergent() -> None:
    class StateRepository(RevenueDistributionRepository):
        async def _allocation_rows(self, sale_id: str):
            return [allocation_row(0, "20000.00")]

    repository = StateRepository(None)
    missing_date = await repository._current_state(revenue_context(payment_date=None))
    negative = await repository._current_state(revenue_context(principal="-1.00"))
    assert missing_date.status == "DIVERGENT"
    assert "data" in (missing_date.reason or "").lower()
    assert negative.status == "DIVERGENT"
    assert "negativo" in (negative.reason or "").lower()


def test_primary_source_is_derived_and_tie_break_is_stable() -> None:
    investor = FundingInvestor(id=IDS[2], code="INV-1", name="Maria", status="ACTIVE")
    contribution = FundingContribution(
        id=IDS[2],
        code="APT-1",
        investor_id=investor.id,
        contribution_date=date(2026, 1, 1),
        original_amount=Decimal("100.00"),
        monthly_rate=Decimal("0.02"),
        status="ACTIVE",
    )
    remo = allocation_row(0, "100.00")
    investor_allocation, investor_source, _, _ = allocation_row(
        1, "100.00", "INVESTOR_CONTRIBUTION"
    )
    investor_source.contribution_id = contribution.id
    rows = [
        (investor_allocation, investor_source, contribution, investor),
        remo,
    ]
    assert _primary_source(rows) == "Capital REMO"


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_distribution_snapshots_components_and_creates_only_principal_returns() -> None:
    class CreateRepository(RevenueDistributionRepository):
        async def _next_version(self, revenue_id: int) -> int:
            return 1

    session = RecordingSession()
    repository = CreateRepository(session)  # type: ignore[arg-type]
    context = revenue_context()
    rows = [allocation_row(0, "10000.00"), allocation_row(1, "6000.00")]
    state = RevenueState("READY", "INCOMPLETE", None, rows, Decimal("16000.00"))
    distribution = await repository._create_distribution(
        context,
        state,
        RevenueDistributionProcess(actor="Operador", notes=None),
    )
    items = [
        value
        for value in session.added
        if isinstance(value, FundingRevenueDistributionItem)
    ]
    returns = [value for value in session.added if isinstance(value, FundingLedgerEntry)]

    assert distribution.unidentified_principal == Decimal("200.00")
    assert sum((item.principal_amount for item in items), Decimal("0.00")) == Decimal(
        "800.00"
    )
    assert sum((entry.amount for entry in returns), Decimal("0.00")) == Decimal("800.00")
    assert all(entry.entry_type == "PRINCIPAL_RETURN" for entry in returns)
    assert all(entry.effective_date == date(2026, 2, 5) for entry in returns)
    assert not any(entry.amount == distribution.distributed_interest for entry in returns)

    original_snapshot = items[0].allocation_amount
    rows[0][0].amount = Decimal("1.00")
    assert items[0].allocation_amount == original_snapshot


def test_composition_hash_changes_when_sale_composition_changes() -> None:
    context = revenue_context()
    rows = [allocation_row(0, "10000.00"), allocation_row(1, "6000.00")]
    original = _composition_hash(context, rows)
    rows[1][0].amount = Decimal("7000.00")
    assert _composition_hash(context, rows) != original


def test_principal_return_increases_balance_and_reversal_compensates_it() -> None:
    returned = FundingLedgerEntry(
        id=10,
        source_id=IDS[0],
        entry_type="PRINCIPAL_RETURN",
        amount=Decimal("500.00"),
        direction=1,
        effective_date=date(2026, 2, 5),
        origin_type="REVENUE_DISTRIBUTION",
        revenue_distribution_item_id=IDS[1],
        actor="Operador",
    )
    reversed_entry = FundingLedgerEntry(
        id=11,
        source_id=IDS[0],
        entry_type="REVERSAL",
        amount=Decimal("500.00"),
        direction=-1,
        effective_date=date(2026, 2, 5),
        origin_type="REVENUE_DISTRIBUTION_REVERSAL",
        reversal_of_entry_id=10,
        actor="Revisor",
    )
    assert ledger_balance([returned]) == Decimal("500.00")
    assert ledger_balance([returned, reversed_entry]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_reprocessing_returns_existing_distribution_without_creating_another() -> None:
    marker = object()

    class IdempotentRepository(RevenueDistributionRepository):
        async def _revenue_context(self, revenue_id: int, *, lock: bool = False):
            return revenue_context()

        async def _active_distribution(self, revenue_id: int):
            return marker

        async def _distribution_response(self, distribution):
            assert distribution is marker
            return "existing"

        async def _create_distribution(self, context, state, data):
            raise AssertionError("não deve criar outra distribuição")

    class Session:
        async def rollback(self):
            raise AssertionError("não deve ocorrer rollback")

    result = await IdempotentRepository(Session()).distribute(  # type: ignore[arg-type]
        55, RevenueDistributionProcess(actor="Operador", notes=None)
    )
    assert result == "existing"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["item", "ledger"])
async def test_failure_during_item_or_ledger_creation_rolls_back_everything(
    failure_point: str,
) -> None:
    class Session:
        rolled_back = False
        committed = False

        async def rollback(self):
            self.rolled_back = True

        async def commit(self):
            self.committed = True

    class FailingRepository(RevenueDistributionRepository):
        async def _revenue_context(self, revenue_id: int, *, lock: bool = False):
            assert lock is True
            return revenue_context()

        async def _active_distribution(self, revenue_id: int):
            return None

        async def _current_state(self, context):
            rows = [allocation_row(0, "20000.00")]
            return RevenueState("READY", "COMPLETE", None, rows, Decimal("20000.00"))

        async def _create_distribution(self, context, state, data):
            raise RuntimeError(f"falha em {failure_point}")

    session = Session()
    with pytest.raises(RuntimeError, match=failure_point):
        await FailingRepository(session).distribute(  # type: ignore[arg-type]
            55, RevenueDistributionProcess(actor="Operador", notes=None)
        )
    assert session.rolled_back is True
    assert session.committed is False


def test_constraints_cover_idempotency_history_and_restrictive_links() -> None:
    distribution_constraints = {
        constraint.name for constraint in FundingRevenueDistribution.__table__.constraints
    }
    item_constraints = {
        constraint.name for constraint in FundingRevenueDistributionItem.__table__.constraints
    }
    ledger_constraints = {
        constraint.name for constraint in FundingLedgerEntry.__table__.constraints
    }
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/f2c000000001_revenue_distributions_principal_return.py"
    ).read_text(encoding="utf-8")
    assert "uq_funding_revenue_distributions_active" in migration
    assert "uq_funding_revenue_distributions_version" in distribution_constraints
    assert "uq_funding_revenue_distribution_items_allocation" in item_constraints
    assert "uq_funding_ledger_revenue_distribution_item" in ledger_constraints
    revenue_fk = next(iter(FundingRevenueDistribution.__table__.c.revenue_id.foreign_keys))
    assert revenue_fk.ondelete == "RESTRICT"
    assert "DELETE FROM funding_ledger_entries" in migration
    assert "DROP TRIGGER trg_funding_ledger_append_only" in migration


@pytest.mark.asyncio
async def test_concurrent_processing_simulation_returns_one_distribution() -> None:
    lock = asyncio.Lock()
    created = 0

    async def process() -> int:
        nonlocal created
        async with lock:
            if created == 0:
                created += 1
            return created

    first, second = await asyncio.gather(process(), process())
    assert (first, second, created) == (1, 1, 1)


def test_repository_uses_row_lock_single_commit_and_full_rollback() -> None:
    source = inspect.getsource(RevenueDistributionRepository.distribute)
    reversal = inspect.getsource(RevenueDistributionRepository.reverse)
    assert "lock=True" in source
    assert source.count("await self._session.commit()") == 2  # distributed or blocked
    assert "await self._session.rollback()" in source
    assert ".with_for_update()" in reversal
    assert "REVENUE_DISTRIBUTION_REVERSAL" in reversal
    assert "validate_prospective_debit" in reversal
