from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtContinuityAuditEvent,
    OperationalDebtContinuityPredecessor,
    OperationalDebtFundingContinuity,
    OperationalDebtRefinancedInstallment,
)
from app.models.funding import (
    FundingAllocation,
    FundingLedgerEntry,
    FundingRevenueDistributionItem,
)
from app.models.identity import (
    OperationalRevenueIdentity,
    OperationalRevenueSnapshot,
    OperationalSaleIdentity,
    OperationalSaleSnapshot,
)
from app.models.normalized import (
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPromotion,
)
from app.models.operational import OperationalImportBatch, utc_now
from app.schemas.debt_continuity import (
    DebtContinuityConfirm,
    DebtContinuityReject,
    DebtContinuityResponse,
    DebtContinuityReviewCreate,
    DebtFundingContinuityResponse,
    RefinancingCorrection,
    RefinancingCreate,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def operational_new_disbursement(released_amount: Decimal | None) -> Decimal | None:
    """Return only the operational release; never infer cash from contract balances."""

    if released_amount is not None and released_amount < ZERO:
        raise DebtContinuityConflictError("Liberação operacional não pode ser negativa.")
    return released_amount


def require_refinancing_new_disbursement(released_amount: Decimal | None) -> Decimal:
    """REFINANCING requires positive operational cash; otherwise use RENEGOTIATION."""

    validated = operational_new_disbursement(released_amount)
    if validated is None or validated <= ZERO:
        raise DebtContinuityConflictError(
            "REFIN exige nova liberação operacional positiva; sem dinheiro novo, "
            "registre RENEGOTIATION."
        )
    return validated


def is_refinancing_closure_candidate(
    payment_date: date | None, paid_amount: Decimal | None
) -> bool:
    """A partial or dated payment is real revenue and can never be closed as REFIN."""

    return payment_date is None and (paid_amount is None or paid_amount <= ZERO)


class DebtContinuityNotFoundError(LookupError):
    pass


class DebtContinuityConflictError(ValueError):
    pass


def validate_same_client_identity(
    successor_client_id: int | None,
    predecessor_client_ids: dict[UUID, int | None],
) -> None:
    """Names are display-only; confirmation uses the canonical operational client id."""

    if successor_client_id is None or any(
        value is None for value in predecessor_client_ids.values()
    ):
        raise DebtContinuityConflictError(
            "Não foi possível confirmar a identidade canônica do cliente em todos os contratos."
        )
    if any(value != successor_client_id for value in predecessor_client_ids.values()):
        raise DebtContinuityConflictError(
            "Todos os contratos predecessores devem pertencer ao mesmo cliente canônico "
            "do contrato sucessor."
        )


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

    async def create_refinancing(self, data: RefinancingCreate) -> DebtContinuityResponse:
        """Record a human-confirmed REFIN without deriving rolled or released cash."""

        try:
            predecessor_ids = data.resolved_predecessor_ids
            successor_id = data.successor_sale_identity_id
            if successor_id is None:
                successor_id = await self._session.scalar(
                    select(OperationalSaleIdentity.id).where(
                        OperationalSaleIdentity.source_contract_code
                        == data.successor_contract_code
                    )
                )
                if successor_id is None:
                    raise DebtContinuityNotFoundError("Contrato sucessor não encontrado.")
            for predecessor_id in predecessor_ids:
                await self._require_sale(predecessor_id)
            await self._require_sale(successor_id)
            if (
                funding_rows
                and successor_id != continuity.successor_sale_identity_id
            ):
                raise DebtContinuityConflictError(
                    "Este REFIN possui funding herdado; a correção do sucessor exige "
                    "revisão financeira dedicada."
                )
            if successor_id in predecessor_ids:
                raise DebtContinuityConflictError(
                    "REFIN exige contratos predecessor e sucessor distintos."
                )
            promotion = await self._current_promotion()
            await self._validate_same_client(promotion.id, successor_id, predecessor_ids)
            existing = await self._session.scalar(
                select(OperationalDebtContinuity).where(
                    OperationalDebtContinuity.source_batch_id == promotion.source_batch_id,
                    OperationalDebtContinuity.successor_sale_identity_id
                    == successor_id,
                )
            )
            if existing is not None:
                existing_predecessors = await self._predecessor_ids(existing)
                if (
                    existing.continuity_type == "REFINANCING"
                    and set(existing_predecessors) == set(predecessor_ids)
                    and existing.status == "REFIN_CONFIRMED"
                ):
                    return await self._response(existing)
                raise DebtContinuityConflictError(
                    "O contrato sucessor já possui uma decisão de continuidade neste batch."
                )
            for predecessor_id in predecessor_ids:
                predecessor_continuity = await self._confirmed_for_predecessor(
                    promotion.source_batch_id, predecessor_id
                )
                if predecessor_continuity is not None:
                    raise DebtContinuityConflictError(
                        "Um dos contratos predecessores já possui continuidade confirmada; "
                        "use a correção auditada."
                    )

            released_amount = require_refinancing_new_disbursement(
                await self._operational_released_amount(promotion.id, successor_id)
            )
            continuity = OperationalDebtContinuity(
                id=uuid4(),
                source_batch_id=promotion.source_batch_id,
                continuity_type="REFINANCING",
                scope="NEW_CONTRACT",
                predecessor_sale_identity_id=predecessor_ids[0],
                successor_sale_identity_id=successor_id,
                status="REFIN_CONFIRMED",
                principal_rolled=data.principal_rolled,
                has_new_disbursement=True,
                effective_date=data.effective_date,
                reason=(data.notes or "Classificação manual como refinanciamento."),
                evidence={
                    "decision": "REFIN_CONFIRMED",
                    "classification_source": "HUMAN_REVIEW",
                    "operational_released_amount": (
                        format(released_amount, "f") if released_amount is not None else None
                    ),
                    "released_amount_source": "CURRENT_OPERATIONAL_PROMOTION",
                    "rolled_principal_was_inferred": False,
                    "automatic_allocation_created": False,
                    "ledger_mutated": False,
                },
                created_by=self._actor_user_id,
                confirmed_by=self._actor_user_id,
                confirmed_at=utc_now(),
            )
            self._session.add(continuity)
            await self._session.flush()
            await self._replace_predecessors(continuity, predecessor_ids)
            refinanced_rows: list[OperationalDebtRefinancedInstallment] = []
            for predecessor_id in predecessor_ids:
                refinanced_rows.extend(
                    await self._classify_unpaid_installments(
                        continuity, promotion.id, predecessor_id
                    )
                )
            funding_rows: list[OperationalDebtFundingContinuity] = []
            if data.principal_rolled is not None:
                funding_rows = await self._inherit_funding(
                    continuity,
                    predecessor_ids,
                    data.principal_rolled,
                )
            continuity.evidence = {
                **continuity.evidence,
                "refinanced_installment_count": len(refinanced_rows),
                "funding_continuity_rows": len(funding_rows),
            }
            self._audit(
                continuity.id,
                "REFIN_CONFIRMED",
                {
                    "previous_state": None,
                    "new_state": {
                        "predecessor_sale_identity_ids": [
                            str(value) for value in predecessor_ids
                        ],
                        "successor_sale_identity_id": str(successor_id),
                        "effective_date": data.effective_date.isoformat(),
                        "principal_rolled": (
                            format(data.principal_rolled, "f")
                            if data.principal_rolled is not None
                            else None
                        ),
                    },
                    "operational_released_amount": (
                        format(released_amount, "f") if released_amount is not None else None
                    ),
                    "refinanced_installment_count": len(refinanced_rows),
                    "automatic_allocation_created": False,
                    "ledger_mutated": False,
                },
            )
            await self._session.commit()
            return await self._response(continuity)
        except Exception:
            await self._session.rollback()
            raise

    async def correct_refinancing(
        self, continuity_id: UUID, data: RefinancingCorrection
    ) -> DebtContinuityResponse:
        """Correct the successor link while preserving the original decision audit."""

        try:
            continuity = await self._locked(continuity_id)
            if (
                continuity.continuity_type != "REFINANCING"
                or continuity.status != "REFIN_CONFIRMED"
            ):
                raise DebtContinuityConflictError(
                    "Somente um REFIN confirmado pode ter o vínculo corrigido."
                )
            current_predecessors = await self._predecessor_ids(continuity)
            predecessor_ids = (
                data.predecessor_sale_identity_ids
                if data.predecessor_sale_identity_ids is not None
                else current_predecessors
            )
            for predecessor_id in predecessor_ids:
                await self._require_sale(predecessor_id)
            funding_rows = int(
                await self._session.scalar(
                select(func.count())
                .select_from(OperationalDebtFundingContinuity)
                .where(OperationalDebtFundingContinuity.continuity_id == continuity.id)
                )
                or 0
            )
            classified_rows = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(OperationalDebtRefinancedInstallment)
                    .where(OperationalDebtRefinancedInstallment.continuity_id == continuity.id)
                )
                or 0
            )
            predecessors_changed = set(predecessor_ids) != set(current_predecessors)
            if predecessors_changed and (funding_rows or classified_rows):
                raise DebtContinuityConflictError(
                    "Este REFIN possui funding herdado ou parcelas classificadas; a correção "
                    "dos predecessores exige revisão financeira dedicada."
                )
            successor_id = data.successor_sale_identity_id
            if successor_id is None:
                successor_id = await self._session.scalar(
                    select(OperationalSaleIdentity.id).where(
                        OperationalSaleIdentity.source_contract_code
                        == data.successor_contract_code
                    )
                )
                if successor_id is None:
                    raise DebtContinuityNotFoundError("Contrato sucessor não encontrado.")
            await self._require_sale(successor_id)
            if successor_id in predecessor_ids:
                raise DebtContinuityConflictError(
                    "REFIN exige contratos predecessor e sucessor distintos."
                )
            promotion = await self._current_promotion()
            if promotion.source_batch_id != continuity.source_batch_id:
                raise DebtContinuityConflictError(
                    "A correção só pode usar a promoção operacional corrente do REFIN."
                )
            await self._validate_same_client(promotion.id, successor_id, predecessor_ids)
            conflict = await self._session.scalar(
                select(OperationalDebtContinuity.id).where(
                    OperationalDebtContinuity.source_batch_id == continuity.source_batch_id,
                    OperationalDebtContinuity.successor_sale_identity_id == successor_id,
                    OperationalDebtContinuity.id != continuity.id,
                )
            )
            if conflict is not None:
                raise DebtContinuityConflictError(
                    "O novo contrato sucessor já possui uma decisão de continuidade neste batch."
                )
            previous_state = {
                "predecessor_sale_identity_ids": [
                    str(value) for value in current_predecessors
                ],
                "successor_sale_identity_id": str(continuity.successor_sale_identity_id),
                "effective_date": (
                    continuity.effective_date.isoformat()
                    if continuity.effective_date is not None
                    else None
                ),
                "reason": continuity.reason,
            }
            released_amount = require_refinancing_new_disbursement(
                await self._operational_released_amount(promotion.id, successor_id)
            )
            continuity.successor_sale_identity_id = successor_id
            if predecessors_changed:
                await self._replace_predecessors(continuity, predecessor_ids)
            continuity.effective_date = data.effective_date
            continuity.reason = data.notes
            continuity.has_new_disbursement = True
            continuity.confirmed_by = self._actor_user_id
            continuity.confirmed_at = utc_now()
            continuity.updated_at = utc_now()
            continuity.evidence = {
                **continuity.evidence,
                "operational_released_amount": (
                    format(released_amount, "f") if released_amount is not None else None
                ),
                "correction_source": "HUMAN_REVIEW",
                "last_correction_note": data.notes,
                "automatic_allocation_created": False,
                "ledger_mutated": False,
            }
            if predecessors_changed:
                self._audit(
                    continuity.id,
                    "PREDECESSORS_CORRECTED",
                    {
                        "before": [str(value) for value in current_predecessors],
                        "after": [str(value) for value in predecessor_ids],
                        "observation": data.notes,
                    },
                )
            self._audit(
                continuity.id,
                "REFIN_CORRECTED",
                {
                    "previous_state": previous_state,
                    "new_state": {
                        "predecessor_sale_identity_ids": [
                            str(value) for value in predecessor_ids
                        ],
                        "successor_sale_identity_id": str(successor_id),
                        "effective_date": data.effective_date.isoformat(),
                        "reason": data.notes,
                    },
                    "operational_released_amount": (
                        format(released_amount, "f") if released_amount is not None else None
                    ),
                    "automatic_allocation_created": False,
                    "ledger_mutated": False,
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
            if data.has_new_disbursement:
                raise DebtContinuityConflictError(
                    "RENEGOTIATION apenas reprograma saldo e não admite nova liberação; "
                    "use REFIN para dinheiro novo operacional comprovado."
                )
            predecessor_ids = data.resolved_predecessor_ids
            for predecessor_id in predecessor_ids:
                self._validate_predecessor(continuity, predecessor_id)
            candidate_ids = {
                UUID(value)
                for value in continuity.evidence.get(
                    "candidate_predecessor_sale_identity_ids", []
                )
            }
            if not set(predecessor_ids).issubset(candidate_ids):
                raise DebtContinuityConflictError(
                    "Um dos contratos predecessores não pertence aos candidatos revisados."
                )
            promotion = await self._promotion_for_batch(continuity.source_batch_id)
            await self._validate_same_client(
                promotion.id, continuity.successor_sale_identity_id, predecessor_ids
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
                and any(
                    value != continuity.successor_sale_identity_id
                    for value in predecessor_ids
                )
                and data.principal_rolled > ZERO
            ):
                funding_rows = await self._inherit_funding(
                    continuity,
                    predecessor_ids,
                    data.principal_rolled,
                )
            await self._replace_predecessors(continuity, predecessor_ids)
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
                    "predecessor_sale_identity_ids": [
                        str(value) for value in predecessor_ids
                    ],
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
        predecessor_ids: list[UUID],
        principal_rolled: Decimal,
    ) -> list[OperationalDebtFundingContinuity]:
        allocations = list(
            await self._session.scalars(
                select(FundingAllocation)
                .where(
                    FundingAllocation.sale_identity_id.in_(predecessor_ids),
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
        predecessor_ids = await self._predecessor_ids(continuity)
        funding = list(
            await self._session.scalars(
                select(OperationalDebtFundingContinuity)
                .where(
                    OperationalDebtFundingContinuity.continuity_id == continuity.id
                )
                .order_by(OperationalDebtFundingContinuity.origin_allocation_id)
            )
        )
        funding_predecessors = dict(
            (
                await self._session.execute(
                    select(FundingAllocation.id, FundingAllocation.sale_identity_id).where(
                        FundingAllocation.id.in_([item.origin_allocation_id for item in funding])
                    )
                )
            ).all()
        ) if funding else {}
        identities = {
            item.id: item.source_contract_code
            for item in await self._session.scalars(
                select(OperationalSaleIdentity).where(
                    OperationalSaleIdentity.id.in_(
                        {
                            *predecessor_ids,
                            continuity.successor_sale_identity_id,
                        }
                        - {None}
                    )
                )
            )
        }
        refinanced_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(OperationalDebtRefinancedInstallment)
                .where(
                    OperationalDebtRefinancedInstallment.continuity_id == continuity.id
                )
            )
            or 0
        )
        promotion = await self._session.get(
            OperationalPromotion,
            await self._session.scalar(
                select(OperationalPromotion.id).where(
                    OperationalPromotion.source_batch_id == continuity.source_batch_id
                )
            ),
        )
        released_amount = (
            await self._operational_released_amount(
                promotion.id, continuity.successor_sale_identity_id
            )
            if promotion is not None
            else None
        )
        return DebtContinuityResponse.model_validate(
            {
                **continuity.__dict__,
                "funding_sources": [
                    DebtFundingContinuityResponse.model_validate(
                        {
                            **item.__dict__,
                            "predecessor_sale_identity_id": funding_predecessors.get(
                                item.origin_allocation_id
                            ),
                        }
                    )
                    for item in funding
                ],
                "predecessor_sale_identity_ids": predecessor_ids,
                "predecessor_contract_code": identities.get(
                    predecessor_ids[0] if predecessor_ids else None
                ),
                "predecessor_contract_codes": [
                    identities[value]
                    for value in predecessor_ids
                    if identities.get(value) is not None
                ],
                "successor_contract_code": identities.get(
                    continuity.successor_sale_identity_id
                ),
                "refinanced_installment_count": refinanced_count,
                "operational_new_disbursement": released_amount,
            }
        )

    async def _current_promotion(self) -> OperationalPromotion:
        promotion = await self._session.scalar(
            select(OperationalPromotion).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
        )
        if promotion is None:
            raise DebtContinuityNotFoundError(
                "Nenhuma promoção operacional atual está disponível."
            )
        return promotion

    async def _promotion_for_batch(self, source_batch_id: int) -> OperationalPromotion:
        promotion = await self._session.scalar(
            select(OperationalPromotion).where(
                OperationalPromotion.source_batch_id == source_batch_id
            )
        )
        if promotion is None:
            raise DebtContinuityNotFoundError(
                "Promoção operacional do vínculo não foi encontrada."
            )
        return promotion

    async def _predecessor_ids(
        self, continuity: OperationalDebtContinuity
    ) -> list[UUID]:
        rows = list(
            await self._session.scalars(
                select(OperationalDebtContinuityPredecessor.sale_identity_id)
                .where(
                    OperationalDebtContinuityPredecessor.continuity_id == continuity.id,
                    OperationalDebtContinuityPredecessor.is_current.is_(True),
                )
                .order_by(
                    OperationalDebtContinuityPredecessor.added_at,
                    OperationalDebtContinuityPredecessor.id,
                )
            )
        )
        if rows:
            return rows
        return (
            [continuity.predecessor_sale_identity_id]
            if continuity.predecessor_sale_identity_id is not None
            else []
        )

    async def _replace_predecessors(
        self,
        continuity: OperationalDebtContinuity,
        predecessor_ids: list[UUID],
    ) -> None:
        ordered = sorted(set(predecessor_ids), key=str)
        current = list(
            await self._session.scalars(
                select(OperationalDebtContinuityPredecessor)
                .where(
                    OperationalDebtContinuityPredecessor.continuity_id == continuity.id,
                    OperationalDebtContinuityPredecessor.is_current.is_(True),
                )
                .with_for_update()
            )
        )
        current_by_sale = {item.sale_identity_id: item for item in current}
        now = utc_now()
        for sale_id, item in current_by_sale.items():
            if sale_id not in ordered:
                item.is_current = False
                item.removed_by = self._actor_user_id
                item.removed_at = now
        self._session.add_all(
            [
                OperationalDebtContinuityPredecessor(
                    id=uuid4(),
                    continuity_id=continuity.id,
                    sale_identity_id=sale_id,
                    added_by=self._actor_user_id,
                )
                for sale_id in ordered
                if sale_id not in current_by_sale
            ]
        )
        # Transitional compatibility only; the association table is canonical.
        continuity.predecessor_sale_identity_id = ordered[0]
        await self._session.flush()

    async def _confirmed_for_predecessor(
        self, source_batch_id: int, predecessor_id: UUID
    ) -> OperationalDebtContinuity | None:
        return await self._session.scalar(
            select(OperationalDebtContinuity)
            .outerjoin(
                OperationalDebtContinuityPredecessor,
                and_(
                    OperationalDebtContinuityPredecessor.continuity_id
                    == OperationalDebtContinuity.id,
                    OperationalDebtContinuityPredecessor.is_current.is_(True),
                ),
            )
            .where(
                OperationalDebtContinuity.source_batch_id == source_batch_id,
                OperationalDebtContinuity.status.in_(
                    ("REFIN_CONFIRMED", "RENEGOTIATION_CONFIRMED")
                ),
                or_(
                    OperationalDebtContinuityPredecessor.sale_identity_id
                    == predecessor_id,
                    OperationalDebtContinuity.predecessor_sale_identity_id
                    == predecessor_id,
                ),
            )
            .limit(1)
        )

    async def _validate_same_client(
        self,
        promotion_id: int,
        successor_id: UUID,
        predecessor_ids: list[UUID],
    ) -> None:
        successor_client_id = await self._operational_client_id(
            promotion_id, successor_id
        )
        predecessor_client_ids = {
            value: await self._operational_client_id(promotion_id, value)
            for value in predecessor_ids
        }
        validate_same_client_identity(successor_client_id, predecessor_client_ids)

    async def _operational_client_id(
        self, promotion_id: int, sale_identity_id: UUID
    ) -> int | None:
        snapshot = await self._session.scalar(
            select(OperationalSaleSnapshot).where(
                OperationalSaleSnapshot.promotion_id == promotion_id,
                OperationalSaleSnapshot.sale_identity_id == sale_identity_id,
            )
        )
        if snapshot is None:
            raise DebtContinuityNotFoundError(
                "Contrato não encontrado na promoção operacional atual."
            )
        if snapshot.contract_id is not None:
            contract = await self._session.get(OperationalContract, snapshot.contract_id)
            return contract.client_id if contract is not None else None
        if snapshot.loan_id is not None:
            loan = await self._session.get(OperationalLoan, snapshot.loan_id)
            return loan.client_id if loan is not None else None
        return None

    async def _operational_released_amount(
        self, promotion_id: int, sale_identity_id: UUID
    ) -> Decimal | None:
        snapshot = await self._session.scalar(
            select(OperationalSaleSnapshot).where(
                OperationalSaleSnapshot.promotion_id == promotion_id,
                OperationalSaleSnapshot.sale_identity_id == sale_identity_id,
            )
        )
        if snapshot is None:
            raise DebtContinuityNotFoundError(
                "Contrato não encontrado na promoção operacional atual."
            )
        if snapshot.contract_id is not None:
            contract = await self._session.get(OperationalContract, snapshot.contract_id)
            return contract.released_amount if contract is not None else None
        if snapshot.loan_id is not None:
            loan = await self._session.get(OperationalLoan, snapshot.loan_id)
            return loan.released_amount if loan is not None else None
        return None

    async def _classify_unpaid_installments(
        self,
        continuity: OperationalDebtContinuity,
        promotion_id: int,
        predecessor_id: UUID,
    ) -> list[OperationalDebtRefinancedInstallment]:
        rows = (
            await self._session.execute(
                select(OperationalRevenueSnapshot, OperationalInstallment)
                .join(
                    OperationalRevenueIdentity,
                    OperationalRevenueIdentity.id
                    == OperationalRevenueSnapshot.revenue_identity_id,
                )
                .join(
                    OperationalInstallment,
                    OperationalInstallment.id == OperationalRevenueSnapshot.installment_id,
                )
                .where(
                    OperationalRevenueSnapshot.promotion_id == promotion_id,
                    OperationalRevenueIdentity.sale_identity_id == predecessor_id,
                )
            )
        ).all()
        classifications = [
            OperationalDebtRefinancedInstallment(
                id=uuid4(),
                continuity_id=continuity.id,
                revenue_identity_id=snapshot.revenue_identity_id,
                original_status=installment.installment_status,
                classified_by=self._actor_user_id,
            )
            for snapshot, installment in rows
            if is_refinancing_closure_candidate(
                installment.payment_date, installment.paid_amount
            )
        ]
        self._session.add_all(classifications)
        return classifications

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
