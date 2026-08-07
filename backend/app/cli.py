from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.services.excel.errors import OperationalExcelError, SourceConfigurationError
from app.services.excel.source import LocalFileSource
from app.services.excel.store import SqlAlchemyOperationalStore
from app.services.excel.sync import OperationalExcelSyncService
from app.services.operational.promotion import (
    OperationalPromotionError,
    OperationalPromotionService,
)
from app.services.operational.store import SqlAlchemyOperationalPromotionRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser(
        "sync-operational-excel",
        help="Sincroniza uma cópia segura do Cadastro de Clientes.",
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa explicitamente uma versão já sincronizada.",
    )
    promote_parser = subparsers.add_parser(
        "promote-operational-batch",
        help="Promove explicitamente um batch sucedido para a camada normalizada.",
    )
    promote_parser.add_argument("batch_id", type=int, help="ID explícito do batch de origem.")
    return parser


async def _run_sync(*, force: bool) -> int:
    settings = get_settings()
    if settings.operational_excel_path is None:
        raise SourceConfigurationError("OPERATIONAL_EXCEL_PATH não está configurado.")
    service = OperationalExcelSyncService(
        source=LocalFileSource(settings.operational_excel_path),
        store=SqlAlchemyOperationalStore(SessionFactory),
    )
    report = await service.synchronize(force=force)
    print(report.message)
    print(f"sync_run_id={report.sync_run_id}")
    if report.import_batch_id is not None:
        print(f"import_batch_id={report.import_batch_id}")
    if report.counters:
        print(f"linhas={report.counters['total_rows']}")
        print(f"inconsistencias={report.counters['total_inconsistencies']}")
    return 0


async def _main_async(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sync-operational-excel":
        return await _run_sync(force=args.force)
    if args.command == "promote-operational-batch":
        service = OperationalPromotionService(
            SqlAlchemyOperationalPromotionRepository(SessionFactory)
        )
        report = await service.promote(args.batch_id)
        print(f"status={report.status}")
        print(f"promotion_id={report.promotion_id}")
        print(f"source_batch_id={report.source_batch_id}")
        print(f"idempotent={str(report.idempotent).lower()}")
        return 0
    return 2


async def _entrypoint(argv: list[str] | None = None) -> int:
    try:
        return await _main_async(argv)
    except (OperationalExcelError, OperationalPromotionError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_entrypoint(argv))


if __name__ == "__main__":
    raise SystemExit(main())
