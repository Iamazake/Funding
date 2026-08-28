from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
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
from app.services.operational.read import (
    OperationalReadRepository,
    RevenueQuery,
    _RevenueRecord,
    calculate_revenue_kpis,
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


class NegativeComponentOperationalRepository:
    """Read-only repository that reproduces the Batch #4 KPI failure."""

    def __init__(self) -> None:
        self.mutation_calls = 0
        self.item = revenue_item(
            id=500,
            revenue_identity_id=UUID("a50936bb-37dd-3ebf-2feb-1e6ae2d313db"),
            contract_code="2406001207",
            installment_code="1",
            due_date=date(2025, 4, 4),
            payment_date=date(2025, 4, 2),
            expected_amount=Decimal("223.00"),
            paid_amount=Decimal("218.18"),
            principal_component=Decimal("-75.60"),
            interest_component=Decimal("298.60"),
            discount_amount=Decimal("4.82"),
            installment_status="PAGO_ANTEC",
            data_quality_status="WARNING",
            warning_count=1,
            divergence_count=0,
        )

    async def list_revenue(self, query):
        kpis = calculate_revenue_kpis([self.item], date(2026, 8, 27))
        return RevenuePage(
            items=[self.item],
            pagination=PageMeta(
                page=query.page,
                page_size=query.page_size,
                total=1,
                pages=1,
            ),
            summary=RevenueSummary(
                total_records=1,
                expected_amount=self.item.expected_amount,
                paid_amount=kpis["paid_total"],
                principal_received=kpis["principal_received"],
                interest_amount=kpis["interest_total"],
                discount_amount=kpis["discount_total"],
                pending_records=0,
                warning_records=1,
                divergent_records=0,
                principal_total=kpis["principal_total"],
                principal_open=kpis["principal_open"],
                average_pmt=kpis["average_pmt"],
                overdue_principal=kpis["overdue_principal"],
                overdue_pmt=kpis["overdue_pmt"],
                delinquency_percentage=kpis["delinquency_percentage"],
            ),
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
                    "view": "future",
                    "sort_by": "payment_date",
                    "sort_order": "desc",
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
    assert repository.revenue_query.view == "future"
    assert repository.revenue_query.sort_by == "payment_date"
    assert repository.revenue_query.sort_order == "desc"
    assert_no_forbidden_fields(payload)


def test_revenue_defaults_to_operational_relevance() -> None:
    repository = FakeOperationalRepository()
    try:
        with api_client(repository) as client:
            response = client.get("/api/operational/revenue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.revenue_query == RevenueQuery()


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


def test_revenue_endpoint_keeps_negative_component_record_visible_and_kpis_available() -> None:
    repository = NegativeComponentOperationalRepository()
    original = repository.item.model_copy(deep=True)
    try:
        with api_client(repository) as client:
            response = client.get(
                "/api/operational/revenue",
                params={
                    "page": 1,
                    "page_size": 25,
                    "sort_by": "due_date",
                    "sort_order": "desc",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["revenue_identity_id"] == str(original.revenue_identity_id)
    assert payload["items"][0]["principal_component"] == "-75.60"
    assert payload["summary"]["paid_amount"] == "218.18"
    assert payload["summary"]["principal_received"] == "0.00"
    assert payload["summary"]["interest_amount"] == "298.60"
    assert repository.item == original
    assert repository.mutation_calls == 0


@pytest.mark.asyncio
async def test_revenue_detail_uses_targeted_loader_instead_of_loading_promotion() -> None:
    calls: list[int | None] = []
    repository = OperationalReadRepository(object())  # type: ignore[arg-type]

    async def targeted_loader(revenue_id: int | None = None):
        calls.append(revenue_id)
        return []

    repository._load_revenue = targeted_loader  # type: ignore[method-assign]

    assert await repository._get_revenue_once(37792) is None
    assert calls == [37792]


@pytest.mark.asyncio
async def test_targeted_revenue_detail_preserves_the_existing_dto() -> None:
    item = revenue_item(id=37792, warning_count=0, divergence_count=0)
    record = _RevenueRecord(
        item=item,
        installment_id=37792,
        payment_marker="I",
        source_reference="masked-reference",
        base_amount=Decimal("1000.00"),
    )
    repository = OperationalReadRepository(object())  # type: ignore[arg-type]

    async def targeted_loader(revenue_id: int | None = None):
        assert revenue_id == 37792
        return [record]

    async def quality_loader(_rows):
        return {}

    repository._load_revenue = targeted_loader  # type: ignore[method-assign]
    repository._quality_for_installments = quality_loader  # type: ignore[method-assign]

    detail = await repository._get_revenue_once(37792)

    assert detail is not None
    assert {field: getattr(detail, field) for field in RevenueItem.model_fields} == {
        field: getattr(item, field) for field in RevenueItem.model_fields
    }
    assert detail.payment_marker == "I"
    assert detail.source_reference == "masked-reference"
    assert detail.warnings == []
    assert detail.divergences == []
