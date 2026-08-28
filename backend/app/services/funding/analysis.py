from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funding import (
    FundingAllocation,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingRevenueDistribution,
    FundingRevenueDistributionItem,
    FundingSource,
)
from app.models.identity import OperationalSaleSnapshot
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalLoan,
    OperationalPromotion,
)
from app.models.operational import ExcelEconEmprestimosRow
from app.schemas.contribution_analysis import (
    ContributionAnalysisResponse,
    ContributionAnalysisSummary,
    ContributionMovementAnalysis,
    ContributionOperationAnalysis,
    ContributionReturnAnalysis,
    ContributionReturnTotals,
)
from app.schemas.funding import ContributionResponse
from app.services.funding.ledger import funding_status
from app.services.funding.repository import FundingNotFoundError, FundingRepository

ZERO = Decimal("0.00")
PERCENT_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class OperationIdentity:
    sale_kind: str
    contract_code: str | None
    loan_id: int | None
    client_name: str | None
    operation_date: date | None
    operation_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class AnalysisAmounts:
    available_balance: Decimal
    allocated_capital: Decimal
    returned_principal: Decimal
    exposed_capital: Decimal
    utilization_percentage: Decimal


def valid_principal_returns(
    ledger: list[FundingLedgerEntry],
) -> dict[UUID, Decimal]:
    reversed_entry_ids = {
        entry.reversal_of_entry_id
        for entry in ledger
        if entry.reversal_of_entry_id is not None
    }
    return {
        entry.revenue_distribution_item_id: entry.amount
        for entry in ledger
        if entry.entry_type == "PRINCIPAL_RETURN"
        and entry.id not in reversed_entry_ids
        and entry.revenue_distribution_item_id is not None
    }


def analysis_amounts(
    original_amount: Decimal,
    ledger: list[FundingLedgerEntry],
    operations: list[ContributionOperationAnalysis],
    valid_returns_by_item: dict[UUID, Decimal],
) -> AnalysisAmounts:
    active_operations = [item for item in operations if item.allocation_status == "ACTIVE"]
    allocated_capital = sum(
        (item.allocated_amount for item in active_operations), start=ZERO
    )
    exposed_capital = sum((item.exposed_capital for item in active_operations), start=ZERO)
    returned_principal = sum(valid_returns_by_item.values(), start=ZERO)
    available_balance = sum(
        (entry.amount * entry.direction for entry in ledger), start=ZERO
    )
    utilization = (exposed_capital * Decimal("100") / original_amount).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )
    return AnalysisAmounts(
        available_balance=available_balance,
        allocated_capital=allocated_capital,
        returned_principal=returned_principal,
        exposed_capital=exposed_capital,
        utilization_percentage=utilization,
    )


