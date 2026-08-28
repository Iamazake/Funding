from __future__ import annotations

import inspect

import pytest
from sqlalchemy.exc import DBAPIError

from app.core.database import execute_read_only_with_retry
from app.services.funding.ledger import FundingLedgerRepository
from app.services.funding.revenue import RevenueDistributionRepository
from app.services.operational.debt_continuity import DebtContinuityRepository
from app.services.operational.read import OperationalReadRepository
from app.services.treasury import TreasuryRepository


class RetrySession:
    def __init__(self) -> None:
        self.invalidations = 0

    async def invalidate(self) -> None:
        self.invalidations += 1


def transient_disconnect() -> DBAPIError:
    return DBAPIError(
        "SELECT 1",
        {},
        RuntimeError("connection was closed in the middle of operation"),
        connection_invalidated=True,
    )


@pytest.mark.asyncio
async def test_read_only_retry_repeats_at_most_once_on_transient_disconnect() -> None:
    session = RetrySession()
    calls = 0

    async def succeeds_after_disconnect() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise transient_disconnect()
        return "detail"

    assert await execute_read_only_with_retry(session, succeeds_after_disconnect) == "detail"
    assert calls == 2
    assert session.invalidations == 1

    calls = 0

    async def always_disconnects() -> str:
        nonlocal calls
        calls += 1
        raise transient_disconnect()

    with pytest.raises(DBAPIError):
        await execute_read_only_with_retry(session, always_disconnects)
    assert calls == 2
    assert session.invalidations == 2


@pytest.mark.asyncio
async def test_read_only_retry_does_not_repeat_non_transient_errors() -> None:
    session = RetrySession()
    calls = 0

    async def invalid_query() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid filter")

    with pytest.raises(ValueError, match="invalid filter"):
        await execute_read_only_with_retry(session, invalid_query)
    assert calls == 1
    assert session.invalidations == 0


def test_write_operations_never_use_automatic_read_retry() -> None:
    write_operations = (
        FundingLedgerRepository.create_allocation,
        RevenueDistributionRepository.distribute,
        TreasuryRepository.validate_movement,
        DebtContinuityRepository.create_refinancing,
        DebtContinuityRepository.confirm,
    )
    for operation in write_operations:
        assert "execute_read_only_with_retry" not in inspect.getsource(operation)


def test_operational_details_opt_in_to_the_read_only_retry() -> None:
    assert "execute_read_only_with_retry" in inspect.getsource(
        OperationalReadRepository.get_revenue
    )
    assert "execute_read_only_with_retry" in inspect.getsource(OperationalReadRepository.get_sale)
