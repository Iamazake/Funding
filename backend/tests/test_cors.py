from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.funding import get_funding_repository
from app.core.config import DEVELOPMENT_CORS_ORIGINS, Settings
from app.main import app
from app.schemas.funding import ContributionResponse

INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000001")
CONTRIBUTION_ID = UUID("20000000-0000-0000-0000-000000000001")


class CorsFundingRepository:
    async def list_contributions(self, investor_id=None):
        return []

    async def create_contribution(self, data):
        return ContributionResponse(
            id=CONTRIBUTION_ID,
            code="APT-0001",
            investor_id=data.investor_id,
            contribution_date=data.contribution_date,
            original_amount=data.original_amount,
            monthly_rate=data.monthly_rate,
            status=data.status,
            notes=data.notes,
            original_amount_editable=True,
            created_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
            updated_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
        )


@pytest.fixture
def api() -> Iterator[TestClient]:
    app.dependency_overrides[get_funding_repository] = lambda: CorsFundingRepository()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("origin", DEVELOPMENT_CORS_ORIGINS)
def test_contributions_options_get_and_post_allow_development_origins(
    api: TestClient, origin: str
) -> None:
    preflight = api.options(
        "/api/funding/contributions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    listed = api.get("/api/funding/contributions", headers={"Origin": origin})
    created = api.post(
        "/api/funding/contributions",
        headers={"Origin": origin},
        json={
            "investor_id": str(INVESTOR_ID),
            "contribution_date": str(date(2026, 8, 14)),
            "original_amount": "1000.00",
            "monthly_rate": "0.0200000000",
            "status": "ACTIVE",
            "notes": "Teste CORS",
        },
    )

    assert preflight.status_code == 200
    assert "POST" in preflight.headers["access-control-allow-methods"]
    assert listed.status_code == 200
    assert listed.json() == []
    assert created.status_code == 201
    assert created.json()["original_amount"] == "1000.00"
    for response in (preflight, listed, created):
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"


def test_production_uses_only_explicitly_configured_origins() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@localhost/funding?ssl=require",
        APP_ENV="production",
        CORS_ALLOWED_ORIGINS="https://funding.example.com, https://admin.example.com/",
        FRONTEND_BASE_URL="https://funding.example.com",
        TRUSTED_HOSTS="funding.example.com",
        _env_file=None,
    )

    assert settings.resolved_cors_origins == [
        "https://funding.example.com",
        "https://admin.example.com",
    ]
    assert not set(DEVELOPMENT_CORS_ORIGINS) & set(settings.resolved_cors_origins)
    assert settings.allow_historical_allocation_for_tests is False
    assert settings.resolved_auth_cookie_secure is True
    assert settings.resolved_trusted_hosts == ["funding.example.com"]
    assert settings.resolved_enable_api_docs is False


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"CORS_ALLOWED_ORIGINS": "*"}, "wildcard"),
        ({"CORS_ALLOWED_ORIGINS": "https://*.example.com"}, "wildcard"),
        ({"CORS_ALLOWED_ORIGINS": "http://admin.example.com"}, "HTTPS"),
        ({"AUTH_COOKIE_SECURE": False}, "AUTH_COOKIE_SECURE"),
        (
            {"FUNDING_ALLOW_HISTORICAL_ALLOCATION_FOR_TESTS": True},
            "FUNDING_ALLOW_HISTORICAL_ALLOCATION_FOR_TESTS",
        ),
        ({"FRONTEND_BASE_URL": "http://funding.example.com"}, "HTTPS"),
        (
            {
                "ONEDRIVE_REDIRECT_URI": (
                    "http://funding.example.com/api/integrations/onedrive/callback"
                )
            },
            "HTTPS",
        ),
    ],
)
def test_production_rejects_insecure_configuration(override, message) -> None:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/funding?ssl=require",
        "APP_ENV": "production",
        "FRONTEND_BASE_URL": "https://funding.example.com",
        "TRUSTED_HOSTS": "funding.example.com",
        "_env_file": None,
        **override,
    }
    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_production_requires_ssl_frontend_url_and_trusted_hosts() -> None:
    common = {
        "APP_ENV": "production",
        "FRONTEND_BASE_URL": "https://funding.example.com",
        "TRUSTED_HOSTS": "funding.example.com",
        "_env_file": None,
    }
    with pytest.raises(ValidationError, match="SSL"):
        Settings(DATABASE_URL="postgresql+asyncpg://user:password@localhost/funding", **common)
    with pytest.raises(ValidationError, match="FRONTEND_BASE_URL"):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@localhost/funding?ssl=require",
            **{**common, "FRONTEND_BASE_URL": None},
        )
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@localhost/funding?ssl=require",
            **{**common, "TRUSTED_HOSTS": None},
        )


def test_production_onedrive_requires_all_backend_only_configuration() -> None:
    with pytest.raises(ValidationError, match="ONEDRIVE_"):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@localhost/funding?ssl=require",
            APP_ENV="production",
            FRONTEND_BASE_URL="https://funding.example.com",
            TRUSTED_HOSTS="funding.example.com",
            OPERATIONAL_SOURCE="onedrive",
            _env_file=None,
        )
