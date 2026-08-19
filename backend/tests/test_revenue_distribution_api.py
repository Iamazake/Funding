from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.funding import get_revenue_distribution_repository
from app.main import app
from app.schemas.revenue_distribution import (
    RevenueDistributionItemResponse,
    RevenueDistributionResponse,
)
from app.services.funding.repository import FundingConflictError, FundingNotFoundError

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
DISTRIBUTION_ID = UUID("50000000-0000-0000-0000-000000000001")
ITEM_ID = UUID("60000000-0000-0000-0000-000000000001")
SOURCE_ID = UUID("30000000-0000-0000-0000-000000000001")
ALLOCATION_ID = UUID("40000000-0000-0000-0000-000000000001")


def response(status: str, *, persisted: bool) -> RevenueDistributionResponse:
    item = RevenueDistributionItemResponse(
        id=ITEM_ID,
        source_id=SOURCE_ID,
        source_type="REMO_CAPITAL",
        allocation_id=ALLOCATION_ID,
        contribution_id=None,
        contribution_code=None,
        investor_id=None,
        investor_name=None,
        participation_rate=Decimal("0.800000000000"),
        percentage=Decimal("80.0000"),
        allocation_amount=Decimal("16000.00"),
        principal_amount=Decimal("800.00"),
        interest_amount=Decimal("80.00"),
        discount_amount=Decimal("8.00"),
        total_amount=Decimal("872.00"),
    )
    return RevenueDistributionResponse(
        id=DISTRIBUTION_ID if persisted else None,
        revenue_id=10,
        sale_id="contract:1",
        version=1 if persisted else None,
        status=status,
        funding_status="INCOMPLETE",
        reason=(
            "Funding ainda não informado. Rateio pendente."
            if status == "PENDING_FUNDING"
            else None
        ),
        effective_date=date(2026, 1, 5),
        base_amount=Decimal("20000.00"),
        principal_amount=Decimal("1000.00"),
        interest_amount=Decimal("100.00"),
        discount_amount=Decimal("10.00"),
        identified_amount=Decimal("16000.00"),
        distributed_principal=Decimal("800.00") if persisted else Decimal("0.00"),
        distributed_interest=Decimal("80.00") if persisted else Decimal("0.00"),
        distributed_discount=Decimal("8.00") if persisted else Decimal("0.00"),
        unidentified_principal=Decimal("200.00"),
        unidentified_interest=Decimal("20.00"),
        unidentified_discount=Decimal("2.00"),
        distributed_total=Decimal("872.00") if persisted else Decimal("0.00"),
        unidentified_total=Decimal("218.00"),
        primary_source_name="Capital REMO",
        source_count=1,
        items=[item] if persisted else [],
        created_at=NOW if persisted else None,
        reversed_at=NOW if status == "REVERSED" else None,
    )


class FakeRevenueRepository:
    async def get_distribution(self, revenue_id: int):
        if revenue_id == 404:
            raise FundingNotFoundError("Receita operacional não encontrada.")
        return response("PENDING_FUNDING", persisted=False)

    async def distribute(self, revenue_id: int, data):
        if revenue_id == 409:
            raise FundingConflictError("Receita sem data real de pagamento/baixa.")
        return response("DISTRIBUTED", persisted=True)

    async def reverse(self, distribution_id, data):
        return response("REVERSED", persisted=True)


@contextmanager
def api_client():
    app.dependency_overrides[get_revenue_distribution_repository] = (
        lambda: FakeRevenueRepository()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_get_pending_distribution_has_no_fictitious_items() -> None:
    with api_client() as client:
        result = client.get("/api/funding/revenue/10/distribution")
    assert result.status_code == 200
    assert result.json()["status"] == "PENDING_FUNDING"
    assert result.json()["items"] == []


def test_distribute_returns_decimal_snapshot_and_gap() -> None:
    with api_client() as client:
        result = client.post(
            "/api/funding/revenue/10/distribute",
            json={"actor": "Operador", "notes": "Processamento explícito"},
        )
    assert result.status_code == 201
    assert result.json()["status"] == "DISTRIBUTED"
    assert result.json()["items"][0]["principal_amount"] == "800.00"
    assert result.json()["unidentified_principal"] == "200.00"


def test_reversal_is_an_explicit_endpoint() -> None:
    with api_client() as client:
        result = client.post(
            f"/api/funding/revenue/distributions/{DISTRIBUTION_ID}/reversal",
            json={"actor": "Revisor", "reason": "Correção necessária"},
        )
    assert result.status_code == 200
    assert result.json()["status"] == "REVERSED"


def test_api_maps_not_found_and_conflict_without_fallback() -> None:
    with api_client() as client:
        missing = client.get("/api/funding/revenue/404/distribution")
        conflict = client.post(
            "/api/funding/revenue/409/distribute",
            json={"actor": "Operador", "notes": None},
        )
    assert missing.status_code == 404
    assert conflict.status_code == 409
