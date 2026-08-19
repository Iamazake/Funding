from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.funding import get_funding_ledger_repository
from app.main import app
from app.schemas.funding_ledger import (
    AllocationResponse,
    FundingSourceResponse,
    LedgerEntryResponse,
    SaleCompositionResponse,
    SourceBalanceResponse,
)

SOURCE_ID = UUID("30000000-0000-0000-0000-000000000001")
CONTRIBUTION_SOURCE_ID = UUID("30000000-0000-0000-0000-000000000002")
CONTRIBUTION_ID = UUID("20000000-0000-0000-0000-000000000001")
INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000001")
ALLOCATION_ID = UUID("40000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


class FakeLedgerRepository:
    async def list_sources(self):
        return [
            FundingSourceResponse(
                id=SOURCE_ID,
                source_type="REMO_CAPITAL",
                contribution_id=None,
                status="ACTIVE",
                current_balance=Decimal("0.00"),
                created_at=NOW,
                updated_at=NOW,
            ),
            FundingSourceResponse(
                id=CONTRIBUTION_SOURCE_ID,
                source_type="INVESTOR_CONTRIBUTION",
                contribution_id=CONTRIBUTION_ID,
                status="ACTIVE",
                investor_id=INVESTOR_ID,
                investor_name="Investidor Real",
                contribution_code="APT-REAL",
                contribution_date=date(2026, 1, 1),
                original_amount=Decimal("20000.00"),
                monthly_rate=Decimal("0.02"),
                current_balance=Decimal("20000.00"),
                created_at=NOW,
                updated_at=NOW,
            ),
        ]

    async def get_source(self, source_id):
        return (await self.list_sources())[0]

    async def list_ledger(self, source_id):
        return [self._entry(source_id)]

    async def get_balance(self, source_id, as_of):
        return SourceBalanceResponse(source_id=source_id, as_of=as_of, balance="8000.00")

    async def register_remo_capital(self, data):
        return self._entry(SOURCE_ID, amount=data.amount)

    async def get_composition(self, sale_id):
        return self._composition(sale_id, "NOT_INFORMED", [])

    async def create_allocation(self, sale_id, data):
        allocation = AllocationResponse(
            id=ALLOCATION_ID,
            sale_id=sale_id,
            source_id=data.source_id,
            source_type="INVESTOR_CONTRIBUTION",
            contribution_id=CONTRIBUTION_ID,
            contribution_code="APT-REAL",
            investor_id=INVESTOR_ID,
            investor_name="Investidor Real",
            amount=data.amount,
            percentage=Decimal("100.0000"),
            effective_date=date(2026, 1, 2),
            status="ACTIVE",
            actor=data.actor,
            notes=data.notes,
            created_at=NOW,
            reversed_at=None,
        )
        return self._composition(sale_id, "COMPLETE", [allocation])

    async def reverse_allocation(self, allocation_id, data):
        allocation = AllocationResponse(
            id=allocation_id,
            sale_id="loan:40",
            source_id=CONTRIBUTION_SOURCE_ID,
            source_type="INVESTOR_CONTRIBUTION",
            contribution_id=CONTRIBUTION_ID,
            contribution_code="APT-REAL",
            investor_id=INVESTOR_ID,
            investor_name="Investidor Real",
            amount=Decimal("600.00"),
            percentage=Decimal("100.0000"),
            effective_date=date(2026, 1, 2),
            status="REVERSED",
            actor=data.actor,
            notes=data.reason,
            created_at=NOW,
            reversed_at=NOW,
        )
        return self._composition("loan:40", "NOT_INFORMED", [allocation])

    @staticmethod
    def _entry(source_id, amount=Decimal("1000.00")):
        return LedgerEntryResponse(
            id=1,
            source_id=source_id,
            entry_type="ADJUSTMENT",
            amount=amount,
            direction=1,
            signed_amount=amount,
            effective_date=date(2026, 1, 1),
            origin_type="REMO_ADMIN",
            contribution_id=None,
            allocation_id=None,
            reversal_of_entry_id=None,
            actor="Operador",
            notes="Registro real",
            created_at=NOW,
        )

    @staticmethod
    def _composition(sale_id, status, allocations):
        amount = sum((item.amount for item in allocations if item.status == "ACTIVE"), Decimal())
        return SaleCompositionResponse(
            sale_id=sale_id,
            operation_date=date(2026, 1, 2),
            operation_amount=Decimal("600.00"),
            identified_amount=amount,
            difference=Decimal("600.00") - amount,
            funding_status=status,
            source_count=sum(item.status == "ACTIVE" for item in allocations),
            allocations=allocations,
        )


def api_client() -> TestClient:
    app.dependency_overrides[get_funding_ledger_repository] = FakeLedgerRepository
    return TestClient(app)


def test_sources_include_contribution_and_remo_without_fake_investor() -> None:
    try:
        with api_client() as client:
            response = client.get("/api/funding/sources")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    remo, contribution = response.json()
    assert remo["source_type"] == "REMO_CAPITAL"
    assert remo["investor_id"] is None
    assert remo["current_balance"] == "0.00"
    assert contribution["contribution_id"] == str(CONTRIBUTION_ID)


def test_balance_ledger_and_remo_capital_entry_are_decimal() -> None:
    try:
        with api_client() as client:
            balance = client.get(
                f"/api/funding/sources/{SOURCE_ID}/balance", params={"as_of": "2026-01-18"}
            )
            ledger = client.get(f"/api/funding/sources/{SOURCE_ID}/ledger")
            capital = client.post(
                "/api/funding/sources/remo-capital/entries",
                json={
                    "amount": "1000.00",
                    "effective_date": "2026-01-01",
                    "direction": "CREDIT",
                    "actor": "Operador",
                    "notes": "Capital próprio confirmado",
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert balance.json() == {
        "source_id": str(SOURCE_ID),
        "as_of": "2026-01-18",
        "balance": "8000.00",
    }
    assert ledger.json()[0]["signed_amount"] == "1000.00"
    assert capital.status_code == 201
    assert capital.json()["amount"] == "1000.00"


def test_contract_without_funding_and_orphan_loan_allocation_and_reversal() -> None:
    try:
        with api_client() as client:
            empty = client.get("/api/funding/sales/contract:10/composition")
            allocated = client.post(
                "/api/funding/sales/loan:40/allocations",
                json={
                    "source_id": str(CONTRIBUTION_SOURCE_ID),
                    "amount": "600.00",
                    "actor": "Operador",
                    "notes": "Órfão financiado",
                },
            )
            reversed_response = client.post(
                f"/api/funding/allocations/{ALLOCATION_ID}/reversal",
                json={"actor": "Revisor", "reason": "Composição corrigida"},
            )
    finally:
        app.dependency_overrides.clear()
    assert empty.json()["funding_status"] == "NOT_INFORMED"
    assert allocated.status_code == 201
    assert allocated.json()["sale_id"] == "loan:40"
    assert allocated.json()["funding_status"] == "COMPLETE"
    assert allocated.json()["allocations"][0]["percentage"] == "100.0000"
    assert reversed_response.json()["allocations"][0]["status"] == "REVERSED"


def test_invalid_zero_allocation_is_rejected() -> None:
    try:
        with api_client() as client:
            response = client.post(
                "/api/funding/sales/contract:10/allocations",
                json={
                    "source_id": str(CONTRIBUTION_SOURCE_ID),
                    "amount": "0.00",
                    "actor": "Operador",
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
