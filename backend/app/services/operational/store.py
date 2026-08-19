from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic_ns

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPaymentMovement,
    OperationalPromotion,
    OperationalQualityLink,
)
from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
    OperationalImportBatch,
)
from app.services.excel.store import SessionFactory
from app.services.operational.identity import CanonicalIdentityResolver
from app.services.operational.promotion import (
    ExistingPromotion,
    MirrorBatch,
    OperationalDataset,
)


class SqlAlchemyOperationalPromotionRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get_batch_status(self, batch_id: int) -> str | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(OperationalImportBatch.status).where(OperationalImportBatch.id == batch_id)
            )

    async def get_succeeded_promotion(self, batch_id: int) -> ExistingPromotion | None:
        async with self._session_factory() as session:
            promotion = (
                await session.execute(
                    select(OperationalPromotion).where(
                        OperationalPromotion.source_batch_id == batch_id,
                    )
                )
            ).scalar_one_or_none()
            if promotion is None:
                return None
            return ExistingPromotion(promotion.id, promotion.summary, promotion.status)

    async def load_batch(self, batch_id: int) -> MirrorBatch:
        clients = await self._rows(ExcelBcliCadastroRow, batch_id)
        contracts = await self._rows(ExcelDfenContratoRow, batch_id)
        loans = await self._rows(ExcelEconEmprestimosRow, batch_id)
        amortizations = await self._rows(ExcelEconAmortizacoesRow, batch_id)
        inconsistencies = await self._rows(DataInconsistency, batch_id)
        return MirrorBatch(clients, contracts, loans, amortizations, inconsistencies)

    async def persist(
        self,
        batch_id: int,
        dataset: OperationalDataset,
        *,
        started_at: datetime,
        started_ns: int,
    ) -> ExistingPromotion:
        async with self._session_factory() as session, session.begin():
            existing = (
                await session.execute(
                    select(OperationalPromotion).where(
                        OperationalPromotion.source_batch_id == batch_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return ExistingPromotion(existing.id, existing.summary, existing.status)

            promotion = OperationalPromotion(
                source_batch_id=batch_id,
                status="identity_matching",
                is_current=False,
                summary=dataset.summary,
                duration_ms=0,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            session.add(promotion)
            await session.flush()

            entity_maps: dict[str, dict[int, object]] = {
                "client": {},
                "contract": {},
                "loan": {},
                "installment": {},
                "payment_movement": {},
            }
            clients = [
                OperationalClient(promotion_id=promotion.id, **record.values)
                for record in dataset.clients
            ]
            session.add_all(clients)
            await session.flush()
            entity_maps["client"] = {
                record.source_row_id: entity
                for record, entity in zip(dataset.clients, clients, strict=True)
            }

            contracts = []
            for record in dataset.contracts:
                values = dict(record.values)
                client_source_row_id = values.pop("client_source_row_id")
                client = entity_maps["client"].get(client_source_row_id)
                contracts.append(
                    OperationalContract(
                        promotion_id=promotion.id,
                        client_id=getattr(client, "id", None),
                        **values,
                    )
                )
            session.add_all(contracts)
            await session.flush()
            entity_maps["contract"] = {
                record.source_row_id: entity
                for record, entity in zip(dataset.contracts, contracts, strict=True)
            }

            loans = []
            for record in dataset.loans:
                values = dict(record.values)
                client_source_row_id = values.pop("client_source_row_id")
                contract_source_row_id = values.pop("contract_source_row_id")
                client = entity_maps["client"].get(client_source_row_id)
                contract = entity_maps["contract"].get(contract_source_row_id)
                loans.append(
                    OperationalLoan(
                        promotion_id=promotion.id,
                        client_id=getattr(client, "id", None),
                        contract_id=getattr(contract, "id", None),
                        **values,
                    )
                )
            session.add_all(loans)
            await session.flush()
            entity_maps["loan"] = {
                record.source_row_id: entity
                for record, entity in zip(dataset.loans, loans, strict=True)
            }

            installments = []
            for record in dataset.installments:
                values = dict(record.values)
                contract_source_row_id = values.pop("contract_source_row_id")
                contract = entity_maps["contract"].get(contract_source_row_id)
                installments.append(
                    OperationalInstallment(
                        promotion_id=promotion.id,
                        contract_id=getattr(contract, "id", None),
                        **values,
                    )
                )
            session.add_all(installments)
            await session.flush()
            entity_maps["installment"] = {
                record.source_row_id: entity
                for record, entity in zip(dataset.installments, installments, strict=True)
            }

            movements = []
            for record in dataset.payment_movements:
                values = dict(record.values)
                installment_source_row_id = values.pop("installment_source_row_id")
                installment = entity_maps["installment"][installment_source_row_id]
                movements.append(
                    OperationalPaymentMovement(
                        promotion_id=promotion.id,
                        installment_id=installment.id,
                        **values,
                    )
                )
            session.add_all(movements)
            await session.flush()
            entity_maps["payment_movement"] = {
                record.source_row_id: entity
                for record, entity in zip(dataset.payment_movements, movements, strict=True)
            }

            quality_links = []
            for link in dataset.quality_links:
                entity = entity_maps[link.entity_kind][link.entity_source_row_id]
                target_column = f"{link.entity_kind}_id"
                quality_links.append(
                    OperationalQualityLink(
                        promotion_id=promotion.id,
                        data_inconsistency_id=link.data_inconsistency_id,
                        issue_type=link.issue_type,
                        severity=link.severity,
                        message=link.message,
                        **{target_column: entity.id},
                    )
                )
            session.add_all(quality_links)
            identity_report = await CanonicalIdentityResolver(session).resolve(promotion)
            promotion.summary = {
                **dataset.summary,
                "identity_resolution": identity_report.as_dict(),
            }
            if identity_report.review_required:
                promotion.status = "identity_review_required"
                promotion.is_current = False
            else:
                await session.execute(
                    update(OperationalPromotion)
                    .where(
                        OperationalPromotion.is_current.is_(True),
                        OperationalPromotion.id != promotion.id,
                    )
                    .values(is_current=False)
                )
                promotion.status = "succeeded"
                promotion.is_current = True
            promotion.completed_at = datetime.now(UTC)
            promotion.duration_ms = max(0, (monotonic_ns() - started_ns) // 1_000_000)
            return ExistingPromotion(promotion.id, promotion.summary, promotion.status)

    async def _rows(self, model, batch_id: int):
        # Keep promotion reads bounded. Mirrors include JSON evidence and can be
        # large enough for a single asyncpg result frame to be interrupted by
        # remote poolers. A short-lived read session per page avoids depending
        # on one long SSL stream; retrying a SELECT page is side-effect free.
        page_size = 250
        offset = 0
        rows = []
        while True:
            for attempt in range(3):
                try:
                    async with self._session_factory() as session:
                        page = list(
                            (
                                await session.scalars(
                                    select(model)
                                    .where(model.import_batch_id == batch_id)
                                    .order_by(model.source_row_number, model.id)
                                    .limit(page_size)
                                    .offset(offset)
                                )
                            ).all()
                        )
                        await session.invalidate()
                    break
                except DBAPIError:
                    if attempt == 2:
                        raise
            rows.extend(page)
            if len(page) < page_size:
                return rows
            offset += page_size