class ContributionAnalysisRepository:
    """Builds a read-only view from the Phase 2A-2C sources of truth."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_analysis(self, contribution_id: UUID) -> ContributionAnalysisResponse:
        contribution_row = (
            await self._session.execute(
                select(FundingContribution, FundingInvestor, FundingSource)
                .join(FundingInvestor, FundingInvestor.id == FundingContribution.investor_id)
                .join(FundingSource, FundingSource.contribution_id == FundingContribution.id)
                .where(FundingContribution.id == contribution_id)
            )
        ).one_or_none()
        if contribution_row is None:
            raise FundingNotFoundError("Aporte não encontrado.")
        contribution, investor, source = contribution_row

        ledger = list(
            await self._session.scalars(
                select(FundingLedgerEntry)
                .where(FundingLedgerEntry.source_id == source.id)
                .order_by(FundingLedgerEntry.effective_date, FundingLedgerEntry.id)
            )
        )
        allocations = list(
            await self._session.scalars(
                select(FundingAllocation)
                .where(FundingAllocation.source_id == source.id)
                .order_by(
                    FundingAllocation.effective_date,
                    FundingAllocation.created_at,
                    FundingAllocation.id,
                )
            )
        )
        sale_ids = sorted({allocation.sale_id for allocation in allocations})
        identities = await self._operation_identities(sale_ids)
        sale_totals = await self._sale_allocation_totals(sale_ids)
        distribution_rows = (
            await self._session.execute(
                select(FundingRevenueDistributionItem, FundingRevenueDistribution)
                .join(
                    FundingRevenueDistribution,
                    FundingRevenueDistribution.id
                    == FundingRevenueDistributionItem.distribution_id,
                )
                .where(FundingRevenueDistributionItem.source_id == source.id)
                .order_by(
                    FundingRevenueDistribution.effective_date,
                    FundingRevenueDistribution.revenue_id,
                    FundingRevenueDistributionItem.id,
                )
            )
        ).all()

        valid_returns_by_item = valid_principal_returns(ledger)
        principal_by_allocation: dict[UUID, Decimal] = {}
        for item, distribution in distribution_rows:
            if distribution.status != "DISTRIBUTED":
                continue
            amount = valid_returns_by_item.get(item.id, ZERO)
            principal_by_allocation[item.allocation_id] = (
                principal_by_allocation.get(item.allocation_id, ZERO) + amount
            )

        operations = [
            self._operation_response(
                allocation,
                identities.get(allocation.sale_id),
                sale_totals.get(allocation.sale_id, ZERO),
                principal_by_allocation.get(allocation.id, ZERO),
            )
            for allocation in allocations
        ]
        amounts = analysis_amounts(
            contribution.original_amount,
            ledger,
            operations,
            valid_returns_by_item,
        )
        returns = [
            self._return_response(item, distribution)
            for item, distribution in distribution_rows
        ]
        active_return_rows = [
            (item, distribution)
            for item, distribution in distribution_rows
            if distribution.status == "DISTRIBUTED"
        ]

        return ContributionAnalysisResponse(
            source_id=source.id,
            contribution=ContributionResponse.model_validate(
                {
                    **contribution.__dict__,
                    "original_amount_editable": (
                        contribution.original_amount_locked_at is None
                    ),
                }
            ),
            investor=FundingRepository._investor_response(investor),
            summary=ContributionAnalysisSummary(
                contribution_id=contribution.id,
                contribution_code=contribution.code,
                investor_id=investor.id,
                investor_name=investor.name,
                original_amount=contribution.original_amount,
                available_balance=amounts.available_balance,
                allocated_capital=amounts.allocated_capital,
                returned_principal=amounts.returned_principal,
                exposed_capital=amounts.exposed_capital,
                utilization_percentage=amounts.utilization_percentage,
                monthly_rate=contribution.monthly_rate,
                contribution_date=contribution.contribution_date,
                status=contribution.status,
            ),
            operations=operations,
            movements=self._movement_responses(ledger),
            return_totals=ContributionReturnTotals(
                principal_amount=amounts.returned_principal,
                interest_amount=sum((item.interest_amount for item, _ in active_return_rows), ZERO),
                discount_amount=sum((item.discount_amount for item, _ in active_return_rows), ZERO),
            ),
            returns=returns,
        )

    async def _operation_identities(
        self, sale_ids: list[str]
    ) -> dict[str, OperationIdentity]:
        canonical_ids = []
        for value in sale_ids:
            if value.startswith("sale:"):
                try:
                    canonical_ids.append(UUID(value.split(":", 1)[1]))
                except ValueError:
                    continue
        contract_ids = [
            int(value.split(":", 1)[1])
            for value in sale_ids
            if value.startswith("contract:")
        ]
        loan_ids = [int(value.split(":", 1)[1]) for value in sale_ids if value.startswith("loan:")]
        identities: dict[str, OperationIdentity] = {}
        source_names = await self._operational_display_names()
        if canonical_ids:
            rows = (
                await self._session.execute(
                    select(
                        OperationalSaleSnapshot,
                        OperationalContract,
                        OperationalLoan,
                        OperationalClient,
                    )
                    .outerjoin(
                        OperationalContract,
                        OperationalContract.id == OperationalSaleSnapshot.contract_id,
                    )
                    .outerjoin(
                        OperationalLoan,
                        OperationalLoan.id == OperationalSaleSnapshot.loan_id,
                    )
                    .outerjoin(
                        OperationalClient,
                        OperationalClient.id
                        == func.coalesce(
                            OperationalContract.client_id,
                            OperationalLoan.client_id,
                        ),
                    )
                    .join(
                        OperationalPromotion,
                        OperationalPromotion.id == OperationalSaleSnapshot.promotion_id,
                    )
                    .where(
                        OperationalSaleSnapshot.sale_identity_id.in_(canonical_ids),
                        OperationalPromotion.is_current.is_(True),
                        OperationalPromotion.status == "succeeded",
                    )
                )
            ).all()
            for snapshot, contract, loan, client in rows:
                operation = contract or loan
                if operation is None:
                    continue
                identities[f"sale:{snapshot.sale_identity_id}"] = OperationIdentity(
                    "CONTRACT" if contract is not None else "ORPHAN_LOAN",
                    operation.contract_code,
                    loan.id if contract is None and loan is not None else None,
                    (
                        client.name
                        if client and client.name
                        else source_names.get(operation.contract_code)
                    ),
                    operation.operation_date,
                    operation.released_amount,
                )
        if contract_ids:
            rows = (
                await self._session.execute(
                    select(OperationalContract, OperationalClient)
                    .outerjoin(
                        OperationalClient,
                        OperationalClient.id == OperationalContract.client_id,
                    )
                    .where(OperationalContract.id.in_(contract_ids))
                )
            ).all()
            for operation, client in rows:
                identities[f"contract:{operation.id}"] = OperationIdentity(
                    "CONTRACT",
                    operation.contract_code,
                    None,
                    (
                        client.name
                        if client and client.name
                        else source_names.get(operation.contract_code)
                    ),
                    operation.operation_date,
                    operation.released_amount,
                )
        if loan_ids:
            rows = (
                await self._session.execute(
                    select(OperationalLoan, OperationalClient)
                    .outerjoin(OperationalClient, OperationalClient.id == OperationalLoan.client_id)
                    .where(OperationalLoan.id.in_(loan_ids), OperationalLoan.contract_id.is_(None))
                )
            ).all()
            for operation, client in rows:
                identities[f"loan:{operation.id}"] = OperationIdentity(
                    "ORPHAN_LOAN",
                    operation.contract_code,
                    operation.id,
                    (
                        client.name
                        if client and client.name
                        else source_names.get(operation.contract_code)
                    ),
                    operation.operation_date,
                    operation.released_amount,
                )
        return identities

    async def _operational_display_names(self) -> dict[str, str]:
        rows = (
            await self._session.execute(
                select(OperationalLoan.contract_code, ExcelEconEmprestimosRow.nome_cliente)
                .join(
                    ExcelEconEmprestimosRow,
                    ExcelEconEmprestimosRow.id == OperationalLoan.source_loan_row_id,
                )
                .join(
                    OperationalPromotion,
                    OperationalPromotion.id == OperationalLoan.promotion_id,
                )
                .where(
                    OperationalPromotion.is_current.is_(True),
                    OperationalPromotion.status == "succeeded",
                )
            )
        ).all()
        values: dict[str, set[str]] = {}
        for contract_code, name in rows:
            normalized = (name or "").strip()
            if contract_code and normalized:
                values.setdefault(contract_code, set()).add(normalized)
        return {
            contract_code: next(iter(names))
            for contract_code, names in values.items()
            if len(names) == 1
        }

    async def _sale_allocation_totals(self, sale_ids: list[str]) -> dict[str, Decimal]:
        if not sale_ids:
            return {}
        rows = (
            await self._session.execute(
                select(FundingAllocation.sale_id, func.sum(FundingAllocation.amount))
                .where(
                    FundingAllocation.sale_id.in_(sale_ids),
                    FundingAllocation.status == "ACTIVE",
                )
                .group_by(FundingAllocation.sale_id)
            )
        ).all()
        return {sale_id: Decimal(amount) for sale_id, amount in rows}

    @staticmethod
    def _operation_response(
        allocation: FundingAllocation,
        identity: OperationIdentity | None,
        sale_total: Decimal,
        returned_principal: Decimal,
    ) -> ContributionOperationAnalysis:
        if identity is None or identity.operation_date is None:
            raise FundingNotFoundError(
                f"Venda operacional {allocation.sale_id} não encontrada para o aporte."
            )
        percentage = None
        if identity.operation_amount is not None and identity.operation_amount > ZERO:
            percentage = (
                allocation.amount * Decimal("100") / identity.operation_amount
            ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)
        exposed = (
            max(allocation.amount - returned_principal, ZERO)
            if allocation.status == "ACTIVE"
            else ZERO
        )
        funding, _ = funding_status(identity.operation_amount, sale_total, sale_total > ZERO)
        return ContributionOperationAnalysis(
            allocation_id=allocation.id,
            sale_id=allocation.sale_id,
            sale_kind=identity.sale_kind,
            contract_code=identity.contract_code,
            loan_id=identity.loan_id,
            client_name=identity.client_name,
            operation_date=identity.operation_date,
            operation_amount=identity.operation_amount,
            allocated_amount=allocation.amount,
            operation_percentage=percentage,
            returned_principal=returned_principal,
            exposed_capital=exposed,
            allocation_status=allocation.status,
            funding_status=funding,
        )

    @staticmethod
    def _movement_responses(
        entries: list[FundingLedgerEntry],
    ) -> list[ContributionMovementAnalysis]:
        running = ZERO
        responses = []
        for entry in entries:
            signed = entry.amount * entry.direction
            running += signed
            responses.append(
                ContributionMovementAnalysis(
                    id=entry.id,
                    effective_date=entry.effective_date,
                    entry_type=entry.entry_type,
                    origin_type=entry.origin_type,
                    contribution_id=entry.contribution_id,
                    allocation_id=entry.allocation_id,
                    revenue_distribution_item_id=entry.revenue_distribution_item_id,
                    reversal_of_entry_id=entry.reversal_of_entry_id,
                    inflow=entry.amount if entry.direction == 1 else ZERO,
                    outflow=entry.amount if entry.direction == -1 else ZERO,
                    running_balance=running,
                    actor=entry.actor,
                    notes=entry.notes,
                    created_at=entry.created_at,
                )
            )
        return responses

    @staticmethod
    def _return_response(
        item: FundingRevenueDistributionItem,
        distribution: FundingRevenueDistribution,
    ) -> ContributionReturnAnalysis:
        return ContributionReturnAnalysis(
            distribution_id=distribution.id,
            distribution_item_id=item.id,
            revenue_id=distribution.revenue_identity_id or distribution.revenue_id,
            sale_id=distribution.sale_id,
            allocation_id=item.allocation_id,
            effective_date=distribution.effective_date,
            status=distribution.status,
            principal_amount=item.principal_amount,
            interest_amount=item.interest_amount,
            discount_amount=item.discount_amount,
        )
