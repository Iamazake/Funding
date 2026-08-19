from __future__ import annotations

import hashlib
import json
import re
import secrets
import tempfile
import unicodedata
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx
import msal
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.auth import AppUser, AppUserAuditEvent
from app.models.integrations import OneDriveOAuthState, OperationalSourceConnection
from app.models.operational import OperationalImportBatch, SyncRun
from app.schemas.integrations import OperationalSourceStatus
from app.services.excel.errors import (
    OperationalExcelError,
    SourceConfigurationError,
    SourceUnavailableError,
)
from app.services.excel.source import FileMetadata, FileSource, StagedFile, _approved_staged_file

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["Files.Read"]
CANONICAL_FILE_NAME = "Cadastro de Clientes.xlsm"


class OneDriveError(OperationalExcelError):
    """A safe integration error that never contains credentials or download URLs."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str = "onedrive_error",
        stage: str | None = None,
        http_status: int | None = None,
        graph_error_code: str | None = None,
        observed_names: Mapping[str, tuple[str, ...]] | None = None,
        diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.stage = stage
        self.http_status = http_status
        self.graph_error_code = graph_error_code
        self.observed_names = dict(observed_names or {})
        self.diagnostics = dict(diagnostics or {})


class OAuthStateError(OneDriveError):
    pass


class ReconnectRequiredError(OneDriveError):
    pass


class OneDriveFileNotFoundError(OneDriveError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("diagnostic_code", "file_not_found")
        super().__init__(message, **kwargs)


@dataclass(frozen=True, slots=True)
class DriveItem:
    drive_id: str
    item_id: str
    name: str
    size: int
    modified_at: datetime
    etag: str | None = None
    ctag: str | None = None

    @classmethod
    def from_graph(cls, payload: Mapping[str, Any]) -> DriveItem:
        name = str(payload.get("name") or "")
        if name != CANONICAL_FILE_NAME or Path(name).suffix.casefold() != ".xlsm":
            raise OneDriveFileNotFoundError("O item configurado não é o arquivo Excel oficial.")
        if not isinstance(payload.get("file"), Mapping):
            raise OneDriveFileNotFoundError("O caminho configurado não aponta para um arquivo.")
        parent = payload.get("parentReference")
        drive_id = str(parent.get("driveId") or "") if isinstance(parent, Mapping) else ""
        item_id = str(payload.get("id") or "")
        if not drive_id or not item_id:
            raise OneDriveError("O Microsoft Graph não retornou a identidade completa do arquivo.")
        try:
            modified = datetime.fromisoformat(
                str(payload["lastModifiedDateTime"]).replace("Z", "+00:00")
            )
            size = int(payload["size"])
        except (KeyError, TypeError, ValueError) as error:
            raise OneDriveError(
                "O Microsoft Graph retornou metadados incompletos do arquivo."
            ) from error
        return cls(
            drive_id=drive_id,
            item_id=item_id,
            name=name,
            size=size,
            modified_at=modified.astimezone(UTC),
            etag=str(payload.get("eTag")) if payload.get("eTag") else None,
            ctag=str(payload.get("cTag")) if payload.get("cTag") else None,
        )


@dataclass(frozen=True, slots=True)
class DriveResolution:
    item: DriveItem
    root_relevant_names: tuple[str, ...]
    client_folder_name: str
    client_folder_relevant_names: tuple[str, ...]
    operational_folder_name: str
    file_names: tuple[str, ...]
    drive_type: str | None = None
    default_drive_id: str | None = None
    owner_type: str | None = None
    owner_identifier_hash: str | None = None
    root_first_page_count: int = 0
    root_had_next_link: bool = False
    root_total_count: int = 0
    client_folder_page: int | None = None
    root_parent_drive_matches: bool = False
    client_folder_item_type: str = "normal"


@dataclass(frozen=True, slots=True)
class DriveMetadata:
    drive_type: str | None
    drive_id: str
    owner_type: str | None
    owner_identifier_hash: str | None


@dataclass(frozen=True, slots=True)
class ChildrenListing:
    items: tuple[Mapping[str, Any], ...]
    first_page_count: int
    had_next_link: bool
    total_count: int
    exact_match_page: int | None


class TokenCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise SourceConfigurationError(
                "ONEDRIVE_TOKEN_ENCRYPTION_KEY deve ser uma chave Fernet válida."
            ) from error

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as error:
            raise ReconnectRequiredError("É necessário reconectar o OneDrive.") from error


class MsalClient:
    def __init__(self, settings: Settings, cipher: TokenCipher) -> None:
        if not settings.onedrive_client_id or not settings.onedrive_client_secret:
            raise SourceConfigurationError(
                "As credenciais do aplicativo OneDrive não estão configuradas."
            )
        if not settings.onedrive_redirect_uri:
            raise SourceConfigurationError("ONEDRIVE_REDIRECT_URI não está configurado.")
        secret_value = settings.onedrive_client_secret.get_secret_value().strip()
        if re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            secret_value,
        ):
            raise OneDriveError(
                "ONEDRIVE_CLIENT_SECRET contém um Secret ID. Configure o Value do secret.",
                diagnostic_code="invalid_client_secret",
            )
        self._settings = settings
        self._cipher = cipher

    def _application(
        self, cache: msal.SerializableTokenCache
    ) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            self._settings.onedrive_client_id,
            authority=self._settings.onedrive_authority,
            client_credential=self._settings.onedrive_client_secret.get_secret_value(),
            token_cache=cache,
        )

    def initiate(self, state: str) -> dict[str, Any]:
        cache = msal.SerializableTokenCache()
        try:
            return self._application(cache).initiate_auth_code_flow(
                scopes=GRAPH_SCOPES,
                redirect_uri=self._settings.onedrive_redirect_uri,
                state=state,
                response_mode="form_post",
            )
        except Exception as error:
            raise OneDriveError("Não foi possível iniciar a autorização Microsoft.") from error

    def complete(self, encrypted_flow: str, query: Mapping[str, str]) -> tuple[str, str]:
        try:
            flow = json.loads(self._cipher.decrypt(encrypted_flow))
            cache = msal.SerializableTokenCache()
            result = self._application(cache).acquire_token_by_auth_code_flow(flow, dict(query))
        except Exception as error:
            raise OneDriveError(
                "Não foi possível concluir a autorização Microsoft.",
                diagnostic_code="token_exchange_exception",
            ) from error
        token = result.get("access_token")
        if not token:
            raise _sanitized_msal_error(result)
        return str(token), self._cipher.encrypt(cache.serialize())

    def acquire_silent(self, encrypted_cache: str) -> tuple[str, str | None]:
        try:
            cache = msal.SerializableTokenCache()
            cache.deserialize(self._cipher.decrypt(encrypted_cache))
            application = self._application(cache)
            accounts = application.get_accounts()
            result = (
                application.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
                if accounts
                else None
            )
        except Exception as error:
            raise ReconnectRequiredError("É necessário reconectar o OneDrive.") from error
        if not result or not result.get("access_token"):
            raise ReconnectRequiredError("É necessário reconectar o OneDrive.")
        updated = self._cipher.encrypt(cache.serialize()) if cache.has_state_changed else None
        return str(result["access_token"]), updated


class GraphClientProtocol(Protocol):
    async def resolve_operational_item(
        self, access_token: str, path: str
    ) -> DriveResolution: ...
    async def item_by_path(self, access_token: str, path: str) -> DriveItem: ...
    async def item_by_id(self, access_token: str, drive_id: str, item_id: str) -> DriveItem: ...
    def download(self, access_token: str, item: DriveItem, target: Path) -> str: ...


class MicrosoftGraphClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def resolve_operational_item(
        self, access_token: str, path: str
    ) -> DriveResolution:
        segments = _configured_path_segments(path)
        if len(segments) != 3 or segments[-1] != CANONICAL_FILE_NAME:
            raise SourceConfigurationError(
                "ONEDRIVE_FILE_PATH deve conter duas pastas e o nome oficial exato."
            )
        client_folder_name, operational_folder_name, configured_file_name = segments

        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
            drive = await self._drive_metadata(client, access_token)
            root_listing = await self._children(
                client,
                access_token,
                "/me/drive/root/children",
                "graph_root_children",
                exact_name=client_folder_name,
            )
            root_children = list(root_listing.items)
            root_relevant = _relevant_names(root_children, client_folder_name)
            client_folder = _exact_folder(root_children, client_folder_name)
            root_diagnostics = {
                "drive_type": drive.drive_type,
                "default_drive_id": drive.drive_id,
                "owner_type": drive.owner_type,
                "owner_identifier_hash": drive.owner_identifier_hash,
                "root_first_page_count": root_listing.first_page_count,
                "root_had_next_link": root_listing.had_next_link,
                "root_total_count": root_listing.total_count,
                "client_folder_page": root_listing.exact_match_page,
                "root_parent_drive_matches": _parent_drive_matches(
                    root_children, drive.drive_id
                ),
            }
            if client_folder is None:
                raise OneDriveFileNotFoundError(
                    "A pasta raiz operacional configurada não foi encontrada.",
                    stage="graph_root_children",
                    observed_names={"root_relevant_names": root_relevant},
                    diagnostics=root_diagnostics,
                )
            drive_id, client_folder_id = _folder_identity(client_folder)

            client_listing = await self._children(
                client,
                access_token,
                _children_endpoint(drive_id, client_folder_id),
                "graph_client_folder_children",
                exact_name=operational_folder_name,
            )
            client_children = list(client_listing.items)
            client_relevant = _relevant_names(client_children, operational_folder_name)
            operational_folder = _exact_folder(client_children, operational_folder_name)
            if operational_folder is None:
                raise OneDriveFileNotFoundError(
                    "A subpasta operacional configurada não foi encontrada.",
                    stage="graph_client_folder_children",
                    observed_names={
                        "root_relevant_names": root_relevant,
                        "client_folder_relevant_names": client_relevant,
                    },
                    diagnostics={
                        **root_diagnostics,
                        "client_folder_item_type": _item_type(client_folder),
                    },
                )
            drive_id, operational_folder_id = _folder_identity(operational_folder)

            file_listing = await self._children(
                client,
                access_token,
                _children_endpoint(drive_id, operational_folder_id),
                "graph_operational_folder_children",
                exact_name=configured_file_name,
            )
            file_children = list(file_listing.items)
            file_names = _file_candidate_names(file_children)
            official_payload = _exact_file(file_children, configured_file_name)
            if official_payload is None:
                raise OneDriveFileNotFoundError(
                    "O arquivo oficial configurado não foi encontrado.",
                    stage="graph_operational_folder_children",
                    observed_names={
                        "root_relevant_names": root_relevant,
                        "client_folder_relevant_names": client_relevant,
                        "file_names": file_names,
                    },
                    diagnostics={
                        **root_diagnostics,
                        "client_folder_item_type": _item_type(client_folder),
                    },
                )

        return DriveResolution(
            item=DriveItem.from_graph(official_payload),
            root_relevant_names=root_relevant,
            client_folder_name=str(client_folder["name"]),
            client_folder_relevant_names=client_relevant,
            operational_folder_name=str(operational_folder["name"]),
            file_names=file_names,
            drive_type=drive.drive_type,
            default_drive_id=drive.drive_id,
            owner_type=drive.owner_type,
            owner_identifier_hash=drive.owner_identifier_hash,
            root_first_page_count=root_listing.first_page_count,
            root_had_next_link=root_listing.had_next_link,
            root_total_count=root_listing.total_count,
            client_folder_page=root_listing.exact_match_page,
            root_parent_drive_matches=root_diagnostics["root_parent_drive_matches"] is True,
            client_folder_item_type=_item_type(client_folder),
        )

    async def _drive_metadata(
        self, client: httpx.AsyncClient, access_token: str
    ) -> DriveMetadata:
        try:
            response = await client.get(
                f"{GRAPH_BASE_URL}/me/drive",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"$select": "id,driveType,owner"},
            )
        except httpx.HTTPError as error:
            raise OneDriveError(
                "Não foi possível consultar o drive pessoal.",
                diagnostic_code="graph_drive_failed",
                stage="graph_drive_metadata",
            ) from error
        if response.status_code in {401, 403}:
            raise ReconnectRequiredError(
                "É necessário reconectar o OneDrive.",
                diagnostic_code=(
                    "graph_auth_failed"
                    if response.status_code == 401
                    else "graph_permission_denied"
                ),
                stage="graph_drive_metadata",
                http_status=response.status_code,
                graph_error_code=_safe_graph_error_code(response),
            )
        try:
            response.raise_for_status()
            payload = response.json()
            drive_id = str(payload.get("id") or "")
            if not drive_id:
                raise ValueError("missing drive id")
            owner_type, owner_identifier_hash = _owner_identity(payload.get("owner"))
            return DriveMetadata(
                drive_type=str(payload.get("driveType") or "") or None,
                drive_id=drive_id,
                owner_type=owner_type,
                owner_identifier_hash=owner_identifier_hash,
            )
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OneDriveError(
                "Não foi possível consultar o drive pessoal.",
                diagnostic_code="graph_drive_failed",
                stage="graph_drive_metadata",
                http_status=response.status_code,
                graph_error_code=_safe_graph_error_code(response),
            ) from error

    async def item_by_path(self, access_token: str, path: str) -> DriveItem:
        encoded = _encode_graph_path(path)
        return await self._metadata(access_token, f"/me/drive/root:/{encoded}")

    async def item_by_id(self, access_token: str, drive_id: str, item_id: str) -> DriveItem:
        return await self._metadata(
            access_token, f"/drives/{quote(drive_id, safe='')}/items/{quote(item_id, safe='')}"
        )

    async def _metadata(self, access_token: str, endpoint: str) -> DriveItem:
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
            response = await client.get(
                f"{GRAPH_BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "$select": "id,name,size,eTag,cTag,lastModifiedDateTime,file,parentReference"
                },
            )
        if response.status_code == 404:
            raise OneDriveFileNotFoundError(
                "O arquivo oficial configurado não foi encontrado.",
                stage="graph_path_metadata",
                http_status=404,
                graph_error_code=_safe_graph_error_code(response),
            )
        if response.status_code in {401, 403}:
            raise ReconnectRequiredError(
                "É necessário reconectar o OneDrive.",
                diagnostic_code=(
                    "graph_auth_failed"
                    if response.status_code == 401
                    else "graph_permission_denied"
                ),
                stage="graph_path_metadata",
                http_status=response.status_code,
                graph_error_code=_safe_graph_error_code(response),
            )
        try:
            response.raise_for_status()
            return DriveItem.from_graph(response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise OneDriveError(
                "Não foi possível consultar o arquivo no OneDrive.",
                diagnostic_code="graph_drive_failed",
                stage="graph_path_metadata",
                http_status=response.status_code,
                graph_error_code=_safe_graph_error_code(response),
            ) from error

    async def _children(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        endpoint: str,
        stage: str,
        *,
        exact_name: str | None = None,
    ) -> ChildrenListing:
        url = f"{GRAPH_BASE_URL}{endpoint}"
        params: Mapping[str, str] | None = {
            "$select": (
                "id,name,size,eTag,cTag,lastModifiedDateTime,file,folder,parentReference,remoteItem"
            ),
            "$top": "200",
        }
        items: list[Mapping[str, Any]] = []
        first_page_count = 0
        had_next_link = False
        exact_match_page: int | None = None
        page_number = 0
        while url:
            page_number += 1
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )
            except httpx.HTTPError as error:
                raise OneDriveError(
                    "Não foi possível consultar a estrutura do OneDrive.",
                    diagnostic_code="graph_drive_failed",
                    stage=stage,
                ) from error
            if response.status_code in {401, 403}:
                raise ReconnectRequiredError(
                    "É necessário reconectar o OneDrive.",
                    diagnostic_code=(
                        "graph_auth_failed"
                        if response.status_code == 401
                        else "graph_permission_denied"
                    ),
                    stage=stage,
                    http_status=response.status_code,
                    graph_error_code=_safe_graph_error_code(response),
                )
            if response.status_code == 404:
                raise OneDriveFileNotFoundError(
                    "A estrutura configurada não foi encontrada no OneDrive.",
                    stage=stage,
                    http_status=404,
                    graph_error_code=_safe_graph_error_code(response),
                )
            try:
                response.raise_for_status()
                payload = response.json()
                values = payload.get("value")
                if not isinstance(values, list):
                    raise ValueError("invalid children payload")
                page_items = [item for item in values if isinstance(item, Mapping)]
                if page_number == 1:
                    first_page_count = len(page_items)
                if exact_match_page is None and exact_name is not None:
                    if any(item.get("name") == exact_name for item in page_items):
                        exact_match_page = page_number
                items.extend(page_items)
                next_link = payload.get("@odata.nextLink")
                if page_number == 1:
                    had_next_link = bool(next_link)
                url = _validated_graph_next_link(next_link) if next_link else ""
                params = None
            except (httpx.HTTPError, ValueError, TypeError) as error:
                raise OneDriveError(
                    "Não foi possível consultar a estrutura do OneDrive.",
                    diagnostic_code="graph_drive_failed",
                    stage=stage,
                    http_status=response.status_code,
                    graph_error_code=_safe_graph_error_code(response),
                ) from error
        return ChildrenListing(
            items=tuple(items),
            first_page_count=first_page_count,
            had_next_link=had_next_link,
            total_count=len(items),
            exact_match_page=exact_match_page,
        )

    def download(self, access_token: str, item: DriveItem, target: Path) -> str:
        endpoint = (
            f"{GRAPH_BASE_URL}/drives/{quote(item.drive_id, safe='')}/items/"
            f"{quote(item.item_id, safe='')}/content"
        )
        digest = hashlib.sha256()
        downloaded = 0
        try:
            with httpx.Client(
                timeout=httpx.Timeout(180.0, connect=30.0), follow_redirects=True
            ) as client:
                with client.stream(
                    "GET", endpoint, headers={"Authorization": f"Bearer {access_token}"}
                ) as response:
                    if response.status_code in {401, 403}:
                        raise ReconnectRequiredError("É necessário reconectar o OneDrive.")
                    if response.status_code == 404:
                        raise OneDriveFileNotFoundError(
                            "O arquivo oficial configurado não foi encontrado."
                        )
                    response.raise_for_status()
                    with target.open("xb") as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
                            downloaded += len(chunk)
        except (httpx.HTTPError, OSError) as error:
            raise SourceUnavailableError(
                "Não foi possível baixar o arquivo operacional."
            ) from error
        if downloaded != item.size:
            raise SourceUnavailableError("O download do arquivo operacional ficou incompleto.")
        return digest.hexdigest()


class OneDriveSource(FileSource):
    def __init__(
        self, access_token: str, item: DriveItem, graph: GraphClientProtocol | None = None
    ) -> None:
        self._access_token = access_token
        self._item = item
        self._graph = graph or MicrosoftGraphClient()

    @contextmanager
    def stage(self) -> Iterator[StagedFile]:
        with tempfile.TemporaryDirectory(prefix="remo-funding-operational-") as temp_dir:
            target = Path(temp_dir) / "operational.xlsm"
            sha256 = self._graph.download(self._access_token, self._item, target)
            metadata = FileMetadata(
                name=self._item.name, size=self._item.size, modified_at=self._item.modified_at
            )
            yield _approved_staged_file(target, metadata, sha256)


class OneDriveIntegrationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        graph: GraphClientProtocol | None = None,
        msal_client: MsalClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._graph = graph or MicrosoftGraphClient()
        self._cipher: TokenCipher | None = None
        self._msal = msal_client

    def _make_cipher(self) -> TokenCipher:
        key = self._settings.onedrive_token_encryption_key
        if key is None:
            raise SourceConfigurationError("ONEDRIVE_TOKEN_ENCRYPTION_KEY não está configurada.")
        return TokenCipher(key.get_secret_value())

    def _token_cipher(self) -> TokenCipher:
        if self._cipher is None:
            self._cipher = self._make_cipher()
        return self._cipher

    def _oauth_client(self) -> MsalClient:
        if self._msal is None:
            self._msal = MsalClient(self._settings, self._token_cipher())
        return self._msal

    def _configured_file_path(self) -> str:
        path = self._settings.onedrive_file_path
        if not path:
            raise SourceConfigurationError("ONEDRIVE_FILE_PATH não está configurado.")
        return path

    async def connect(self, admin_id: UUID) -> tuple[str, datetime]:
        state = secrets.token_urlsafe(32)
        try:
            self._configured_file_path()
            flow = self._oauth_client().initiate(state)
        except (SourceConfigurationError, OneDriveError) as error:
            self._audit(
                "ONEDRIVE_CONNECT_FAILED",
                admin_id,
                {
                    "stage": "configuration",
                    "error_code": getattr(error, "diagnostic_code", "configuration_error"),
                    "error_type": type(error).__name__,
                    "message": str(error),
                },
            )
            await self._session.commit()
            raise
        authorization_url = str(flow.get("auth_uri") or "")
        if not authorization_url or flow.get("state") != state:
            raise OneDriveError("Não foi possível iniciar a autorização Microsoft.")
        expires_at = datetime.now(UTC) + timedelta(
            minutes=self._settings.onedrive_oauth_state_minutes
        )
        self._session.add(
            OneDriveOAuthState(
                state_hash=_state_hash(state),
                encrypted_auth_flow=self._token_cipher().encrypt(json.dumps(flow)),
                admin_user_id=admin_id,
                expires_at=expires_at,
            )
        )
        self._audit("ONEDRIVE_CONNECT_STARTED", admin_id)
        await self._session.commit()
        return authorization_url, expires_at

    async def callback(self, admin_id: UUID | None, query: Mapping[str, str]) -> None:
        state = query.get("state")
        if not state:
            raise OAuthStateError("Estado OAuth ausente ou inválido.")
        record = await self._session.scalar(
            select(OneDriveOAuthState)
            .where(OneDriveOAuthState.state_hash == _state_hash(state))
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            record is None
            or record.consumed_at is not None
            or _as_utc(record.expires_at) <= now
        ):
            raise OAuthStateError("Estado OAuth ausente, expirado ou já utilizado.")
        if admin_id is not None and record.admin_user_id != admin_id:
            raise OAuthStateError("Estado OAuth ausente, expirado ou já utilizado.")
        admin = await self._session.scalar(
            select(AppUser).where(
                AppUser.id == record.admin_user_id,
                AppUser.role == "ADMIN",
                AppUser.status == "ACTIVE",
            )
        )
        if admin is None:
            raise OAuthStateError("Estado OAuth ausente, expirado ou já utilizado.")
        admin_id = record.admin_user_id
        record.consumed_at = now
        await self._session.commit()
        if query.get("error"):
            provider_code = _safe_provider_error(query.get("error"))
            message = (
                "A autorização Microsoft foi cancelada."
                if provider_code == "access_denied"
                else "Não foi possível concluir a autorização Microsoft."
            )
            self._audit(
                "ONEDRIVE_CONNECT_FAILED",
                admin_id,
                {
                    "stage": "provider_callback",
                    "error_code": provider_code,
                    "error_type": "MicrosoftProviderError",
                    "message": message,
                },
            )
            await self._session.commit()
            raise OneDriveError(message, diagnostic_code=provider_code)
        try:
            access_token, encrypted_cache = self._oauth_client().complete(
                record.encrypted_auth_flow, query
            )
        except (SourceConfigurationError, OneDriveError) as error:
            self._audit(
                "ONEDRIVE_CONNECT_FAILED",
                admin_id,
                {
                    "stage": "token_exchange",
                    "error_code": getattr(error, "diagnostic_code", "configuration_error"),
                    "error_type": type(error).__name__,
                    "message": str(error),
                },
            )
            await self._session.commit()
            raise
        try:
            file_path = self._configured_file_path()
            resolution = await self._graph.resolve_operational_item(access_token, file_path)
            item = resolution.item
        except OneDriveFileNotFoundError as error:
            details = _graph_audit_details(error, "graph_id_navigation")
            self._audit(
                "ONEDRIVE_FILE_NOT_FOUND",
                admin_id,
                details,
            )
            await self._session.commit()
            raise
        except OneDriveError as error:
            self._audit(
                "ONEDRIVE_CONNECT_FAILED",
                admin_id,
                _graph_audit_details(error, "graph_id_navigation"),
            )
            await self._session.commit()
            raise
        connection = await self._connection() or OperationalSourceConnection(
            source_type="ONEDRIVE", status="DISCONNECTED", update_status="UNKNOWN"
        )
        self._session.add(connection)
        connection.encrypted_token_cache = encrypted_cache
        connection.drive_id = item.drive_id
        connection.drive_item_id = item.item_id
        connection.canonical_file_name = item.name
        connection.canonical_file_path = file_path
        connection.last_known_etag = item.etag
        connection.last_known_ctag = item.ctag
        connection.last_known_modified_at = item.modified_at
        connection.last_known_size = item.size
        connection.last_checked_sha256 = None
        connection.last_checked_at = None
        connection.connected_at = now
        connection.connected_by_user_id = admin_id
        connection.updated_at = now
        connection.status = "CONNECTED"
        connection.update_status = "UNKNOWN"
        self._audit(
            "ONEDRIVE_PATH_RESOLVED",
            admin_id,
            {
                "stage": "graph_id_navigation",
                "root_relevant_names": list(resolution.root_relevant_names),
                "client_folder_name": resolution.client_folder_name,
                "client_folder_relevant_names": list(
                    resolution.client_folder_relevant_names
                ),
                "operational_folder_name": resolution.operational_folder_name,
                "file_names": list(resolution.file_names),
                "file_name": item.name,
                "drive_type": resolution.drive_type,
                "default_drive_id": resolution.default_drive_id,
                "owner_type": resolution.owner_type,
                "owner_identifier_hash": resolution.owner_identifier_hash,
                "root_first_page_count": resolution.root_first_page_count,
                "root_had_next_link": resolution.root_had_next_link,
                "root_total_count": resolution.root_total_count,
                "client_folder_page": resolution.client_folder_page,
                "root_parent_drive_matches": resolution.root_parent_drive_matches,
                "client_folder_item_type": resolution.client_folder_item_type,
            },
        )
        self._audit(
            "ONEDRIVE_CONNECTED",
            admin_id,
            {"drive_item_id": item.item_id, "file_name": item.name},
        )
        await self._session.commit()

    async def disconnect(self, admin_id: UUID) -> None:
        connection = await self._connection()
        if connection is not None:
            connection.encrypted_token_cache = None
            connection.drive_id = None
            connection.drive_item_id = None
            connection.status = "DISCONNECTED"
            connection.update_status = "UNKNOWN"
            connection.updated_at = datetime.now(UTC)
        self._audit("ONEDRIVE_DISCONNECTED", admin_id)
        await self._session.commit()

    async def source(
        self, admin_id: UUID
    ) -> tuple[OneDriveSource, DriveItem, OperationalSourceConnection]:
        connection = await self._require_connection(admin_id)
        access_token = await self._access_token(connection, admin_id)
        try:
            item = await self._graph.item_by_id(
                access_token, connection.drive_id or "", connection.drive_item_id or ""
            )
        except OneDriveFileNotFoundError:
            await self._mark_file_not_found(connection, admin_id)
            raise
        except ReconnectRequiredError:
            await self._mark_reconnect(admin_id, connection)
            raise
        return OneDriveSource(access_token, item, self._graph), item, connection

    async def check_update(self, admin_id: UUID) -> OperationalSourceStatus:
        try:
            source, item, connection = await self.source(admin_id)
            metadata_unchanged = (
                item.etag == connection.last_known_etag
                and item.ctag == connection.last_known_ctag
                and item.size == connection.last_known_size
                and item.modified_at == connection.last_known_modified_at
            )
            if metadata_unchanged and connection.last_checked_sha256:
                sha256 = connection.last_checked_sha256
            else:
                with source.stage() as staged:
                    sha256 = staged.sha256
            last_sync, batch_id = await self._last_sync()
            current = last_sync is not None and last_sync.source_sha256 == sha256
            connection.last_known_etag = item.etag
            connection.last_known_ctag = item.ctag
            connection.last_known_modified_at = item.modified_at
            connection.last_known_size = item.size
            connection.last_checked_sha256 = sha256
            connection.last_checked_at = datetime.now(UTC)
            connection.updated_at = datetime.now(UTC)
            connection.status = "CONNECTED"
            connection.update_status = "CURRENT" if current else "UPDATE_AVAILABLE"
            self._audit(
                "ONEDRIVE_UPDATE_CHECKED",
                admin_id,
                {"result": connection.update_status, "drive_item_id": item.item_id},
            )
            await self._session.commit()
            return self._status_from(connection, last_sync, batch_id)
        except ReconnectRequiredError:
            await self._mark_reconnect(admin_id)
            raise

    async def status(self) -> OperationalSourceStatus:
        last_sync, batch_id = await self._last_sync()
        if self._settings.operational_source == "local":
            configured = self._settings.operational_excel_path is not None
            return OperationalSourceStatus(
                source_type="local",
                connection_status="CONNECTED" if configured else "DISCONNECTED",
                update_status="UNKNOWN",
                file_name=CANONICAL_FILE_NAME if configured else None,
                last_sync_at=last_sync.finished_at if last_sync else None,
                last_sync_sha256=last_sync.source_sha256 if last_sync else None,
                last_batch_id=batch_id,
                message=(
                    "Fonte local configurada." if configured else "Fonte local não configurada."
                ),
            )
        connection = await self._connection()
        if connection is None:
            return OperationalSourceStatus(
                source_type="onedrive",
                connection_status="DISCONNECTED",
                update_status="UNKNOWN",
                file_name=CANONICAL_FILE_NAME,
                file_path=self._settings.onedrive_file_path,
                last_sync_at=last_sync.finished_at if last_sync else None,
                last_sync_sha256=last_sync.source_sha256 if last_sync else None,
                last_batch_id=batch_id,
                message="OneDrive não conectado.",
            )
        return self._status_from(connection, last_sync, batch_id)

    async def note_sync_result(
        self, connection: OperationalSourceConnection, item: DriveItem, sha256: str | None
    ) -> None:
        connection.last_known_etag = item.etag
        connection.last_known_ctag = item.ctag
        connection.last_known_modified_at = item.modified_at
        connection.last_known_size = item.size
        if sha256:
            connection.last_checked_sha256 = sha256
            connection.update_status = "CURRENT"
        connection.last_checked_at = datetime.now(UTC)
        connection.updated_at = datetime.now(UTC)
        await self._session.commit()

    def audit(self, action: str, admin_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit(action, admin_id, details)

    async def commit(self) -> None:
        await self._session.commit()

    async def record_error(
        self,
        action: str,
        admin_id: UUID,
        error: Exception,
        *,
        status: str | None = None,
        connection_status: str | None = None,
    ) -> None:
        connection = await self._connection()
        if connection is not None:
            if status is not None:
                connection.update_status = status
            if connection_status is not None:
                connection.status = connection_status
            connection.updated_at = datetime.now(UTC)
        self._audit(action, admin_id, {"error_type": type(error).__name__})
        await self._session.commit()

    async def _access_token(self, connection: OperationalSourceConnection, admin_id: UUID) -> str:
        if not connection.encrypted_token_cache:
            await self._mark_reconnect(admin_id, connection)
            raise ReconnectRequiredError("É necessário reconectar o OneDrive.")
        try:
            access_token, updated_cache = self._oauth_client().acquire_silent(
                connection.encrypted_token_cache
            )
        except ReconnectRequiredError:
            await self._mark_reconnect(admin_id, connection)
            raise
        if updated_cache:
            connection.encrypted_token_cache = updated_cache
            connection.updated_at = datetime.now(UTC)
            await self._session.commit()
        return access_token

    async def _require_connection(self, admin_id: UUID) -> OperationalSourceConnection:
        connection = await self._connection()
        if (
            connection is None
            or connection.status == "DISCONNECTED"
            or not connection.drive_id
            or not connection.drive_item_id
        ):
            raise OneDriveError("OneDrive não conectado.")
        if connection.status == "RECONNECT_REQUIRED":
            raise ReconnectRequiredError("É necessário reconectar o OneDrive.")
        return connection

    async def _connection(self) -> OperationalSourceConnection | None:
        return await self._session.scalar(
            select(OperationalSourceConnection).where(
                OperationalSourceConnection.source_type == "ONEDRIVE"
            )
        )

    async def _last_sync(self) -> tuple[SyncRun | None, int | None]:
        run = await self._session.scalar(
            select(SyncRun)
            .where(SyncRun.status == "succeeded")
            .order_by(SyncRun.finished_at.desc(), SyncRun.id.desc())
            .limit(1)
        )
        if run is None:
            return None, None
        batch_id = await self._session.scalar(
            select(OperationalImportBatch.id).where(OperationalImportBatch.sync_run_id == run.id)
        )
        return run, batch_id

    async def _mark_reconnect(
        self, admin_id: UUID, connection: OperationalSourceConnection | None = None
    ) -> None:
        connection = connection or await self._connection()
        if connection is not None:
            connection.status = "RECONNECT_REQUIRED"
            connection.update_status = "RECONNECT_REQUIRED"
            connection.updated_at = datetime.now(UTC)
        self._audit("ONEDRIVE_RECONNECT_REQUIRED", admin_id)
        await self._session.commit()

    async def _mark_file_not_found(
        self, connection: OperationalSourceConnection, admin_id: UUID
    ) -> None:
        connection.status = "FILE_NOT_FOUND"
        connection.update_status = "FILE_NOT_FOUND"
        connection.updated_at = datetime.now(UTC)
        self._audit(
            "ONEDRIVE_FILE_NOT_FOUND",
            admin_id,
            {"drive_item_id": connection.drive_item_id or ""},
        )
        await self._session.commit()

    def _status_from(
        self,
        connection: OperationalSourceConnection,
        last_sync: SyncRun | None,
        batch_id: int | None,
    ) -> OperationalSourceStatus:
        messages = {
            "CONNECTED": "OneDrive conectado.",
            "DISCONNECTED": "OneDrive não conectado.",
            "RECONNECT_REQUIRED": "É necessário reconectar o OneDrive.",
            "FILE_NOT_FOUND": "O arquivo oficial configurado não foi encontrado.",
        }
        return OperationalSourceStatus(
            source_type="onedrive",
            connection_status=connection.status,
            update_status=connection.update_status,
            file_name=connection.canonical_file_name or CANONICAL_FILE_NAME,
            file_path=connection.canonical_file_path or self._settings.onedrive_file_path,
            size=connection.last_known_size,
            modified_at=connection.last_known_modified_at,
            last_checked_at=connection.last_checked_at,
            last_sync_at=last_sync.finished_at if last_sync else None,
            last_sync_sha256=last_sync.source_sha256 if last_sync else None,
            last_batch_id=batch_id,
            message=messages[connection.status],
        )

    def _audit(self, action: str, admin_id: UUID, details: dict[str, object] | None = None) -> None:
        self._session.add(
            AppUserAuditEvent(
                actor_user_id=admin_id,
                action=action,
                details=details or {},
            )
        )


def _state_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _configured_path_segments(path: str) -> tuple[str, ...]:
    return tuple(segment for segment in path.replace("\\", "/").split("/") if segment)


def _encode_graph_path(path: str) -> str:
    return "/".join(quote(segment, safe="") for segment in _configured_path_segments(path))


def _children_endpoint(drive_id: str, item_id: str) -> str:
    return (
        f"/drives/{quote(drive_id, safe='')}/items/{quote(item_id, safe='')}/children"
    )


def _exact_folder(
    items: list[Mapping[str, Any]], expected_name: str
) -> Mapping[str, Any] | None:
    for item in items:
        if item.get("name") == expected_name and _is_folder(item):
            return item
    return None


def _exact_file(
    items: list[Mapping[str, Any]], expected_name: str
) -> Mapping[str, Any] | None:
    for item in items:
        if item.get("name") == expected_name and isinstance(item.get("file"), Mapping):
            return item
    return None


def _is_folder(item: Mapping[str, Any]) -> bool:
    if isinstance(item.get("folder"), Mapping):
        return True
    remote = item.get("remoteItem")
    return isinstance(remote, Mapping) and isinstance(remote.get("folder"), Mapping)


def _item_type(item: Mapping[str, Any]) -> str:
    remote = item.get("remoteItem")
    return "remoteItem" if isinstance(remote, Mapping) and remote.get("id") else "normal"


def _folder_identity(item: Mapping[str, Any]) -> tuple[str, str]:
    remote = item.get("remoteItem")
    identity = remote if isinstance(remote, Mapping) and remote.get("id") else item
    parent = identity.get("parentReference")
    drive_id = str(parent.get("driveId") or "") if isinstance(parent, Mapping) else ""
    item_id = str(identity.get("id") or "")
    if not drive_id or not item_id:
        raise OneDriveError(
            "O Microsoft Graph não retornou a identidade completa de uma pasta.",
            diagnostic_code="graph_drive_failed",
            stage="graph_id_navigation",
        )
    return drive_id, item_id


def _parent_drive_matches(items: list[Mapping[str, Any]], drive_id: str) -> bool:
    if not items:
        return False
    parent_drive_ids: list[str] = []
    for item in items:
        parent = item.get("parentReference")
        if not isinstance(parent, Mapping) or not parent.get("driveId"):
            return False
        parent_drive_ids.append(str(parent["driveId"]))
    return all(parent_drive_id == drive_id for parent_drive_id in parent_drive_ids)


def _owner_identity(owner: object) -> tuple[str | None, str | None]:
    if not isinstance(owner, Mapping):
        return None, None
    for owner_type in ("user", "group", "application", "device", "site"):
        value = owner.get(owner_type)
        if not isinstance(value, Mapping):
            continue
        identifier = str(value.get("id") or value.get("displayName") or "")
        identifier_hash = (
            hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:12]
            if identifier
            else None
        )
        return owner_type, identifier_hash
    return None, None


def _diagnostic_name_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


def _relevant_names(
    items: list[Mapping[str, Any]], expected_name: str
) -> tuple[str, ...]:
    expected_key = _diagnostic_name_key(expected_name)
    expected_tokens = set(expected_key.split())
    names: list[str] = []
    for item in items:
        name = str(item.get("name") or "")
        if not name:
            continue
        key = _diagnostic_name_key(name)
        tokens = set(key.split())
        if key == expected_key or (
            expected_tokens and len(tokens & expected_tokens) >= max(2, len(expected_tokens) - 1)
        ):
            names.append(name)
    return tuple(dict.fromkeys(names))


def _file_candidate_names(items: list[Mapping[str, Any]]) -> tuple[str, ...]:
    prefix = _diagnostic_name_key(Path(CANONICAL_FILE_NAME).stem)
    names = [
        str(item.get("name"))
        for item in items
        if item.get("name")
        and _diagnostic_name_key(Path(str(item["name"])).stem).startswith(prefix)
    ]
    return tuple(dict.fromkeys(names))


def _safe_graph_error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
        error = payload.get("error")
        value = str(error.get("code") or "") if isinstance(error, Mapping) else ""
    except (ValueError, TypeError):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else None


def _validated_graph_next_link(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid Graph next link")
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc.casefold() != "graph.microsoft.com":
        raise ValueError("invalid Graph next link")
    if not parts.path.startswith("/v1.0/"):
        raise ValueError("invalid Graph next link")
    return value


def _graph_audit_details(error: OneDriveError, default_stage: str) -> dict[str, object]:
    details: dict[str, object] = {
        "stage": error.stage or default_stage,
        "error_code": error.diagnostic_code,
        "error_type": type(error).__name__,
        "message": str(error),
    }
    if error.http_status is not None:
        details["http_status"] = error.http_status
    if error.graph_error_code:
        details["graph_error_code"] = error.graph_error_code
    details.update({key: list(names) for key, names in error.observed_names.items()})
    details.update(error.diagnostics)
    return details


def _sanitized_msal_error(result: Mapping[str, Any]) -> OneDriveError:
    provider_error = str(result.get("error") or "").casefold()
    description = str(result.get("error_description") or "").casefold()
    combined = f"{provider_error} {description}"
    if "7000222" in combined:
        return OneDriveError(
            "O client secret Microsoft expirou. Cadastre um novo valor no ambiente.",
            diagnostic_code="client_secret_expired",
        )
    if provider_error == "invalid_client" or "7000215" in combined:
        return OneDriveError(
            "O client secret Microsoft é inválido. Use o Value do secret, não o Secret ID.",
            diagnostic_code="invalid_client_secret",
        )
    if "50011" in combined:
        return OneDriveError(
            "O redirect URI não corresponde ao valor registrado no Microsoft Entra.",
            diagnostic_code="redirect_uri_mismatch",
        )
    if provider_error == "invalid_grant":
        return OneDriveError(
            "O código de autorização Microsoft expirou ou já foi utilizado. "
            "Tente conectar novamente.",
            diagnostic_code="authorization_code_invalid",
        )
    if provider_error == "access_denied":
        return OneDriveError(
            "A autorização Microsoft foi cancelada.",
            diagnostic_code="access_denied",
        )
    return OneDriveError(
        "Não foi possível concluir a autorização Microsoft.",
        diagnostic_code="token_exchange_failed",
    )


def _safe_provider_error(value: str | None) -> str:
    allowed = {"access_denied", "consent_required", "interaction_required"}
    normalized = (value or "").strip().casefold()
    return normalized if normalized in allowed else "provider_error"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
