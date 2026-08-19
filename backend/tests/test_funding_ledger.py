from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.models.funding import (
    FundingAllocation,
    FundingAuditEvent,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingSource,
)
from app.models.normalized import OperationalContract, OperationalLoan
from app.schemas.funding import ContributionCreate
from app.services.funding.ledger import (
    FundingLedgerRepository,
    funding_status,
    ledger_balance,
    validate_prospective_debit,
)
from app.services.funding.repository import FundingConflictError, FundingRepository
from app.services.funding.sales import FundingSale, resolve_funding_sale

INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


def ledger_entry(
    effective_date: date, amount: str, direction: int, entry_id: int
) -> FundingLedgerEntry:
    return FundingLedgerEntry(
        id=entry_id,
        source_id=uuid4(),
        entry_type="ADJUSTMENT",
        amount=Decimal(amount),
        direction=direction,
        effective_date=effective_date,
        origin_type="REMO_ADMIN",
        actor="Teste",
        notes="Teste de linha do tempo",
        created_at=NOW,
    )


def timeline() -> list[FundingLedgerEntry]:
    return [
        ledger_entry(date(2026, 1, 1), "100000.00", 1, 1),
        ledger_entry(date(2026, 1, 15), "20000.00", -1, 2),
        ledger_entry(date(2026, 1, 20), "30000.00", -1, 3),
    ]


def test_current_and_historical_balance_use_effective_date() -> None:
    entries = timeline()
    assert ledger_balance(entries, date(2026, 1, 18)) == Decimal("80000.00")
    assert ledger_balance(entries) == Decimal("50000.00")


def test_reversal_restores_balance_without_mutating_original() -> None:
    original = ledger_entry(date(2026, 1, 15), "20000.00", -1, 2)
    reversal = ledger_entry(date(2026, 1, 15), "20000.00", 1, 3)
    reversal.entry_type = "REVERSAL"
    reversal.reversal_of_entry_id = original.id
    assert ledger_balance([ledger_entry(date(2026, 1, 1), "100000.00", 1, 1), original]) == Decimal(
        "80000.00"
    )
    assert ledger_balance(
        [ledger_entry(date(2026, 1, 1), "100000.00", 1, 1), original, reversal]
    ) == Decimal("100000.00")
    assert original.direction == -1


def test_valid_and_invalid_retroactive_debits() -> None:
    entries = [
        ledger_entry(date(2026, 1, 1), "100000.00", 1, 1),
        ledger_entry(date(2026, 1, 20), "70000.00", -1, 2),
    ]
    validate_prospective_debit(entries, date(2026, 1, 15), Decimal("30000.00"))
    with pytest.raises(FundingConflictError, match="saldo futuro negativo"):
        validate_prospective_debit(entries, date(2026, 1, 15), Decimal("50000.00"))


def test_allocation_above_historical_balance_fails() -> None:
    with pytest.raises(FundingConflictError, match="Saldo histórico insuficiente"):
        validate_prospective_debit(timeline(), date(2026, 1, 18), Decimal("80000.01"))


async def test_development_override_uses_current_balance_for_investor_source() -> None:
    source = FundingSource(
        id=uuid4(),
        source_type="INVESTOR_CONTRIBUTION",
        contribution_id=uuid4(),
        status="ACTIVE",
    )

    class Repository(FundingLedgerRepository):
        async def _balance(self, source_id, as_of):
            assert source_id == source.id
            assert as_of is None
            return Decimal("100000.00")

        async def _validate_debit(self, source_id, effective_date, amount):
            raise AssertionError("A validação histórica não deve ser usada no override de teste.")

    repository = Repository(  # type: ignore[arg-type]
        None,
        allow_historical_allocation_for_tests=True,
    )
    await repository._validate_allocation_debit(
        source,
        date(2026, 6, 1),
        Decimal("25000.00"),
    )
    with pytest.raises(FundingConflictError, match="Saldo atual insuficiente"):
        await repository._validate_allocation_debit(
            source,
            date(2026, 6, 1),
            Decimal("100000.01"),
        )


