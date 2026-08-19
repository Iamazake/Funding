from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.funding import FundingAllocation, FundingRevenueDistribution
from app.models.identity import OperationalRevenueSnapshot, OperationalSaleSnapshot
from app.models.treasury import TreasuryBankValidation
from app.services.operational.identity import RevenueEvidence, match_revenues
from app.services.operational.store import SqlAlchemyOperationalPromotionRepository

PAIR_CONTRACTS = ("240600386", "240600423", "240600489", "240600663")


def evidence(
    source_id: int,
    identity: int | None,
    *,
    contract: str = "240600386",
    installment: str = "7",
    row_hash: str | None = None,
    expected: str = "100.00",
    payment_date: date | None = date(2026, 1, 10),
    paid: str = "100.00",
) -> RevenueEvidence:
    return RevenueEvidence(
        source_record_id=source_id,
        identity_id=(
            UUID(f"00000000-0000-0000-0000-{identity:012d}") if identity is not None else None
        ),
        sale_identity_id=UUID("10000000-0000-0000-0000-000000000001"),
        contract_code=contract,
        installment_code=installment,
        source_row_hash=row_hash,
        due_date=date(2026, 1, 5),
        principal=Decimal("80.00"),
        interest=Decimal("20.00"),
        expected_amount=Decimal(expected),
        payment_date=payment_date,
        paid_amount=Decimal(paid),
        discount_amount=Decimal("0.00"),
        financial_product="CPBOL",
        installment_status="PAGO",
    )


def test_real_repeated_contract_installment_pairs_remain_two_distinct_revenues() -> None:
    for index, contract in enumerate(PAIR_CONTRACTS, start=1):
        previous = [
            evidence(index * 10, index * 10, contract=contract, row_hash=f"{contract}-a"),
            evidence(
                index * 10 + 1,
                index * 10 + 1,
                contract=contract,
                row_hash=f"{contract}-b",
                expected="125.00",
                paid="125.00",
            ),
        ]
        current = [
            evidence(index * 100, None, contract=contract, row_hash=f"{contract}-a"),
            evidence(
                index * 100 + 1,
                None,
                contract=contract,
                row_hash=f"{contract}-b",
                expected="125.00",
                paid="125.00",
            ),
        ]
        decisions = match_revenues(previous, current)
        assert [item.status for item in decisions] == ["AUTO_MATCH", "AUTO_MATCH"]
        assert len({item.identity_id for item in decisions}) == 2


def test_mutable_payment_correction_preserves_identity_with_strong_schedule_evidence() -> None:
    previous = [evidence(1, 1, row_hash="before")]
    current = [
        evidence(
            2,
            None,
            row_hash="after",
            payment_date=date(2026, 1, 12),
            paid="99.00",
        )
    ]
    decision = match_revenues(previous, current)[0]
    assert decision.status == "AUTO_MATCH"
    assert decision.identity_id == previous[0].identity_id
    assert decision.reason == "UNIQUE_STRONG_EVIDENCE"


def test_tied_candidates_without_financial_reference_get_new_identity_without_merge() -> None:
    previous = [evidence(1, 1), evidence(2, 2)]
    decision = match_revenues(previous, [evidence(3, None)])[0]
    assert decision.status == "NEW_IDENTITY"
    assert decision.identity_id is None


def test_tied_candidates_with_financial_reference_require_review() -> None:
    previous = [evidence(1, 1), evidence(2, 2)]
    protected = {item.identity_id for item in previous if item.identity_id is not None}
    decision = match_revenues(
        previous,
        [evidence(3, None)],
        protected_identity_ids=protected,
    )[0]
    assert decision.status == "REVIEW_REQUIRED"
    assert decision.identity_id is None


def test_identical_ambiguous_rows_without_financial_reference_are_not_merged() -> None:
    previous = [
        evidence(1, 1, row_hash="same"),
        evidence(2, 2, row_hash="same"),
    ]
    decision = match_revenues(previous, [evidence(3, None, row_hash="same")])[0]
    assert decision.status == "NEW_IDENTITY"
    assert decision.identity_id is None


def test_missing_unreferenced_old_row_remains_only_in_historical_snapshot() -> None:
    assert match_revenues([evidence(1, 1, row_hash="old")], []) == []


def test_new_row_without_prior_candidate_gets_a_new_identity() -> None:
    decision = match_revenues([], [evidence(3, None)])[0]
    assert decision.status == "NEW_IDENTITY"


