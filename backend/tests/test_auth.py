from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.auth as auth_api_module
from app.api.auth import get_auth_service, get_current_user
from app.core.security import (
    SESSION_COOKIE_NAME,
    hash_password,
    login_rate_limiter,
    new_session_token,
    session_token_hash,
    verify_password,
)
from app.main import app
from app.models.auth import AppUser
from app.schemas.auth import UserResponse
from app.services.auth import (
    AuthenticatedSession,
    AuthenticationError,
    AuthService,
    UserConflictError,
)
from app.services.treasury import TreasuryRepository

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
ADMIN_ID = UUID("90000000-0000-0000-0000-000000000001")
ANALYST_ID = UUID("90000000-0000-0000-0000-000000000002")


def user(role: str = "ADMIN", *, active: bool = True) -> AppUser:
    return AppUser(
        id=ADMIN_ID if role == "ADMIN" else ANALYST_ID,
        name="Administrador" if role == "ADMIN" else "Analista",
        email=f"{role.lower()}@remo.local",
        password_hash=hash_password("frase senha segura"),
        role=role,
        status="ACTIVE" if active else "INACTIVE",
        last_login_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeAuthService:
    def __init__(self) -> None:
        self.users = [user("ADMIN"), user("ANALYST")]
        self.logged_out = False
        self.reset = False

    async def authenticate(self, email, password):
        found = next((item for item in self.users if item.email == email), None)
        if found is None or password != "senha correta" or found.status != "ACTIVE":
            raise AuthenticationError("E-mail ou senha inválidos.")
        return found

    async def create_session(self, current, lifetime):
        return "opaque-token", SimpleNamespace(expires_at=NOW + lifetime)

    async def resolve_session(self, token):
        if token == "expired":
            raise AuthenticationError("Sessão inválida ou expirada.")
        return AuthenticatedSession(user=self.users[0], session=SimpleNamespace())

    async def logout(self, _session):
        self.logged_out = True

    async def list_users(self):
        return [UserResponse.model_validate(item) for item in self.users]

    async def create_user(self, data, _actor):
        if any(item.email == data.email for item in self.users):
            raise UserConflictError("Já existe um usuário com este e-mail.")
        created = AppUser(
            id=UUID("90000000-0000-0000-0000-000000000003"),
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            status="ACTIVE",
            created_at=NOW,
            updated_at=NOW,
        )
        self.users.append(created)
        return UserResponse.model_validate(created)

    async def get_user(self, user_id):
        return next(item for item in self.users if item.id == user_id)

    async def update_user(self, user_id, data, _actor):
        current = await self.get_user(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(current, field, value)
        return UserResponse.model_validate(current)

    async def reset_password(self, _user_id, _data, _actor):
        self.reset = True


@pytest.fixture
def auth_api():
    service = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides.pop(get_current_user, None)
    login_rate_limiter.reset()
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()
        login_rate_limiter.reset()


@pytest.mark.parametrize("email", ["admin@remo.local", "analyst@remo.local"])
def test_admin_and_analyst_login_use_http_only_cookie(auth_api, email) -> None:
    client, _ = auth_api
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "senha correta"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] in {"ADMIN", "ANALYST"}
    assert "password" not in str(response.json()).lower()
    cookie = response.headers["set-cookie"].lower()
    assert SESSION_COOKIE_NAME in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "path=/" in cookie and "domain=" not in cookie
    assert "secure" not in cookie


@pytest.mark.parametrize(
    "email,password",
    [("missing@remo.local", "senha correta"), ("admin@remo.local", "senha errada")],
)
def test_invalid_credentials_are_generic(auth_api, email, password) -> None:
    client, _ = auth_api
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "E-mail ou senha inválidos."}


def test_inactive_user_cannot_login(auth_api) -> None:
    client, service = auth_api
    service.users[1].status = "INACTIVE"
    response = client.post(
        "/api/auth/login", json={"email": "analyst@remo.local", "password": "senha correta"}
    )
    assert response.status_code == 401


def test_expired_session_and_private_endpoint_without_authentication(auth_api) -> None:
    client, _ = auth_api
    expired = client.get("/api/auth/me", cookies={SESSION_COOKIE_NAME: "expired"})
    private = client.get("/api/operational/sales")
    assert expired.status_code == 401
    assert private.status_code == 401


def test_me_and_logout(auth_api) -> None:
    client, service = auth_api
    client.cookies.set(SESSION_COOKIE_NAME, "valid")
    me = client.get("/api/auth/me")
    logged_out = client.post("/api/auth/logout")
    assert me.status_code == 200 and me.json()["email"] == "admin@remo.local"
    assert logged_out.status_code == 204 and service.logged_out
    cleared_cookie = logged_out.headers["set-cookie"].lower()
    assert SESSION_COOKIE_NAME in cleared_cookie and "max-age=0" in cleared_cookie


