from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.core.database import get_session
from app.main import app


class HealthySession:
    async def execute(self, _statement):
        return HealthyResult()


class HealthyResult:
    def scalar_one(self) -> int:
        return 1


class UnhealthySession:
    async def execute(self, _statement):
        raise ConnectionError("Database unavailable")


def override_session(session) -> None:
    async def dependency() -> AsyncIterator[object]:
        yield session

    app.dependency_overrides[get_session] = dependency


def test_health_reports_api_and_database() -> None:
    override_session(HealthySession())
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api": "ok",
        "database": "connected",
    }


def test_health_hides_database_error_details() -> None:
    override_session(UnhealthySession())
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "api": "ok",
        "database": "unavailable",
    }
    assert "connection" not in response.text.lower()