def test_240600833_preserves_exact_row_and_creates_distinct_schedule_addition() -> None:
    previous = [evidence(1, 1, contract="240600833", installment="1", row_hash="original")]
    current = [
        evidence(2, None, contract="240600833", installment="1", row_hash="original"),
        evidence(3, None, contract="240600833", installment="1", row_hash="renumbered"),
    ]
    decisions = match_revenues(previous, current)
    assert [item.status for item in decisions] == ["AUTO_MATCH", "NEW_IDENTITY"]
    assert decisions[0].identity_id == previous[0].identity_id
    assert decisions[1].identity_id is None


def test_240600833_33_to_56_is_not_reconciled_with_1_to_24() -> None:
    previous = [
        evidence(
            installment,
            installment,
            contract="240600833",
            installment=str(installment),
            row_hash=f"old-{installment}",
        )
        for installment in range(33, 57)
    ]
    current = [
        evidence(
            1000 + installment,
            None,
            contract="240600833",
            installment=str(installment),
            row_hash=f"new-{installment}",
        )
        for installment in range(1, 25)
    ]

    decisions = match_revenues(previous, current)

    assert len(decisions) == 24
    assert {item.status for item in decisions} == {"NEW_IDENTITY"}
    assert {item.identity_id for item in decisions} == {None}


def test_sale_funding_survives_contract_snapshot_id_1456_to_2912() -> None:
    sale_identity_id = uuid4()
    current = OperationalSaleSnapshot(
        sale_identity_id=sale_identity_id,
        promotion_id=1,
        contract_id=1456,
        match_status="BASELINE",
        match_evidence={"source_contract_code": "2406001474"},
    )
    next_snapshot = OperationalSaleSnapshot(
        sale_identity_id=sale_identity_id,
        promotion_id=2,
        contract_id=2912,
        match_status="AUTO_MATCH",
        match_evidence={"source_contract_code": "2406001474"},
    )
    canonical_key = f"sale:{sale_identity_id}"
    allocation = FundingAllocation(
        sale_id=canonical_key,
        sale_identity_id=sale_identity_id,
        legacy_sale_id="contract:1456",
        amount=Decimal("300.00"),
    )
    validation = TreasuryBankValidation(
        movement_key=canonical_key,
        legacy_movement_key="sale:contract:1456",
        sale_identity_id=sale_identity_id,
    )

    assert current.contract_id == 1456
    assert next_snapshot.contract_id == 2912
    assert current.sale_identity_id == next_snapshot.sale_identity_id
    assert allocation.sale_id == validation.movement_key == canonical_key
    assert allocation.amount == Decimal("300.00")


def test_revenue_funding_survives_installment_snapshot_id_change() -> None:
    sale_identity_id = uuid4()
    revenue_identity_id = uuid4()
    current = OperationalRevenueSnapshot(
        revenue_identity_id=revenue_identity_id,
        promotion_id=1,
        installment_id=120,
        match_status="BASELINE",
        match_evidence={"exact_hash": True},
    )
    next_snapshot = OperationalRevenueSnapshot(
        revenue_identity_id=revenue_identity_id,
        promotion_id=2,
        installment_id=241,
        match_status="AUTO_MATCH",
        match_evidence={"exact_hash": True},
    )
    canonical_key = f"revenue:{revenue_identity_id}"
    distribution = FundingRevenueDistribution(
        revenue_id=current.installment_id,
        revenue_identity_id=revenue_identity_id,
        sale_identity_id=sale_identity_id,
        sale_id=f"sale:{sale_identity_id}",
    )
    validation = TreasuryBankValidation(
        movement_key=canonical_key,
        legacy_movement_key=f"revenue:{current.installment_id}",
        revenue_identity_id=revenue_identity_id,
    )

    assert current.installment_id != next_snapshot.installment_id
    assert current.revenue_identity_id == next_snapshot.revenue_identity_id
    assert distribution.revenue_identity_id == next_snapshot.revenue_identity_id
    assert validation.movement_key == canonical_key


def test_promotion_activates_snapshot_only_after_canonical_identity_resolution() -> None:
    source = inspect.getsource(SqlAlchemyOperationalPromotionRepository.persist)
    assert source.index("CanonicalIdentityResolver") < source.index("promotion.is_current = True")
    assert 'promotion.status = "identity_review_required"' in source
