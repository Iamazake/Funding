from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AppUser, AppUserAuditEvent
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPromotion,
)
from app.models.operational import OperationalImportBatch, SyncRun
from app.schemas.batches import (
    BatchComparison,
    BatchCountComparison,
    BatchDataCounts,
    BatchPromotionInfo,
    BatchQualityCounts,
    BatchUser,
    OperationalBatchDetail,
    OperationalBatchList,
    OperationalBatchSummary,
)
from app.services.excel.store import SessionFactory
from app.services.operational.promotion import OperationalPromotionBuilder
from app.services.operational.store import SqlAlchemyOperationalPromotionRepository


class OperationalBatchNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _AuditContext:
    source_type: str | None = None
    user: BatchUser | None = None


class OperationalBatchReviewService:
    def __init__(
        self,
        session: AsyncSession,
        session_factory: SessionFactory,
    ) -> None:
        self._session = session
        self._promotion_repository = SqlAlchemyOperationalPromotionRepository(session_factory)

    async def list_batches(self, *, limit: int = 50) -> OperationalBatchList:
        rows = (
            await self._session.execute(
                select(OperationalImportBatch, SyncRun)
                .join(SyncRun, SyncRun.id == OperationalImportBatch.sync_run_id)
                .order_by(OperationalImportBatch.id.desc())
                .limit(limit)
            )
        ).all()
        contexts = await self._sync_audit_contexts()
        promotions, promotion_users = await self._promotion_contexts()
        return OperationalBatchList(
            items=[
                self._summary(
                    batch,
                    run,
                    contexts.get(run.id, _AuditContext()),
                    promotions.get(batch.id),
                    promotion_users.get(batch.id),
                )
                for batch, run in rows
            ]
        )

    async def get_batch(self, batch_id: int) -> OperationalBatchDetail:
        row = (
            await self._session.execute(
                select(OperationalImportBatch, SyncRun)
                .join(SyncRun, SyncRun.id == OperationalImportBatch.sync_run_id)
                .where(OperationalImportBatch.id == batch_id)
            )
        ).one_or_none()
        if row is None:
            raise OperationalBatchNotFoundError("O batch informado não existe.")
        batch, run = row
        contexts = await self._sync_audit_contexts()
        promotions, promotion_users = await self._promotion_contexts()
        promotion = promotions.get(batch.id)
        summary = self._summary(
            batch,
            run,
            contexts.get(run.id, _AuditContext()),
            promotion,
            promotion_users.get(batch.id),
        )

        candidate_records, preview_error = await self._candidate_records(batch)
        current_promotion, current_records = await self._current_records()
        comparison = _comparison(current_promotion, current_records, candidate_records)
        eligible = batch.status == "succeeded" and promotion is None and preview_error is None
        if promotion is not None:
            reason = "Este batch já foi promovido."
        elif batch.status != "succeeded":
            reason = "Somente batches sucedidos podem ser promovidos."
        elif preview_error is not None:
            reason = preview_error
        else:
            reason = "Batch sucedido, revisado pelo pipeline e ainda não promovido."
        return OperationalBatchDetail(
            **summary.model_dump(),
            comparison=comparison,
            promotion_eligible=eligible,
            promotion_eligibility_reason=reason,
        )

    def _summary(
        self,
        batch: OperationalImportBatch,
        run: SyncRun,
        context: _AuditContext,
        promotion: OperationalPromotion | None,
        promoted_by: BatchUser | None,
    ) -> OperationalBatchSummary:
        counts, quality = _batch_counters(batch.counters)
        source = (context.source_type or "LOCAL").upper()
        return OperationalBatchSummary(
            id=batch.id,
            sync_run_id=run.id,
            started_at=batch.started_at,
            completed_at=batch.completed_at,
            source_type="ONEDRIVE" if source == "ONEDRIVE" else "LOCAL",
            source_name=run.source_name,
            source_size=run.source_size,
            source_sha256=batch.source_sha256,
            status=batch.status,
            data_counts=counts,
            quality_counts=quality,
            initiated_by=context.user,
            promotion=(
                BatchPromotionInfo(
                    id=promotion.id,
                    is_current=promotion.is_current,
                    promoted_at=promotion.completed_at,
                    promoted_by=promoted_by,
                )
                if promotion is not None
                else None
            ),
        )

    async def _candidate_records(
        self, batch: OperationalImportBatch
    ) -> tuple[dict[str, int], str | None]:
        try:
            source = await self._promotion_repository.load_batch(batch.id)
            dataset = OperationalPromotionBuilder().build(batch.id, source)
            records = dataset.summary.get("records", {})
            counts = _record_counts(records)
            counts["sales"] = len(dataset.contracts) + sum(
                record.values.get("contract_source_row_id") is None
                for record in dataset.loans
            )
            counts["revenue"] = len(dataset.installments)
            return counts, None
        except (RuntimeError, ValueError):
            return _record_counts({}), "O preview da promoção não pôde ser calculado."

    async def _current_records(
        self,
    ) -> tuple[OperationalPromotion | None, dict[str, int]]:
        promotion = await self._session.scalar(
            select(OperationalPromotion).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
        )
        if promotion is None:
            return None, _record_counts({})
        counts: dict[str, int] = {}
        for name, model in (
            ("clients", OperationalClient),
            ("contracts", OperationalContract),
            ("loans", OperationalLoan),
            ("installments", OperationalInstallment),
        ):
            counts[name] = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.promotion_id == promotion.id)
                )
                or 0
            )
        orphan_loans = int(
            await self._session.scalar(
                select(func.count())
                .select_from(OperationalLoan)
                .where(
                    OperationalLoan.promotion_id == promotion.id,
                    OperationalLoan.contract_id.is_(None),
                )
            )
            or 0
        )
        counts["sales"] = counts["contracts"] + orphan_loans
        counts["revenue"] = counts["installments"]
        return promotion, counts

    async def _sync_audit_contexts(self) -> dict[int, _AuditContext]:
        events = (
            await self._session.scalars(
                select(AppUserAuditEvent)
                .where(AppUserAuditEvent.action == "OPERATIONAL_SYNC_COMPLETED")
                .order_by(AppUserAuditEvent.created_at.desc())
            )
        ).all()
        users = await self._users({event.actor_user_id for event in events if event.actor_user_id})
        contexts: dict[int, _AuditContext] = {}
        for event in events:
            try:
                sync_run_id = int(event.details["sync_run_id"])
            except (KeyError, TypeError, ValueError):
                continue
            contexts.setdefault(
                sync_run_id,
                _AuditContext(
                    source_type=str(event.details.get("source_type") or "") or None,
                    user=users.get(event.actor_user_id),
                ),
            )
        return contexts

    async def _promotion_contexts(
        self,
    ) -> tuple[dict[int, OperationalPromotion], dict[int, BatchUser]]:
        promotions = {
            promotion.source_batch_id: promotion
            for promotion in (
                await self._session.scalars(
                    select(OperationalPromotion).where(OperationalPromotion.status == "succeeded")
                )
            ).all()
        }
        events = (
            await self._session.scalars(
                select(AppUserAuditEvent)
                .where(AppUserAuditEvent.action == "OPERATIONAL_BATCH_PROMOTED")
                .order_by(AppUserAuditEvent.created_at.desc())
            )
        ).all()
        users = await self._users({event.actor_user_id for event in events if event.actor_user_id})
        promotion_users: dict[int, BatchUser] = {}
        for event in events:
            try:
                batch_id = int(event.details["source_batch_id"])
            except (KeyError, TypeError, ValueError):
                continue
            user = users.get(event.actor_user_id)
            if user is not None:
                promotion_users.setdefault(batch_id, user)
        return promotions, promotion_users

    async def _users(self, ids: set[UUID]) -> dict[UUID, BatchUser]:
        if not ids:
            return {}
        users = (
            await self._session.scalars(select(AppUser).where(AppUser.id.in_(ids)))
        ).all()
        return {user.id: BatchUser(id=user.id, name=user.name) for user in users}


