from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.identity import OperationalRevenueSnapshot
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
)
from app.services.operational.read import (
    RevenueQuery,
    _apply_revenue_filters,
    _apply_revenue_ordering,
    _is_refinanced_expression,
    _loan_display_names_query,
)

AS_OF = date(2026, 8, 27)


def compiled_revenue_query(query: RevenueQuery) -> str:
    loan_names = _loan_display_names_query(3)
    refinanced = _is_refinanced_expression()
    statement = (
        select(OperationalInstallment.id)
        .outerjoin(
            OperationalContract,
            OperationalContract.id == OperationalInstallment.contract_id,
        )
        .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
        .outerjoin(
            loan_names,
            loan_names.c.contract_code == OperationalInstallment.contract_code,
        )
        .join(
            OperationalRevenueSnapshot,
            OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
        )
        .where(OperationalInstallment.promotion_id == 3)
    )
    statement = _apply_revenue_filters(
        statement,
        query,
        AS_OF,
        loan_names,
        refinanced,
    )
    statement = (
        _apply_revenue_ordering(statement, query, AS_OF, refinanced)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).casefold()


def test_search_includes_contract_installment_and_display_client_name() -> None:
    sql = compiled_revenue_query(RevenueQuery(search="cliente remo"))

    assert "operational_installments.contract_code ilike" in sql
    assert "operational_installments.installment_code ilike" in sql
    assert "operational_clients.name" in sql
    assert "revenue_loan_names.client_name" in sql


def test_received_filter_uses_real_payment_date_and_positive_paid_amount() -> None:
    sql = compiled_revenue_query(RevenueQuery(view="received"))

    assert "payment_date is not null" in sql
    assert "paid_amount" in sql
    assert "> 0.00" in sql


def test_open_and_overdue_filters_exclude_confirmed_refinancing() -> None:
    open_sql = compiled_revenue_query(RevenueQuery(view="open"))
    overdue_sql = compiled_revenue_query(RevenueQuery(view="overdue"))

    assert "not (exists" in open_sql
    assert "refin_confirmed" in open_sql
    assert "payment_date is null" in open_sql
    assert "due_date < '2026-08-27'" in overdue_sql


def test_future_filter_and_distant_due_sort_keep_2030_accessible() -> None:
    future_sql = compiled_revenue_query(
        RevenueQuery(
            page=3,
            page_size=25,
            view="future",
            due_to=date(2030, 12, 31),
            sort_by="due_date",
            sort_order="desc",
        )
    )

    assert "due_date > '2026-08-27'" in future_sql
    assert "due_date <= '2030-12-31'" in future_sql
    assert "due_date desc nulls last" in future_sql
    assert "limit 25 offset 50" in " ".join(future_sql.split())


def test_operational_relevance_is_server_side_and_pushes_distant_future_last() -> None:
    sql = compiled_revenue_query(RevenueQuery())

    assert "case when" in sql
    assert "due_date < '2026-08-27'" in sql
    assert "due_date <= '2026-09-26'" in sql
    assert "payment_date" in sql
    assert "end desc nulls last" in sql
    assert "due_date asc nulls last" in sql
    assert "limit 25 offset 0" in " ".join(sql.split())
