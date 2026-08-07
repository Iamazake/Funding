from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.services.excel import store as store_module
from app.services.excel.errors import MissingRequiredSheetError, OperationalExcelError
from app.services.excel.mapping import WorkbookImport
from app.services.excel.source import FileMetadata, LocalFileSource
from app.services.excel.sync import OperationalExcelSyncService
from tests.excel_helpers import create_workbook


class InMemoryStore:
    def __init__(self, *, fail_promotion: bool = False) -> None:
        self.runs: dict[int, dict[str, Any]] = {}
        self.batches: list[WorkbookImport] = []
        self.successful_hashes: set[str] = set()
        self.fail_promotion = fail_promotion

    async def start_run(self, *, forced: bool, started_at: datetime) -> int:
        run_id = len(self.runs) + 1
        self.runs[run_id] = {
            "status": "running",
            "forced": forced,
            "started_at": started_at,
        }
        return run_id

    async def record_source(self, run_id: int, metadata: FileMetadata, source_sha256: str) -> None:
        self.runs[run_id].update(metadata=metadata, source_sha256=source_sha256)

    async def hash_already_succeeded(self, source_sha256: str) -> bool:
        return source_sha256 in self.successful_hashes

    async def mark_skipped(self, run_id: int, *, duration_ms: int) -> None:
        self.runs[run_id].update(status="skipped_duplicate", duration_ms=duration_ms)

    async def mark_failed(
        self, run_id: int, error_type: str, message: str, *, duration_ms: int
    ) -> None:
        self.runs[run_id].update(
            status="failed",
            error_type=error_type,
            message=message,
            duration_ms=duration_ms,
        )

    async def promote(
        self,
        run_id: int,
        source_sha256: str,
        imported: WorkbookImport,
        *,
        sync_started_ns: int,
    ) -> tuple[int, dict[str, Any]]:
        if self.fail_promotion:
            raise RuntimeError("synthetic persistence failure")
        self.batches.append(imported)
        self.successful_hashes.add(source_sha256)
        self.runs[run_id].update(status="succeeded", sync_started_ns=sync_started_ns)
        return len(self.batches), imported.counters()


@pytest.mark.asyncio
async def test_same_hash_is_skipped_unless_force_is_explicit(tmp_path: Path) -> None:
    original = create_workbook(tmp_path / "Cadastro de Clientes.xlsm")
    store = InMemoryStore()
    service = OperationalExcelSyncService(source=LocalFileSource(original), store=store)

    first = await service.synchronize()
    duplicate = await service.synchronize()
    forced = await service.synchronize(force=True)

    assert first.status == "succeeded"
    assert duplicate.status == "skipped_duplicate"
    assert duplicate.message == "Esta versão do arquivo já foi sincronizada."
    assert forced.status == "succeeded"
    assert store.runs[3]["forced"] is True
    assert len(store.batches) == 2


@pytest.mark.asyncio
async def test_structural_error_creates_no_batch_and_marks_run_failed(tmp_path: Path) -> None:
    original = create_workbook(
        tmp_path / "Cadastro de Clientes.xlsm", missing_sheet="ECON_AMORTIZACOES"
    )
    store = InMemoryStore()
    service = OperationalExcelSyncService(source=LocalFileSource(original), store=store)

    with pytest.raises(MissingRequiredSheetError):
        await service.synchronize()

    assert store.batches == []
    assert store.runs[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_sync_counters_include_every_sheet_and_inconsistencies(tmp_path: Path) -> None:
    original = create_workbook(
        tmp_path / "Cadastro de Clientes.xlsm",
        rows={"ECON_EMPRESTIMOS": {"COD_CONTRATO": "ORFAO"}},
    )
    store = InMemoryStore()
    report = await OperationalExcelSyncService(
        source=LocalFileSource(original), store=store
    ).synchronize()

    assert report.counters["total_rows"] == 4
    assert set(report.counters["sheets"]) == {
        "BCLI_CADASTRO",
        "DFEN_CONTRATO",
        "ECON_EMPRESTIMOS",
        "ECON_AMORTIZACOES",
    }
    assert report.counters["total_inconsistencies"] >= 1


@pytest.mark.asyncio
async def test_failed_promotion_is_reported_without_committed_batch(tmp_path: Path) -> None:
    original = create_workbook(tmp_path / "Cadastro de Clientes.xlsm")
    store = InMemoryStore(fail_promotion=True)
    service = OperationalExcelSyncService(source=LocalFileSource(original), store=store)

    with pytest.raises(OperationalExcelError):
        await service.synchronize()

    assert store.batches == []
    assert store.runs[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_sync_uses_utc_timestamps_and_monotonic_duration(tmp_path: Path) -> None:
    original = create_workbook(tmp_path / "Cadastro de Clientes.xlsm")
    store = InMemoryStore()

    await OperationalExcelSyncService(
        source=LocalFileSource(original), store=store
    ).synchronize()

    started_at = store.runs[1]["started_at"]
    assert started_at.tzinfo is not None
    assert started_at.utcoffset() == UTC.utcoffset(started_at)
    assert store.runs[1]["sync_started_ns"] > 0


def test_duration_uses_monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "monotonic_ns", lambda: 1_750_000_000)
    assert store_module._elapsed_ms(1_000_000_000) == 750
