from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import msal
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.api.integrations import get_onedrive_service
from app.core.config import Settings
from app.core.logging import OAuthCallbackAccessLogFilter
from app.main import app
from app.models.auth import AppUser, AppUserAuditEvent
from app.models.integrations import OneDriveOAuthState, OperationalSourceConnection
from app.schemas.integrations import OperationalSourceStatus
from app.services.excel.errors import SourceUnavailableError
from app.services.onedrive import (
    DriveItem,
    DriveResolution,
    MicrosoftGraphClient,
    MsalClient,
    OAuthStateError,
    OneDriveError,
    OneDriveFileNotFoundError,
    OneDriveIntegrationService,
    OneDriveSource,
    ReconnectRequiredError,
    TokenCipher,
    _encode_graph_path,
)

ADMIN_ID = UUID("90000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
KEY = Fernet.generate_key().decode("ascii")


def settings(**overrides) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://user:password@example.test/database",
        "APP_ENV": "test",
        "OPERATIONAL_SOURCE": "onedrive",
        "ONEDRIVE_CLIENT_ID": "client-id",
        "ONEDRIVE_CLIENT_SECRET": "client-secret",
        "ONEDRIVE_REDIRECT_URI": "https://funding.test/api/integrations/onedrive/callback",
        "ONEDRIVE_TOKEN_ENCRYPTION_KEY": KEY,
    }
    values.update(overrides)
    return Settings(**values)


def drive_item(name: str = "Cadastro de Clientes.xlsm") -> DriveItem:
    return DriveItem(
        drive_id="drive-id",
        item_id="official-item-id",
        name=name,
        size=7,
        modified_at=NOW,
        etag="etag-1",
        ctag="ctag-1",
    )


def connection() -> OperationalSourceConnection:
    return OperationalSourceConnection(
        source_type="ONEDRIVE",
        encrypted_token_cache="encrypted-cache",
        drive_id="persisted-drive-id",
        drive_item_id="persisted-item-id",
        canonical_file_name="Cadastro de Clientes.xlsm",
        canonical_file_path="/official/Cadastro de Clientes.xlsm",
        last_known_etag="etag-1",
        last_known_ctag="ctag-1",
        last_known_modified_at=NOW,
        last_known_size=7,
        status="CONNECTED",
        update_status="UNKNOWN",
    )


class FakeGraph:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.path_lookups: list[str] = []
        self.id_lookups: list[tuple[str, str]] = []
        self.targets: list[Path] = []

    async def item_by_path(self, _token: str, path: str) -> DriveItem:
        self.path_lookups.append(path)
        return drive_item()

    async def resolve_operational_item(self, _token: str, path: str) -> DriveResolution:
        self.path_lookups.append(path)
        return DriveResolution(
            item=drive_item(),
            root_relevant_names=("01. CADASTRO DE CLIENTES",),
            client_folder_name="01. CADASTRO DE CLIENTES",
            client_folder_relevant_names=("01. REMO - SOLUCOES E NEGOCIOS",),
            operational_folder_name="01. REMO - SOLUCOES E NEGOCIOS",
            file_names=("Cadastro de Clientes.xlsm",),
        )

    async def item_by_id(self, _token: str, drive_id: str, item_id: str) -> DriveItem:
        self.id_lookups.append((drive_id, item_id))
        return drive_item()

    def download(self, _token: str, _item: DriveItem, target: Path) -> str:
        self.targets.append(target)
        target.write_bytes(b"content")
        if self.fail:
            raise SourceUnavailableError("download failed")
        return "ed7002b439e9ac845f22357d822bac1444737f49ea716f7d64a89ce15e97f8a5"


class FakeMsal:
    def initiate(self, state: str):
        return {"state": state, "auth_uri": f"https://login.test/authorize?state={state}"}

    def complete(self, _flow: str, _query):
        return "access-token", "encrypted-cache"

    def acquire_silent(self, _cache: str):
        return "renewed-access-token", "renewed-encrypted-cache"


class FailingMsal(FakeMsal):
    def complete(self, _flow: str, _query):
        raise OneDriveError(
            "O client secret Microsoft é inválido. Use o Value do secret, não o Secret ID.",
            diagnostic_code="invalid_client_secret",
        )


