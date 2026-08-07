from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.api.operational import get_operational_repository
from app.main import app
from app.schemas.operational import (
    PageMeta,
    QualityMessage,
    RevenueDetail,
    RevenueItem,
    RevenuePage,
    RevenueSummary,
    SaleDetail,
    SaleItem,
    SalesPage,
    SaleSummary,
)


def sale_item(**updates: Any) -> SaleItem:
    values = {
        "id": "contract:10",
        "contract_code": "CTR-MASKED",
        "client_name": "Cliente Operacional",
        "source_client_code": "CLI-001",
        "operation_date": date(2026, 1, 2),
        "release_date": date(2026, 1, 3),
        "first_due_date": date(2026, 2, 2),
        "term": 12,
        "principal": Decimal("1000.10"),
        "iof": Decimal("10.01"),
        "financed_amount": Decimal("1010.11"),
        "installment_amount": Decimal("90.00"),
        "released_amount": Decimal("1000.10"),
        "interest_rate": Decimal("0.0123456789"),
        "irr_rate": Decimal("0.0200000000"),
        "cet_monthly_rate": Decimal("0.0300000000"),
        "status": "ATIVO",
        "data_quality_status": "WARNING",
        "warning_count": 2,
        "divergence_count": 0,
    }
    values.update(updates)
    return SaleItem(**values)


def revenue_item(**updates: Any) -> RevenueItem:
    values = {
        "id": 30,
        "contract_code": "CTR-MASKED",
        "client_name": "Cliente Operacional",
        "installment_code": "1",
        "due_date": date(2026, 2, 2),
        "payment_date": date(2026, 2, 3),
        "expected_amount": Decimal("90.00"),
        "paid_amount": Decimal("45.00"),
        "principal_component": Decimal("40.00"),
        "interest_component": Decimal("5.00"),
        "discount_amount": Decimal("0.00"),
        "installment_status": "PARCIAL",
        "situation": "EM ABERTO",
        "anticipation_marker": "N",
        "data_quality_status": "DIVERGENT",
        "warning_count": 0,
        "divergence_count": 1,
    }
    values.update(updates)
    return RevenueItem(**values)


class FakeOperationalRepository:
    def __init__(self) -> None:
        self.sales_query = None
        self.revenue_query = None

    async def list_sales(self, query):
        self.sales_query = query
        return SalesPage(
            items=[sale_item()],
            pagination=PageMeta(page=query.page, page_size=query.page_size, total=1459, pages=59),
            summary=SaleSummary(
                total_contracts=1459,
                principal=Decimal("1000.10"),
                released_amount=Decimal("1000.10"),
                financed_amount=Decimal("1010.11"),
                warning_contracts=10,
                divergent_contracts=3,
            ),
        )

    async def get_sale(self, sale_id: str):
        if sale_id == "missing":
            return None
        item = sale_item(
            id=sale_id,
            data_quality_status="DIVERGENT",
            warning_count=1,
            divergence_count=1,
        )
        return SaleDetail(
            **item.model_dump(),
            warnings=[
                QualityMessage(type="invalid_date", severity="WARNING", message="Data inválida.")
            ],
            divergences=[
                QualityMessage(
                    type="orphan_loan",
                    severity="DIVERGENT",
                    message="Empréstimo sem contrato correspondente.",
                )
            ],
        )

    async def list_revenue(self, query):
        self.revenue_query = query
        return RevenuePage(
            items=[revenue_item()],
            pagination=PageMeta(page=query.page, page_size=query.page_size, total=12120, pages=485),
            summary=RevenueSummary(
                total_records=12120,
                expected_amount=Decimal("90.00"),
                paid_amount=Decimal("45.00"),
                principal_received=Decimal("40.00"),
                interest_amount=Decimal("5.00"),
                discount_amount=Decimal("0.00"),
                pending_records=1,
                warning_records=38,
                divergent_records=14,
            ),
        )

    async def get_revenue(self, revenue_id: int):
        if revenue_id == 404:
            return None
        item = revenue_item(id=revenue_id)
        return RevenueDetail(
            **item.model_dump(),
            payment_marker="I",
            source_reference="masked-reference",
            divergences=[
                QualityMessage(
                    type="orphan_amortization_loan",
                    severity="DIVERGENT",
                    message="Parcela encontrada sem empréstimo correspondente.",
                )
            ],
        )


def api_client(repository: FakeOperationalRepository):
    app.dependency_overrides[get_operational_repository] = lambda: repository
    return TestClient(app)


def assert_no_forbidden_fields(value: Any) -> None:
    forbidden = {"raw_data", "cpf_original", "cpf_normalized", "source_row_hash"}
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            assert_no_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_forbidden_fields(child)


def test_sales_pagination_filters_money_and_security() -> None:
    repository = FakeOperationalRepository()
    try:
        with api_client(repository) as client:
            response = client.get(
                "/api/operational/sales",
                params={
                    "page": 2,
                    "page_size": 25,
                    "search": "CTR",
                    "contract": "001",
                    "client": "Cliente",
                    "status": "ATIVO",
                    "period_from": "2026-01-01",
                    "period_to": "2026-12-31",
                    "quality": "WARNING",
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 2
    assert payload["items"][0]["principal"] == "1000.10"
    assert repository.sales_query.search == "CTR"
    assert repository.sales_query.quality == "WARNING"
    assert_no_forbidden_fields(payload)
    assert "cpf" not in response.text.lower()


def test_sales_detail_exposes_friendly_quality_and_orphan_loan() -> None:
    repository = FakeOperationalRepository()
    try:
        with api_client(repository) as client:
            response = client.get("/api/operational/sales/loan:21")
            missing = client.get("/api/operational/sales/missing")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["divergences"][0]["message"] == (
        "Empréstimo sem contrato correspondente."
    )
    assert response.json()["funding_status"] == "NOT_INFORMED"
    assert missing.status_code == 404


def test_revenue_pagination_filters_and_multiple_rows_are_not_collapsed() -> None:
    repository = FakeOperationalRepository()
    try:
        with api_client(repository) as client:
            response = client.get(
                "/api/operational/revenue",
                params={
                    "page": 3,
                    "page_size": 25,
                    "contract": "CTR",
                    "client": "Cliente",
                    "status": "PARCIAL",
                    "due_from": "2026-01-01",
                    "due_to": "2026-12-31",
                    "payment_from": "2026-01-01",
                    "payment_to": "2026-12-31",
                    "quality": "DIVERGENT",
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 12120
    assert payload["items"][0]["paid_amount"] == "45.00"
    assert repository.revenue_query.status == "PARCIAL"
    assert repository.revenue_query.quality == "DIVERGENT"
    assert_no_forbidden_fields(payload)


def test_revenue_detail_preserves_marker_and_friendly_divergence() -> None:
    repository = FakeOperationalRepository()
    try:
        with api_client(repository) as client:
            response = client.get("/api/operational/revenue/30")
            missing = client.get("/api/operational/revenue/404")
    finally:
        app.dependency_overrides.clear()
    payload = response.json()
    assert response.status_code == 200
    assert payload["payment_marker"] == "I"
    assert payload["divergences"][0]["message"] == (
        "Parcela encontrada sem empréstimo correspondente."
    )
    assert payload["bank_validation_status"] == "NOT_RECORDED"
    assert missing.status_code == 404
    assert_no_forbidden_fields(payload)
