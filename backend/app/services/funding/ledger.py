from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.debt import OperationalDebtFundingContinuity
from app.models.funding import (
    FundingAllocation,
    FundingAuditEvent,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingSource,
)
from app.models.operational import utc_now
from app.schemas.funding_ledger import (
    AllocationCreate,
    AllocationResponse,
    AllocationReverse,
    FundingSourceResponse,
    LedgerEntryResponse,
    RemoCapitalEntryCreate,
    SaleCompositionResponse,
    SourceBalanceResponse,
)
from app.services.funding.repository import FundingConflictError, FundingNotFoundError
from app.services.funding.sales import FundingSale, resolve_funding_sale

ZERO = Decimal("0.00")
PERCENT_QUANTUM = Decimal("0.0001")


class FundingLedgerRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        allow_historical_allocation_for_tests: bool | None = None,
        actor_user_id: UUID | None = None,
        actor_label: str | None = None,
    ) -> None:
        self._session = session
        self._actor_user_id = actor_user_id
        self._actor_label = actor_label
        self._allow_historical_allocation_for_tests = (
            get_settings().allow_historical_allocation_for_tests
            if allow_historical_allocation_for_tests is None
            else allow_historical_allocation_for_tests
        )

    async def list_sources(self) -> list[FundingSourceResponse]:
        rows = await self._source_rows()
        balances = await self._balances([source.id for source, _, _ in rows])
        return [
            self._source_response(source, contribution, investor, balances.get(source.id, ZERO))
            for source, contribution, investor in rows
        ]

    async def get_source(self, source_id: UUID) -> FundingSourceResponse:
        row = await self._source_row(source_id)
        return self._source_response(*row, await self._balance(source_id, None))

    async def list_ledger(self, source_id: UUID) -> list[LedgerEntryResponse]:
        await self._require_source(source_id)
        entries = await self._session.scalars(
            select(FundingLedgerEntry)
            .where(FundingLedgerEntry.source_id == source_id)
            .order_by(
                FundingLedgerEntry.effective_date,
                FundingLedgerEntry.id,
            )
        )
        return [self._ledger_response(entry) for entry in entries]

    async def get_balance(self, source_id: UUID, as_of: date | None) -> SourceBalanceResponse:
        await self._require_source(source_id)
        return SourceBalanceResponse(
            source_id=source_id,
            as_of=as_of,
            balance=await self._balance(source_id, as_of),
        )

    async def register_remo_capital(self, data: RemoCapitalEntryCreate) -> LedgerEntryResponse:
        if self._actor_label is not None:
            data = data.model_copy(update={"actor": self._actor_label})
        try:
            source = await self._locked_remo_source()
            direction = 1 if data.direction == "CREDIT" else -1
            if direction < 0:
                await self._validate_debit(source.id, data.effective_date, data.amount)
            entry = FundingLedgerEntry(
                source_id=source.id,
                entry_type="ADJUSTMENT",
                amount=data.amount,
                direction=direction,
                effective_date=data.effective_date,
                origin_type="REMO_ADMIN",
                actor=data.actor,
                notes=data.notes,
            )
            self._session.add(entry)
            await self._session.flush()
            self._audit(
                "SOURCE",
                source.id,
                "REMO_CAPITAL_REGISTERED",
                {
                    "ledger_entry_id": entry.id,
                    "amount": format(data.amount, "f"),
                    "direction": data.direction,
                    "effective_date": data.effective_date.isoformat(),
                },
            )
            await self._session.commit()
            await self._session.refresh(entry)
            return self._ledger_response(entry)
        except Exception:
            await self._session.rollback()
            raise

    async def get_composition(self, sale_id: str) -> SaleCompositionResponse:
        sale = await resolve_funding_sale(self._session, sale_id)
        rows = await self._allocation_rows(sale)
        return self._composition_response(sale, rows)

    async def create_allocation(
        self, sale_id: str, data: AllocationCreate
    ) -> SaleCompositionResponse:
        if self._actor_label is not None:
            data = data.model_copy(update={"actor": self._actor_label})
        try:
            sale = await resolve_funding_sale(self._session, sale_id)
            if not sale.has_new_disbursement:
                raise FundingConflictError(
                    "Venda sucessora sem nova liberação herda o Funding; nova allocation bloqueada."
                )
            source = await self._locked_source(data.source_id)
            if source.status != "ACTIVE":
                raise FundingConflictError("A fonte de Funding está inativa.")
            duplicate = await self._session.scalar(
                select(FundingAllocation.id).where(
                    FundingAllocation.sale_id == sale.sale_id,
                    FundingAllocation.source_id == source.id,
                    FundingAllocation.status == "ACTIVE",
                )
            )
            if duplicate is not None:
                raise FundingConflictError("A fonte já está ativa na composição desta Venda.")
            await self._validate_allocation_debit(
                source,
                sale.operation_date,
                data.amount,
            )

            allocation = FundingAllocation(
                id=uuid4(),
                sale_id=sale.sale_id,
                sale_identity_id=sale.sale_identity_id,
                source_id=source.id,
                amount=data.amount,
                effective_date=sale.operation_date,
                status="ACTIVE",
                actor=data.actor,
                notes=data.notes,
            )
            self._session.add(allocation)
            await self._session.flush()
            entry = FundingLedgerEntry(
                source_id=source.id,
                entry_type="ALLOCATION",
                amount=data.amount,
                direction=-1,
                effective_date=sale.operation_date,
                origin_type="SALE_ALLOCATION",
                allocation_id=allocation.id,
                actor=data.actor,
                notes=data.notes,
            )
            self._session.add(entry)
            await self._session.flush()
            self._audit(
                "ALLOCATION",
                allocation.id,
                "CREATED",
                {
                    "sale_id": sale.sale_id,
                    "source_id": str(source.id),
                    "amount": format(data.amount, "f"),
                    "ledger_entry_id": entry.id,
                    "effective_date": sale.operation_date.isoformat(),
                    "balance_validation": (
                        "CURRENT_BALANCE_DEVELOPMENT_OVERRIDE"
                        if self._uses_current_balance_override(source)
                        else "HISTORICAL_BALANCE"
                    ),
                },
            )
            await self._session.commit()
            return await self.get_composition(sale.sale_id)
        except Exception:
            await self._session.rollback()
            raise

    async def reverse_allocation(
        self, allocation_id: UUID, data: AllocationReverse
    ) -> SaleCompositionResponse:
        if self._actor_label is not None:
            data = data.model_copy(update={"actor": self._actor_label})
        try:
            initial = await self._session.get(FundingAllocation, allocation_id)
            if initial is None:
                raise FundingNotFoundError("Alocação não encontrada.")
            await self._locked_source(initial.source_id)
            allocation = await self._session.scalar(
                select(FundingAllocation)
                .where(FundingAllocation.id == allocation_id)
                .with_for_update()
            )
            if allocation is None:
                raise FundingNotFoundError("Alocação não encontrada.")
            if allocation.status == "REVERSED":
                raise FundingConflictError("A alocação já foi revertida.")
            original_entry = await self._session.scalar(
                select(FundingLedgerEntry).where(
                    FundingLedgerEntry.allocation_id == allocation.id,
                    FundingLedgerEntry.entry_type == "ALLOCATION",
                )
            )
            if original_entry is None:
                raise FundingConflictError("Alocação sem lançamento financeiro correspondente.")
            existing_reversal = await self._session.scalar(
                select(FundingLedgerEntry.id).where(
                    FundingLedgerEntry.reversal_of_entry_id == original_entry.id
                )
            )
            if existing_reversal is not None:
                raise FundingConflictError("A movimentação da alocação já foi revertida.")

            reversal = FundingLedgerEntry(
                source_id=allocation.source_id,
                entry_type="REVERSAL",
                amount=allocation.amount,
                direction=1,
                effective_date=allocation.effective_date,
                origin_type="ALLOCATION_REVERSAL",
                reversal_of_entry_id=original_entry.id,
                actor=data.actor,
                notes=data.reason,
            )
            self._session.add(reversal)
            allocation.status = "REVERSED"
            allocation.reversed_at = utc_now()
            await self._session.flush()
            self._audit(
                "ALLOCATION",
                allocation.id,
                "REVERSED",
                {
                    "reversal_ledger_entry_id": reversal.id,
                    "original_ledger_entry_id": original_entry.id,
                    "reason": data.reason,
                },
            )
            sale_id = allocation.sale_id
            await self._session.commit()
            return await self.get_composition(sale_id)
        except Exception:
            await self._session.rollback()
            raise

    async def _validate_debit(self, source_id: UUID, effective_date: date, amount: Decimal) -> None:
        entries = list(
            await self._session.scalars(
                select(FundingLedgerEntry)
                .where(FundingLedgerEntry.source_id == source_id)
                .order_by(FundingLedgerEntry.effective_date, FundingLedgerEntry.id)
            )
        )
        validate_prospective_debit(entries, effective_date, amount)

    async def _validate_allocation_debit(
        self,
        source: FundingSource,
        effective_date: date,
        amount: Decimal,
    ) -> None:
        if self._uses_current_balance_override(source):
            current_balance = await self._balance(source.id, None)
            if current_balance - amount < ZERO:
                raise FundingConflictError("Saldo atual insuficiente para a alocação de teste.")
            return
        await self._validate_debit(source.id, effective_date, amount)

    def _uses_current_balance_override(self, source: FundingSource) -> bool:
        return (
            self._allow_historical_allocation_for_tests
            and source.source_type == "INVESTOR_CONTRIBUTION"
        )

    async def _source_rows(self):
        return (
            await self._session.execute(
                select(FundingSource, FundingContribution, FundingInvestor)
                .outerjoin(
                    FundingContribution,
                    FundingContribution.id == FundingSource.contribution_id,
                )
                .outerjoin(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
                .order_by(FundingSource.source_type, FundingSource.created_at, FundingSource.id)
            )
        ).all()

    async def _source_row(self, source_id: UUID):
        row = (
            await self._session.execute(
                select(FundingSource, FundingContribution, FundingInvestor)
                .outerjoin(
                    FundingContribution,
                    FundingContribution.id == FundingSource.contribution_id,
                )
                .outerjoin(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
                .where(FundingSource.id == source_id)
            )
        ).one_or_none()
        if row is None:
            raise FundingNotFoundError("Fonte de Funding não encontrada.")
        return row

    async def _require_source(self, source_id: UUID) -> FundingSource:
        source = await self._session.get(FundingSource, source_id)
        if source is None:
            raise FundingNotFoundError("Fonte de Funding não encontrada.")
        return source

    async def _locked_source(self, source_id: UUID) -> FundingSource:
        source = await self._session.scalar(
            select(FundingSource).where(FundingSource.id == source_id).with_for_update()
        )
        if source is None:
            raise FundingNotFoundError("Fonte de Funding não encontrada.")
        return source

    async def _locked_remo_source(self) -> FundingSource:
        source = await self._session.scalar(
            select(FundingSource)
            .where(FundingSource.source_type == "REMO_CAPITAL")
            .with_for_update()
        )
        if source is None:
            raise FundingNotFoundError("Fonte de capital próprio REMO não encontrada.")
        return source

    async def _balance(self, source_id: UUID, as_of: date | None) -> Decimal:
        statement = select(
            func.coalesce(func.sum(FundingLedgerEntry.amount * FundingLedgerEntry.direction), ZERO)
        ).where(FundingLedgerEntry.source_id == source_id)
        if as_of is not None:
            statement = statement.where(FundingLedgerEntry.effective_date <= as_of)
        return Decimal(await self._session.scalar(statement) or ZERO)

    async def _balances(self, source_ids: list[UUID]) -> dict[UUID, Decimal]:
        if not source_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    FundingLedgerEntry.source_id,
                    func.sum(FundingLedgerEntry.amount * FundingLedgerEntry.direction),
                )
                .where(FundingLedgerEntry.source_id.in_(source_ids))
                .group_by(FundingLedgerEntry.source_id)
            )
        ).all()
        return {source_id: Decimal(balance) for source_id, balance in rows}

    async def _allocation_rows(self, sale: FundingSale):
        direct = (
            await self._session.execute(
                select(FundingAllocation, FundingSource, FundingContribution, FundingInvestor)
                .join(FundingSource, FundingSource.id == FundingAllocation.source_id)
                .outerjoin(
                    FundingContribution,
                    FundingContribution.id == FundingSource.contribution_id,
                )
                .outerjoin(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
                .where(FundingAllocation.sale_id == sale.sale_id)
                .order_by(FundingAllocation.effective_date, FundingAllocation.created_at)
            )
        ).all()
        if sale.funding_origin_sale_identity_id is None:
            return [(*row, None) for row in direct]
        inherited = (
            await self._session.execute(
                select(
                    OperationalDebtFundingContinuity,
                    FundingAllocation,
                    FundingSource,
                    FundingContribution,
                    FundingInvestor,
                )
                .join(
                    FundingAllocation,
                    FundingAllocation.id
                    == OperationalDebtFundingContinuity.origin_allocation_id,
                )
                .join(FundingSource, FundingSource.id == FundingAllocation.source_id)
                .outerjoin(
                    FundingContribution,
                    FundingContribution.id == FundingSource.contribution_id,
                )
                .outerjoin(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
                .where(
                    OperationalDebtFundingContinuity.successor_sale_identity_id
                    == sale.sale_identity_id
                )
                .order_by(OperationalDebtFundingContinuity.origin_allocation_id)
            )
        ).all()
        inherited_rows = [
            (allocation, source, contribution, investor, continuity.rolled_amount)
            for continuity, allocation, source, contribution, investor in inherited
        ]
        return [(*row, None) for row in direct] + inherited_rows

    def _composition_response(self, sale: FundingSale, rows) -> SaleCompositionResponse:
        active = [row for row in rows if row[0].status == "ACTIVE"]
        funding_active = (
            [row for row in active if len(row) < 5 or row[4] is None]
            if sale.has_new_disbursement
            else active
        )
        identified = sum(
            (_allocation_row_amount(row) for row in funding_active),
            start=ZERO,
        )
        status, difference = funding_status(
            sale.released_amount, identified, bool(funding_active)
        )
        allocations = [
            self._allocation_response(
                *row[:4],
                sale.released_amount,
                effective_amount=(row[4] if len(row) > 4 else None),
                response_sale_id=sale.sale_id,
                origin_sale_id=(
                    f"sale:{sale.funding_origin_sale_identity_id}"
                    if len(row) > 4
                    and row[4] is not None
                    and sale.funding_origin_sale_identity_id
                    else None
                ),
            )
            for row in rows
        ]
        return SaleCompositionResponse(
            sale_id=sale.sale_id,
            operation_date=sale.operation_date,
            operation_amount=sale.released_amount,
            identified_amount=identified,
            difference=difference,
            funding_status=status,
            source_count=len(funding_active),
            allocations=allocations,
            has_new_disbursement=sale.has_new_disbursement,
            funding_origin_sale_id=(
                f"sale:{sale.funding_origin_sale_identity_id}"
                if sale.funding_origin_sale_identity_id
                else None
            ),
        )

    @staticmethod
    def _source_response(
        source: FundingSource,
        contribution: FundingContribution | None,
        investor: FundingInvestor | None,
        balance: Decimal,
    ) -> FundingSourceResponse:
        return FundingSourceResponse(
            id=source.id,
            source_type=source.source_type,
            contribution_id=source.contribution_id,
            status=source.status,
            investor_id=investor.id if investor else None,
            investor_name=investor.name if investor else None,
            contribution_code=contribution.code if contribution else None,
            contribution_date=contribution.contribution_date if contribution else None,
            original_amount=contribution.original_amount if contribution else None,
            monthly_rate=contribution.monthly_rate if contribution else None,
            current_balance=balance,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    @staticmethod
    def _ledger_response(entry: FundingLedgerEntry) -> LedgerEntryResponse:
        return LedgerEntryResponse(
            id=entry.id,
            source_id=entry.source_id,
            entry_type=entry.entry_type,
            amount=entry.amount,
            direction=entry.direction,
            signed_amount=entry.amount * entry.direction,
            effective_date=entry.effective_date,
            origin_type=entry.origin_type,
            contribution_id=entry.contribution_id,
            allocation_id=entry.allocation_id,
            revenue_distribution_item_id=entry.revenue_distribution_item_id,
            reversal_of_entry_id=entry.reversal_of_entry_id,
            actor=entry.actor,
            notes=entry.notes,
            created_at=entry.created_at,
        )

    @staticmethod
    def _allocation_response(
        allocation: FundingAllocation,
        source: FundingSource,
        contribution: FundingContribution | None,
        investor: FundingInvestor | None,
        base_amount: Decimal | None,
        *,
        effective_amount: Decimal | None = None,
        response_sale_id: str | None = None,
        origin_sale_id: str | None = None,
    ) -> AllocationResponse:
        amount = effective_amount if effective_amount is not None else allocation.amount
        percentage = None
        if base_amount is not None and base_amount > ZERO:
            percentage = (amount * Decimal("100") / base_amount).quantize(
                PERCENT_QUANTUM, rounding=ROUND_HALF_UP
            )
        return AllocationResponse(
            id=allocation.id,
            sale_id=response_sale_id or allocation.sale_id,
            source_id=allocation.source_id,
            source_type=source.source_type,
            contribution_id=source.contribution_id,
            contribution_code=contribution.code if contribution else None,
            investor_id=investor.id if investor else None,
            investor_name=investor.name if investor else None,
            amount=amount,
            percentage=percentage,
            effective_date=allocation.effective_date,
            status=allocation.status,
            actor=allocation.actor,
            notes=allocation.notes,
            created_at=allocation.created_at,
            reversed_at=allocation.reversed_at,
            inherited_from_predecessor=effective_amount is not None,
            origin_sale_id=origin_sale_id,
        )

    def _audit(
        self, entity_type: str, entity_id: UUID, action: str, changes: dict[str, object]
    ) -> None:
        self._session.add(
            FundingAuditEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changes=changes,
                actor_user_id=self._actor_user_id,
            )
        )


def funding_status(
    base_amount: Decimal | None, identified: Decimal, has_allocations: bool
) -> tuple[str, Decimal | None]:
    if not has_allocations:
        return "NOT_INFORMED", base_amount
    if base_amount is None:
        return "BASE_AMOUNT_UNAVAILABLE", None
    difference = base_amount - identified
    if difference > ZERO:
        return "INCOMPLETE", difference
    if difference == ZERO:
        return "COMPLETE", ZERO
    return "OVERFUNDED", difference


def _allocation_row_amount(row: tuple) -> Decimal:
    return Decimal(row[4] if len(row) > 4 and row[4] is not None else row[0].amount)


def ledger_balance(entries: list[FundingLedgerEntry], as_of: date | None = None) -> Decimal:
    return sum(
        (
            entry.amount * entry.direction
            for entry in entries
            if as_of is None or entry.effective_date <= as_of
        ),
        start=ZERO,
    )


def validate_prospective_debit(
    entries: list[FundingLedgerEntry], effective_date: date, amount: Decimal
) -> None:
    daily: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for entry in entries:
        daily[entry.effective_date] += entry.amount * entry.direction

    running = ZERO
    for entry_date in sorted(day for day in daily if day <= effective_date):
        running += daily[entry_date]
    if running - amount < ZERO:
        raise FundingConflictError("Saldo histórico insuficiente na data efetiva da movimentação.")
    for entry_date in sorted(day for day in daily if day > effective_date):
        running += daily[entry_date]
        if running - amount < ZERO:
            raise FundingConflictError(
                "A movimentação retroativa tornaria o saldo futuro negativo."
            )


async def allocation_summaries(
    session: AsyncSession, sale_ids: list[str]
) -> dict[str, tuple[Decimal, int]]:
    if not sale_ids:
        return {}
    rows = (
        await session.execute(
            select(
                FundingAllocation.sale_id,
                func.sum(FundingAllocation.amount),
                func.count(FundingAllocation.id),
            )
            .where(
                FundingAllocation.sale_id.in_(sale_ids),
                FundingAllocation.status == "ACTIVE",
            )
            .group_by(FundingAllocation.sale_id)
        )
    ).all()
    summaries = {
        sale_id: (Decimal(total), int(count)) for sale_id, total, count in rows
    }
    canonical_ids: list[UUID] = []
    for sale_id in sale_ids:
        if not sale_id.startswith("sale:"):
            continue
        try:
            canonical_ids.append(UUID(sale_id.split(":", 1)[1]))
        except ValueError:
            continue
    if canonical_ids:
        inherited = (
            await session.execute(
                select(
                    OperationalDebtFundingContinuity.successor_sale_identity_id,
                    func.sum(OperationalDebtFundingContinuity.rolled_amount),
                    func.count(OperationalDebtFundingContinuity.id),
                )
                .where(
                    OperationalDebtFundingContinuity.successor_sale_identity_id.in_(
                        canonical_ids
                    )
                )
                .group_by(
                    OperationalDebtFundingContinuity.successor_sale_identity_id
                )
            )
        ).all()
        for sale_identity_id, total, count in inherited:
            summaries.setdefault(
                f"sale:{sale_identity_id}",
                (Decimal(total), int(count)),
            )
    return summaries
