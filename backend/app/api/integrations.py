from __future__ import annotations

from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentAdmin
from app.core.config import get_settings
from app.core.database import SessionFactory, get_session
from app.schemas.integrations import (
    OneDriveConnectResponse,
    OperationalSourceStatus,
    SyncResponse,
)
from app.services.excel.errors import OperationalExcelError, SourceConfigurationError
from app.services.excel.source import LocalFileSource
from app.services.excel.store import SqlAlchemyOperationalStore
from app.services.excel.sync import OperationalExcelSyncService
from app.services.onedrive import (
    OAuthStateError,
    OneDriveError,
    OneDriveFileNotFoundError,
    OneDriveIntegrationService,
    ReconnectRequiredError,
)

router = APIRouter(prefix="/api/integrations/onedrive", tags=["integrations"])
MAX_OAUTH_CALLBACK_BODY_BYTES = 32 * 1024
OAUTH_CALLBACK_FIELDS = {
    "state",
    "code",
    "error",
    "error_description",
    "error_uri",
    "session_state",
}


def get_onedrive_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OneDriveIntegrationService:
    return OneDriveIntegrationService(session, get_settings())


Service = Annotated[OneDriveIntegrationService, Depends(get_onedrive_service)]


@router.get("/status", response_model=OperationalSourceStatus)
async def integration_status(_: CurrentAdmin, service: Service) -> OperationalSourceStatus:
    return await service.status()


@router.post("/connect", response_model=OneDriveConnectResponse)
async def connect(admin: CurrentAdmin, service: Service) -> OneDriveConnectResponse:
    try:
        authorization_url, expires_at = await service.connect(admin.id)
        return OneDriveConnectResponse(authorization_url=authorization_url, expires_at=expires_at)
    except (SourceConfigurationError, OneDriveError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/callback", response_model=None)
async def callback(request: Request, service: Service):
    form = await _oauth_callback_form(request)
    try:
        # A cross-site form POST does not carry our SameSite=Lax session cookie.
        # The one-time state identifies the initiating admin, who is revalidated
        # by the service before the authorization code is exchanged.
        await service.callback(None, form)
    except OAuthStateError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OneDriveError as error:
        return RedirectResponse(
            _post_auth_url("error", error.diagnostic_code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except SourceConfigurationError:
        return RedirectResponse(
            _post_auth_url("error", "configuration_error"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(_post_auth_url("connected"), status_code=status.HTTP_303_SEE_OTHER)


async def _oauth_callback_form(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Formato de callback OAuth inválido.")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_OAUTH_CALLBACK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Callback OAuth excede o limite permitido.")
    try:
        pairs = parse_qsl(
            body.decode("utf-8"),
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=16,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Callback OAuth inválido.") from error

    result: dict[str, str] = {}
    for key, value in pairs:
        if key not in OAUTH_CALLBACK_FIELDS:
            continue
        if key in result:
            raise HTTPException(status_code=400, detail="Callback OAuth inválido.")
        result[key] = value
    return result


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(admin: CurrentAdmin, service: Service) -> None:
    await service.disconnect(admin.id)


@router.post("/check", response_model=OperationalSourceStatus)
async def check_update(admin: CurrentAdmin, service: Service) -> OperationalSourceStatus:
    if get_settings().operational_source != "onedrive":
        raise HTTPException(status_code=409, detail="A fonte operacional ativa não é OneDrive.")
    try:
        return await service.check_update(admin.id)
    except ReconnectRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OneDriveFileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (SourceConfigurationError, OneDriveError, OperationalExcelError) as error:
        await service.record_error("ONEDRIVE_UPDATE_CHECK_FAILED", admin.id, error, status="ERROR")
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/sync", response_model=SyncResponse)
async def synchronize(
    admin: CurrentAdmin,
    service: Service,
    forced: Annotated[bool, Query()] = False,
) -> SyncResponse:
    settings = get_settings()
    connection = None
    item = None
    try:
        if settings.operational_source == "local":
            source = LocalFileSource(settings.operational_excel_path)
        else:
            source, item, connection = await service.source(admin.id)
        service.audit(
            "OPERATIONAL_SYNC_STARTED",
            admin.id,
            {"source_type": settings.operational_source, "forced": forced},
        )
        await service.commit()
        report = await OperationalExcelSyncService(
            source=source,
            store=SqlAlchemyOperationalStore(SessionFactory),
        ).synchronize(force=forced)
        if connection is not None and item is not None:
            await service.note_sync_result(connection, item, await _run_sha(report.sync_run_id))
        service.audit(
            "OPERATIONAL_SYNC_COMPLETED",
            admin.id,
            {
                "source_type": settings.operational_source,
                "sync_run_id": report.sync_run_id,
                "status": report.status,
            },
        )
        await service.commit()
        return SyncResponse(
            sync_run_id=report.sync_run_id,
            import_batch_id=report.import_batch_id,
            status=report.status,
            counters=report.counters,
            message=report.message,
        )
    except ReconnectRequiredError as error:
        await service.record_error(
            "OPERATIONAL_SYNC_FAILED",
            admin.id,
            error,
            status="RECONNECT_REQUIRED",
            connection_status="RECONNECT_REQUIRED",
        )
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OneDriveFileNotFoundError as error:
        await service.record_error(
            "OPERATIONAL_SYNC_FAILED",
            admin.id,
            error,
            status="FILE_NOT_FOUND",
            connection_status="FILE_NOT_FOUND",
        )
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (SourceConfigurationError, OneDriveError, OperationalExcelError) as error:
        service.audit(
            "OPERATIONAL_SYNC_FAILED",
            admin.id,
            {"source_type": settings.operational_source, "error_type": type(error).__name__},
        )
        await service.commit()
        raise HTTPException(status_code=422, detail=str(error)) from error


async def _run_sha(sync_run_id: int) -> str | None:
    from app.models.operational import SyncRun

    async with SessionFactory() as session:
        run = await session.get(SyncRun, sync_run_id)
        return run.source_sha256 if run else None


def _post_auth_url(result: str, error_code: str | None = None) -> str:
    configured = f"{get_settings().resolved_frontend_base_url}/sincronizacao"
    parts = urlsplit(configured)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["onedrive"] = result
    if error_code:
        query["error_code"] = error_code
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