async def test_production_keeps_historical_validation_for_investor_source() -> None:
    source = FundingSource(
        id=uuid4(),
        source_type="INVESTOR_CONTRIBUTION",
        contribution_id=uuid4(),
        status="ACTIVE",
    )
    calls: list[tuple[UUID, date, Decimal]] = []

    class Repository(FundingLedgerRepository):
        async def _validate_debit(self, source_id, effective_date, amount):
            calls.append((source_id, effective_date, amount))

    repository = Repository(  # type: ignore[arg-type]
        None,
        allow_historical_allocation_for_tests=False,
    )
    await repository._validate_allocation_debit(
        source,
        date(2026, 6, 1),
        Decimal("25000.00"),
    )
    assert calls == [(source.id, date(2026, 6, 1), Decimal("25000.00"))]


@pytest.mark.parametrize(
    ("base", "identified", "has_allocations", "expected"),
    [
        (Decimal("20000"), Decimal("0"), False, "NOT_INFORMED"),
        (Decimal("20000"), Decimal("17000"), True, "INCOMPLETE"),
        (Decimal("20000"), Decimal("20000"), True, "COMPLETE"),
        (Decimal("20000"), Decimal("21000"), True, "OVERFUNDED"),
        (None, Decimal("100"), True, "BASE_AMOUNT_UNAVAILABLE"),
    ],
)
def test_sale_funding_statuses(base, identified, has_allocations, expected) -> None:
    assert funding_status(base, identified, has_allocations)[0] == expected