def test_production_https_login_me_browser_refresh_and_logout(monkeypatch) -> None:
    service = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides.pop(get_current_user, None)
    monkeypatch.setattr(
        auth_api_module,
        "get_settings",
        lambda: SimpleNamespace(auth_session_hours=8, resolved_auth_cookie_secure=True),
    )
    login_rate_limiter.reset()
    try:
        with TestClient(app, base_url="https://testserver") as client:
            logged_in = client.post(
                "/api/auth/login",
                json={"email": "admin@remo.local", "password": "senha correta"},
            )
            cookie = logged_in.headers["set-cookie"].lower()
            assert logged_in.status_code == 200
            assert "httponly" in cookie and "secure" in cookie
            assert "samesite=lax" in cookie and "path=/" in cookie
            assert client.get("/api/auth/me").status_code == 200
            # A browser refresh reconstructs the frontend session through /me.
            assert client.get("/api/auth/me").json()["email"] == "admin@remo.local"
            logged_out = client.post("/api/auth/logout")
            cleared = logged_out.headers["set-cookie"].lower()
            assert logged_out.status_code == 204
            assert "max-age=0" in cleared and "secure" in cleared and "httponly" in cleared
    finally:
        app.dependency_overrides.clear()
        login_rate_limiter.reset()


def test_login_logout_and_login_again(auth_api) -> None:
    client, _ = auth_api
    first = client.post(
        "/api/auth/login",
        json={"email": "admin@remo.local", "password": "senha correta"},
    )
    assert first.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    second = client.post(
        "/api/auth/login",
        json={"email": "admin@remo.local", "password": "senha correta"},
    )
    assert second.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_admin_can_manage_users_and_analyst_receives_403(auth_api) -> None:
    client, service = auth_api
    app.dependency_overrides[get_current_user] = lambda: service.users[0]
    listed = client.get("/api/admin/users")
    created = client.post(
        "/api/admin/users",
        json={
            "name": "Nova Analista",
            "email": "NOVA@REMO.LOCAL",
            "password": "senha temporaria",
            "role": "ANALYST",
        },
    )
    changed = client.patch(
        f"/api/admin/users/{ANALYST_ID}", json={"role": "ADMIN", "status": "ACTIVE"}
    )
    reset = client.post(
        f"/api/admin/users/{ANALYST_ID}/reset-password",
        json={"new_password": "outra senha segura"},
    )
    assert listed.status_code == 200
    assert created.status_code == 201 and created.json()["email"] == "nova@remo.local"
    duplicate = client.post(
        "/api/admin/users",
        json={
            "name": "Duplicada",
            "email": "NOVA@REMO.LOCAL",
            "password": "senha temporaria",
            "role": "ANALYST",
        },
    )
    assert changed.status_code == 200 and changed.json()["role"] == "ADMIN"
    assert reset.status_code == 204 and service.reset
    assert duplicate.status_code == 409
    deactivated = client.patch(
        f"/api/admin/users/{ANALYST_ID}", json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200 and deactivated.json()["status"] == "INACTIVE"
    assert "password_hash" not in str(listed.json()) + str(created.json())

    app.dependency_overrides[get_current_user] = lambda: user("ANALYST")
    assert client.get("/api/admin/users").status_code == 403


def test_argon2id_session_hash_rate_limit_and_audit_guards() -> None:
    password_hash = hash_password("uma frase senha segura")
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "uma frase senha segura")
    assert not verify_password(password_hash, "senha incorreta")
    token, token_hash = new_session_token()
    assert token != token_hash and session_token_hash(token) == token_hash
    response = UserResponse.model_validate(user())
    assert "password" not in response.model_dump()
    source = inspect.getsource(AuthService)
    assert "_require_another_active_admin" in source
    assert '"PASSWORD_RESET"' in source
    assert "new_password" not in inspect.getsource(AuthService.audit)


def test_rate_limiter_is_temporary_and_does_not_store_plain_email() -> None:
    key = login_rate_limiter.key("127.0.0.1", "Pessoa@Remo.Local")
    assert "pessoa@remo.local" not in key
    for _ in range(5):
        login_rate_limiter.record_failure(key, NOW)
    assert login_rate_limiter.retry_after(key, NOW) > 0
    assert login_rate_limiter.retry_after(key, NOW + timedelta(minutes=16)) == 0


def test_new_treasury_validation_uses_authenticated_user_id() -> None:
    source = inspect.getsource(TreasuryRepository.validate_movement)
    assert "validated_by=self._actor_user_id" in source
