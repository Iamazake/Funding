from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.api.batches import (
    get_batch_review_service,
    get_operational_promotion_service,
)
from app.core.database import get_session
from app.main import app
from app.models.auth import AppUser, AppUserAuditEvent
from app.schemas.batches import OperationalBatchDetail, OperationalBatchList

NOW = datetime(2026, 8, 18, 23, 24, tzinfo=UTC)
ADMIN_ID = UUID("90000000-0000-0000-0000-000000000001")


def admin(role: str = "ADMIN") -> AppUser:
    return AppUser(
        id=ADMIN_ID,
        name="Admin Remo",
        email="admin@teste.local",
        password_hash="not-returned",
        role=role,
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )


def detail() -> OperationalBatchDetail:
    return OperationalBatchDetail.model_validate(
        {
            "id": 3,
            "sync_run_id": 4,
            "started_at": NOW,
            "completed_at": NOW,
            "source_type": "ONEDRIVE",
            "source_name": "Cadastro de Clientes.xlsm",
            "source_size": 27_706_933,
            "source_sha256": "a" * 64,
            "status": "succeeded",
            "data_counts": {
                "bcli_cadastro": 1528,
                "dfen_contrato": 1525,
                "econ_emprestimos": 1504,
                "econ_amortizacoes": 12866,
            },
            "quality_counts": {
                "valid": 17325,
                "warning": 81,
                "divergent": 17,
                "invalid": 0,
            },
            "initiated_by": {"id": ADMIN_ID, "name": "Admin Remo"},
            "promotion": None,
            "comparison": {
                "current_promotion_id": 1,
                "current_source_batch_id": 2,
                "clients": {"current": 1459, "candidate": 1528, "difference": 69},
                "contracts": {"current": 1456, "candidate": 1525, "difference": 69},
                "loans": {"current": 1436, "candidate": 1504, "difference": 68},
                "installments": {"current": 12120, "candidate": 12866, "difference": 746},
                "sales": {"current": 1459, "candidate": 1528, "difference": 69},
                "revenue": {"current": 12120, "candidate": 12866, "difference": 746},
            },
            "promotion_eligible": True,
            "promotion_eligibility_reason": "Elegível.",
        }
    )


class FakeReviewService:
    async def list_batches(self, *, limit: int):
        assert limit == 50
        item = detail()
        return OperationalBatchList(items=[item])

    async def get_batch(self, batch_id: int):
        assert batch_id == 3
        return detail()


class FakePromotionService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def promote(self, batch_id: int):
        self.calls.append(batch_id)
        return SimpleNamespace(
            promotion_id=2,
            source_batch_id=batch_id,
            status="succeeded",
            idempotent=False,
            summary={"records": {"contracts": 1525}},
        )


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1


def test_admin_can_list_and_review_batches() -> None:
    app.dependency_overrides[get_current_user] = lambda: admin()
    app.dependency_overrides[get_batch_review_service] = FakeReviewService
    try:
        with TestClient(app) as client:
            listing = client.get("/api/operational/batches")
            reviewed = client.get("/api/operational/batches/3")
        assert listing.status_code == 200
        assert listing.json()["items"][0]["id"] == 3
        assert reviewed.status_code == 200
        assert reviewed.json()["promotion_eligible"] is True
    finally:
        app.dependency_overrides.clear()


def test_promotion_endpoint_reuses_service_and_audits_admin_without_real_promotion() -> None:
    promotion = FakePromotionService()
    session = FakeSession()
    app.dependency_overrides[get_current_user] = lambda: admin()
    app.dependency_overrides[get_operational_promotion_service] = lambda: promotion
    app.dependency_overrides[get_batch_review_service] = FakeReviewService
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.post("/api/operational/batches/3/promote")
        assert response.status_code == 200
        assert promotion.calls == [3]
        event = next(item for item in session.added if isinstance(item, AppUserAuditEvent))
        assert event.actor_user_id == ADMIN_ID
        assert event.action == "OPERATIONAL_BATCH_PROMOTED"
        assert event.details["source_batch_id"] == 3
        assert session.commits == 1
    finally:
        app.dependency_overrides.clear()


def test_batch_administration_is_admin_only() -> None:
    app.dependency_overrides[get_current_user] = lambda: admin("ANALYST")
    app.dependency_overrides[get_batch_review_service] = FakeReviewService
    try:
        with TestClient(app) as client:
            assert client.get("/api/operational/batches").status_code == 403
            assert client.get("/api/operational/batches/3").status_code == 403
    finally:
        app.dependency_overrides.clear()
