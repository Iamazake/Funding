from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.services.auth import AuthService, BootstrapConfigurationError
from app.services.excel.errors import OperationalExcelError, SourceConfigurationError
from app.services.excel.source import LocalFileSource
from app.services.excel.store import SqlAlchemyOperationalStore
from app.services.excel.sync import OperationalExcelSyncService
from app.services.operational.debt_continuity import preview_debt_continuity_migration
from app.services.operational.identity import preview_current_identity_backfill
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
    subparsers.add_parser(
        "preview-operational-identity-backfill",
        help="Audita, sem escrever, o backfill canonico da promocao atual.",
    )
    subparsers.add_parser(
        "preview-debt-continuity-migration",
        help="Audita, sem escrever, a migration de continuidade da divida.",
    )
    subparsers.add_parser(
        "bootstrap-admin",
        help="Cria idempotentemente o primeiro ADMIN usando variáveis de ambiente.",
    )
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
        return 1 if report.status == "identity_review_required" else 0
    if args.command == "preview-operational-identity-backfill":
        async with SessionFactory() as session:
            preview = await preview_current_identity_backfill(session)
        print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "preview-debt-continuity-migration":
        async with SessionFactory() as session:
            preview = await preview_debt_continuity_migration(session)
        print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "bootstrap-admin":
        settings = get_settings()
        password = settings.funding_bootstrap_admin_password
        if not (
            settings.funding_bootstrap_admin_name
            and settings.funding_bootstrap_admin_email
            and password is not None
        ):
            raise BootstrapConfigurationError(
                "Configure FUNDING_BOOTSTRAP_ADMIN_NAME, "
                "FUNDING_BOOTSTRAP_ADMIN_EMAIL e FUNDING_BOOTSTRAP_ADMIN_PASSWORD."
            )
        async with SessionFactory() as session:
            user, created = await AuthService(session).bootstrap_admin(
                settings.funding_bootstrap_admin_name,
                settings.funding_bootstrap_admin_email,
                password.get_secret_value(),
            )
        print(f"status={'created' if created else 'already_exists'}")
        print(f"user_id={user.id}")
        return 0
    return 2


async def _entrypoint(argv: list[str] | None = None) -> int:
    try:
        return await _main_async(argv)
    except (
        BootstrapConfigurationError,
        OperationalExcelError,
        OperationalPromotionError,
        ValueError,
    ) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_entrypoint(argv))


if __name__ == "__main__":
    raise SystemExit(main())
