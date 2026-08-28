from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtFundingContinuity,
)
from app.models.funding import (
    FundingAllocation,
    FundingAuditEvent,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingRevenueDistribution,
    FundingRevenueDistributionItem,
    FundingSource,
)
from app.models.identity import (
    OperationalRevenueSnapshot,
    OperationalSaleSnapshot,
)
from app.models.normalized import OperationalContract, OperationalInstallment, OperationalPromotion
from app.models.operational import utc_now
from app.schemas.revenue_distribution import (
    RevenueDistributionItemResponse,
    RevenueDistributionProcess,
    RevenueDistributionResponse,
    RevenueDistributionReverse,
)
from app.services.funding.ledger import funding_status, validate_prospective_debit
from app.services.funding.repository import FundingConflictError, FundingNotFoundError

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
RATE_QUANTUM = Decimal("0.000000000001")
PERCENT_QUANTUM = Decimal("0.0001")
AllocationRow = tuple


@dataclass(frozen=True, slots=True)
class RevenueContext:
    installment: OperationalInstallment
    sale_id: str | None
    base_amount: Decimal | None
    revenue_identity_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    sale_identity_id: UUID | None = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True, slots=True)
class RevenueState:
    status: str
    funding_status: str | None
    reason: str | None
    allocations: list[AllocationRow]
    identified_amount: Decimal


@dataclass(frozen=True, slots=True)
class RevenueFundingInput:
    revenue_id: UUID | int | None
    sale_id: str | None
    base_amount: Decimal | None
    payment_date: date | None
    principal_amount: Decimal | None
    interest_amount: Decimal | None
    discount_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class RevenueFundingSummary:
    distribution_status: str
    funding_status: str | None
    primary_source_name: str | None


class RevenueDistributionRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID | None = None,
        actor_label: str | None = None,
    ) -> None:
        self._session = session
        self._actor_user_id = actor_user_id
        self._actor_label = actor_label

    async def get_distribution(self, revenue_id: UUID | int | str) -> RevenueDistributionResponse:
        context = await self._revenue_context(revenue_id)
        latest = await self._latest_distribution(context.revenue_identity_id)
        if latest is not None:
            if latest.status == "DIVERGENT":
                state = await self._current_state(context)
                current_hash = _composition_hash(context, state.allocations)
                if current_hash != latest.composition_hash:
                    return self._pending_response(context, state)
            return await self._distribution_response(latest)
        state = await self._current_state(context)
        return self._pending_response(context, state)

    async def distribute(
        self, revenue_id: UUID | int | str, data: RevenueDistributionProcess
    ) -> RevenueDistributionResponse:
        if self._actor_label is not None:
            data = data.model_copy(update={"actor": self._actor_label})
        try:
            context = await self._revenue_context(revenue_id, lock=True)
            active = await self._active_distribution(context.revenue_identity_id)
            if active is not None:
                return await self._distribution_response(active)

            state = await self._current_state(context)
            if state.status != "READY":
                if state.funding_status == "OVERFUNDED":
                    blocked = await self._record_divergent(context, state, data)
                    await self._session.commit()
                    return await self._distribution_response(blocked)
                raise FundingConflictError(state.reason or "Receita indisponível para rateio.")

            distribution = await self._create_distribution(context, state, data)
            await self._session.commit()
            return await self._distribution_response(distribution)
        except Exception:
            await self._session.rollback()
            raise

    async def reverse(
        self, distribution_id: UUID, data: RevenueDistributionReverse
    ) -> RevenueDistributionResponse:
        if self._actor_label is not None:
            data = data.model_copy(update={"actor": self._actor_label})
        try:
            distribution = await self._session.scalar(
                select(FundingRevenueDistribution)
                .where(FundingRevenueDistribution.id == distribution_id)
                .with_for_update()
            )
            if distribution is None:
                raise FundingNotFoundError("Rateio de Receita não encontrado.")
            if distribution.status == "REVERSED":
                return await self._distribution_response(distribution)
            if distribution.status != "DISTRIBUTED":
                raise FundingConflictError("Somente um rateio distribuído pode ser revertido.")

            items = list(
                await self._session.scalars(
                    select(FundingRevenueDistributionItem)
                    .where(
                        FundingRevenueDistributionItem.distribution_id == distribution.id
                    )
                    .order_by(FundingRevenueDistributionItem.source_id)
                )
            )
            source_ids = sorted({item.source_id for item in items}, key=str)
            if source_ids:
                await self._session.scalars(
                    select(FundingSource)
                    .where(FundingSource.id.in_(source_ids))
                    .order_by(FundingSource.id)
                    .with_for_update()
                )

            item_ids = [item.id for item in items]
            returns = list(
                await self._session.scalars(
                    select(FundingLedgerEntry).where(
                        FundingLedgerEntry.revenue_distribution_item_id.in_(item_ids),
                        FundingLedgerEntry.entry_type == "PRINCIPAL_RETURN",
                    )
                )
            ) if item_ids else []
            for entry in returns:
                existing_reversal = await self._session.scalar(
                    select(FundingLedgerEntry.id).where(
                        FundingLedgerEntry.reversal_of_entry_id == entry.id
                    )
                )
                if existing_reversal is not None:
                    raise FundingConflictError("O retorno de principal já foi revertido.")
                timeline = list(
                    await self._session.scalars(
                        select(FundingLedgerEntry)
                        .where(FundingLedgerEntry.source_id == entry.source_id)
                        .order_by(
                            FundingLedgerEntry.effective_date,
                            FundingLedgerEntry.id,
                        )
                    )
                )
                validate_prospective_debit(timeline, entry.effective_date, entry.amount)
                self._session.add(
                    FundingLedgerEntry(
                        source_id=entry.source_id,
                        entry_type="REVERSAL",
                        amount=entry.amount,
                        direction=-1,
                        effective_date=entry.effective_date,
                        origin_type="REVENUE_DISTRIBUTION_REVERSAL",
                        reversal_of_entry_id=entry.id,
                        actor=data.actor,
                        notes=data.reason,
                    )
                )

            distribution.status = "REVERSED"
            distribution.reversed_at = utc_now()
            distribution.reason = data.reason
            await self._session.flush()
            self._audit(
                distribution.id,
                "REVERSED",
                {
                    "revenue_id": str(distribution.revenue_identity_id),
                    "reason": data.reason,
                    "principal_return_reversals": len(returns),
                },
            )
            await self._session.commit()
            return await self._distribution_response(distribution)
        except Exception:
            await self._session.rollback()
            raise

    async def _create_distribution(
        self,
        context: RevenueContext,
        state: RevenueState,
        data: RevenueDistributionProcess,
    ) -> FundingRevenueDistribution:
        installment = context.installment
        assert context.sale_id is not None
        assert context.base_amount is not None
        assert installment.payment_date is not None

        components = _components(installment)
        allocation_weights = [
            (row[0].id, _allocation_amount(row)) for row in state.allocations
        ]
        component_shares = {
            name: allocate_component(amount, allocation_weights, context.base_amount)
            for name, amount in components.items()
        }
        distribution = FundingRevenueDistribution(
            id=uuid4(),
            revenue_id=installment.id,
            revenue_identity_id=context.revenue_identity_id,
            sale_id=context.sale_id,
            sale_identity_id=context.sale_identity_id,
            version=await self._next_version(context.revenue_identity_id),
            status="DISTRIBUTED",
            composition_hash=_composition_hash(context, state.allocations),
            effective_date=installment.payment_date,
            base_amount=context.base_amount,
            principal_amount=components["principal"],
            interest_amount=components["interest"],
            discount_amount=components["discount"],
            identified_amount=state.identified_amount,
            distributed_principal=sum(component_shares["principal"][0].values(), ZERO),
            distributed_interest=sum(component_shares["interest"][0].values(), ZERO),
            distributed_discount=sum(component_shares["discount"][0].values(), ZERO),
            unidentified_principal=component_shares["principal"][1],
            unidentified_interest=component_shares["interest"][1],
            unidentified_discount=component_shares["discount"][1],
            source_count=len(state.allocations),
            actor=data.actor,
            notes=data.notes,
            reason=None,
        )
        self._session.add(distribution)

        for row in state.allocations:
            allocation, source, _contribution, _investor = row[:4]
            allocation_amount = _allocation_amount(row)
            item = FundingRevenueDistributionItem(
                id=uuid4(),
                distribution_id=distribution.id,
                source_id=source.id,
                allocation_id=allocation.id,
                participation_rate=(allocation_amount / context.base_amount).quantize(
                    RATE_QUANTUM, rounding=ROUND_HALF_UP
                ),
                allocation_amount=allocation_amount,
                base_amount=context.base_amount,
                principal_amount=component_shares["principal"][0][allocation.id],
                interest_amount=component_shares["interest"][0][allocation.id],
                discount_amount=component_shares["discount"][0][allocation.id],
            )
            self._session.add(item)
            if item.principal_amount > ZERO:
                self._session.add(
                    FundingLedgerEntry(
                        source_id=source.id,
                        entry_type="PRINCIPAL_RETURN",
                        amount=item.principal_amount,
                        direction=1,
                        effective_date=installment.payment_date,
                        origin_type="REVENUE_DISTRIBUTION",
                        revenue_distribution_item_id=item.id,
                        actor=data.actor,
                        notes=f"Retorno de principal da Receita operacional {installment.id}.",
                    )
                )

        await self._session.flush()
        self._audit(
            distribution.id,
            "CREATED",
            {
                "revenue_id": str(context.revenue_identity_id),
                "sale_id": context.sale_id,
                "version": distribution.version,
                "source_count": distribution.source_count,
                "effective_date": installment.payment_date.isoformat(),
            },
        )
        self._audit(
            distribution.id,
            "REVENUE_PROCESSED",
            {
                "principal": format(components["principal"], "f"),
                "interest": format(components["interest"], "f"),
                "discount": format(components["discount"], "f"),
                "unidentified_principal": format(
                    distribution.unidentified_principal, "f"
                ),
            },
        )
        return distribution

    async def _record_divergent(
        self,
        context: RevenueContext,
        state: RevenueState,
        data: RevenueDistributionProcess,
    ) -> FundingRevenueDistribution:
        installment = context.installment
        assert context.sale_id is not None
        assert context.base_amount is not None
        assert installment.payment_date is not None
        composition_hash = _composition_hash(context, state.allocations)
        existing = await self._session.scalar(
            select(FundingRevenueDistribution).where(
                FundingRevenueDistribution.revenue_identity_id
                == context.revenue_identity_id,
                FundingRevenueDistribution.composition_hash == composition_hash,
                FundingRevenueDistribution.status == "DIVERGENT",
            )
        )
        if existing is not None:
            return existing
        components = _components(installment)
        distribution = FundingRevenueDistribution(
            id=uuid4(),
            revenue_id=installment.id,
            revenue_identity_id=context.revenue_identity_id,
            sale_id=context.sale_id,
            sale_identity_id=context.sale_identity_id,
            version=await self._next_version(context.revenue_identity_id),
            status="DIVERGENT",
            composition_hash=composition_hash,
            effective_date=installment.payment_date,
            base_amount=context.base_amount,
            principal_amount=components["principal"],
            interest_amount=components["interest"],
            discount_amount=components["discount"],
            identified_amount=state.identified_amount,
            distributed_principal=ZERO,
            distributed_interest=ZERO,
            distributed_discount=ZERO,
            unidentified_principal=components["principal"],
            unidentified_interest=components["interest"],
            unidentified_discount=components["discount"],
            source_count=len(state.allocations),
            actor=data.actor,
            notes=data.notes,
            reason=state.reason,
        )
        self._session.add(distribution)
        await self._session.flush()
        self._audit(
            distribution.id,
            "BLOCKED_DIVERGENT",
            {
                "revenue_id": str(context.revenue_identity_id),
                "sale_id": context.sale_id,
                "funding_status": state.funding_status,
                "reason": state.reason,
            },
        )
        return distribution

    async def _current_state(self, context: RevenueContext) -> RevenueState:
        if context.sale_id is None:
            return RevenueState(
                "DIVERGENT",
                None,
                "Receita sem vínculo relacional estável com uma Venda operacional.",
                [],
                ZERO,
            )
        allocations = await self._allocation_rows(context.sale_id)
        identified = sum((_allocation_amount(row) for row in allocations), ZERO)
        current_funding_status, _ = funding_status(
            context.base_amount, identified, bool(allocations)
        )
        if not allocations:
            return RevenueState(
                "PENDING_FUNDING",
                current_funding_status,
                "Funding ainda não informado. Rateio pendente.",
                allocations,
                identified,
            )
        if context.base_amount is None or context.base_amount <= ZERO:
            return RevenueState(
                "DIVERGENT",
                "BASE_AMOUNT_UNAVAILABLE",
                "Venda sem valor liberado positivo para calcular o rateio.",
                allocations,
                identified,
            )
        if context.installment.payment_date is None:
            return RevenueState(
                "DIVERGENT",
                current_funding_status,
                "Receita sem data real de pagamento/baixa.",
                allocations,
                identified,
            )
        components = _components(context.installment)
        if any(value < ZERO for value in components.values()):
            return RevenueState(
                "DIVERGENT",
                current_funding_status,
                "Receita possui componente financeiro negativo e exige revisão.",
                allocations,
                identified,
            )
        if identified > context.base_amount:
            return RevenueState(
                "DIVERGENT",
                "OVERFUNDED",
                "Funding da Venda ultrapassa o valor-base; rateio bloqueado.",
                allocations,
                identified,
            )
        if sum(components.values(), ZERO) <= ZERO:
            return RevenueState(
                "DIVERGENT",
                current_funding_status,
                "Receita não possui componente financeiro positivo para rateio.",
                allocations,
                identified,
            )
        return RevenueState(
            "READY",
            current_funding_status,
            None,
            allocations,
            identified,
        )

    async def _revenue_context(
        self, revenue_id: UUID | int | str, *, lock: bool = False
    ) -> RevenueContext:
        promotion_id = await self._session.scalar(
            select(OperationalPromotion.id).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
        )
        if promotion_id is None:
            raise FundingNotFoundError("Nenhuma promoção operacional atual está disponível.")
        try:
            canonical_id = UUID(str(revenue_id))
            legacy_id = None
        except (TypeError, ValueError):
            canonical_id = None
            try:
                legacy_id = int(revenue_id)
            except (TypeError, ValueError) as error:
                raise FundingNotFoundError("Receita operacional não encontrada.") from error
        statement = (
            select(
                OperationalInstallment,
                OperationalContract,
                OperationalRevenueSnapshot,
                OperationalSaleSnapshot,
            )
            .outerjoin(
                OperationalContract,
                OperationalContract.id == OperationalInstallment.contract_id,
            )
            .join(
                OperationalRevenueSnapshot,
                OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
            )
            .outerjoin(
                OperationalSaleSnapshot,
                (OperationalSaleSnapshot.promotion_id == OperationalInstallment.promotion_id)
                & (OperationalSaleSnapshot.contract_id == OperationalInstallment.contract_id),
            )
            .where(
                OperationalInstallment.promotion_id == promotion_id,
                (
                    OperationalRevenueSnapshot.revenue_identity_id == canonical_id
                    if canonical_id is not None
                    else OperationalInstallment.id == legacy_id
                ),
            )
        )
        if lock:
            statement = statement.with_for_update(of=OperationalInstallment)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise FundingNotFoundError("Receita operacional não encontrada.")
        installment, contract, revenue_snapshot, sale_snapshot = row
        continuity = None
        if sale_snapshot is not None:
            continuity = await self._session.scalar(
                select(OperationalDebtContinuity).where(
                    OperationalDebtContinuity.successor_sale_identity_id
                    == sale_snapshot.sale_identity_id,
                    OperationalDebtContinuity.predecessor_sale_identity_id
                    != sale_snapshot.sale_identity_id,
                    OperationalDebtContinuity.status.in_(
                        ("RENEGOTIATION_CONFIRMED", "REFIN_CONFIRMED")
                    ),
                )
            )
        return RevenueContext(
            installment=installment,
            revenue_identity_id=revenue_snapshot.revenue_identity_id,
            sale_identity_id=(sale_snapshot.sale_identity_id if sale_snapshot else None),
            sale_id=(f"sale:{sale_snapshot.sale_identity_id}" if sale_snapshot else None),
            base_amount=(
                (
                    (continuity.principal_rolled or ZERO)
                    + (contract.released_amount or ZERO)
                    if continuity.status == "REFIN_CONFIRMED"
                    else continuity.principal_rolled
                )
                if continuity is not None
                else contract.released_amount if contract is not None else None
            ),
        )

    async def _allocation_rows(self, sale_id: str):
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
                .where(
                    FundingAllocation.sale_id == sale_id,
                    FundingAllocation.status == "ACTIVE",
                )
                .order_by(FundingAllocation.id)
            )
        ).all()
        try:
            sale_identity_id = UUID(sale_id.split(":", 1)[1])
        except (IndexError, ValueError):
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
                    == sale_identity_id
                )
                .order_by(OperationalDebtFundingContinuity.origin_allocation_id)
            )
        ).all()
        inherited_rows = [
            (allocation, source, contribution, investor, continuity.rolled_amount)
            for continuity, allocation, source, contribution, investor in inherited
        ]
        return [(*row, None) for row in direct] + inherited_rows

    async def _active_distribution(
        self, revenue_id: UUID
    ) -> FundingRevenueDistribution | None:
        return await self._session.scalar(
            select(FundingRevenueDistribution).where(
                FundingRevenueDistribution.revenue_identity_id == revenue_id,
                FundingRevenueDistribution.status == "DISTRIBUTED",
            )
        )

    async def _latest_distribution(
        self, revenue_id: UUID
    ) -> FundingRevenueDistribution | None:
        return await self._session.scalar(
            select(FundingRevenueDistribution)
            .where(FundingRevenueDistribution.revenue_identity_id == revenue_id)
            .order_by(FundingRevenueDistribution.version.desc())
            .limit(1)
        )

    async def _next_version(self, revenue_id: UUID) -> int:
        current = await self._session.scalar(
            select(func.coalesce(func.max(FundingRevenueDistribution.version), 0)).where(
                FundingRevenueDistribution.revenue_identity_id == revenue_id
            )
        )
        return int(current or 0) + 1

    async def _distribution_response(
        self, distribution: FundingRevenueDistribution
    ) -> RevenueDistributionResponse:
        rows = (
            await self._session.execute(
                select(
                    FundingRevenueDistributionItem,
                    FundingSource,
                    FundingContribution,
                    FundingInvestor,
                )
                .join(
                    FundingSource,
                    FundingSource.id == FundingRevenueDistributionItem.source_id,
                )
                .outerjoin(
                    FundingContribution,
                    FundingContribution.id == FundingSource.contribution_id,
                )
                .outerjoin(
                    FundingInvestor,
                    FundingInvestor.id == FundingContribution.investor_id,
                )
                .where(
                    FundingRevenueDistributionItem.distribution_id == distribution.id
                )
                .order_by(FundingRevenueDistributionItem.allocation_id)
            )
        ).all()
        items = [self._item_response(*row) for row in rows]
        historical_funding_status, _ = funding_status(
            distribution.base_amount,
            distribution.identified_amount,
            distribution.source_count > 0,
        )
        primary = _primary_source(rows)
        return RevenueDistributionResponse(
            id=distribution.id,
            revenue_id=distribution.revenue_identity_id,
            sale_id=distribution.sale_id,
            version=distribution.version,
            status=distribution.status,
            funding_status=historical_funding_status,
            reason=distribution.reason,
            effective_date=distribution.effective_date,
            base_amount=distribution.base_amount,
            principal_amount=distribution.principal_amount,
            interest_amount=distribution.interest_amount,
            discount_amount=distribution.discount_amount,
            identified_amount=distribution.identified_amount,
            distributed_principal=distribution.distributed_principal,
            distributed_interest=distribution.distributed_interest,
            distributed_discount=distribution.distributed_discount,
            unidentified_principal=distribution.unidentified_principal,
            unidentified_interest=distribution.unidentified_interest,
            unidentified_discount=distribution.unidentified_discount,
            distributed_total=_net_total(
                distribution.distributed_principal,
                distribution.distributed_interest,
                distribution.distributed_discount,
            ),
            unidentified_total=_net_total(
                distribution.unidentified_principal,
                distribution.unidentified_interest,
                distribution.unidentified_discount,
            ),
            primary_source_name=primary,
            source_count=distribution.source_count,
            items=items,
            created_at=distribution.created_at,
            reversed_at=distribution.reversed_at,
        )

    def _pending_response(
        self, context: RevenueContext, state: RevenueState
    ) -> RevenueDistributionResponse:
        components = _components(context.installment)
        primary = _primary_source(state.allocations)
        return RevenueDistributionResponse(
            id=None,
            revenue_id=context.revenue_identity_id,
            sale_id=context.sale_id,
            version=None,
            status=state.status,
            funding_status=state.funding_status,
            reason=state.reason,
            effective_date=context.installment.payment_date,
            base_amount=context.base_amount,
            principal_amount=components["principal"],
            interest_amount=components["interest"],
            discount_amount=components["discount"],
            identified_amount=state.identified_amount,
            distributed_principal=ZERO,
            distributed_interest=ZERO,
            distributed_discount=ZERO,
            unidentified_principal=components["principal"],
            unidentified_interest=components["interest"],
            unidentified_discount=components["discount"],
            distributed_total=ZERO,
            unidentified_total=_net_total(
                components["principal"],
                components["interest"],
                components["discount"],
            ),
            primary_source_name=primary,
            source_count=len(state.allocations),
            items=[],
            created_at=None,
            reversed_at=None,
        )

    @staticmethod
    def _item_response(
        item: FundingRevenueDistributionItem,
        source: FundingSource,
        contribution: FundingContribution | None,
        investor: FundingInvestor | None,
    ) -> RevenueDistributionItemResponse:
        return RevenueDistributionItemResponse(
            id=item.id,
            source_id=item.source_id,
            source_type=source.source_type,
            allocation_id=item.allocation_id,
            contribution_id=source.contribution_id,
            contribution_code=contribution.code if contribution else None,
            investor_id=investor.id if investor else None,
            investor_name=investor.name if investor else None,
            participation_rate=item.participation_rate,
            percentage=(item.participation_rate * Decimal("100")).quantize(
                PERCENT_QUANTUM, rounding=ROUND_HALF_UP
            ),
            allocation_amount=item.allocation_amount,
            principal_amount=item.principal_amount,
            interest_amount=item.interest_amount,
            discount_amount=item.discount_amount,
            total_amount=_net_total(
                item.principal_amount,
                item.interest_amount,
                item.discount_amount,
            ),
        )

    def _audit(self, entity_id: UUID, action: str, changes: dict[str, object]) -> None:
        self._session.add(
            FundingAuditEvent(
                entity_type="DISTRIBUTION",
                entity_id=entity_id,
                action=action,
                changes=changes,
                actor_user_id=self._actor_user_id,
            )
        )


