from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic_ns
from typing import Any

from app.services.excel.errors import OperationalExcelError, WorkbookStructureError
from app.services.excel.mapping import WorkbookMapper
from app.services.excel.reader import OperationalWorkbookReader
from app.services.excel.source import FileSource
from app.services.excel.store import OperationalStore


@dataclass(frozen=True, slots=True)
class SyncReport:
    sync_run_id: int
    status: str
    import_batch_id: int | None = None
    counters: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class OperationalExcelSyncService:
    def __init__(
        self,
        *,
        source: FileSource,
        store: OperationalStore,
        mapper: WorkbookMapper | None = None,
    ) -> None:
        self._source = source
        self._store = store
        self._mapper = mapper or WorkbookMapper()

    async def synchronize(self, *, force: bool = False) -> SyncReport:
        started_ns = monotonic_ns()
        run_id = await self._store.start_run(
            forced=force,
            started_at=datetime.now(UTC),
        )
        try:
            with self._source.stage() as staged:
                await self._store.record_source(run_id, staged.metadata, staged.sha256)
                if not force and await self._store.hash_already_succeeded(staged.sha256):
                    await self._store.mark_skipped(
                        run_id,
                        duration_ms=_elapsed_ms(started_ns),
                    )
                    return SyncReport(
                        sync_run_id=run_id,
                        status="skipped_duplicate",
                        message="Esta versão do arquivo já foi sincronizada.",
                    )

                with OperationalWorkbookReader(staged) as reader:
                    # No batch exists until all four sheets pass structural validation.
                    reader.validate_layout()
                    imported = self._mapper.map(reader)

                batch_id, counters = await self._store.promote(
                    run_id,
                    staged.sha256,
                    imported,
                    sync_started_ns=started_ns,
                )
                return SyncReport(
                    sync_run_id=run_id,
                    import_batch_id=batch_id,
                    status="succeeded",
                    counters=counters,
                    message="Sincronização operacional concluída.",
                )
        except WorkbookStructureError as exc:
            await self._store.mark_failed(
                run_id,
                type(exc).__name__,
                str(exc),
                duration_ms=_elapsed_ms(started_ns),
            )
            raise
        except OperationalExcelError as exc:
            await self._store.mark_failed(
                run_id,
                type(exc).__name__,
                str(exc),
                duration_ms=_elapsed_ms(started_ns),
            )
            raise
        except Exception as exc:
            safe_message = "Falha interna durante a sincronização operacional."
            await self._store.mark_failed(
                run_id,
                type(exc).__name__,
                safe_message,
                duration_ms=_elapsed_ms(started_ns),
            )
            raise OperationalExcelError(safe_message) from exc


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (monotonic_ns() - started_ns) // 1_000_000)
