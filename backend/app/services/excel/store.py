from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic_ns
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
    OperationalImportBatch,
    SyncRun,
)
from app.services.excel.mapping import WorkbookImport
from app.services.excel.source import FileMetadata

SessionFactory = Callable[[], AsyncSession]


class OperationalStore(Protocol):
    async def start_run(self, *, forced: bool, started_at: datetime) -> int: ...

    async def record_source(
        self, run_id: int, metadata: FileMetadata, source_sha256: str
    ) -> None: ...

    async def hash_already_succeeded(self, source_sha256: str) -> bool: ...

    async def mark_skipped(self, run_id: int, *, duration_ms: int) -> None: ...

    async def mark_failed(
        self, run_id: int, error_type: str, message: str, *, duration_ms: int
    ) -> None: ...

    async def promote(
        self,
        run_id: int,
        source_sha256: str,
        imported: WorkbookImport,
        *,
        sync_started_ns: int,
    ) -> tuple[int, dict[str, Any]]: ...


class SqlAlchemyOperationalStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def start_run(self, *, forced: bool, started_at: datetime) -> int:
        async with self._session_factory() as session, session.begin():
            run = SyncRun(
                status="running",
                forced=forced,
                counters={},
                started_at=started_at,
            )
            session.add(run)
            await session.flush()
            return run.id

    async def record_source(self, run_id: int, metadata: FileMetadata, source_sha256: str) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    source_name=metadata.name,
                    source_size=metadata.size,
                    source_modified_at=metadata.modified_at,
                    source_sha256=source_sha256,
                )
            )

    async def hash_already_succeeded(self, source_sha256: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SyncRun.id)
                .where(
                    SyncRun.source_sha256 == source_sha256,
                    SyncRun.status == "succeeded",
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def mark_skipped(self, run_id: int, *, duration_ms: int) -> None:
        await self._finish_run(
            run_id,
            status="skipped_duplicate",
            counters={},
            duration_ms=duration_ms,
        )

    async def mark_failed(
        self, run_id: int, error_type: str, message: str, *, duration_ms: int
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    status="failed",
                    error_type=error_type[:80],
                    error_message=message,
                    duration_ms=duration_ms,
                    finished_at=datetime.now(UTC),
                )
            )

    async def promote(
        self,
        run_id: int,
        source_sha256: str,
        imported: WorkbookImport,
        *,
        sync_started_ns: int,
    ) -> tuple[int, dict[str, Any]]:
        counters = imported.counters()
        batch_started_at = datetime.now(UTC)
        batch_started_ns = monotonic_ns()
        async with self._session_factory() as session, session.begin():
            batch = OperationalImportBatch(
                sync_run_id=run_id,
                source_sha256=source_sha256,
                status="promoting",
                counters=counters,
                started_at=batch_started_at,
            )
            session.add(batch)
            await session.flush()

            model_by_sheet = {
                "BCLI_CADASTRO": ExcelBcliCadastroRow,
                "DFEN_CONTRATO": ExcelDfenContratoRow,
                "ECON_EMPRESTIMOS": ExcelEconEmprestimosRow,
                "ECON_AMORTIZACOES": ExcelEconAmortizacoesRow,
            }

            mirror_rows = []
            for sheet_name, rows in imported.rows.items():
                model = model_by_sheet[sheet_name]
                for row in rows:
                    mirror_rows.append(
                        model(
                            import_batch_id=batch.id,
                            source_sheet=row.source_sheet,
                            source_row_number=row.source_row_number,
                            source_row_hash=row.source_row_hash,
                            source_key=row.source_key,
                            validation_status=row.validation_status,
                            validation_errors=row.validation_errors,
                            raw_data=row.raw_data,
                            last_seen_batch_id=batch.id,
                            source_active=True,
                            **row.data,
                        )
                    )
            session.add_all(mirror_rows)
            session.add_all(
                [
                    DataInconsistency(
                        sync_run_id=run_id,
                        import_batch_id=batch.id,
                        source_sheet=issue.source_sheet,
                        source_row_number=issue.source_row_number,
                        inconsistency_type=issue.inconsistency_type,
                        field_name=issue.field_name,
                        message=issue.message,
                        masked_value=issue.masked_value,
                        severity=issue.severity,
                        review_status="pending",
                    )
                    for issue in imported.inconsistencies
                ]
            )
            completed_at = datetime.now(UTC)
            batch.status = "succeeded"
            batch.completed_at = completed_at
            batch.duration_ms = _elapsed_ms(batch_started_ns)
            await session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    status="succeeded",
                    counters=counters,
                    duration_ms=_elapsed_ms(sync_started_ns),
                    finished_at=completed_at,
                )
            )
            return batch.id, counters

    async def _finish_run(
        self,
        run_id: int,
        *,
        status: str,
        counters: dict[str, Any],
        duration_ms: int,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    status=status,
                    counters=counters,
                    duration_ms=duration_ms,
                    finished_at=datetime.now(UTC),
                )
            )


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (monotonic_ns() - started_ns) // 1_000_000)
