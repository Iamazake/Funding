from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import OperationalDebtContinuity
from app.models.funding import FundingAllocation, FundingRevenueDistribution
from app.models.identity import (
    OperationalIdentityMatchReview,
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
from app.models.operational import ExcelEconAmortizacoesRow
from app.models.treasury import TreasuryBankValidation

SOURCE_SYSTEM = "CADASTRO_CLIENTES"
MATCH_THRESHOLD = 8


@dataclass(frozen=True, slots=True)
class RevenueEvidence:
    source_record_id: int
    identity_id: UUID | None
    sale_identity_id: UUID | None
    contract_code: str | None
    installment_code: str | None
    source_row_hash: str | None = None
    due_date: date | None = None
    principal: Decimal | None = None
    interest: Decimal | None = None
    expected_amount: Decimal | None = None
    payment_date: date | None = None
    paid_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    financial_product: str | None = None
    installment_status: str | None = None
    situation: str | None = None
    anticipation_marker: str | None = None

    @property
    def partition(self) -> str:
        if self.sale_identity_id is not None:
            return f"sale:{self.sale_identity_id}"
        return f"unresolved:{self.contract_code or ''}"

    @property
    def candidate_group(self) -> tuple[str, str | None]:
        return self.partition, self.installment_code


@dataclass(frozen=True, slots=True)
class RevenueMatchDecision:
    source_record_id: int
    status: str
    identity_id: UUID | None
    score: int | None
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IdentityResolutionReport:
    sale_auto_matches: int
    sale_new_identities: int
    revenue_auto_matches: int
    revenue_new_identities: int
    review_required: int

    def as_dict(self) -> dict[str, int]:
        return {
            "sale_auto_matches": self.sale_auto_matches,
            "sale_new_identities": self.sale_new_identities,
            "revenue_auto_matches": self.revenue_auto_matches,
            "revenue_new_identities": self.revenue_new_identities,
            "review_required": self.review_required,
        }


def match_revenues(
    previous: list[RevenueEvidence],
    current: list[RevenueEvidence],
    *,
    confirmed_renegotiation_sales: set[UUID] | None = None,
    protected_identity_ids: set[UUID] | None = None,
) -> list[RevenueMatchDecision]:
    """Conservative one-to-one matcher; candidate generation never uses row position or CHAVE."""

    previous_by_group: dict[tuple[str, str | None], list[RevenueEvidence]] = defaultdict(list)
    current_by_group: dict[tuple[str, str | None], list[RevenueEvidence]] = defaultdict(list)
    for item in previous:
        previous_by_group[item.candidate_group].append(item)
    for item in current:
        current_by_group[item.candidate_group].append(item)

    confirmed_renegotiation_sales = confirmed_renegotiation_sales or set()
    protected_identity_ids = protected_identity_ids or set()
    decisions: list[RevenueMatchDecision] = []
    for group, new_rows in current_by_group.items():
        old_rows = previous_by_group.get(group, [])
        sale_identity_id = next(
            (row.sale_identity_id for row in new_rows if row.sale_identity_id is not None),
            None,
        )
        if sale_identity_id in confirmed_renegotiation_sales:
            decisions.extend(
                _match_group(
                    old_rows,
                    new_rows,
                    protected_identity_ids=protected_identity_ids,
                    new_identity_reason="CONFIRMED_NEW_SCHEDULE",
                )
            )
            continue

        if not old_rows:
            decisions.extend(
                RevenueMatchDecision(
                    row.source_record_id,
                    "NEW_IDENTITY",
                    None,
                    None,
                    "NO_PRIOR_CANDIDATE",
                    {"candidate_group": list(group)},
                )
                for row in new_rows
            )
            continue
        decisions.extend(
            _match_group(
                old_rows,
                new_rows,
                protected_identity_ids=protected_identity_ids,
                new_identity_reason="UNMATCHED_WITHOUT_PERSISTENT_FINANCIAL_REFERENCE",
            )
        )
    return sorted(decisions, key=lambda item: item.source_record_id)


def _match_confirmed_schedule(
    old_rows: list[RevenueEvidence], new_rows: list[RevenueEvidence]
) -> list[RevenueMatchDecision]:
    """Compatibility wrapper for callers that already classified a renegotiation."""

    return _match_group(
        old_rows,
        new_rows,
        protected_identity_ids=set(),
        new_identity_reason="CONFIRMED_NEW_SCHEDULE",
    )


def _match_group(
    old_rows: list[RevenueEvidence],
    new_rows: list[RevenueEvidence],
    *,
    protected_identity_ids: set[UUID],
    new_identity_reason: str,
) -> list[RevenueMatchDecision]:
    """Match safely; ambiguity without persistent references creates no false merge."""

    unmatched_old = list(old_rows)
    unmatched_new: list[RevenueEvidence] = []
    decisions: list[RevenueMatchDecision] = []
    for new_row in new_rows:
        exact = [
            old
            for old in unmatched_old
            if old.source_row_hash
            and new_row.source_row_hash
            and old.source_row_hash == new_row.source_row_hash
        ]
        if len(exact) > 1:
            if any(
                old.identity_id in protected_identity_ids
                for old in exact
                if old.identity_id is not None
            ):
                return _reviews(
                    new_rows,
                    "AMBIGUOUS_EXACT_HASH_WITH_PERSISTENT_FINANCIAL_REFERENCE",
                    old_rows,
                    {"candidate_count": len(old_rows)},
                )
            unmatched_new.append(new_row)
            continue
        if not exact:
            unmatched_new.append(new_row)
            continue
        matched = exact[0]
        unmatched_old.remove(matched)
        decisions.append(
            RevenueMatchDecision(
                new_row.source_record_id,
                "AUTO_MATCH",
                matched.identity_id,
                100,
                "EXACT_HASH",
                {"exact_hash": True},
            )
        )

    if not unmatched_new:
        return decisions
    if not unmatched_old:
        return [
            *decisions,
            *[
                RevenueMatchDecision(
                    row.source_record_id,
                    "NEW_IDENTITY",
                    None,
                    None,
                    new_identity_reason,
                    {"historical_snapshot_preserved": True},
                )
                for row in unmatched_new
            ],
        ]

    proposed: dict[int, tuple[RevenueEvidence, int, dict[str, Any]]] = {}
    group_failed = False
    for new_row in unmatched_new:
        scored = sorted(
            (_score(old_row, new_row) for old_row in unmatched_old),
            key=lambda item: item[1],
            reverse=True,
        )
        best = scored[0]
        tied = len(scored) > 1 and scored[1][1] == best[1]
        if tied or best[1] < MATCH_THRESHOLD:
            group_failed = True
            break
        proposed[new_row.source_record_id] = best

    claimed = Counter(best[0].identity_id for best in proposed.values())
    duplicate_claim = any(identity is not None and count > 1 for identity, count in claimed.items())
    if group_failed or duplicate_claim:
        protected = any(
            old.identity_id in protected_identity_ids
            for old in unmatched_old
            if old.identity_id is not None
        )
        if protected:
            return [
                *decisions,
                *_reviews(
                    unmatched_new,
                    "AMBIGUOUS_OR_INSUFFICIENT_EVIDENCE_WITH_PERSISTENT_FINANCIAL_REFERENCE",
                    unmatched_old,
                    {"candidate_count": len(unmatched_old)},
                ),
            ]
        return [
            *decisions,
            *[
                RevenueMatchDecision(
                    row.source_record_id,
                    "NEW_IDENTITY",
                    None,
                    None,
                    new_identity_reason,
                    {
                        "historical_snapshot_preserved": True,
                        "automatic_merge_performed": False,
                    },
                )
                for row in unmatched_new
            ],
        ]

    for new_row in unmatched_new:
        old_row, score, evidence = proposed[new_row.source_record_id]
        decisions.append(
            RevenueMatchDecision(
                new_row.source_record_id,
                "AUTO_MATCH",
                old_row.identity_id,
                score,
                "UNIQUE_STRONG_EVIDENCE",
                evidence,
            )
        )
    return decisions


def _reviews(
    rows: list[RevenueEvidence],
    reason: str,
    candidates: list[RevenueEvidence],
    extra: dict[str, Any],
) -> list[RevenueMatchDecision]:
    return [
        RevenueMatchDecision(
            row.source_record_id,
            "REVIEW_REQUIRED",
            None,
            None,
            reason,
            {
                **extra,
                "candidate_identity_ids": [
                    str(candidate.identity_id)
                    for candidate in candidates
                    if candidate.identity_id is not None
                ],
                "contract_code": row.contract_code,
                "installment_code": row.installment_code,
            },
        )
        for row in rows
    ]


def _score(
    previous: RevenueEvidence, current: RevenueEvidence
) -> tuple[RevenueEvidence, int, dict[str, Any]]:
    exact_hash = bool(
        previous.source_row_hash
        and current.source_row_hash
        and previous.source_row_hash == current.source_row_hash
    )
    weights = {
        "due_date": 3,
        "principal": 2,
        "interest": 2,
        "expected_amount": 2,
        "payment_date": 1,
        "paid_amount": 1,
        "discount_amount": 1,
        "financial_product": 1,
        "installment_status": 1,
        "situation": 1,
        "anticipation_marker": 1,
    }
    agreeing = []
    score = 100 if exact_hash else 0
    for field_name, weight in weights.items():
        left = getattr(previous, field_name)
        right = getattr(current, field_name)
        if left is not None and right is not None and left == right:
            score += weight
            agreeing.append(field_name)
    return previous, score, {"exact_hash": exact_hash, "agreeing_fields": agreeing}


class CanonicalIdentityResolver:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, promotion: OperationalPromotion) -> IdentityResolutionReport:
        current_promotion_id = await self._session.scalar(
            select(OperationalPromotion.id).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
                OperationalPromotion.id != promotion.id,
            )
        )
        sale_auto, sale_new = await self._resolve_sales(promotion)
        previous = (
            await self._revenue_evidence(current_promotion_id)
            if current_promotion_id is not None
            else []
        )
        current = await self._revenue_evidence(promotion.id, include_unlinked=True)
        confirmed_sales = set(
            await self._session.scalars(
                select(OperationalDebtContinuity.successor_sale_identity_id).where(
                    OperationalDebtContinuity.source_batch_id == promotion.source_batch_id,
                    OperationalDebtContinuity.status == "RENEGOTIATION_CONFIRMED",
                    OperationalDebtContinuity.scope == "SAME_CONTRACT",
                    OperationalDebtContinuity.has_new_disbursement.is_(False),
                )
            )
        )
        persistent_references = await self._persistent_revenue_references()
        decisions = match_revenues(
            previous,
            current,
            confirmed_renegotiation_sales=confirmed_sales,
            protected_identity_ids=set(persistent_references),
        )
        current_by_source = {item.source_record_id: item for item in current}
        revenue_auto = 0
        revenue_new = 0
        reviews = 0
        matched_previous_ids = {
            decision.identity_id
            for decision in decisions
            if decision.status == "AUTO_MATCH" and decision.identity_id is not None
        }
        for item in previous:
            if (
                item.identity_id is None
                or item.identity_id in matched_previous_ids
                or item.identity_id not in persistent_references
            ):
                continue
            reviews += 1
            self._session.add(
                OperationalIdentityMatchReview(
                    source_batch_id=promotion.source_batch_id,
                    promotion_id=promotion.id,
                    entity_type="REVENUE",
                    source_record_id=item.source_record_id,
                    candidate_identity_id=item.identity_id,
                    status="REVIEW_REQUIRED",
                    critical=True,
                    reason="MISSING_FROM_CURRENT_SNAPSHOT_WITH_PERSISTENT_FINANCIAL_REFERENCE",
                    evidence={
                        "historical_snapshot_preserved": True,
                        "automatic_financial_movement_performed": False,
                        "persistent_references": persistent_references[item.identity_id],
                        "contract_code": item.contract_code,
                        "installment_code": item.installment_code,
                    },
                )
            )
        for decision in decisions:
            item = current_by_source[decision.source_record_id]
            if decision.status == "REVIEW_REQUIRED":
                reviews += 1
                self._session.add(
                    OperationalIdentityMatchReview(
                        source_batch_id=promotion.source_batch_id,
                        promotion_id=promotion.id,
                        entity_type="REVENUE",
                        source_record_id=item.source_record_id,
                        status="REVIEW_REQUIRED",
                        critical=True,
                        reason=decision.reason,
                        evidence=decision.evidence,
                    )
                )
                continue
            identity_id = decision.identity_id
            if identity_id is None:
                identity = OperationalRevenueIdentity(
                    sale_identity_id=item.sale_identity_id,
                    unresolved_contract_code=(
                        item.contract_code if item.sale_identity_id is None else None
                    ),
                    status="ACTIVE",
                )
                self._session.add(identity)
                await self._session.flush()
                identity_id = identity.id
                revenue_new += 1
            else:
                revenue_auto += 1
            self._session.add(
                OperationalRevenueSnapshot(
                    revenue_identity_id=identity_id,
                    promotion_id=promotion.id,
                    installment_id=item.source_record_id,
                    match_status=decision.status,
                    match_score=decision.score,
                    match_evidence={"reason": decision.reason, **decision.evidence},
                )
            )
        await self._session.flush()
        return IdentityResolutionReport(sale_auto, sale_new, revenue_auto, revenue_new, reviews)

    async def _persistent_revenue_references(self) -> dict[UUID, list[str]]:
        reasons: dict[UUID, set[str]] = defaultdict(set)
        for identity_id in await self._session.scalars(
            select(FundingRevenueDistribution.revenue_identity_id).where(
                FundingRevenueDistribution.revenue_identity_id.is_not(None)
            )
        ):
            reasons[identity_id].add("FUNDING_REVENUE_DISTRIBUTION")
        for identity_id in await self._session.scalars(
            select(TreasuryBankValidation.revenue_identity_id).where(
                TreasuryBankValidation.revenue_identity_id.is_not(None)
            )
        ):
            reasons[identity_id].add("TREASURY_BANK_VALIDATION")

        protected_sales = set(
            await self._session.scalars(
                select(FundingAllocation.sale_identity_id).where(
                    FundingAllocation.sale_identity_id.is_not(None)
                )
            )
        )
        validated_sales = set(
            await self._session.scalars(
                select(TreasuryBankValidation.sale_identity_id).where(
                    TreasuryBankValidation.sale_identity_id.is_not(None)
                )
            )
        )
        if protected_sales or validated_sales:
            revenue_sales = (
                await self._session.execute(
                    select(
                        OperationalRevenueIdentity.id,
                        OperationalRevenueIdentity.sale_identity_id,
                    ).where(
                        OperationalRevenueIdentity.sale_identity_id.in_(
                            protected_sales | validated_sales
                        )
                    )
                )
            ).all()
            for revenue_id, sale_id in revenue_sales:
                if sale_id in protected_sales:
                    reasons[revenue_id].add("SALE_FUNDING_ALLOCATION")
                if sale_id in validated_sales:
                    reasons[revenue_id].add("SALE_TREASURY_BANK_VALIDATION")
        return {
            identity_id: sorted(reference_types) for identity_id, reference_types in reasons.items()
        }

    async def _resolve_sales(self, promotion: OperationalPromotion) -> tuple[int, int]:
        identities = {
            item.source_contract_code: item
            for item in await self._session.scalars(select(OperationalSaleIdentity))
        }
        contracts = list(
            await self._session.scalars(
                select(OperationalContract)
                .where(OperationalContract.promotion_id == promotion.id)
                .order_by(OperationalContract.id)
            )
        )
        loans = list(
            await self._session.scalars(
                select(OperationalLoan)
                .where(OperationalLoan.promotion_id == promotion.id)
                .order_by(OperationalLoan.id)
            )
        )
        loans_by_contract = {
            loan.contract_id: loan for loan in loans if loan.contract_id is not None
        }
        auto = 0
        created = 0
        for contract in contracts:
            identity = identities.get(contract.contract_code or "")
            status = "AUTO_MATCH"
            if identity is None:
                identity = OperationalSaleIdentity(
                    source_system=SOURCE_SYSTEM,
                    source_contract_code=contract.contract_code or "",
                    origin_kind="CONTRACT",
                    status="ACTIVE",
                )
                self._session.add(identity)
                await self._session.flush()
                identities[identity.source_contract_code] = identity
                status = "NEW_IDENTITY"
                created += 1
            else:
                auto += 1
            loan = loans_by_contract.get(contract.id)
            self._session.add(
                OperationalSaleSnapshot(
                    sale_identity_id=identity.id,
                    promotion_id=promotion.id,
                    contract_id=contract.id,
                    loan_id=loan.id if loan else None,
                    match_status=status,
                    match_evidence={
                        "method": "UNIQUE_STABLE_CONTRACT_CODE",
                        "contract_code": contract.contract_code,
                    },
                )
            )
        for loan in (item for item in loans if item.contract_id is None):
            identity = identities.get(loan.contract_code or "")
            status = "AUTO_MATCH"
            if identity is None:
                identity = OperationalSaleIdentity(
                    source_system=SOURCE_SYSTEM,
                    source_contract_code=loan.contract_code or "",
                    origin_kind="ORPHAN_LOAN",
                    status="ACTIVE",
                )
                self._session.add(identity)
                await self._session.flush()
                identities[identity.source_contract_code] = identity
                status = "NEW_IDENTITY"
                created += 1
            else:
                auto += 1
            self._session.add(
                OperationalSaleSnapshot(
                    sale_identity_id=identity.id,
                    promotion_id=promotion.id,
                    loan_id=loan.id,
                    match_status=status,
                    match_evidence={
                        "method": "UNIQUE_STABLE_ORPHAN_LOAN_CONTRACT_CODE",
                        "contract_code": loan.contract_code,
                    },
                )
            )
        await self._session.flush()
        return auto, created

    async def _revenue_evidence(
        self, promotion_id: int, *, include_unlinked: bool = False
    ) -> list[RevenueEvidence]:
        statement = (
            select(
                OperationalInstallment,
                ExcelEconAmortizacoesRow.source_row_hash,
                OperationalRevenueSnapshot.revenue_identity_id,
                OperationalSaleSnapshot.sale_identity_id,
            )
            .join(
                ExcelEconAmortizacoesRow,
                ExcelEconAmortizacoesRow.id == OperationalInstallment.source_amortization_row_id,
            )
            .outerjoin(
                OperationalRevenueSnapshot,
                OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
            )
            .outerjoin(
                OperationalSaleSnapshot,
                (OperationalSaleSnapshot.promotion_id == OperationalInstallment.promotion_id)
                & or_(
                    OperationalSaleSnapshot.contract_id == OperationalInstallment.contract_id,
                    (
                        OperationalInstallment.contract_id.is_(None)
                        & (
                            OperationalSaleSnapshot.sale_identity_id
                            == select(OperationalSaleIdentity.id)
                            .where(
                                OperationalSaleIdentity.source_contract_code
                                == OperationalInstallment.contract_code
                            )
                            .scalar_subquery()
                        )
                    ),
                ),
            )
            .where(OperationalInstallment.promotion_id == promotion_id)
            .order_by(OperationalInstallment.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            RevenueEvidence(
                source_record_id=item.id,
                identity_id=revenue_identity_id,
                sale_identity_id=sale_identity_id,
                contract_code=item.contract_code,
                installment_code=item.installment_code,
                source_row_hash=source_hash,
                due_date=item.due_date,
                principal=item.principal_component,
                interest=item.interest_component,
                expected_amount=item.expected_amount,
                payment_date=item.payment_date,
                paid_amount=item.paid_amount,
                discount_amount=item.discount_amount,
                financial_product=item.financial_product,
                installment_status=item.installment_status,
                situation=item.situation,
                anticipation_marker=item.anticipation_marker,
            )
            for item, source_hash, revenue_identity_id, sale_identity_id in rows
            if include_unlinked or revenue_identity_id is not None
        ]


async def preview_current_identity_backfill(session: AsyncSession) -> dict[str, Any]:
    promotion = await session.scalar(
        select(OperationalPromotion).where(
            OperationalPromotion.is_current.is_(True),
            OperationalPromotion.status == "succeeded",
        )
    )
    if promotion is None:
        raise RuntimeError("Nenhuma promoção operacional atual está disponível.")
    identity_schema_applied = bool(
        await session.scalar(text("SELECT to_regclass('operational_sale_identities') IS NOT NULL"))
    )
    if identity_schema_applied:
        return await _preview_applied_identity_backfill(session, promotion)

    contract_count = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalContract)
            .where(OperationalContract.promotion_id == promotion.id)
        )
        or 0
    )
    orphan_loan_count = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalLoan)
            .where(
                OperationalLoan.promotion_id == promotion.id,
                OperationalLoan.contract_id.is_(None),
            )
        )
        or 0
    )
    revenue_count = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalInstallment)
            .where(OperationalInstallment.promotion_id == promotion.id)
        )
        or 0
    )
    allocation_total = int(
        await session.scalar(select(func.count()).select_from(FundingAllocation)) or 0
    )
    allocation_resolved = int(
        await session.scalar(
            select(func.count())
            .select_from(FundingAllocation)
            .outerjoin(
                OperationalContract,
                and_(
                    FundingAllocation.sale_id.like("contract:%"),
                    OperationalContract.id
                    == func.split_part(FundingAllocation.sale_id, ":", 2).cast(
                        OperationalContract.id.type
                    ),
                    OperationalContract.promotion_id == promotion.id,
                ),
            )
            .outerjoin(
                OperationalLoan,
                and_(
                    FundingAllocation.sale_id.like("loan:%"),
                    OperationalLoan.id
                    == func.split_part(FundingAllocation.sale_id, ":", 2).cast(
                        OperationalLoan.id.type
                    ),
                    OperationalLoan.promotion_id == promotion.id,
                ),
            )
            .where(or_(OperationalContract.id.is_not(None), OperationalLoan.id.is_not(None)))
        )
        or 0
    )
    distributions = int(
        await session.scalar(select(func.count()).select_from(FundingRevenueDistribution)) or 0
    )
    validations = int(
        await session.scalar(
            select(func.count())
            .select_from(TreasuryBankValidation)
            .where(TreasuryBankValidation.movement_type.in_(("SALE", "REVENUE")))
        )
        or 0
    )
    return {
        "current_promotion_id": promotion.id,
        "current_source_batch_id": promotion.source_batch_id,
        "canonical_sales": contract_count + orphan_loan_count,
        "canonical_revenues": revenue_count,
        "unambiguous_matches": contract_count + orphan_loan_count + revenue_count,
        "ambiguities": 0,
        "funding_references": {
            "allocations": allocation_total,
            "allocations_resolved": allocation_resolved,
            "revenue_distributions": distributions,
            "treasury_validations": validations,
        },
    }


