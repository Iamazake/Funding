from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.funding import MONTHLY_RATE, FundingContribution, FundingInvestor
from app.schemas.funding import ContributionCreate


def test_funding_numeric_types_and_explicit_status_constraints() -> None:
    assert FundingContribution.__table__.c.original_amount.type.precision == 14
    assert FundingContribution.__table__.c.original_amount.type.scale == 2
    assert MONTHLY_RATE.precision == 12
    assert MONTHLY_RATE.scale == 10
    assert any(
        "ACTIVE" in str(item.sqltext)
        for item in FundingInvestor.__table__.constraints
        if hasattr(item, "sqltext")
    )


def test_rate_is_decimal_fraction_never_float() -> None:
    contribution = ContributionCreate(
        investor_id="10000000-0000-0000-0000-000000000001",
        contribution_date="2026-08-11",
        original_amount="100000.10",
        monthly_rate="0.0200000000",
        status="ACTIVE",
    )
    assert contribution.original_amount == Decimal("100000.10")
    assert contribution.monthly_rate == Decimal("0.0200000000")
    assert not isinstance(contribution.monthly_rate, float)


@pytest.mark.parametrize("rate", ["-0.0001", "1.0000000001", "2"])
def test_invalid_contractual_rates_are_rejected(rate: str) -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(
            investor_id="10000000-0000-0000-0000-000000000001",
            contribution_date="2026-08-11",
            original_amount="100.00",
            monthly_rate=rate,
            status="ACTIVE",
        )
