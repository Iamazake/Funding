from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.api.auth import get_current_user
from app.main import app
from app.models.auth import AppUser

TEST_USER = AppUser(
    id=UUID("90000000-0000-0000-0000-000000000002"),
    name="Analista de Teste",
    email="analista@teste.local",
    password_hash="$argon2id$never-returned",
    role="ANALYST",
    status="ACTIVE",
    created_at=datetime(2026, 8, 18, tzinfo=UTC),
    updated_at=datetime(2026, 8, 18, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def authenticated_legacy_api_tests():
    """Keep pre-auth regression tests focused on their original domain."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
