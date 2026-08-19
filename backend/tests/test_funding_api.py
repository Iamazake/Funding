from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.funding import get_funding_repository
from app.main import app
from app.schemas.funding import ContributionResponse, InvestorResponse
from app.services.funding.repository import FundingConflictError, FundingNotFoundError

INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000001")
SECOND_INVESTOR_ID = UUID("10000000-0000-0000-0000-000000000002")
CONTRIBUTION_IDS = (
    UUID("20000000-0000-0000-0000-000000000001"),
    UUID("20000000-0000-0000-0000-000000000002"),
)
NOW = datetime(2026, 8, 11, 12, tzinfo=UTC)


class FakeFundingRepository:
    def __init__(self) -> None:
        self.investors: dict[UUID, InvestorResponse] = {}
        self.contributions: dict[UUID, ContributionResponse] = {}

    async def list_investors(self):
        return list(self.investors.values())

    async def get_investor(self, investor_id):
        try:
            return self.investors[investor_id]
        except KeyError as error:
            raise FundingNotFoundError("Investidor não encontrado.") from error

    async def create_investor(self, data):
        identifier = INVESTOR_ID if not self.investors else SECOND_INVESTOR_ID
        item = InvestorResponse(
            id=identifier,
            code=f"INV-{len(self.investors) + 1:04}",
            **data.model_dump(),
            created_at=NOW,
            updated_at=NOW,
        )
        self.investors[identifier] = item
        return item

    async def update_investor(self, investor_id, data):
        current = await self.get_investor(investor_id)
        updated = current.model_copy(
            update={**data.model_dump(exclude_unset=True), "updated_at": NOW}
        )
        self.investors[investor_id] = updated
        return updated

    async def list_contributions(self, investor_id=None):
        if investor_id is not None and investor_id not in self.investors:
            raise FundingNotFoundError("Investidor não encontrado.")
        return [
            item
            for item in self.contributions.values()
            if investor_id is None or item.investor_id == investor_id
        ]

    async def get_contribution(self, contribution_id):
        try:
            return self.contributions[contribution_id]
        except KeyError as error:
            raise FundingNotFoundError("Aporte não encontrado.") from error

    async def create_contribution(self, data):
        if data.investor_id not in self.investors:
            raise FundingNotFoundError("Investidor não encontrado.")
        identifier = CONTRIBUTION_IDS[len(self.contributions)]
        item = ContributionResponse(
            id=identifier,
            code=f"APT-{len(self.contributions) + 1:04}",
            **data.model_dump(),
            original_amount_editable=True,
            created_at=NOW,
            updated_at=NOW,
        )
        self.contributions[identifier] = item
        return item

    async def update_contribution(self, contribution_id, data):
        current = await self.get_contribution(contribution_id)
        if not current.original_amount_editable and "original_amount" in data.model_fields_set:
            raise FundingConflictError(
                "O valor original não pode ser sobrescrito após movimentação financeira."
            )
        updated = current.model_copy(
            update={**data.model_dump(exclude_unset=True), "updated_at": NOW}
        )
        self.contributions[contribution_id] = updated
        return updated


def client(repository: FakeFundingRepository) -> TestClient:
    app.dependency_overrides[get_funding_repository] = lambda: repository
    return TestClient(app)


def create_investor(api: TestClient, name: str = "Investidor Real"):
    return api.post(
        "/api/funding/investors",
        json={"name": name, "status": "ACTIVE", "notes": "Cadastro pela interface"},
    )


def test_investor_create_edit_and_query() -> None:
    repository = FakeFundingRepository()
    try:
        with client(repository) as api:
            created = create_investor(api)
            edited = api.patch(
                f"/api/funding/investors/{INVESTOR_ID}",
                json={"name": "Investidor Atualizado", "status": "INACTIVE"},
            )
            fetched = api.get(f"/api/funding/investors/{INVESTOR_ID}")
            listed = api.get("/api/funding/investors")
    finally:
        app.dependency_overrides.clear()
    assert created.status_code == 201
    assert edited.status_code == 200
    assert edited.json()["name"] == "Investidor Atualizado"
    assert fetched.json()["status"] == "INACTIVE"
    assert len(listed.json()) == 1


def test_multiple_contributions_for_same_investor_and_decimal_response() -> None:
    repository = FakeFundingRepository()
    try:
        with client(repository) as api:
            create_investor(api)
            payload = {
                "investor_id": str(INVESTOR_ID),
                "contribution_date": "2026-08-11",
                "original_amount": "100000.10",
                "monthly_rate": "0.0200000000",
                "status": "ACTIVE",
                "notes": None,
            }
            first = api.post("/api/funding/contributions", json=payload)
            second = api.post(
                "/api/funding/contributions", json={**payload, "original_amount": "50000.00"}
            )
            linked = api.get(f"/api/funding/investors/{INVESTOR_ID}/contributions")
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == second.status_code == 201
    assert first.json()["original_amount"] == "100000.10"
    assert first.json()["monthly_rate"] == "0.0200000000"
    assert len(linked.json()) == 2
    assert all(item["investor_id"] == str(INVESTOR_ID) for item in linked.json())


def test_contribution_validations_relationship_and_locked_original_amount() -> None:
    repository = FakeFundingRepository()
    try:
        with client(repository) as api:
            invalid_investor = api.post(
                "/api/funding/contributions",
                json={
                    "investor_id": str(INVESTOR_ID),
                    "contribution_date": "2026-08-11",
                    "original_amount": "100.00",
                    "monthly_rate": "0.02",
                    "status": "ACTIVE",
                },
            )
            create_investor(api)
            invalid_amount = api.post(
                "/api/funding/contributions",
                json={
                    "investor_id": str(INVESTOR_ID),
                    "contribution_date": "not-a-date",
                    "original_amount": "0.00",
                    "monthly_rate": "1.01",
                    "status": "DELETED",
                },
            )
            created = api.post(
                "/api/funding/contributions",
                json={
                    "investor_id": str(INVESTOR_ID),
                    "contribution_date": date(2026, 8, 11).isoformat(),
                    "original_amount": "100.00",
                    "monthly_rate": "0.02",
                    "status": "ACTIVE",
                },
            )
            identifier = UUID(created.json()["id"])
            repository.contributions[identifier] = repository.contributions[identifier].model_copy(
                update={"original_amount_editable": False}
            )
            locked = api.patch(
                f"/api/funding/contributions/{identifier}", json={"original_amount": "120.00"}
            )
    finally:
        app.dependency_overrides.clear()
    assert invalid_investor.status_code == 404
    assert invalid_amount.status_code == 422
    assert locked.status_code == 409
    assert "não pode ser sobrescrito" in locked.json()["detail"]


def test_funding_routes_do_not_offer_physical_delete() -> None:
    paths = app.openapi()["paths"]
    assert "delete" not in paths["/api/funding/investors/{investor_id}"]
    assert "delete" not in paths["/api/funding/contributions/{contribution_id}"]
