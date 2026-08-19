from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.treasury import get_treasury_repository
from app.main import app
from app.schemas.treasury import (
    TreasuryMovementResponse,
    TreasuryMovementsResponse,
    TreasuryPageMeta,
    TreasurySummaryResponse,
    TreasuryValidationHistory,
    TreasuryValidationResponse,
    TreasuryValidationState,
)
from app.services.treasury import TreasuryConflictError, TreasuryNotFoundError

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


def movement() -> TreasuryMovementResponse:
    return TreasuryMovementResponse(
        id="sale:contract:10",
        movement_type="SALE",
        direction="OUTFLOW",
        movement_date=date(2026, 1, 2),
        reference="contract:10",
        description="Liberação da Venda CTR-001",
        contract_code="CTR-001",
        investor_id=None,
        investor_name=None,
        inflow=Decimal("0.00"),
        outflow=Decimal("20000.00"),
        amount=Decimal("20000.00"),
        origin="operational_contracts",
        source_record_id="contract:10",
        detail_path="/vendas/contract:10",
        status="ATIVO",
    )


class FakeTreasuryRepository:
    def __init__(self) -> None:
        self.queries = []

    async def summary(self, query):
        self.queries.append(query)
        return TreasurySummaryResponse(
            period_from=query.period_from,
            period_to=query.period_to,
            total_inflows=Decimal("102000.00"),
            total_outflows=Decimal("20000.00"),
            known_net_flow=Decimal("82000.00"),
            contributions=Decimal("100000.00"),
            revenues=Decimal("2000.00"),
            sales=Decimal("20000.00"),
            contribution_count=1,
            revenue_count=1,
            sale_count=1,
            undated_movement_count=0,
            unknown_amount_count=0,
            pending_validation_count=1,
            validated_count=0,
            divergent_count=0,
            net_difference_amount=Decimal("0.00"),
        )

    async def movements(self, query):
        self.queries.append(query)
        return TreasuryMovementsResponse(
            items=[movement()],
            pagination=TreasuryPageMeta(
                page=query.page, page_size=query.page_size, total=1, pages=1
            ),
        )

    async def get_movement(self, movement_id):
        if movement_id == "missing":
            raise TreasuryNotFoundError("Movimento de Tesouraria não encontrado.")
        return movement()

    async def get_validation(self, movement_id):
        if movement_id == "missing":
            raise TreasuryNotFoundError("Movimento de Tesouraria não encontrado.")
        return TreasuryValidationState(movement_key=movement_id, status="PENDING", current=None)

    async def validate_movement(self, movement_id, data):
        if movement_id == "missing":
            raise TreasuryNotFoundError("Movimento de Tesouraria não encontrado.")
        if data.observed_amount != Decimal("20000.00") and not data.justification:
            raise TreasuryConflictError("Justificativa é obrigatória.")
        difference = data.observed_amount - Decimal("20000.00")
        return validation(movement_id, data.observed_amount, difference)

    async def validation_history(self, movement_id):
        if movement_id == "missing":
            raise TreasuryNotFoundError("Movimento de Tesouraria não encontrado.")
        return TreasuryValidationHistory(
            movement_key=movement_id,
            items=[validation(movement_id, Decimal("20000.00"), Decimal("0.00"))],
        )


def validation(
    movement_key: str,
    observed: Decimal,
    difference: Decimal,
) -> TreasuryValidationResponse:
    return TreasuryValidationResponse(
        id="70000000-0000-0000-0000-000000000001",
        movement_key=movement_key,
        version=1,
        is_current=True,
        supersedes_validation_id=None,
        movement_type="SALE",
        direction="OUTFLOW",
        system_amount_snapshot=Decimal("20000.00"),
        system_date_snapshot=date(2026, 1, 2),
        observed_amount=observed,
        observed_date=date(2026, 1, 3),
        difference_amount=difference,
        status="VALIDATED" if difference == 0 else "DIVERGENT",
        bank_reference="EXTRATO-1",
        justification="Conferido" if difference else None,
        validated_at=NOW,
        validated_by=None,
        created_at=NOW,
    )


@contextmanager
def api_client(repository):
    app.dependency_overrides[get_treasury_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_summary_and_movements_support_real_filters_and_decimal_strings() -> None:
    repository = FakeTreasuryRepository()
    with api_client(repository) as client:
        summary = client.get(
            "/api/treasury/summary",
            params={"period_from": "2026-01-01", "period_to": "2026-01-31"},
        )
        movements = client.get(
            "/api/treasury/movements",
            params={
                "page": 2,
                "page_size": 25,
                "movement_type": "SALE",
                "search": "CTR",
                "installment": "03",
                "eligible_for_validation": True,
            },
        )
    assert summary.status_code == 200
    assert summary.json()["known_net_flow"] == "82000.00"
    assert movements.status_code == 200
    assert movements.json()["items"][0]["outflow"] == "20000.00"
    assert repository.queries[0].period_from == date(2026, 1, 1)
    assert repository.queries[1].movement_type == "SALE"
    assert repository.queries[1].installment == "03"
    assert repository.queries[1].eligible_for_validation is True


def test_detail_empty_and_api_errors_are_explicit() -> None:
    repository = FakeTreasuryRepository()
    with api_client(repository) as client:
        detail = client.get("/api/treasury/movements/sale:contract:10")
        missing = client.get("/api/treasury/movements/missing")
        invalid_period = client.get(
            "/api/treasury/summary",
            params={"period_from": "2026-02-01", "period_to": "2026-01-01"},
        )
    assert detail.status_code == 200
    assert missing.status_code == 404
    assert invalid_period.status_code == 422


def test_empty_movement_page_is_not_filled_with_mock_data() -> None:
    class EmptyRepository(FakeTreasuryRepository):
        async def movements(self, query):
            return TreasuryMovementsResponse(
                items=[],
                pagination=TreasuryPageMeta(
                    page=query.page, page_size=query.page_size, total=0, pages=0
                ),
            )

    with api_client(EmptyRepository()) as client:
        response = client.get("/api/treasury/movements")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_validation_endpoints_cover_pending_creation_and_history() -> None:
    repository = FakeTreasuryRepository()
    with api_client(repository) as client:
        pending = client.get("/api/treasury/movements/sale:contract:10/validation")
        created = client.post(
            "/api/treasury/movements/sale:contract:10/validation",
            json={
                "observed_amount": "20000.00",
                "observed_date": "2026-01-03",
                "bank_reference": "EXTRATO-1",
                "justification": None,
            },
        )
        history = client.get(
            "/api/treasury/movements/sale:contract:10/validation-history"
        )
    assert pending.json() == {
        "movement_key": "sale:contract:10",
        "status": "PENDING",
        "current": None,
    }
    assert created.status_code == 201
    assert created.json()["status"] == "VALIDATED"
    assert created.json()["validated_by"] is None
    assert history.json()["items"][0]["system_amount_snapshot"] == "20000.00"


def test_validation_api_rejects_orphan_and_missing_justification() -> None:
    repository = FakeTreasuryRepository()
    with api_client(repository) as client:
        missing = client.post(
            "/api/treasury/movements/missing/validation",
            json={"observed_amount": "10.00", "observed_date": "2026-01-03"},
        )
        divergent_without_reason = client.post(
            "/api/treasury/movements/sale:contract:10/validation",
            json={"observed_amount": "19999.00", "observed_date": "2026-01-03"},
        )
    assert missing.status_code == 404
    assert divergent_without_reason.status_code == 409