def allocate_component(
    component: Decimal,
    allocations: list[tuple[UUID, Decimal]],
    base_amount: Decimal,
) -> tuple[dict[UUID, Decimal], Decimal]:
    component_cents = int((component / CENT).to_integral_exact())
    identified = sum((amount for _, amount in allocations), ZERO)
    source_target = int(
        (Decimal(component_cents) * identified / base_amount).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    source_target = min(component_cents, source_target)
    quotas: list[tuple[UUID, int, Decimal]] = []
    for allocation_id, amount in allocations:
        exact = Decimal(component_cents) * amount / base_amount
        floor = int(exact.to_integral_value(rounding=ROUND_DOWN))
        quotas.append((allocation_id, floor, exact - floor))
    residual = source_target - sum(floor for _, floor, _ in quotas)
    winners = {
        allocation_id
        for allocation_id, _floor, _fraction in sorted(
            quotas,
            key=lambda row: (-row[2], str(row[0])),
        )[:residual]
    }
    shares = {
        allocation_id: Decimal(floor + (1 if allocation_id in winners else 0)) * CENT
        for allocation_id, floor, _fraction in quotas
    }
    gap = Decimal(component_cents - source_target) * CENT
    return shares, gap


def _components(installment: OperationalInstallment) -> dict[str, Decimal]:
    principal = Decimal(installment.principal_component or ZERO)
    interest = Decimal(installment.interest_component or ZERO)
    discount = Decimal(installment.discount_amount or ZERO)
    if installment.paid_amount is None:
        return {
            "principal": principal,
            "interest": interest,
            "discount": discount,
        }
    return realized_revenue_components(
        principal=principal,
        interest=interest,
        discount=discount,
        paid_amount=Decimal(installment.paid_amount),
    )


def realized_revenue_components(
    *,
    principal: Decimal,
    interest: Decimal,
    discount: Decimal,
    paid_amount: Decimal,
) -> dict[str, Decimal]:
    """Limit economic components to cash received, applying payment to interest first."""

    if any(value < ZERO for value in (principal, interest, discount, paid_amount)):
        raise ValueError("Componentes realizados não podem ser negativos.")
    if paid_amount == ZERO:
        return {"principal": ZERO, "interest": ZERO, "discount": ZERO}
    gross_available = paid_amount + discount
    realized_interest = min(interest, gross_available)
    realized_discount = min(discount, realized_interest)
    remaining_cash = max(
        paid_amount - (realized_interest - realized_discount),
        ZERO,
    )
    realized_principal = min(principal, remaining_cash)
    return {
        "principal": realized_principal,
        "interest": realized_interest,
        "discount": realized_discount,
    }


def _composition_hash(context: RevenueContext, allocations: list[tuple]) -> str:
    payload = {
        "revenue_id": str(context.revenue_identity_id),
        "sale_id": context.sale_id,
        "effective_date": (
            context.installment.payment_date.isoformat()
            if context.installment.payment_date
            else None
        ),
        "base_amount": _decimal_text(context.base_amount),
        "components": {
            name: _decimal_text(value)
            for name, value in _components(context.installment).items()
        },
        "allocations": [
            {
                "id": str(allocation.id),
                "source_id": str(source.id),
                "amount": _decimal_text(_allocation_amount(row)),
            }
            for row in allocations
            for allocation, source in [row[:2]]
        ],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _allocation_amount(row: tuple) -> Decimal:
    return Decimal(row[4] if len(row) > 4 and row[4] is not None else row[0].amount)


def _net_total(principal: Decimal, interest: Decimal, discount: Decimal) -> Decimal:
    return principal + interest - discount


def _primary_source(rows: list[tuple]) -> str | None:
    if not rows:
        return None
    def ordering(row: tuple) -> tuple[Decimal, str]:
        entity = row[0]
        if isinstance(entity, FundingRevenueDistributionItem):
            return -entity.allocation_amount, str(entity.allocation_id)
        return -_allocation_amount(row), str(entity.id)

    selected = sorted(rows, key=ordering)[0]
    source = selected[1]
    investor = selected[3]
    contribution = selected[2]
    if source.source_type == "REMO_CAPITAL":
        return "Capital REMO"
    if investor is not None:
        return investor.name
    return contribution.code if contribution is not None else "Aporte de investidor"


async def revenue_funding_summaries(
    session: AsyncSession,
    inputs: list[RevenueFundingInput],
) -> dict[UUID | int | None, RevenueFundingSummary]:
    if not inputs:
        return {}
    revenue_ids = {item.revenue_id for item in inputs if item.revenue_id is not None}
    canonical_ids = [value for value in revenue_ids if isinstance(value, UUID)]
    legacy_ids = [value for value in revenue_ids if isinstance(value, int)]
    identity_filters = []
    if canonical_ids:
        identity_filters.append(
            FundingRevenueDistribution.revenue_identity_id.in_(canonical_ids)
        )
    if legacy_ids:
        identity_filters.append(FundingRevenueDistribution.revenue_id.in_(legacy_ids))
    distributions = list(
        await session.scalars(
            select(FundingRevenueDistribution)
            .where(or_(*identity_filters))
            .order_by(
                FundingRevenueDistribution.revenue_identity_id,
                FundingRevenueDistribution.version.desc(),
            )
        )
    ) if identity_filters else []
    latest: dict[UUID | int, FundingRevenueDistribution] = {}
    for distribution in distributions:
        key = distribution.revenue_identity_id or distribution.revenue_id
        latest.setdefault(key, distribution)

    distribution_ids = [distribution.id for distribution in latest.values()]
    snapshot_rows = (
        await session.execute(
            select(
                FundingRevenueDistributionItem,
                FundingSource,
                FundingContribution,
                FundingInvestor,
            )
            .join(
                FundingSource,
                FundingSource.id == FundingRevenueDistributionItem.source_id,
            )
            .outerjoin(
                FundingContribution,
                FundingContribution.id == FundingSource.contribution_id,
            )
            .outerjoin(
                FundingInvestor,
                FundingInvestor.id == FundingContribution.investor_id,
            )
            .where(
                FundingRevenueDistributionItem.distribution_id.in_(distribution_ids)
            )
        )
    ).all() if distribution_ids else []
    snapshot_by_distribution: dict[UUID, list[tuple]] = {}
    for row in snapshot_rows:
        snapshot_by_distribution.setdefault(row[0].distribution_id, []).append(row)

    sale_ids = sorted({item.sale_id for item in inputs if item.sale_id is not None})
    allocation_rows = (
        await session.execute(
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
            .where(
                FundingAllocation.sale_id.in_(sale_ids),
                FundingAllocation.status == "ACTIVE",
            )
        )
    ).all() if sale_ids else []
    allocations_by_sale: dict[str, list[tuple]] = {}
    for row in allocation_rows:
        allocations_by_sale.setdefault(row[0].sale_id, []).append((*row, None))
    canonical_sale_ids: list[UUID] = []
    for sale_id in sale_ids:
        if not sale_id.startswith("sale:"):
            continue
        try:
            canonical_sale_ids.append(UUID(sale_id.split(":", 1)[1]))
        except ValueError:
            continue
    inherited_rows = (
        await session.execute(
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
                OperationalDebtFundingContinuity.successor_sale_identity_id.in_(
                    canonical_sale_ids
                )
            )
        )
    ).all() if canonical_sale_ids else []
    for continuity, allocation, source, contribution, investor in inherited_rows:
        key = f"sale:{continuity.successor_sale_identity_id}"
        allocations_by_sale.setdefault(key, []).append(
            (
                allocation,
                source,
                contribution,
                investor,
                continuity.rolled_amount,
            )
        )

    summaries: dict[int, RevenueFundingSummary] = {}
    for item in inputs:
        historical = latest.get(item.revenue_id)
        if historical is not None:
            historical_status, _ = funding_status(
                historical.base_amount,
                historical.identified_amount,
                historical.source_count > 0,
            )
            summaries[item.revenue_id] = RevenueFundingSummary(
                distribution_status=historical.status,
                funding_status=historical_status,
                primary_source_name=_primary_source(
                    snapshot_by_distribution.get(historical.id, [])
                ),
            )
            continue
        current_rows = allocations_by_sale.get(item.sale_id or "", [])
        identified = sum((_allocation_amount(row) for row in current_rows), ZERO)
        current_funding, _ = funding_status(
            item.base_amount,
            identified,
            bool(current_rows),
        )
        if item.sale_id is None:
            status = "DIVERGENT"
        elif not current_rows:
            status = "PENDING_FUNDING"
        elif item.base_amount is None or item.base_amount <= ZERO:
            status = "DIVERGENT"
        elif item.payment_date is None:
            status = "DIVERGENT"
        elif any(
            Decimal(value or ZERO) < ZERO
            for value in (
                item.principal_amount,
                item.interest_amount,
                item.discount_amount,
            )
        ):
            status = "DIVERGENT"
        elif identified > item.base_amount:
            status = "DIVERGENT"
        elif sum(
            (
                Decimal(item.principal_amount or ZERO),
                Decimal(item.interest_amount or ZERO),
                Decimal(item.discount_amount or ZERO),
            ),
            ZERO,
        ) <= ZERO:
            status = "DIVERGENT"
        else:
            status = "READY"
        summaries[item.revenue_id] = RevenueFundingSummary(
            distribution_status=status,
            funding_status=current_funding if item.sale_id is not None else None,
            primary_source_name=_primary_source(current_rows),
        )
    return summaries
