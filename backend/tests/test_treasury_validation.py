from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.treasury import TreasuryBankValidation
from app.services.treasury import (
    TreasuryConflictError,
    TreasuryQuery,
    TreasuryRepository,
    validation_outcome,
)


@pytest.mark.parametrize(
    ("system", "observed", "expected_difference", "expected_status"),
    [
        ("300.00", "300.00", "0.00", "VALIDATED"),
        ("300.00", "305.00", "5.00", "DIVERGENT"),
        ("300.00", "295.00", "-5.00", "DIVERGENT"),
    ],
)
def test_status_and_signed_difference_are_derived_by_backend(
    system, observed, expected_difference, expected_status
) -> None:
    result = validation_outcome(
        Decimal(system),
        Decimal(observed),
        "Conferência" if system != observed else None,
    )
    assert result[2] == Decimal(expected_difference)
    assert result[3] == expected_status


def test_divergent_validation_requires_free_text_justification() -> None:
    with pytest.raises(TreasuryConflictError, match="Justificativa é obrigatória"):
        validation_outcome(Decimal("300.00"), Decimal("295.00"), None)


def test_round_half_up_is_explicit_and_never_uses_float() -> None:
    expected, observed, difference, status = validation_outcome(
        Decimal("300.004"), Decimal("300.005"), "Arredondamento conferido"
    )
    assert expected == Decimal("300.00")
    assert observed == Decimal("300.01")
    assert difference == Decimal("0.01")
    assert status == "DIVERGENT"


def test_pending_is_derived_without_database_row() -> None:
    source = inspect.getsource(TreasuryRepository._movement_response)
    assert 'or "PENDING"' in source
    assert "PENDING" not in {
        constraint.name or ""
        for constraint in TreasuryBankValidation.__table__.constraints
    }


def test_history_and_current_validation_have_database_guards() -> None:
    constraints = {
        constraint.name
        for constraint in TreasuryBankValidation.__table__.constraints
    }
    indexes = {index.name: index for index in TreasuryBankValidation.__table__.indexes}
    assert "uq_treasury_bank_validations_movement_version" in constraints
    assert "uq_treasury_bank_validations_supersedes" in constraints
    assert indexes["uq_treasury_bank_validations_current"].unique
    assert "is_current" in str(
        indexes["uq_treasury_bank_validations_current"].dialect_options["postgresql"][
            "where"
        ]
    )


def test_creation_uses_transaction_lock_snapshot_and_never_updates_origins() -> None:
    source = inspect.getsource(TreasuryRepository.validate_movement)
    assert "pg_advisory_xact_lock" in source
    assert ".with_for_update()" in source
    assert "system_amount_snapshot=expected" in source
    assert "system_date_snapshot=movement.movement_date" in source
    assert "supersedes_validation_id=current.id" in source
    assert "FundingContribution" not in source
    assert "OperationalContract" not in source
    assert "OperationalInstallment" not in source


def test_validation_filter_is_applied_in_sql_before_pagination() -> None:
    repository = TreasuryRepository(None)  # type: ignore[arg-type]
    statement = repository._filtered_movement_statement(
        TreasuryQuery(validation_status="PENDING")
    )
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "treasury_bank_validations.id IS NULL" in sql


def test_operational_validation_projection_uses_real_shared_identities_and_fields() -> None:
    repository = TreasuryRepository(None)  # type: ignore[arg-type]
    sql = str(repository._movement_union().compile(compile_kwargs={"literal_binds": True}))
    assert "sale:" in sql
    assert "operational_sale_snapshots" in sql
    assert "contract:" not in sql and "loan:" not in sql
    assert "revenue:" in sql
    assert "operational_contracts" in sql
    assert "operational_loans" in sql
    assert "operational_installments" in sql
    assert "client_name" in sql
    assert "installment_code" in sql
    assert "data_quality_status" in sql
    assert "funding_status" in sql


def test_revenue_eligibility_and_installment_filter_are_applied_in_sql() -> None:
    repository = TreasuryRepository(None)  # type: ignore[arg-type]
    statement = repository._filtered_movement_statement(
        TreasuryQuery(movement_type="REVENUE", installment="03")
    )
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "operational_installments.payment_date IS NOT NULL" in sql
    assert "operational_installments.paid_amount IS NOT NULL" in sql
    assert "operational_installments.paid_amount > 0.00" in sql
    assert "lower(derived_treasury_movements.installment_code) LIKE '%03%'" in sql


def test_validation_page_can_filter_non_positive_or_unknown_amounts_before_pagination() -> None:
    repository = TreasuryRepository(None)  # type: ignore[arg-type]
    statement = repository._filtered_movement_statement(
        TreasuryQuery(movement_type="SALE", eligible_for_validation=True)
    )
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "derived_treasury_movements.amount IS NOT NULL" in sql
    assert "derived_treasury_movements.amount > 0.00" in sql


def test_migration_is_reversible_and_performs_no_backfill() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "f2e200000001_treasury_bank_validations.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "f2c000000001"' in migration
    assert 'op.create_table(\n        "treasury_bank_validations"' in migration
    assert 'op.drop_table("treasury_bank_validations")' in migration
    assert "INSERT INTO" not in migration.upper()
