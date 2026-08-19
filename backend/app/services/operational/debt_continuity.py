from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtContinuityAuditEvent,
    OperationalDebtFundingContinuity,
)
from app.models.funding import (
    FundingAllocation,
    FundingLedgerEntry,
    FundingRevenueDistributionItem,
)
from app.models.identity import OperationalSaleIdentity
from app.models.normalized import OperationalPromotion
from app.models.operational import OperationalImportBatch, utc_now
from app.schemas.debt_continuity import (
    DebtContinuityConfirm,
    DebtContinuityReject,
    DebtContinuityResponse,
    DebtContinuityReviewCreate,
    DebtFundingContinuityResponse,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class DebtContinuityNotFoundError(LookupError):
    pass


class DebtContinuityConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DebtContinuityTerms:
    original_principal: Decimal
    principal_paid: Decimal
    principal_rolled: Decimal
    interest_paid: Decimal
    has_new_disbursement: bool
    new_disbursement_amount: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class DebtEconomicEffects:
    interest_revenue: Decimal
    principal_return: Decimal
    remaining_exposure: Decimal
    treasury_outflow: Decimal
    inherits_funding: bool
    requires_new_allocation: bool


@dataclass(frozen=True, slots=True)
class PredecessorAssessment:
    status: str
    predecessor_sale_identity_id: UUID | None
    funding_transfer_allowed: bool
    ledger_mutation_allowed: bool


def assess_predecessor_candidates(
    candidate_sale_identity_ids: list[UUID],
) -> PredecessorAssessment:
    """Candidate evidence never authorizes an automatic debt or Funding transfer."""

    unique = set(candidate_sale_identity_ids)
    return PredecessorAssessment(
        status="REVIEW_REQUIRED" if unique else "NO_CANDIDATE",
        predecessor_sale_identity_id=None,
        funding_transfer_allowed=False,
        ledger_mutation_allowed=False,
    )


def debt_economic_effects(terms: DebtContinuityTerms) -> DebtEconomicEffects:
    values = (
        terms.original_principal,
        terms.principal_paid,
        terms.principal_rolled,
        terms.interest_paid,
        terms.new_disbursement_amount,
    )
    if any(value < ZERO for value in values):
        raise DebtContinuityConflictError("Valores de continuidade não podem ser negativos.")
    if terms.original_principal != terms.principal_paid + terms.principal_rolled:
        raise DebtContinuityConflictError(
            "Principal original deve ser igual ao principal pago mais o rolado."
        )
    if not terms.has_new_disbursement and terms.new_disbursement_amount != ZERO:
        raise DebtContinuityConflictError(
            "Rolagem sem nova liberação não pode possuir saída de Tesouraria."
        )
    if terms.has_new_disbursement and terms.new_disbursement_amount <= ZERO:
        raise DebtContinuityConflictError(
            "Nova liberação real exige valor de desembolso positivo."
        )
    return DebtEconomicEffects(
        interest_revenue=terms.interest_paid,
        principal_return=terms.principal_paid,
        remaining_exposure=terms.principal_rolled,
        treasury_outflow=terms.new_disbursement_amount,
        inherits_funding=not terms.has_new_disbursement,
        requires_new_allocation=terms.has_new_disbursement,
    )


class DebtContinuityRepository:
    def __init__(self, session: AsyncSession, actor_user_id: UUID) -> None:
        self._session = session
        self._actor_user_id = actor_user_id

    async def list(self) -> list[DebtContinuityResponse]:
        rows = list(
            await self._session.scalars(
                select(OperationalDebtContinuity).order_by(
                    OperationalDebtContinuity.created_at,
                    OperationalDebtContinuity.id,
                )
            )
        )
        return [await self._response(item) for item in rows]

    async def create_review(
        self, data: DebtContinuityReviewCreate
    ) -> DebtContinuityResponse:
        try:
            await self._require_batch(data.source_batch_id)
            await self._require_sale(data.successor_sale_identity_id)
            for candidate in set(data.candidate_predecessor_sale_identity_ids):
                await self._require_sale(candidate)
            existing = await self._session.scalar(
                select(OperationalDebtContinuity).where(
                    OperationalDebtContinuity.source_batch_id == data.source_batch_id,
                    OperationalDebtContinuity.successor_sale_identity_id
                    == data.successor_sale_identity_id,
                )
            )
            if existing is not None:
                return await self._response(existing)
            candidates = sorted(
                {str(value) for value in data.candidate_predecessor_sale_identity_ids}
            )
            continuity = OperationalDebtContinuity(
                id=uuid4(),
                source_batch_id=data.source_batch_id,
                continuity_type=data.continuity_type,
                scope=data.scope,
                predecessor_sale_identity_id=(
                    data.successor_sale_identity_id
                    if data.scope == "SAME_CONTRACT"
                    else None
                ),
                successor_sale_identity_id=data.successor_sale_identity_id,
                status="REVIEW_REQUIRED",
                effective_date=data.effective_date,
                reason=data.reason,
                evidence={
                    **data.evidence,
                    "candidate_predecessor_sale_identity_ids": candidates,
                    "automatic_transfer_performed": False,
                },
                created_by=self._actor_user_id,
            )
            self._session.add(continuity)
            await self._session.flush()
            self._audit(
                continuity.id,
                "REVIEW_CREATED",
                {
                    "candidate_predecessor_sale_identity_ids": candidates,
                    "source_batch_id": data.source_batch_id,
                    "automatic_transfer_performed": False,
                },
            )
            await self._session.commit()
            return await self._response(continuity)
        except Exception:
            await self._session.rollback()
            raise

    async def confirm(
        self, continuity_id: UUID, data: DebtContinuityConfirm
    ) -> DebtContinuityResponse:
        try:
            continuity = await self._locked(continuity_id)
            if continuity.status == "RENEGOTIATION_CONFIRMED":
                return await self._response(continuity)
            if continuity.status == "REJECTED":
                raise DebtContinuityConflictError("Uma revisão rejeitada não pode ser confirmada.")
            self._validate_predecessor(continuity, data.predecessor_sale_identity_id)
            candidate_ids = {
                UUID(value)
                for value in continuity.evidence.get(
                    "candidate_predecessor_sale_identity_ids", []
                )
            }
            if data.predecessor_sale_identity_id not in candidate_ids:
                raise DebtContinuityConflictError(
                    "A Venda predecessora escolhida não pertence aos candidatos revisados."
                )
            effects = debt_economic_effects(
                DebtContinuityTerms(
                    original_principal=data.original_principal,
                    principal_paid=data.principal_paid,
                    principal_rolled=data.principal_rolled,
                    interest_paid=data.interest_paid,
                    has_new_disbursement=data.has_new_disbursement,
                    new_disbursement_amount=(
                        data.principal_rolled if data.has_new_disbursement else ZERO
                    ),
                )
            )
            funding_rows: list[OperationalDebtFundingContinuity] = []
            if (
                effects.inherits_funding
                and data.predecessor_sale_identity_id
                != continuity.successor_sale_identity_id
                and data.principal_rolled > ZERO
            ):
                funding_rows = await self._inherit_funding(
                    continuity,
                    data.predecessor_sale_identity_id,
                    data.principal_rolled,
                )
            continuity.predecessor_sale_identity_id = data.predecessor_sale_identity_id
            continuity.original_principal = data.original_principal
            continuity.principal_paid = data.principal_paid
            continuity.principal_rolled = data.principal_rolled
            continuity.interest_paid = data.interest_paid
            continuity.has_new_disbursement = data.has_new_disbursement
            continuity.effective_date = data.effective_date
            continuity.evidence = {
                **continuity.evidence,
                **data.evidence,
                "decision": "RENEGOTIATION_CONFIRMED",
                "automatic_transfer_performed": False,
                "funding_continuity_rows": len(funding_rows),
            }
            continuity.status = "RENEGOTIATION_CONFIRMED"
            continuity.confirmed_by = self._actor_user_id
            continuity.confirmed_at = utc_now()
            continuity.updated_at = utc_now()
            await self._session.flush()
            self._audit(
                continuity.id,
                "RENEGOTIATION_CONFIRMED",
                {
                    "predecessor_sale_identity_id": str(data.predecessor_sale_identity_id),
                    "successor_sale_identity_id": str(
                        continuity.successor_sale_identity_id
                    ),
                    "original_principal": format(data.original_principal, "f"),
                    "principal_paid": format(data.principal_paid, "f"),
                    "principal_rolled": format(data.principal_rolled, "f"),
                    "interest_paid": format(data.interest_paid, "f"),
                    "has_new_disbursement": data.has_new_disbursement,
                    "treasury_outflow": format(effects.treasury_outflow, "f"),
                    "funding_continuity_rows": len(funding_rows),
                },
            )
            await self._session.commit()
            return await self._response(continuity)
        except Exception:
            await self._session.rollback()
            raise

    async def reject(
        self, continuity_id: UUID, data: DebtContinuityReject
    ) -> DebtContinuityResponse:
        try:
            continuity = await self._locked(continuity_id)
            if continuity.status == "RENEGOTIATION_CONFIRMED":
                raise DebtContinuityConflictError(
                    "Uma confirmação não pode ser apagada; registre uma correção futura."
                )
            continuity.status = "REJECTED"
            continuity.reason = data.reason
            continuity.evidence = {**continuity.evidence, **data.evidence}
            continuity.confirmed_by = self._actor_user_id
            continuity.confirmed_at = utc_now()
            continuity.updated_at = utc_now()
            self._audit(
                continuity.id,
                "REJECTED",
                {"reason": data.reason, "automatic_transfer_performed": False},
            )
            await self._session.commit()
            return await self._response(continuity)
        except Exception:
            await self._session.rollback()
            raise

    async def _inherit_funding(
        self,
        continuity: OperationalDebtContinuity,
        predecessor_id: UUID,
        principal_rolled: Decimal,
    ) -> list[OperationalDebtFundingContinuity]:
        allocations = list(
            await self._session.scalars(
                select(FundingAllocation)
                .where(
                    FundingAllocation.sale_identity_id == predecessor_id,
                    FundingAllocation.status == "ACTIVE",
                )
                .order_by(FundingAllocation.id)
                .with_for_update()
            )
        )
        if not allocations:
            return []
        reversed_returns = select(FundingLedgerEntry.reversal_of_entry_id).where(
            FundingLedgerEntry.reversal_of_entry_id.is_not(None)
        )
        returned_rows = (
            await self._session.execute(
                select(
                    FundingRevenueDistributionItem.allocation_id,
                    func.sum(FundingLedgerEntry.amount),
                )
                .join(
                    FundingLedgerEntry,
                    FundingLedgerEntry.revenue_distribution_item_id
                    == FundingRevenueDistributionItem.id,
                )
                .where(
                    FundingLedgerEntry.entry_type == "PRINCIPAL_RETURN",
                    FundingLedgerEntry.id.not_in(reversed_returns),
                    FundingRevenueDistributionItem.allocation_id.in_(
                        [item.id for item in allocations]
                    ),
                )
                .group_by(FundingRevenueDistributionItem.allocation_id)
            )
        ).all()
        returned = {allocation_id: Decimal(amount) for allocation_id, amount in returned_rows}
        outstanding = [
            (allocation, max(allocation.amount - returned.get(allocation.id, ZERO), ZERO))
            for allocation in allocations
        ]
        outstanding = [(item, amount) for item, amount in outstanding if amount > ZERO]
        available = sum((amount for _, amount in outstanding), ZERO)
        if principal_rolled > available:
            raise DebtContinuityConflictError(
                "Principal rolado excede a exposição financiada ainda existente."
            )
        shares = _allocate_rollover(principal_rolled, outstanding)
        rows = [
            OperationalDebtFundingContinuity(
                id=uuid4(),
                continuity_id=continuity.id,
                successor_sale_identity_id=continuity.successor_sale_identity_id,
                origin_allocation_id=allocation.id,
                source_id=allocation.source_id,
                rolled_amount=shares[allocation.id],
            )
            for allocation, _ in outstanding
            if shares[allocation.id] > ZERO
        ]
        self._session.add_all(rows)
        return rows

    async def _response(
        self, continuity: OperationalDebtContinuity
    ) -> DebtContinuityResponse:
        funding = list(
            await self._session.scalars(
                select(OperationalDebtFundingContinuity)
                .where(
                    OperationalDebtFundingContinuity.continuity_id == continuity.id
                )
                .order_by(OperationalDebtFundingContinuity.origin_allocation_id)
            )
        )
        return DebtContinuityResponse.model_validate(
            {
                **continuity.__dict__,
                "funding_sources": [
                    DebtFundingContinuityResponse.model_validate(item) for item in funding
                ],
            }
        )

    async def _locked(self, continuity_id: UUID) -> OperationalDebtContinuity:
        continuity = await self._session.scalar(
            select(OperationalDebtContinuity)
            .where(OperationalDebtContinuity.id == continuity_id)
            .with_for_update()
        )
        if continuity is None:
            raise DebtContinuityNotFoundError("Revisão de renegociação não encontrada.")
        return continuity

    async def _require_batch(self, batch_id: int) -> None:
        if await self._session.get(OperationalImportBatch, batch_id) is None:
            raise DebtContinuityNotFoundError("Batch de evidência não encontrado.")

    async def _require_sale(self, sale_id: UUID) -> None:
        if await self._session.get(OperationalSaleIdentity, sale_id) is None:
            raise DebtContinuityNotFoundError("Venda canônica não encontrada.")

    @staticmethod
    def _validate_predecessor(
        continuity: OperationalDebtContinuity, predecessor_id: UUID
    ) -> None:
        same = predecessor_id == continuity.successor_sale_identity_id
        if continuity.scope == "SAME_CONTRACT" and not same:
            raise DebtContinuityConflictError(
                "SAME_CONTRACT exige a própria Venda como predecessora."
            )
        if continuity.scope == "NEW_CONTRACT" and same:
            raise DebtContinuityConflictError(
                "NEW_CONTRACT exige Vendas predecessora e sucessora distintas."
            )

    def _audit(self, continuity_id: UUID, action: str, details: dict[str, object]) -> None:
        self._session.add(
            OperationalDebtContinuityAuditEvent(
                continuity_id=continuity_id,
                action=action,
                actor_user_id=self._actor_user_id,
                details=details,
            )
        )


def _allocate_rollover(
    amount: Decimal,
    outstanding: list[tuple[FundingAllocation, Decimal]],
) -> dict[UUID, Decimal]:
    total = sum((value for _, value in outstanding), ZERO)
    if amount == ZERO or total == ZERO:
        return {allocation.id: ZERO for allocation, _ in outstanding}
    target_cents = int((amount / CENT).to_integral_exact())
    quotas: list[tuple[UUID, int, Decimal]] = []
    for allocation, exposure in outstanding:
        exact = Decimal(target_cents) * exposure / total
        floor = int(exact.to_integral_value(rounding=ROUND_DOWN))
        quotas.append((allocation.id, floor, exact - floor))
    residual = target_cents - sum(value for _, value, _ in quotas)
    winners = {
        allocation_id
        for allocation_id, _, _ in sorted(
            quotas, key=lambda item: (-item[2], str(item[0]))
        )[:residual]
    }
    return {
        allocation_id: Decimal(floor + (allocation_id in winners)) * CENT
        for allocation_id, floor, _ in quotas
    }


async def preview_debt_continuity_migration(session: AsyncSession) -> dict[str, object]:
    promotion = await session.scalar(
        select(OperationalPromotion).where(
            OperationalPromotion.is_current.is_(True),
            OperationalPromotion.status == "succeeded",
        )
    )
    if promotion is None:
        raise RuntimeError("Nenhuma promoção operacional atual está disponível.")
    candidate = int(
        await session.scalar(
            select(func.count()).select_from(OperationalSaleIdentity).where(
                OperationalSaleIdentity.source_contract_code == "240600833"
            )
        )
        or 0
    )
    applied = bool(
        await session.scalar(
            text("SELECT to_regclass('operational_debt_continuities') IS NOT NULL")
        )
    )
    reviews = 0
    confirmed = 0
    if applied:
        reviews = int(
            await session.scalar(
                select(func.count()).select_from(OperationalDebtContinuity).where(
                    OperationalDebtContinuity.status == "REVIEW_REQUIRED"
                )
            )
            or 0
        )
        confirmed = int(
            await session.scalar(
                select(func.count()).select_from(OperationalDebtContinuity).where(
                    OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED"
                )
            )
            or 0
        )
    return {
        "mode": "APPLIED" if applied else "PRE_MIGRATION",
        "current_promotion_id": promotion.id,
        "current_source_batch_id": promotion.source_batch_id,
        "candidate_same_contract_renegotiations": candidate,
        "deterministic_confirmations": 0,
        "planned_backfill_rows": 0,
        "existing_reviews": reviews,
        "existing_confirmed": confirmed,
        "note": (
            "240600833 é candidato conhecido, mas não será confirmado sem decisão "
            "humana autenticada e valores econômicos explícitos."
        ),
    }