class FakeSession:
    def __init__(self, scalar_results: list[object | None] | None = None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def scalar(self, _statement):
        return self.scalar_results.pop(0) if self.scalar_results else None


def test_token_cache_is_authenticated_encrypted_and_recovers() -> None:
    cipher = TokenCipher(KEY)
    plaintext = json.dumps({"AccessToken": {"secret": "never-plaintext"}})
    encrypted = cipher.encrypt(plaintext)
    assert plaintext not in encrypted
    assert cipher.decrypt(encrypted) == plaintext
    with pytest.raises(ReconnectRequiredError):
        cipher.decrypt(Fernet.generate_key().decode("ascii"))


def test_secret_id_is_rejected_before_starting_oauth() -> None:
    configured = settings(ONEDRIVE_CLIENT_SECRET="11111111-2222-3333-4444-555555555555")
    with pytest.raises(OneDriveError) as captured:
        MsalClient(configured, TokenCipher(KEY))
    assert captured.value.diagnostic_code == "invalid_client_secret"
    assert "Secret ID" in str(captured.value)


def test_msal_starts_oauth_with_form_post(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeApplication:
        def initiate_auth_code_flow(self, **kwargs):
            captured.update(kwargs)
            return {"state": kwargs["state"], "auth_uri": "https://login.test/authorize"}

    client = MsalClient(settings(), TokenCipher(KEY))
    monkeypatch.setattr(client, "_application", lambda _cache: FakeApplication())
    client.initiate("opaque-state")
    assert captured["response_mode"] == "form_post"
    assert captured["redirect_uri"] == settings().onedrive_redirect_uri
    assert captured["scopes"] == ["Files.Read"]


@pytest.mark.parametrize(
    "name",
    [
        "Cadastro de Clientes (2).xlsm",
        "Cadastro de Clientes1.xlsm",
        "Cadastro de Clientes-DESKTOP-ABC.xlsm",
        "Cadastro de Clientes.xlsx",
    ],
)
def test_graph_metadata_accepts_only_exact_official_name(name: str) -> None:
    payload = {
        "id": "candidate",
        "name": name,
        "size": 7,
        "lastModifiedDateTime": "2026-08-18T12:00:00Z",
        "file": {},
        "parentReference": {"driveId": "drive"},
    }
    with pytest.raises(OneDriveFileNotFoundError):
        DriveItem.from_graph(payload)


def test_path_addressing_encodes_each_utf8_segment() -> None:
    assert _encode_graph_path("/Pasta #1/Negócios 100%/Arquivo final.xlsm") == (
        "Pasta%20%231/Neg%C3%B3cios%20100%25/Arquivo%20final.xlsm"
    )


@pytest.mark.asyncio
async def test_graph_resolves_exact_hierarchy_by_ids_and_reports_similar_files() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        payloads = {
            "/v1.0/me/drive": {
                "id": "default-drive-id",
                "driveType": "personal",
                "owner": {"user": {"id": "owner-id"}},
            },
            "/v1.0/me/drive/root/children": {
                "value": [
                    {
                        "id": "wrong-root",
                        "name": "01. CADASTRO DE CLIENTE",
                        "folder": {},
                        "parentReference": {"driveId": "default-drive-id"},
                    },
                    {
                        "id": "shortcut-reference",
                        "name": "01. CADASTRO DE CLIENTES",
                        "parentReference": {"driveId": "default-drive-id"},
                        "remoteItem": {
                            "id": "client-folder",
                            "folder": {},
                            "parentReference": {"driveId": "drive-id"},
                        },
                    },
                ]
            },
            "/v1.0/drives/drive-id/items/client-folder/children": {
                "value": [
                    {
                        "id": "operational-folder",
                        "name": "01. REMO - SOLUCOES E NEGOCIOS",
                        "folder": {},
                        "parentReference": {"driveId": "drive-id"},
                    }
                ]
            },
            "/v1.0/drives/drive-id/items/operational-folder/children": {
                "value": [
                    {
                        "id": "copy",
                        "name": "Cadastro de Clientes (2).xlsm",
                        "size": 8,
                        "file": {},
                        "parentReference": {"driveId": "drive-id"},
                        "lastModifiedDateTime": "2026-08-18T12:00:00Z",
                    },
                    {
                        "id": "official-item-id",
                        "name": "Cadastro de Clientes.xlsm",
                        "size": 7,
                        "file": {},
                        "parentReference": {"driveId": "drive-id"},
                        "lastModifiedDateTime": "2026-08-18T12:00:00Z",
                        "eTag": "etag-1",
                        "cTag": "ctag-1",
                    },
                    {
                        "id": "desktop-copy",
                        "name": "Cadastro de Clientes-DESKTOP-ABC.xlsm",
                        "size": 9,
                        "file": {},
                        "parentReference": {"driveId": "drive-id"},
                        "lastModifiedDateTime": "2026-08-18T12:00:00Z",
                    },
                ]
            },
        }
        return httpx.Response(200, json=payloads[request.url.path])

    graph = MicrosoftGraphClient(transport=httpx.MockTransport(handler))
    result = await graph.resolve_operational_item(
        "secret-token",
        "/01. CADASTRO DE CLIENTES/01. REMO - SOLUCOES E NEGOCIOS/"
        "Cadastro de Clientes.xlsm",
    )
    assert requests == [
        "/v1.0/me/drive",
        "/v1.0/me/drive/root/children",
        "/v1.0/drives/drive-id/items/client-folder/children",
        "/v1.0/drives/drive-id/items/operational-folder/children",
    ]
    assert result.item.item_id == "official-item-id"
    assert result.default_drive_id == "default-drive-id"
    assert result.root_parent_drive_matches is True
    assert result.client_folder_item_type == "remoteItem"
    assert result.file_names == (
        "Cadastro de Clientes (2).xlsm",
        "Cadastro de Clientes.xlsm",
        "Cadastro de Clientes-DESKTOP-ABC.xlsm",
    )


@pytest.mark.asyncio
async def test_graph_never_selects_a_similar_file() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/me/drive":
            return httpx.Response(
                200,
                json={
                    "id": "drive-id",
                    "driveType": "personal",
                    "owner": {"user": {"id": "owner-id"}},
                },
            )
        if request.url.path.endswith("root/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "client-folder",
                            "name": "01. CADASTRO DE CLIENTES",
                            "folder": {},
                            "parentReference": {"driveId": "drive-id"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("client-folder/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "operational-folder",
                            "name": "01. REMO - SOLUCOES E NEGOCIOS",
                            "folder": {},
                            "parentReference": {"driveId": "drive-id"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {"id": "copy", "name": "Cadastro de Clientes (2).xlsm", "file": {}},
                    {"id": "copy-2", "name": "Cadastro de Clientes1.xlsm", "file": {}},
                ]
            },
        )

    graph = MicrosoftGraphClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OneDriveFileNotFoundError) as captured:
        await graph.resolve_operational_item(
            "secret-token",
            "/01. CADASTRO DE CLIENTES/01. REMO - SOLUCOES E NEGOCIOS/"
            "Cadastro de Clientes.xlsm",
        )
    assert captured.value.stage == "graph_operational_folder_children"
    assert captured.value.observed_names["file_names"] == (
        "Cadastro de Clientes (2).xlsm",
        "Cadastro de Clientes1.xlsm",
    )


@pytest.mark.asyncio
async def test_graph_follows_validated_pagination_before_exact_selection() -> None:
    root_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal root_calls
        if request.url.path == "/v1.0/me/drive":
            return httpx.Response(
                200,
                json={
                    "id": "drive-id",
                    "driveType": "personal",
                    "owner": {"user": {"id": "owner-id"}},
                },
            )
        if request.url.path.endswith("root/children"):
            root_calls += 1
            if root_calls == 1:
                return httpx.Response(
                    200,
                    json={
                        "value": [{"id": "unrelated", "name": "Outra pasta", "folder": {}}],
                        "@odata.nextLink": (
                            "https://graph.microsoft.com/v1.0/me/drive/root/children"
                            "?$skiptoken=opaque"
                        ),
                    },
                )
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "client-folder",
                            "name": "01. CADASTRO DE CLIENTES",
                            "folder": {},
                            "parentReference": {"driveId": "drive-id"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("client-folder/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "operational-folder",
                            "name": "01. REMO - SOLUCOES E NEGOCIOS",
                            "folder": {},
                            "parentReference": {"driveId": "drive-id"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "official-item-id",
                        "name": "Cadastro de Clientes.xlsm",
                        "size": 7,
                        "file": {},
                        "parentReference": {"driveId": "drive-id"},
                        "lastModifiedDateTime": "2026-08-18T12:00:00Z",
                    }
                ]
            },
        )

    result = await MicrosoftGraphClient(
        transport=httpx.MockTransport(handler)
    ).resolve_operational_item(
        "secret-token",
        "/01. CADASTRO DE CLIENTES/01. REMO - SOLUCOES E NEGOCIOS/"
        "Cadastro de Clientes.xlsm",
    )
    assert root_calls == 2
    assert result.item.item_id == "official-item-id"
    assert result.drive_type == "personal"
    assert result.root_first_page_count == 1
    assert result.root_had_next_link is True
    assert result.root_total_count == 2
    assert result.client_folder_page == 2
    assert result.root_parent_drive_matches is False


def test_onedrive_source_streams_to_approved_temp_and_removes_it() -> None:
    graph = FakeGraph()
    with OneDriveSource("secret-access-token", drive_item(), graph).stage() as staged:
        target = staged.copy_path
        assert staged.is_reader_approved()
        assert target.read_bytes() == b"content"
        assert staged.metadata.name == "Cadastro de Clientes.xlsm"
    assert not target.exists()


def test_onedrive_source_removes_partial_temp_on_error() -> None:
    graph = FakeGraph(fail=True)
    with pytest.raises(SourceUnavailableError):
        with OneDriveSource("secret-access-token", drive_item(), graph).stage():
            pass
    assert graph.targets and not graph.targets[0].exists()


@pytest.mark.asyncio
async def test_oauth_state_is_hashed_encrypted_short_lived_and_single_use() -> None:
    session = FakeSession()
    graph = FakeGraph()
    service = OneDriveIntegrationService(session, settings(), graph=graph, msal_client=FakeMsal())
    authorization_url, expires_at = await service.connect(ADMIN_ID)
    state = authorization_url.split("state=", 1)[1]
    record = next(item for item in session.added if isinstance(item, OneDriveOAuthState))
    assert record.state_hash != state and state not in record.encrypted_auth_flow
    assert timedelta(0) < expires_at - datetime.now(UTC) <= timedelta(minutes=10)

    session.scalar_results = [record, api_user("ADMIN"), None]
    await service.callback(None, {"state": state, "code": "authorization-code"})
    connection = next(
        item for item in session.added if isinstance(item, OperationalSourceConnection)
    )
    assert connection.drive_item_id == "official-item-id"
    assert connection.encrypted_token_cache == "encrypted-cache"
    assert graph.path_lookups == [settings().onedrive_file_path]
    assert record.consumed_at is not None

    session.scalar_results = [record]
    with pytest.raises(OAuthStateError):
        await service.callback(None, {"state": state, "code": "replay"})


@pytest.mark.asyncio
async def test_oauth_state_requires_its_initiating_user_to_remain_active_admin() -> None:
    record = OneDriveOAuthState(
        state_hash="unused-by-fake-session",
        encrypted_auth_flow="encrypted",
        admin_user_id=ADMIN_ID,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    service = OneDriveIntegrationService(
        FakeSession([record, None]), settings(), graph=FakeGraph(), msal_client=FakeMsal()
    )
    with pytest.raises(OAuthStateError):
        await service.callback(None, {"state": "valid", "code": "opaque"})
    assert record.consumed_at is None


@pytest.mark.asyncio
async def test_subsequent_lookup_uses_persisted_drive_item_id() -> None:
    persisted = connection()
    graph = FakeGraph()
    service = OneDriveIntegrationService(
        FakeSession([persisted]), settings(), graph=graph, msal_client=FakeMsal()
    )
    _source, item, returned_connection = await service.source(ADMIN_ID)
    assert item.item_id == "official-item-id"
    assert returned_connection is persisted
    assert graph.path_lookups == []
    assert graph.id_lookups == [("persisted-drive-id", "persisted-item-id")]
    assert persisted.encrypted_token_cache == "renewed-encrypted-cache"


@pytest.mark.parametrize(
    ("last_hash", "expected"),
    [
        ("ed7002b439e9ac845f22357d822bac1444737f49ea716f7d64a89ce15e97f8a5", "CURRENT"),
        ("0" * 64, "UPDATE_AVAILABLE"),
    ],
)
@pytest.mark.asyncio
async def test_update_check_uses_sha256_as_definitive_result(last_hash, expected) -> None:
    persisted = connection()
    last_run = SimpleNamespace(id=2, source_sha256=last_hash, finished_at=NOW)
    session = FakeSession([persisted, last_run, 2])
    service = OneDriveIntegrationService(
        session, settings(), graph=FakeGraph(), msal_client=FakeMsal()
    )
    result = await service.check_update(ADMIN_ID)
    assert result.update_status == expected
    assert persisted.last_checked_sha256.startswith("ed7002b4")


@pytest.mark.asyncio
async def test_oauth_rejects_missing_expired_and_provider_error_states() -> None:
    service = OneDriveIntegrationService(
        FakeSession(), settings(), graph=FakeGraph(), msal_client=FakeMsal()
    )
    with pytest.raises(OAuthStateError):
        await service.callback(ADMIN_ID, {})

    expired = OneDriveOAuthState(
        state_hash="irrelevant",
        encrypted_auth_flow="encrypted",
        admin_user_id=ADMIN_ID,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    expired_service = OneDriveIntegrationService(
        FakeSession([expired]), settings(), graph=FakeGraph(), msal_client=FakeMsal()
    )
    with pytest.raises(OAuthStateError):
        await expired_service.callback(ADMIN_ID, {"state": "expired"})

    cipher = TokenCipher(KEY)
    rejected = OneDriveOAuthState(
        state_hash="unused-by-fake-session",
        encrypted_auth_flow=cipher.encrypt("{}"),
        admin_user_id=ADMIN_ID,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    rejected_service = OneDriveIntegrationService(
        FakeSession([rejected, api_user("ADMIN")]),
        settings(),
        graph=FakeGraph(),
        msal_client=FakeMsal(),
    )
    with pytest.raises(OneDriveError):
        await rejected_service.callback(ADMIN_ID, {"state": "valid", "error": "access_denied"})
    assert rejected.consumed_at is not None


@pytest.mark.asyncio
async def test_callback_persists_only_sanitized_token_exchange_diagnostic() -> None:
    record = OneDriveOAuthState(
        state_hash="unused-by-fake-session",
        encrypted_auth_flow="encrypted-flow",
        admin_user_id=ADMIN_ID,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session = FakeSession([record, api_user("ADMIN")])
    service = OneDriveIntegrationService(
        session, settings(), graph=FakeGraph(), msal_client=FailingMsal()
    )
    with pytest.raises(OneDriveError):
        await service.callback(
            ADMIN_ID, {"state": "valid", "code": "authorization-code-must-not-persist"}
        )
    event = next(item for item in session.added if isinstance(item, AppUserAuditEvent))
    assert event.action == "ONEDRIVE_CONNECT_FAILED"
    assert event.details == {
        "stage": "token_exchange",
        "error_code": "invalid_client_secret",
        "error_type": "OneDriveError",
        "message": "O client secret Microsoft é inválido. Use o Value do secret, não o Secret ID.",
    }
    serialized = json.dumps(event.details)
    assert "authorization-code-must-not-persist" not in serialized
    assert "access_token" not in serialized and "refresh_token" not in serialized


def test_msal_silent_refresh_and_revocation(monkeypatch: pytest.MonkeyPatch) -> None:
    cipher = TokenCipher(KEY)
    cache = msal.SerializableTokenCache()
    encrypted = cipher.encrypt(cache.serialize())
    client = MsalClient(settings(), cipher)

    application = SimpleNamespace(
        get_accounts=lambda: [{"home_account_id": "account"}],
        acquire_token_silent=lambda scopes, account: {"access_token": "renewed"},
    )
    monkeypatch.setattr(client, "_application", lambda _cache: application)
    token, _updated = client.acquire_silent(encrypted)
    assert token == "renewed"

    application.acquire_token_silent = lambda scopes, account: None
    with pytest.raises(ReconnectRequiredError):
        client.acquire_silent(encrypted)


def test_msal_token_error_is_sanitized_without_provider_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cipher = TokenCipher(KEY)
    client = MsalClient(settings(), cipher)
    provider_description = "AADSTS7000215: invalid secret super-sensitive-provider-detail"
    application = SimpleNamespace(
        acquire_token_by_auth_code_flow=lambda flow, query: {
            "error": "invalid_client",
            "error_description": provider_description,
        }
    )
    monkeypatch.setattr(client, "_application", lambda _cache: application)
    with pytest.raises(OneDriveError) as captured:
        client.complete(cipher.encrypt("{}"), {"state": "valid", "code": "opaque"})
    assert captured.value.diagnostic_code == "invalid_client_secret"
    assert "Value do secret" in str(captured.value)
    assert provider_description not in str(captured.value)


class FakeApiService:
    async def status(self):
        return OperationalSourceStatus(
            source_type="onedrive",
            connection_status="DISCONNECTED",
            update_status="UNKNOWN",
            file_name="Cadastro de Clientes.xlsm",
            message="OneDrive não conectado.",
        )

    async def connect(self, _admin_id):
        return "https://login.test/authorize", NOW + timedelta(minutes=10)

    async def disconnect(self, _admin_id):
        return None


class FakeCallbackService(FakeApiService):
    def __init__(self, failure: OneDriveError | None = None) -> None:
        self.failure = failure

    async def callback(self, _admin_id, _query):
        if self.failure:
            raise self.failure


def api_user(role: str) -> AppUser:
    return AppUser(
        id=ADMIN_ID,
        name="Teste",
        email="teste@remo.local",
        password_hash="not-returned",
        role=role,
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )


def test_only_admin_manages_onedrive_and_responses_never_expose_tokens() -> None:
    app.dependency_overrides[get_onedrive_service] = FakeApiService
    app.dependency_overrides[get_current_user] = lambda: api_user("ADMIN")
    try:
        with TestClient(app) as client:
            status_response = client.get("/api/integrations/onedrive/status")
            connect_response = client.post("/api/integrations/onedrive/connect")
            disconnect_response = client.post("/api/integrations/onedrive/disconnect")
            assert status_response.status_code == 200
            assert connect_response.status_code == 200
            assert disconnect_response.status_code == 204
            serialized = status_response.text + connect_response.text
            assert "access_token" not in serialized and "refresh_token" not in serialized

            app.dependency_overrides[get_current_user] = lambda: api_user("ANALYST")
            assert client.get("/api/integrations/onedrive/status").status_code == 403
            assert client.post("/api/integrations/onedrive/connect").status_code == 403
            assert client.post("/api/integrations/onedrive/disconnect").status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("failure", "expected_location"),
    [
        (None, "http://localhost:5173/sincronizacao?onedrive=connected"),
        (
            OneDriveError("safe", diagnostic_code="invalid_client_secret"),
            "http://localhost:5173/sincronizacao?onedrive=error&error_code=invalid_client_secret",
        ),
    ],
)
def test_callback_redirects_to_absolute_frontend_url(failure, expected_location) -> None:
    app.dependency_overrides[get_onedrive_service] = lambda: FakeCallbackService(failure)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/integrations/onedrive/callback",
                data={"state": "safe", "code": "opaque"},
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert response.headers["location"] == expected_location
        assert "code=opaque" not in response.headers["location"]
    finally:
        app.dependency_overrides.clear()


def test_callback_rejects_query_mode_and_duplicate_sensitive_fields() -> None:
    app.dependency_overrides[get_onedrive_service] = lambda: FakeCallbackService()
    try:
        with TestClient(app) as client:
            query_response = client.get(
                "/api/integrations/onedrive/callback?state=must-not-be-used&code=secret"
            )
            duplicate_response = client.post(
                "/api/integrations/onedrive/callback",
                content="state=first&state=second&code=opaque",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert query_response.status_code == 405
        assert duplicate_response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_uvicorn_access_log_removes_entire_callback_query_string() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "127.0.0.1:12345",
            "GET",
            "/api/integrations/onedrive/callback?code=authorization-secret&state=state-secret",
            "1.1",
            405,
        ),
        exc_info=None,
    )
    OAuthCallbackAccessLogFilter().filter(record)
    rendered = record.getMessage()
    assert rendered.endswith('GET /api/integrations/onedrive/callback HTTP/1.1" 405')
    assert "authorization-secret" not in rendered
    assert "state-secret" not in rendered


def test_uvicorn_access_log_redacts_sensitive_query_values() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "127.0.0.1:12345",
            "POST",
            "/api/auth/login?password=never-log-this&page=2&session_token=secret",
            "1.1",
            200,
        ),
        exc_info=None,
    )
    OAuthCallbackAccessLogFilter().filter(record)
    rendered = record.getMessage()
    assert "never-log-this" not in rendered and "secret" not in rendered
    assert "page=2" in rendered and rendered.count("[REDACTED]") == 2