def _batch_counters(counters: dict[str, Any]) -> tuple[BatchDataCounts, BatchQualityCounts]:
    sheets = counters.get("sheets") if isinstance(counters, dict) else None
    sheets = sheets if isinstance(sheets, dict) else {}

    def sheet(name: str) -> dict[str, Any]:
        value = sheets.get(name)
        return value if isinstance(value, dict) else {}

    data = BatchDataCounts(
        bcli_cadastro=int(sheet("BCLI_CADASTRO").get("read") or 0),
        dfen_contrato=int(sheet("DFEN_CONTRATO").get("read") or 0),
        econ_emprestimos=int(sheet("ECON_EMPRESTIMOS").get("read") or 0),
        econ_amortizacoes=int(sheet("ECON_AMORTIZACOES").get("read") or 0),
    )
    quality = BatchQualityCounts(
        valid=sum(int(sheet(name).get("valid") or 0) for name in sheets),
        warning=sum(int(sheet(name).get("warning") or 0) for name in sheets),
        divergent=sum(int(sheet(name).get("divergent") or 0) for name in sheets),
        invalid=sum(int(sheet(name).get("invalid") or 0) for name in sheets),
    )
    return data, quality


def _record_counts(value: object) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    counts = {
        name: int(source.get(name) or 0)
        for name in ("clients", "contracts", "loans", "installments")
    }
    counts["sales"] = int(source.get("sales") or counts["contracts"])
    counts["revenue"] = int(source.get("revenue") or counts["installments"])
    return counts


def _comparison(
    promotion: OperationalPromotion | None,
    current: dict[str, int],
    candidate: dict[str, int],
) -> BatchComparison:
    def item(name: str) -> BatchCountComparison:
        return BatchCountComparison(
            current=current[name],
            candidate=candidate[name],
            difference=candidate[name] - current[name],
        )

    return BatchComparison(
        current_promotion_id=promotion.id if promotion else None,
        current_source_batch_id=promotion.source_batch_id if promotion else None,
        clients=item("clients"),
        contracts=item("contracts"),
        loans=item("loans"),
        installments=item("installments"),
        sales=item("sales"),
        revenue=item("revenue"),
    )
