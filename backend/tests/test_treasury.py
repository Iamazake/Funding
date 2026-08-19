from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.funding import FundingContribution, FundingInvestor
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
)
from app.schemas.treasury import TreasuryMovementResponse
from app.services.treasury import (
    TreasuryQuery,
    TreasuryRepository,
    contribution_movement,
    filter_treasury_movements,
    revenue_movement,
    sale_movement,
    summarize_treasury_movements,
)

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


def movement(
    movement_id: str,
    movement_type: str,
    amount: str | None,
    movement_date: date | None,
    *,
    investor_id=None,
) -> TreasuryMovementResponse:
    value = Decimal(amount) if amount is not None else None
    inflow = value if movement_type in {"CONTRIBUTION", "REVENUE"} else Decimal("0.00")
    outflow = value if movement_type == "SALE" else Decimal("0.00")
    return TreasuryMovementResponse(
        id=movement_id,
        movement_type=movement_type,
        direction="OUTFLOW" if movement_type == "SALE" else "INFLOW",
        movement_date=movement_date,
        reference=movement_id,
        description=f"Movimento {movement_id}",
        contract_code="CTR-001" if movement_type != "CONTRIBUTION" else None,
        investor_id=investor_id,
        investor_name="João" if investor_id else None,
        inflow=inflow,
        outflow=outflow,
        amount=value,
        origin="test_source",
        source_record_id=movement_id,
        detail_path="/detalhe",
        status="CONFIRMED",
    )


def test_contribution_sale_and_received_revenue_have_correct_cash_direction() -> None:
    investor_id = uuid4()
    investor = FundingInvestor(
        id=investor_id,
        code="INV-001",
        name="João",
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    contribution = FundingContribution(
        id=uuid4(),
        code="APT-001",
        investor_id=investor_id,
        contribution_date=date(2026, 1, 1),
        original_amount=Decimal("100000.00"),
        monthly_rate=Decimal("0.02"),
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    client = OperationalClient(id=1, promotion_id=1, source_bcli_row_id=1, name="Cliente")
    contract = OperationalContract(
        id=10,
        promotion_id=1,
        source_dfen_row_id=1,
        contract_code="CTR-001",
        operation_date=date(2026, 1, 2),
        released_amount=Decimal("20000.00"),
        operational_status="ATIVO",
        data_quality_status="VALID",
    )
    installment = OperationalInstallment(
        id=30,
        promotion_id=1,
        source_amortization_row_id=1,
        contract_code="CTR-001",
        source_key="REC-001",
        payment_date=date(2026, 2, 1),
        paid_amount=Decimal("2000.00"),
        installment_status="PAGA",
        data_quality_status="VALID",
    )
    contribution_row = contribution_movement(contribution, investor)
    sale_row = sale_movement(contract, client, orphan=False)
    revenue_row = revenue_movement(installment, contract, client)
    assert (contribution_row.inflow, contribution_row.outflow) == (
        Decimal("100000.00"), Decimal("0.00")
    )
    assert (sale_row.inflow, sale_row.outflow) == (
        Decimal("0.00"), Decimal("20000.00")
    )
    assert (revenue_row.inflow, revenue_row.outflow) == (
        Decimal("2000.00"), Decimal("0.00")
    )
    assert sale_row.movement_date == contract.operation_date
    assert revenue_row.movement_date == installment.payment_date


def test_allocations_multiple_sources_and_principal_return_do_not_duplicate_cash() -> None:
    cash_movements = [
        movement("sale:contract:10", "SALE", "20000.00", date(2026, 1, 2)),
        movement("revenue:30", "REVENUE", "2000.00", date(2026, 2, 1)),
    ]
    allocations = [Decimal("12000.00"), Decimal("8000.00")]
    distribution_items = [Decimal("1200.00"), Decimal("800.00")]
    principal_returns = [Decimal("900.00")]
    summary = summarize_treasury_movements(cash_movements)
    assert sum(allocations) == Decimal("20000.00")
    assert sum(distribution_items) == Decimal("2000.00")
    assert sum(principal_returns) == Decimal("900.00")
    assert summary.total_outflows == Decimal("20000.00")
    assert summary.total_inflows == Decimal("2000.00")
    assert summary.known_net_flow == Decimal("-18000.00")


def test_treasury_repository_never_turns_internal_funding_events_into_cash_movements() -> None:
    source = inspect.getsource(TreasuryRepository)
    # Active allocations are read only to enrich a Sale with its Funding status.
    assert 'literal("funding_allocations").label("origin")' not in source
    assert "FundingLedgerEntry" not in source
    assert "FundingRevenueDistributionItem" not in source
    assert "PRINCIPAL_RETURN" not in source


def test_incomplete_funding_does_not_remove_sale_and_orphan_identity_is_preserved() -> None:
    loan = OperationalLoan(
        id=40,
        promotion_id=1,
        source_loan_row_id=1,
        contract_id=None,
        operation_date=date(2026, 3, 1),
        released_amount=Decimal("600.00"),
        operational_status="ATIVO",
        data_quality_status="DIVERGENT",
    )
    result = sale_movement(loan, None, orphan=True)
    assert result.id == "sale:loan:40"
    assert result.source_record_id == "loan:40"
    assert result.detail_path == "/vendas/loan:40"
    assert result.outflow == Decimal("600.00")


def test_period_type_search_and_investor_filters_are_real() -> None:
    investor_id = uuid4()
    rows = [
        movement(
            "contribution:1",
            "CONTRIBUTION",
            "100.00",
            date(2026, 1, 1),
            investor_id=investor_id,
        ),
        movement("sale:contract:10", "SALE", "50.00", date(2026, 2, 1)),
        movement("revenue:30", "REVENUE", "20.00", date(2026, 3, 1)),
    ]
    filtered = filter_treasury_movements(
        rows,
        TreasuryQuery(
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
            movement_type="CONTRIBUTION",
            search="joão",
            investor_id=investor_id,
        ),
    )
    assert [item.id for item in filtered] == ["contribution:1"]


def test_aggregates_use_decimal_and_report_unknown_financial_fields() -> None:
    rows = [
        movement("contribution:1", "CONTRIBUTION", "100.10", date(2026, 1, 1)),
        movement("sale:contract:10", "SALE", "20.05", date(2026, 1, 2)),
        movement("sale:contract:11", "SALE", None, None),
        movement("revenue:30", "REVENUE", "2.02", date(2026, 1, 3)),
    ]
    summary = summarize_treasury_movements(rows)
    assert summary.total_inflows == Decimal("102.12")
    assert summary.total_outflows == Decimal("20.05")
    assert summary.known_net_flow == Decimal("82.07")
    assert summary.undated_movement_count == 1
    assert summary.unknown_amount_count == 1