def test_multiple_sources_and_percentage_are_derived_from_amount() -> None:
    remo = FundingSource(
        id=uuid4(),
        source_type="REMO_CAPITAL",
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    contribution_id = uuid4()
    contribution_source = FundingSource(
        id=uuid4(),
        source_type="INVESTOR_CONTRIBUTION",
        contribution_id=contribution_id,
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    contribution = FundingContribution(
        id=contribution_id,
        code="APT-TESTE",
        investor_id=INVESTOR_ID,
        contribution_date=date(2026, 1, 1),
        original_amount=Decimal("10000.00"),
        monthly_rate=Decimal("0.02"),
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    investor = FundingInvestor(
        id=INVESTOR_ID,
        code="INV-TESTE",
        name="Investidor Teste",
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    allocations = [
        FundingAllocation(
            id=uuid4(),
            sale_id="contract:10",
            source_id=remo.id,
            amount=Decimal("5000.00"),
            effective_date=date(2026, 1, 2),
            status="ACTIVE",
            actor="Teste",
            created_at=NOW,
        ),
        FundingAllocation(
            id=uuid4(),
            sale_id="contract:10",
            source_id=contribution_source.id,
            amount=Decimal("2500.00"),
            effective_date=date(2026, 1, 2),
            status="ACTIVE",
            actor="Teste",
            created_at=NOW,
        ),
    ]
    rows = [
        (allocations[0], remo, None, None),
        (allocations[1], contribution_source, contribution, investor),
    ]
    repository = FundingLedgerRepository(None)  # type: ignore[arg-type]
    result = repository._composition_response(
        FundingSale("contract:10", date(2026, 1, 2), Decimal("10000.00")), rows
    )
    assert result.funding_status == "INCOMPLETE"
    assert result.source_count == 2
    assert result.identified_amount == Decimal("7500.00")
    assert [item.percentage for item in result.allocations] == [
        Decimal("50.0000"),
        Decimal("25.0000"),
    ]


def test_source_constraints_keep_remo_separate_from_investors() -> None:
    source_sql = " ".join(
        str(constraint.sqltext)
        for constraint in FundingSource.__table__.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "REMO_CAPITAL" in source_sql
    assert "contribution_id IS NULL" in source_sql
    assert not hasattr(FundingSource, "investor_id")
    assert FundingSource.__table__.c.contribution_id.unique is None


def test_idempotency_and_append_only_constraints_exist() -> None:
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in FundingLedgerEntry.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("contribution_id",) in unique_columns
    assert ("allocation_id",) in unique_columns
    assert ("reversal_of_entry_id",) in unique_columns
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "f2b000000001_funding_sources_ledger_allocations.py"
    )
    assert "prevent_funding_ledger_mutation" in migration.read_text(encoding="utf-8")


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.events: list[tuple[str, str | None]] = []

    async def get(self, model, entity_id):
        if model is FundingInvestor and entity_id == INVESTOR_ID:
            return FundingInvestor(
                id=INVESTOR_ID,
                code="INV-TESTE",
                name="Investidor Teste",
                status="ACTIVE",
                created_at=NOW,
                updated_at=NOW,
            )
        return None

    def add(self, item) -> None:
        self.added.append(item)
        self.events.append(("add", type(item).__name__))

    def add_all(self, items) -> None:
        self.added.extend(items)

    async def flush(self) -> None:
        self.events.append(("flush", None))

    async def commit(self) -> None:
        for item in self.added:
            if hasattr(item, "created_at") and item.created_at is None:
                item.created_at = NOW
            if hasattr(item, "updated_at") and item.updated_at is None:
                item.updated_at = NOW

    async def refresh(self, _item) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def test_contribution_creates_one_source_one_entry_and_locks_amount() -> None:
    session = RecordingSession()
    repository = FundingRepository(session)  # type: ignore[arg-type]
    response = await repository.create_contribution(
        ContributionCreate(
            investor_id=INVESTOR_ID,
            contribution_date=date(2026, 1, 1),
            original_amount=Decimal("100000.00"),
            monthly_rate=Decimal("0.02"),
            status="ACTIVE",
        )
    )
    sources = [item for item in session.added if isinstance(item, FundingSource)]
    entries = [item for item in session.added if isinstance(item, FundingLedgerEntry)]
    contributions = [item for item in session.added if isinstance(item, FundingContribution)]
    assert len(sources) == len(entries) == len(contributions) == 1
    assert entries[0].entry_type == "CONTRIBUTION"
    assert entries[0].amount == Decimal("100000.00")
    assert contributions[0].original_amount_locked_at is not None
    assert response.original_amount_editable is False
    assert session.events[:5] == [
        ("add", "FundingContribution"),
        ("flush", None),
        ("add", "FundingSource"),
        ("flush", None),
        ("add", "FundingLedgerEntry"),
    ]
    assert any(
        isinstance(item, FundingAuditEvent) and item.entity_type == "SOURCE"
        for item in session.added
    )


class InspectLockSession:
    def __init__(self, source: FundingSource) -> None:
        self.source = source
        self.statement = None

    async def scalar(self, statement):
        self.statement = statement
        return self.source


async def test_source_lock_uses_postgresql_for_update() -> None:
    source = FundingSource(id=uuid4(), source_type="REMO_CAPITAL", status="ACTIVE")
    session = InspectLockSession(source)
    repository = FundingLedgerRepository(session)  # type: ignore[arg-type]
    assert await repository._locked_source(source.id) is source
    compiled = str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in compiled


class SaleResolverSession:
    def __init__(self, entity) -> None:
        self.results = [1, entity]

    async def scalar(self, _statement):
        return self.results.pop(0)


@pytest.mark.parametrize(
    ("sale_id", "entity_type"),
    [("contract:10", OperationalContract), ("loan:40", OperationalLoan)],
)
async def test_contract_and_orphan_loan_use_stable_api_identity(sale_id, entity_type) -> None:
    values = {
        "id": int(sale_id.split(":")[1]),
        "promotion_id": 1,
        "operation_date": date(2026, 1, 2),
        "released_amount": Decimal("1000.00"),
    }
    if entity_type is OperationalLoan:
        values["contract_id"] = None
    entity = entity_type(**values)
    session = SaleResolverSession(entity)
    sale = await resolve_funding_sale(session, sale_id)  # type: ignore[arg-type]
    assert sale.sale_id == sale_id
    assert sale.released_amount == Decimal("1000.00")


async def test_two_concurrent_allocations_cannot_spend_same_balance() -> None:
    entries = [ledger_entry(date(2026, 1, 1), "10000.00", 1, 1)]
    lock = asyncio.Lock()

    async def allocate(entry_id: int):
        async with lock:
            validate_prospective_debit(entries, date(2026, 1, 2), Decimal("8000.00"))
            await asyncio.sleep(0)
            entries.append(ledger_entry(date(2026, 1, 2), "8000.00", -1, entry_id))

    results = await asyncio.gather(allocate(2), allocate(3), return_exceptions=True)
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, FundingConflictError) for result in results) == 1
    assert ledger_balance(entries) == Decimal("2000.00")


def test_allocation_transaction_has_single_commit_and_rollback_guard() -> None:
    source = inspect.getsource(FundingLedgerRepository.create_allocation)
    assert source.count("await self._session.commit()") == 1
    assert "self._session.add(allocation)" in source
    assert "self._session.add(entry)" in source
    assert "await self._session.rollback()" in source
    assert FundingAllocation.__table__.c.amount.type.scale == 2