async def _preview_applied_identity_backfill(
    session: AsyncSession, promotion: OperationalPromotion
) -> dict[str, Any]:
    canonical_sales = int(
        await session.scalar(select(func.count()).select_from(OperationalSaleIdentity)) or 0
    )
    canonical_revenues = int(
        await session.scalar(select(func.count()).select_from(OperationalRevenueIdentity)) or 0
    )
    sale_matches = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalSaleSnapshot)
            .where(OperationalSaleSnapshot.promotion_id == promotion.id)
        )
        or 0
    )
    revenue_matches = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalRevenueSnapshot)
            .where(OperationalRevenueSnapshot.promotion_id == promotion.id)
        )
        or 0
    )
    ambiguities = int(
        await session.scalar(
            select(func.count())
            .select_from(OperationalIdentityMatchReview)
            .where(
                OperationalIdentityMatchReview.promotion_id == promotion.id,
                OperationalIdentityMatchReview.status == "REVIEW_REQUIRED",
            )
        )
        or 0
    )
    allocations = int(
        await session.scalar(select(func.count()).select_from(FundingAllocation)) or 0
    )
    allocations_resolved = int(
        await session.scalar(
            select(func.count())
            .select_from(FundingAllocation)
            .where(FundingAllocation.sale_identity_id.is_not(None))
        )
        or 0
    )
    distributions = int(
        await session.scalar(select(func.count()).select_from(FundingRevenueDistribution)) or 0
    )
    validations = int(
        await session.scalar(
            select(func.count())
            .select_from(TreasuryBankValidation)
            .where(TreasuryBankValidation.movement_type.in_(("SALE", "REVENUE")))
        )
        or 0
    )
    return {
        "mode": "APPLIED",
        "current_promotion_id": promotion.id,
        "current_source_batch_id": promotion.source_batch_id,
        "canonical_sales": canonical_sales,
        "canonical_revenues": canonical_revenues,
        "unambiguous_matches": sale_matches + revenue_matches,
        "ambiguities": ambiguities,
        "funding_references": {
            "allocations": allocations,
            "allocations_resolved": allocations_resolved,
            "revenue_distributions": distributions,
            "treasury_validations": validations,
        },
    }
