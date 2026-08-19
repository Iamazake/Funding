from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.funding import get_contribution_analysis_repository
from app.main import app
from app.schemas.contribution_analysis import (
    ContributionAnalysisResponse,
    ContributionAnalysisSummary,
    ContributionReturnTotals,
)
from app.schemas.funding import ContributionResponse, InvestorResponse
from app.services.funding.repository import FundingNotFoundError

CONTRIBUTION_ID = UUID("20000000-0000-0000-0000-000000000001")
SOURCE_ID = UUID("30000000-0000-0000-0000-000000000002")
INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000001")


class FakeAnalysisRepository:
    async def get_analysis(self, contribution_id):
        if contribution_id.int == 0:
            raise FundingNotFoundError("Aporte não encontrado.")
        return ContributionAnalysisResponse(
            source_id=SOURCE_ID,
            contribution=ContributionResponse(
                id=CONTRIBUTION_ID,
                code="APT-0001",
                investor_id=INVESTOR_ID,
                contribution_date=date(2026, 1, 1),
                original_amount=Decimal("10000.00"),
                monthly_rate=Decimal("0.0200000000"),
                status="ACTIVE",
                notes=None,
                original_amount_editable=False,
                created_at="2026-01-01T12:00:00Z",
                updated_at="2026-01-01T12:00:00Z",
            ),
            investor=InvestorResponse(
                id=INVESTOR_ID,
                code="INV-0001",
                name="Investidor",
                status="ACTIVE",
                notes=None,
                created_at="2026-01-01T12:00:00Z",
                updated_at="2026-01-01T12:00:00Z",
            ),
            summary=ContributionAnalysisSummary(
                contribution_id=CONTRIBUTION_ID,
                contribution_code="APT-0001",
                investor_id=INVESTOR_ID,
                investor_name="Investidor",
                original_amount=Decimal("10000.00"),
                available_balance=Decimal("7000.00"),
                allocated_capital=Decimal("4000.00"),
                returned_principal=Decimal("1000.00"),
                exposed_capital=Decimal("3000.00"),
                utilization_percentage=Decimal("30.0000"),
                monthly_rate=Decimal("0.0200000000"),
                contribution_date=date(2026, 1, 1),
                status="ACTIVE",
            ),
            operations=[],
            movements=[],
            return_totals=ContributionReturnTotals(
                principal_amount=Decimal("1000.00"),
                interest_amount=Decimal("100.00"),
                discount_amount=Decimal("10.00"),
            ),
            returns=[],
        )


@contextmanager
def api_client():
    app.dependency_overrides[get_contribution_analysis_repository] = (
        lambda: FakeAnalysisRepository()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_analysis_endpoint_serializes_decimals_and_empty_state() -> None:
    with api_client() as client:
        response = client.get(f"/api/funding/contributions/{CONTRIBUTION_ID}/analysis")
    assert response.status_code == 200
    assert response.json()["summary"]["available_balance"] == "7000.00"
    assert response.json()["summary"]["utilization_percentage"] == "30.0000"
    assert response.json()["operations"] == []
    assert response.json()["returns"] == []


def test_analysis_endpoint_maps_not_found() -> None:
    with api_client() as client:
        response = client.get(
            "/api/funding/contributions/00000000-0000-0000-0000-000000000000/analysis"
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Aporte não encontrado."
