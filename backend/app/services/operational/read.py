from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import execute_read_only_with_retry
from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtContinuityPredecessor,
    OperationalDebtRefinancedInstallment,
)
from app.models.identity import (
    OperationalRevenueSnapshot,
    OperationalSaleIdentity,
    OperationalSaleSnapshot,
)
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPromotion,
    OperationalQualityLink,
)
from app.models.operational import DataInconsistency, ExcelEconEmprestimosRow
from app.models.treasury import TreasuryBankValidation
from app.schemas.operational import (
    PageMeta,
    QualityMessage,
    RevenueDetail,
    RevenueItem,
    RevenuePage,
    RevenueSummary,
    SaleDetail,
    SaleItem,
    SalesPage,
    SaleSummary,
)
from app.services.funding.ledger import allocation_summaries, funding_status
from app.services.funding.revenue import (
    RevenueFundingInput,
    realized_revenue_components,
    revenue_funding_summaries,
)

QUALITY_ORDER = {"VALID": 0, "WARNING": 1, "DIVERGENT": 2, "INVALID": 3}
ZERO = Decimal("0.00")
CENT = Decimal("0.01")

FRIENDLY_MESSAGES = {
    "orphan_loan": "Empréstimo sem contrato correspondente.",
    "orphan_amortization_loan": "Parcela encontrada sem empréstimo correspondente.",
    "orphan_amortization_contract": "Parcela encontrada sem contrato correspondente.",
    "ambiguous_client_identity": "Cliente possui mais de uma identidade operacional possível.",
    "ambiguous_client_relationship": "Relacionamento com cliente não pôde ser resolvido.",
    "invalid_cpf": "CPF inválido na origem; o registro foi preservado.",
    "invalid_date": "Data inválida na origem; o registro foi preservado.",
    "ambiguous_money": "Valor monetário ambíguo; o campo normalizado ficou vazio.",
    "multiple_payment_movements": "Existem múltiplos registros válidos para esta parcela.",
}


@dataclass(frozen=True, slots=True)
class SalesQuery:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    contract: str | None = None
    client: str | None = None
    status: str | None = None
    period_from: date | None = None
    period_to: date | None = None
    quality: str | None = None
    sort_by: str = "operation_date"
    sort_order: Literal["asc", "desc"] = "desc"


@dataclass(frozen=True, slots=True)
class RevenueQuery:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    contract: str | None = None
    client: str | None = None
    status: str | None = None
    due_from: date | None = None
    due_to: date | None = None
    payment_from: date | None = None
    payment_to: date | None = None
    quality: str | None = None
    view: Literal["all", "received", "open", "overdue", "future"] = "all"
    sort_by: str = "operational_relevance"
    sort_order: Literal["asc", "desc"] = "asc"


@dataclass(slots=True)
class _SaleRecord:
    item: SaleItem
    contract_id: int | None
    loan_id: int | None
    client_id: int | None


@dataclass(slots=True)
class _RevenueRecord:
    item: RevenueItem
    installment_id: int
    payment_marker: str | None
    source_reference: str | None
    base_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class OperationalRevenueIssue:
    type: str
    severity: Literal["WARNING", "DIVERGENT"]
    message: str


@dataclass(frozen=True, slots=True)
class OperationalRevenueComponents:
    paid: Decimal
    principal: Decimal
    interest: Decimal
    discount: Decimal
    realized_principal: Decimal
    realized_interest: Decimal
    realized_discount: Decimal
    issues: tuple[OperationalRevenueIssue, ...]


class OperationalReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sales(self, query: SalesQuery) -> SalesPage:
        rows = self._filter_sales(await self._load_sales(), query)
        rows = _sort_sales(rows, query.sort_by, query.sort_order)
        summary = SaleSummary(
            total_contracts=len(rows),
            principal=_sum(row.item.principal for row in rows),
            released_amount=_sum(row.item.released_amount for row in rows),
            financed_amount=_sum(row.item.financed_amount for row in rows),
            warning_contracts=sum(row.item.data_quality_status == "WARNING" for row in rows),
            divergent_contracts=sum(row.item.data_quality_status == "DIVERGENT" for row in rows),
        )
        page_rows, meta = _paginate(rows, query.page, query.page_size)
        quality = await self._quality_for_sales(page_rows)
        items = [self._sale_with_counts(row, quality) for row in page_rows]
        return SalesPage(items=items, pagination=meta, summary=summary)

    async def get_sale(self, sale_id: str) -> SaleDetail | None:
        return await execute_read_only_with_retry(
            self._session, lambda: self._get_sale_once(sale_id)
        )

    async def _get_sale_once(self, sale_id: str) -> SaleDetail | None:
        rows = await self._load_sales(sale_id)
        row = rows[0] if rows else None
        if row is None:
            return None
        quality = await self._quality_for_sales([row])
        item = self._sale_with_counts(row, quality)
        messages = self._sale_messages(row, quality)
        return SaleDetail(
            **item.model_dump(),
            warnings=[message for message in messages if message.severity == "WARNING"],
            divergences=[message for message in messages if message.severity == "DIVERGENT"],
        )

    async def list_revenue(self, query: RevenueQuery) -> RevenuePage:
        as_of = date.today()
        promotion_id = await self._current_promotion_id()
        summary_items = await self._load_revenue_kpi_items(promotion_id, query, as_of)
        kpis = calculate_revenue_kpis(summary_items, as_of)
        current_interest = kpis.pop("interest_total")
        current_discount = kpis.pop("discount_total")
        paid_total = kpis.pop("paid_total")
        principal_received = kpis.pop("principal_received")
        summary = RevenueSummary(
            total_records=len(summary_items),
            expected_amount=_sum(item.expected_amount for item in summary_items),
            paid_amount=paid_total,
            principal_received=principal_received,
            interest_amount=current_interest,
            discount_amount=current_discount,
            pending_records=sum(item.payment_date is None for item in summary_items),
            warning_records=sum(item.data_quality_status == "WARNING" for item in summary_items),
            divergent_records=sum(
                item.data_quality_status == "DIVERGENT" for item in summary_items
            ),
            **kpis,
        )
        page_rows = await self._load_revenue(
            query=query,
            promotion_id=promotion_id,
            as_of=as_of,
        )
        total = len(summary_items)
        meta = PageMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            pages=ceil(total / query.page_size) if total else 0,
        )
        quality = await self._quality_for_installments(page_rows)
        items = [self._revenue_with_counts(row, quality) for row in page_rows]
        return RevenuePage(items=items, pagination=meta, summary=summary)

    async def get_revenue(self, revenue_id: int) -> RevenueDetail | None:
        return await execute_read_only_with_retry(
            self._session, lambda: self._get_revenue_once(revenue_id)
        )

    async def _get_revenue_once(self, revenue_id: int) -> RevenueDetail | None:
        rows = await self._load_revenue(revenue_id)
        row = rows[0] if rows else None
        if row is None:
            return None
        quality = await self._quality_for_installments([row])
        item = self._revenue_with_counts(row, quality)
        messages = quality.get(("installment", row.installment_id), [])
        return RevenueDetail(
            **item.model_dump(),
            payment_marker=row.payment_marker,
            source_reference=row.source_reference,
            warnings=[message for message in messages if message.severity == "WARNING"],
            divergences=[message for message in messages if message.severity == "DIVERGENT"],
        )

    async def _load_sales(self, sale_id: str | None = None) -> list[_SaleRecord]:
        promotion_id = await self._current_promotion_id()
        contract_statement = (
            select(OperationalContract, OperationalClient, OperationalSaleSnapshot)
            .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
            .join(
                OperationalSaleSnapshot,
                OperationalSaleSnapshot.contract_id == OperationalContract.id,
            )
            .where(OperationalContract.promotion_id == promotion_id)
        )
        sale_identity_id, legacy_kind, legacy_id = _parse_sale_reference(sale_id)
        if sale_identity_id is not None:
            contract_statement = contract_statement.where(
                OperationalSaleSnapshot.sale_identity_id == sale_identity_id
            )
        elif legacy_kind == "contract":
            contract_statement = contract_statement.where(OperationalContract.id == legacy_id)
        elif sale_id is not None:
            contract_statement = contract_statement.where(OperationalContract.id.is_(None))
        contract_rows = (await self._session.execute(contract_statement)).all()

        contract_ids = {contract.id for contract, _client, _snapshot in contract_rows}
        loan_statement = (
            select(OperationalLoan, OperationalClient, OperationalSaleSnapshot)
            .outerjoin(OperationalClient, OperationalClient.id == OperationalLoan.client_id)
            .join(
                OperationalSaleSnapshot,
                OperationalSaleSnapshot.loan_id == OperationalLoan.id,
            )
            .where(OperationalLoan.promotion_id == promotion_id)
        )
        if sale_identity_id is not None:
            identity_condition = OperationalSaleSnapshot.sale_identity_id == sale_identity_id
            loan_statement = loan_statement.where(
                or_(identity_condition, OperationalLoan.contract_id.in_(contract_ids))
                if contract_ids
                else identity_condition
            )
        elif legacy_kind == "contract":
            loan_statement = loan_statement.where(OperationalLoan.contract_id == legacy_id)
        elif legacy_kind == "loan":
            loan_statement = loan_statement.where(OperationalLoan.id == legacy_id)
        elif sale_id is not None:
            loan_statement = loan_statement.where(OperationalLoan.id.is_(None))
        loan_rows = (await self._session.execute(loan_statement)).all()
        contract_codes = {
            entity.contract_code
            for entity, _client, _snapshot in (*contract_rows, *loan_rows)
            if entity.contract_code
        }
        loan_names = await self._loan_display_names(
            promotion_id, contract_codes if sale_id is not None else None
        )
        loans_by_contract: dict[
            int, tuple[OperationalLoan, OperationalClient | None, OperationalSaleSnapshot]
        ] = {}
        orphan_loans: list[
            tuple[OperationalLoan, OperationalClient | None, OperationalSaleSnapshot]
        ] = []
        for loan, client, snapshot in loan_rows:
            if loan.contract_id is None:
                orphan_loans.append((loan, client, snapshot))
            else:
                loans_by_contract[loan.contract_id] = (loan, client, snapshot)

        records = []
        for contract, client, snapshot in contract_rows:
            matched = loans_by_contract.get(contract.id)
            loan = matched[0] if matched else None
            client_name, client_name_source, client_name_divergent = _display_client_name(
                client.name if client else None,
                loan_names.get(contract.contract_code or ""),
            )
            quality = _highest_quality(
                contract.data_quality_status,
                loan.data_quality_status if loan is not None else "VALID",
            )
            records.append(
                _SaleRecord(
                    SaleItem(
                        id=f"sale:{snapshot.sale_identity_id}",
                        contract_code=contract.contract_code,
                        client_name=client_name,
                        client_identity_id=contract.client_id,
                        client_name_source=client_name_source,
                        client_name_divergent=client_name_divergent,
                        source_client_code=contract.source_client_code,
                        operation_date=contract.operation_date,
                        release_date=contract.release_date,
                        first_due_date=contract.first_due_date,
                        term=contract.term,
                        principal=contract.principal,
                        iof=contract.iof,
                        financed_amount=contract.financed_amount,
                        installment_amount=contract.installment_amount,
                        released_amount=contract.released_amount,
                        interest_rate=loan.interest_rate if loan else None,
                        irr_rate=loan.irr_rate if loan else None,
                        cet_monthly_rate=loan.cet_monthly_rate if loan else None,
                        status=loan.operational_status if loan else contract.operational_status,
                        data_quality_status=quality,
                    ),
                    contract.id,
                    loan.id if loan else None,
                    contract.client_id,
                )
            )
        for loan, client, snapshot in orphan_loans:
            client_name, client_name_source, client_name_divergent = _display_client_name(
                client.name if client else None,
                loan_names.get(loan.contract_code or ""),
            )
            records.append(
                _SaleRecord(
                    SaleItem(
                        id=f"sale:{snapshot.sale_identity_id}",
                        contract_code=loan.contract_code,
                        client_name=client_name,
                        client_identity_id=loan.client_id,
                        client_name_source=client_name_source,
                        client_name_divergent=client_name_divergent,
                        source_client_code=loan.source_client_code,
                        operation_date=loan.operation_date,
                        release_date=None,
                        first_due_date=loan.first_due_date,
                        term=loan.term,
                        principal=loan.principal,
                        iof=loan.iof,
                        financed_amount=loan.financed_amount,
                        installment_amount=loan.installment_amount,
                        released_amount=loan.released_amount,
                        interest_rate=loan.interest_rate,
                        irr_rate=loan.irr_rate,
                        cet_monthly_rate=loan.cet_monthly_rate,
                        status=loan.operational_status,
                        data_quality_status=loan.data_quality_status,
                    ),
                    None,
                    loan.id,
                    loan.client_id,
                )
            )
        summaries = await allocation_summaries(
            self._session, [record.item.id for record in records]
        )
        for record in records:
            identified, source_count = summaries.get(record.item.id, (ZERO, 0))
            status, difference = funding_status(
                record.item.released_amount,
                identified,
                source_count > 0,
            )
            record.item = record.item.model_copy(
                update={
                    "funding_status": status,
                    "funding_identified_amount": identified,
                    "funding_difference": difference,
                    "funding_source_count": source_count,
                }
            )
        validations = await self._bank_validation_statuses([record.item.id for record in records])
        for record in records:
            record.item = record.item.model_copy(
                update={"bank_validation_status": validations.get(record.item.id, "NOT_RECORDED")}
            )
        relationships = await self._continuity_relationships(
            {record.item.id for record in records} if sale_id is not None else None
        )
        for record in records:
            relationship = relationships.get(record.item.id)
            if relationship is not None:
                record.item = record.item.model_copy(update=relationship)
        return records

    async def _load_revenue(
        self,
        revenue_id: int | None = None,
        *,
        query: RevenueQuery | None = None,
        promotion_id: int | None = None,
        as_of: date | None = None,
    ) -> list[_RevenueRecord]:
        promotion_id = promotion_id or await self._current_promotion_id()
        loan_names_query = _loan_display_names_query(promotion_id)
        refinanced = _is_refinanced_expression()
        statement = (
            select(
                OperationalInstallment,
                OperationalContract,
                OperationalClient,
                OperationalRevenueSnapshot,
                OperationalSaleSnapshot,
            )
            .outerjoin(
                OperationalContract,
                OperationalContract.id == OperationalInstallment.contract_id,
            )
            .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
            .outerjoin(
                loan_names_query,
                loan_names_query.c.contract_code == OperationalInstallment.contract_code,
            )
            .join(
                OperationalRevenueSnapshot,
                OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
            )
            .outerjoin(
                OperationalSaleSnapshot,
                (OperationalSaleSnapshot.promotion_id == OperationalInstallment.promotion_id)
                & (OperationalSaleSnapshot.contract_id == OperationalInstallment.contract_id),
            )
            .where(OperationalInstallment.promotion_id == promotion_id)
        )
        if revenue_id is not None:
            statement = statement.where(OperationalInstallment.id == revenue_id)
        elif query is not None:
            statement = _apply_revenue_filters(
                statement,
                query,
                as_of or date.today(),
                loan_names_query,
                refinanced,
            )
            statement = (
                _apply_revenue_ordering(
                    statement,
                    query,
                    as_of or date.today(),
                    refinanced,
                )
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size)
            )
        rows = (await self._session.execute(statement)).all()
        loan_names = await self._loan_display_names(
            promotion_id,
            {
                installment.contract_code
                for installment, _contract, _client, _revenue, _sale in rows
                if installment.contract_code
            }
            if revenue_id is not None or query is not None
            else None,
        )
        records = []
        refinanced_revenues = await self._refinanced_revenues(
            {
                revenue_snapshot.revenue_identity_id
                for _installment, _contract, _client, revenue_snapshot, _sale in rows
            }
            if revenue_id is not None or query is not None
            else None
        )
        for installment, contract, client, revenue_snapshot, sale_snapshot in rows:
            client_name, client_name_source, client_name_divergent = _display_client_name(
                client.name if client else None,
                loan_names.get(installment.contract_code or ""),
            )
            item = RevenueItem(
                id=installment.id,
                revenue_identity_id=revenue_snapshot.revenue_identity_id,
                contract_code=installment.contract_code,
                client_name=client_name,
                client_name_source=client_name_source,
                client_name_divergent=client_name_divergent,
                installment_code=installment.installment_code,
                due_date=installment.due_date,
                payment_date=installment.payment_date,
                expected_amount=installment.expected_amount,
                paid_amount=installment.paid_amount,
                principal_component=installment.principal_component,
                interest_component=installment.interest_component,
                discount_amount=installment.discount_amount,
                installment_status=(
                    "REFIN"
                    if revenue_snapshot.revenue_identity_id in refinanced_revenues
                    else installment.installment_status
                ),
                situation=installment.situation,
                anticipation_marker=installment.anticipation_marker,
                data_quality_status=installment.data_quality_status,
                refinanced_to_contract_code=refinanced_revenues.get(
                    revenue_snapshot.revenue_identity_id
                ),
                sale_id=(f"sale:{sale_snapshot.sale_identity_id}" if sale_snapshot else None),
            )
            analysis = operational_revenue_components_for_kpi(item)
            for issue in analysis.issues:
                item = item.model_copy(
                    update={
                        "data_quality_status": _highest_quality(
                            item.data_quality_status, issue.severity
                        )
                    }
                )
            records.append(
                _RevenueRecord(
                    item,
                    installment.id,
                    installment.payment_marker_original,
                    installment.source_key,
                    contract.released_amount if contract else None,
                )
            )
        summaries = await revenue_funding_summaries(
            self._session,
            [
                RevenueFundingInput(
                    revenue_id=record.item.revenue_identity_id,
                    sale_id=record.item.sale_id,
                    base_amount=record.base_amount,
                    payment_date=record.item.payment_date,
                    principal_amount=record.item.principal_component,
                    interest_amount=record.item.interest_component,
                    discount_amount=record.item.discount_amount,
                )
                for record in records
            ],
        )
        for record in records:
            summary = summaries[record.item.revenue_identity_id]
            record.item = record.item.model_copy(
                update={
                    "funding_status": summary.funding_status,
                    "distribution_status": summary.distribution_status,
                    "primary_source_name": summary.primary_source_name,
                }
            )
        validations = await self._bank_validation_statuses(
            [
                f"revenue:{record.item.revenue_identity_id}"
                for record in records
                if record.item.revenue_identity_id is not None
            ]
        )
        for record in records:
            key = f"revenue:{record.item.revenue_identity_id}"
            record.item = record.item.model_copy(
                update={"bank_validation_status": validations.get(key, "NOT_RECORDED")}
            )
        return records

    async def _load_revenue_kpi_items(
        self,
        promotion_id: int,
        query: RevenueQuery,
        as_of: date,
    ) -> list[RevenueItem]:
        """Load only filtered KPI columns; ordering and pagination stay in SQL."""

        loan_names_query = _loan_display_names_query(promotion_id)
        refinanced = _is_refinanced_expression()
        quality = _revenue_quality_expression()
        effective_status = case(
            (refinanced, "REFIN"),
            else_=OperationalInstallment.installment_status,
        )
        statement = (
            select(
                OperationalInstallment.id,
                OperationalRevenueSnapshot.revenue_identity_id,
                OperationalInstallment.contract_code,
                OperationalInstallment.installment_code,
                OperationalInstallment.due_date,
                OperationalInstallment.payment_date,
                OperationalInstallment.expected_amount,
                OperationalInstallment.paid_amount,
                OperationalInstallment.principal_component,
                OperationalInstallment.interest_component,
                OperationalInstallment.discount_amount,
                effective_status.label("effective_status"),
                quality.label("effective_quality"),
            )
            .outerjoin(
                OperationalContract,
                OperationalContract.id == OperationalInstallment.contract_id,
            )
            .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
            .outerjoin(
                loan_names_query,
                loan_names_query.c.contract_code == OperationalInstallment.contract_code,
            )
            .join(
                OperationalRevenueSnapshot,
                OperationalRevenueSnapshot.installment_id == OperationalInstallment.id,
            )
            .where(OperationalInstallment.promotion_id == promotion_id)
        )
        statement = _apply_revenue_filters(
            statement,
            query,
            as_of,
            loan_names_query,
            refinanced,
        )
        rows = (await self._session.execute(statement)).all()
        return [
            RevenueItem(
                id=row.id,
                revenue_identity_id=row.revenue_identity_id,
                contract_code=row.contract_code,
                client_name=None,
                installment_code=row.installment_code,
                due_date=row.due_date,
                payment_date=row.payment_date,
                expected_amount=row.expected_amount,
                paid_amount=row.paid_amount,
                principal_component=row.principal_component,
                interest_component=row.interest_component,
                discount_amount=row.discount_amount,
                installment_status=row.effective_status,
                situation=None,
                anticipation_marker=None,
                data_quality_status=row.effective_quality,
            )
            for row in rows
        ]

    async def _continuity_relationships(
        self, sale_ids: set[str] | None = None
    ) -> dict[str, dict[str, object]]:
        statement = (
            select(
                OperationalDebtContinuity,
                OperationalSaleIdentity,
                OperationalDebtContinuityPredecessor.sale_identity_id,
            )
            .join(
                OperationalSaleIdentity,
                OperationalSaleIdentity.id == OperationalDebtContinuity.successor_sale_identity_id,
            )
            .join(
                OperationalDebtContinuityPredecessor,
                and_(
                    OperationalDebtContinuityPredecessor.continuity_id
                    == OperationalDebtContinuity.id,
                    OperationalDebtContinuityPredecessor.is_current.is_(True),
                ),
            )
            .where(
                OperationalDebtContinuity.status.in_(("REFIN_CONFIRMED", "RENEGOTIATION_CONFIRMED"))
            )
            .order_by(
                OperationalDebtContinuity.updated_at,
                OperationalDebtContinuity.id,
                OperationalDebtContinuityPredecessor.added_at,
                OperationalDebtContinuityPredecessor.id,
            )
        )
        if sale_ids is not None:
            identity_ids = {
                parsed
                for value in sale_ids
                for parsed, _kind, _legacy_id in [_parse_sale_reference(value)]
                if parsed is not None
            }
            if not identity_ids:
                return {}
            statement = statement.where(
                or_(
                    OperationalDebtContinuityPredecessor.sale_identity_id.in_(identity_ids),
                    OperationalDebtContinuity.successor_sale_identity_id.in_(identity_ids),
                )
            )
        rows = (await self._session.execute(statement)).all()
        grouped: dict[
            UUID,
            tuple[OperationalDebtContinuity, OperationalSaleIdentity, list[UUID]],
        ] = {}
        for continuity, successor, predecessor_id in rows:
            if continuity.id not in grouped:
                grouped[continuity.id] = (continuity, successor, [])
            grouped[continuity.id][2].append(predecessor_id)
        predecessor_codes = {
            identity.id: identity.source_contract_code
            for identity in await self._session.scalars(
                select(OperationalSaleIdentity).where(
                    OperationalSaleIdentity.id.in_(
                        {
                            predecessor_id
                            for _continuity, _successor, predecessor_ids in grouped.values()
                            for predecessor_id in predecessor_ids
                        }
                    )
                )
            )
        }
        result: dict[str, dict[str, object]] = {}
        for continuity, successor, predecessor_ids in grouped.values():
            successor_key = f"sale:{continuity.successor_sale_identity_id}"
            common = {
                "continuity_id": str(continuity.id),
                "continuity_type": continuity.continuity_type,
                "continuity_effective_date": continuity.effective_date,
                "continuity_notes": continuity.reason,
            }
            for predecessor_id in predecessor_ids:
                predecessor_key = f"sale:{predecessor_id}"
                result[predecessor_key] = {
                    **common,
                    "continuity_role": "PREDECESSOR",
                    "successor_sale_id": successor_key,
                    "successor_contract_code": successor.source_contract_code,
                }
            result[successor_key] = {
                **common,
                "continuity_role": "SUCCESSOR",
                "predecessor_sale_id": (
                    f"sale:{predecessor_ids[0]}" if predecessor_ids else None
                ),
                "predecessor_contract_code": (
                    predecessor_codes.get(predecessor_ids[0])
                    if predecessor_ids
                    else None
                ),
                "predecessor_sale_ids": [
                    f"sale:{predecessor_id}" for predecessor_id in predecessor_ids
                ],
                "predecessor_contract_codes": [
                    predecessor_codes[predecessor_id]
                    for predecessor_id in predecessor_ids
                    if predecessor_codes.get(predecessor_id) is not None
                ],
            }
        return result

    async def _refinanced_revenues(
        self, revenue_identity_ids: set[object] | None = None
    ) -> dict[object, str]:
        statement = (
            select(
                OperationalDebtRefinancedInstallment.revenue_identity_id,
                OperationalSaleIdentity.source_contract_code,
            )
            .join(
                OperationalDebtContinuity,
                OperationalDebtContinuity.id == OperationalDebtRefinancedInstallment.continuity_id,
            )
            .join(
                OperationalSaleIdentity,
                OperationalSaleIdentity.id == OperationalDebtContinuity.successor_sale_identity_id,
            )
            .where(OperationalDebtContinuity.status == "REFIN_CONFIRMED")
        )
        if revenue_identity_ids is not None:
            statement = statement.where(
                OperationalDebtRefinancedInstallment.revenue_identity_id.in_(revenue_identity_ids)
            )
        rows = (await self._session.execute(statement)).all()
        return dict(rows)

    async def _loan_display_names(
        self, promotion_id: int, contract_codes: set[str] | None = None
    ) -> dict[str, tuple[str | None, bool]]:
        statement = (
            select(OperationalLoan.contract_code, ExcelEconEmprestimosRow.nome_cliente)
            .join(
                ExcelEconEmprestimosRow,
                ExcelEconEmprestimosRow.id == OperationalLoan.source_loan_row_id,
            )
            .where(OperationalLoan.promotion_id == promotion_id)
        )
        if contract_codes is not None:
            if not contract_codes:
                return {}
            statement = statement.where(OperationalLoan.contract_code.in_(contract_codes))
        rows = (await self._session.execute(statement)).all()
        names_by_contract: dict[str, set[str]] = {}
        for contract_code, name in rows:
            normalized = (name or "").strip()
            if not contract_code or not normalized:
                continue
            names_by_contract.setdefault(contract_code, set()).add(normalized)
        return {
            contract_code: (next(iter(names)) if len(names) == 1 else None, len(names) > 1)
            for contract_code, names in names_by_contract.items()
        }

    async def _bank_validation_statuses(self, movement_keys: list[str]) -> dict[str, str]:
        if not movement_keys:
            return {}
        rows = (
            await self._session.execute(
                select(
                    TreasuryBankValidation.movement_key,
                    TreasuryBankValidation.status,
                ).where(
                    TreasuryBankValidation.movement_key.in_(movement_keys),
                    TreasuryBankValidation.is_current.is_(True),
                )
            )
        ).all()
        return dict(rows)

    async def _current_promotion_id(self) -> int:
        promotion_id = await self._session.scalar(
            select(OperationalPromotion.id).where(
                OperationalPromotion.is_current.is_(True),
                OperationalPromotion.status == "succeeded",
            )
        )
        if promotion_id is None:
            raise RuntimeError("Nenhuma promoção operacional atual está disponível.")
        return promotion_id

    @staticmethod
    def _filter_sales(rows: list[_SaleRecord], query: SalesQuery) -> list[_SaleRecord]:
        search = _normalized(query.search)
        contract = _normalized(query.contract)
        client = _normalized(query.client)
        status = _normalized(query.status)
        return [
            row
            for row in rows
            if (
                not search
                or search
                in " ".join(
                    filter(
                        None,
                        (
                            _normalized(row.item.contract_code),
                            _normalized(row.item.client_name),
                            _normalized(row.item.source_client_code),
                        ),
                    )
                )
            )
            and (not contract or contract in _normalized(row.item.contract_code))
            and (not client or client in _normalized(row.item.client_name))
            and (not status or status == _normalized(row.item.status))
            and (
                query.period_from is None
                or _date_at_least(row.item.operation_date, query.period_from)
            )
            and (query.period_to is None or _date_at_most(row.item.operation_date, query.period_to))
            and (query.quality is None or row.item.data_quality_status == query.quality)
        ]

    async def _quality_for_sales(
        self, rows: list[_SaleRecord]
    ) -> dict[tuple[str, int], list[QualityMessage]]:
        ids = {
            "contract": {row.contract_id for row in rows if row.contract_id is not None},
            "loan": {row.loan_id for row in rows if row.loan_id is not None},
            "client": {row.client_id for row in rows if row.client_id is not None},
        }
        return await self._load_quality(ids)

    async def _quality_for_installments(
        self, rows: list[_RevenueRecord]
    ) -> dict[tuple[str, int], list[QualityMessage]]:
        quality = await self._load_quality({"installment": {row.installment_id for row in rows}})
        for row in rows:
            key = ("installment", row.installment_id)
            existing_types = {message.type for message in quality.get(key, [])}
            for issue in operational_revenue_components_for_kpi(row.item).issues:
                if issue.type in existing_types:
                    continue
                quality.setdefault(key, []).append(
                    QualityMessage(
                        type=issue.type,
                        severity=issue.severity,
                        message=issue.message,
                    )
                )
                existing_types.add(issue.type)
        return quality

    async def _load_quality(
        self, ids: dict[str, set[int]]
    ) -> dict[tuple[str, int], list[QualityMessage]]:
        conditions = []
        column_by_kind = {
            "client": OperationalQualityLink.client_id,
            "contract": OperationalQualityLink.contract_id,
            "loan": OperationalQualityLink.loan_id,
            "installment": OperationalQualityLink.installment_id,
        }
        for kind, values in ids.items():
            if values:
                conditions.append(column_by_kind[kind].in_(values))
        if not conditions:
            return {}
        rows = (
            await self._session.execute(
                select(OperationalQualityLink, DataInconsistency)
                .outerjoin(
                    DataInconsistency,
                    DataInconsistency.id == OperationalQualityLink.data_inconsistency_id,
                )
                .where(or_(*conditions))
                .order_by(OperationalQualityLink.id)
            )
        ).all()
        result: dict[tuple[str, int], list[QualityMessage]] = {}
        for link, source in rows:
            kind, entity_id = _quality_target(link)
            issue_type = source.inconsistency_type if source else link.issue_type or "data_quality"
            severity = (source.severity if source else link.severity or "warning").upper()
            if severity not in {"WARNING", "DIVERGENT"}:
                continue
            result.setdefault((kind, entity_id), []).append(
                QualityMessage(
                    type=issue_type,
                    severity=severity,
                    message=FRIENDLY_MESSAGES.get(
                        issue_type,
                        source.message
                        if source
                        else link.message or "Qualidade do dado requer revisão.",
                    ),
                )
            )
        return result

    def _sale_with_counts(
        self,
        row: _SaleRecord,
        quality: dict[tuple[str, int], list[QualityMessage]],
    ) -> SaleItem:
        messages = self._sale_messages(row, quality)
        return row.item.model_copy(
            update={
                "warning_count": sum(message.severity == "WARNING" for message in messages),
                "divergence_count": sum(message.severity == "DIVERGENT" for message in messages),
            }
        )

    @staticmethod
    def _sale_messages(
        row: _SaleRecord,
        quality: dict[tuple[str, int], list[QualityMessage]],
    ) -> list[QualityMessage]:
        messages = []
        for kind, entity_id in (
            ("contract", row.contract_id),
            ("loan", row.loan_id),
            ("client", row.client_id),
        ):
            if entity_id is not None:
                messages.extend(quality.get((kind, entity_id), []))
        return messages

    @staticmethod
    def _revenue_with_counts(
        row: _RevenueRecord,
        quality: dict[tuple[str, int], list[QualityMessage]],
    ) -> RevenueItem:
        messages = quality.get(("installment", row.installment_id), [])
        return row.item.model_copy(
            update={
                "warning_count": sum(message.severity == "WARNING" for message in messages),
                "divergence_count": sum(message.severity == "DIVERGENT" for message in messages),
            }
        )


def _quality_target(link: OperationalQualityLink) -> tuple[str, int]:
    for kind in ("client", "contract", "loan", "installment"):
        entity_id = getattr(link, f"{kind}_id")
        if entity_id is not None:
            return kind, entity_id
    raise RuntimeError("Vínculo de qualidade sem registro operacional.")


def _parse_sale_reference(
    sale_id: str | None,
) -> tuple[UUID | None, str | None, int | None]:
    if sale_id is None:
        return None, None, None
    try:
        kind, raw_id = sale_id.split(":", 1)
    except ValueError:
        return None, None, None
    if kind == "sale":
        try:
            return UUID(raw_id), kind, None
        except ValueError:
            return None, kind, None
    if kind not in {"contract", "loan"}:
        return None, kind, None
    try:
        return None, kind, int(raw_id)
    except ValueError:
        return None, kind, None


def calculate_revenue_kpis(items: list[RevenueItem], as_of: date) -> dict[str, Decimal]:
    """Current exposure excludes REFIN while preserving every real payment.

    REGRA PROVISÓRIA REMO: inadimplência = PMT vencida / PMT aberta.
    A fórmula permanece até confirmação futura da REMO.
    """

    analyses = [(item, operational_revenue_components_for_kpi(item)) for item in items]
    current = [
        (item, analysis) for item, analysis in analyses if item.installment_status != "REFIN"
    ]
    open_items = [(item, analysis) for item, analysis in current if item.payment_date is None]
    overdue = [
        (item, analysis)
        for item, analysis in open_items
        if item.due_date is not None and item.due_date < as_of
    ]
    open_pmt = _sum(item.expected_amount for item, _analysis in open_items)
    overdue_pmt = _sum(item.expected_amount for item, _analysis in overdue)
    pmt_values = [
        item.expected_amount for item, _analysis in current if item.expected_amount is not None
    ]
    return {
        "paid_total": _sum(analysis.paid for _item, analysis in analyses),
        "principal_received": _sum(analysis.realized_principal for _item, analysis in analyses),
        "principal_total": _sum(analysis.principal for _item, analysis in current),
        "interest_total": _sum(analysis.interest for _item, analysis in current),
        "discount_total": _sum(analysis.discount for _item, analysis in analyses),
        "principal_open": _sum(analysis.principal for _item, analysis in open_items),
        "average_pmt": (
            (_sum(pmt_values) / Decimal(len(pmt_values))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if pmt_values
            else ZERO
        ),
        "overdue_principal": _sum(analysis.principal for _item, analysis in overdue),
        "overdue_pmt": overdue_pmt,
        "delinquency_percentage": (
            (overdue_pmt / open_pmt * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            if open_pmt > ZERO
            else ZERO
        ),
    }


def operational_revenue_components_for_kpi(
    item: RevenueItem,
) -> OperationalRevenueComponents:
    """Interpret source components for operational analytics without mutating them.

    Negative amortization and negative-interest schedule adjustments are valid source
    characteristics when principal plus interest still reconciles to the expected PMT.
    They are not cash realization: only that negative component is excluded from its
    operational KPI. Other negative values are source divergences and receive the same
    component-local treatment so one legacy row cannot make the whole listing fail.

    Financial distribution remains strict and continues to call
    ``realized_revenue_components`` with the persisted values.
    """

    principal = Decimal(item.principal_component or ZERO)
    interest = Decimal(item.interest_component or ZERO)
    discount = Decimal(item.discount_amount or ZERO)
    paid = Decimal(item.paid_amount or ZERO)
    expected = Decimal(item.expected_amount) if item.expected_amount is not None else None
    schedule_reconciles = bool(
        expected is not None
        and (principal + interest).quantize(CENT, rounding=ROUND_HALF_UP)
        == expected.quantize(CENT, rounding=ROUND_HALF_UP)
    )
    issues: list[OperationalRevenueIssue] = []

    if principal < ZERO:
        if schedule_reconciles and interest >= ZERO:
            issues.append(
                OperationalRevenueIssue(
                    type="negative_amortization",
                    severity="WARNING",
                    message=(
                        "Principal negativo representa amortização negativa no cronograma; "
                        "foi excluído somente dos KPIs de principal e realização. O dado "
                        "original foi preservado."
                    ),
                )
            )
        else:
            issues.append(
                OperationalRevenueIssue(
                    type="negative_principal_component",
                    severity="DIVERGENT",
                    message=(
                        "Componente de principal negativo não reconciliado com a PMT; foi "
                        "excluído somente dos KPIs de principal e realização. O dado "
                        "original foi preservado."
                    ),
                )
            )
        analytic_principal = ZERO
    else:
        analytic_principal = principal

    if interest < ZERO:
        if schedule_reconciles and principal >= ZERO:
            issues.append(
                OperationalRevenueIssue(
                    type="negative_interest_adjustment",
                    severity="WARNING",
                    message=(
                        "Juros negativos representam ajuste no cronograma; foram excluídos "
                        "somente dos KPIs de juros e realização. O dado original foi "
                        "preservado."
                    ),
                )
            )
        else:
            issues.append(
                OperationalRevenueIssue(
                    type="negative_interest_component",
                    severity="DIVERGENT",
                    message=(
                        "Componente de juros negativo não reconciliado com a PMT; foi "
                        "excluído somente dos KPIs de juros e realização. O dado original "
                        "foi preservado."
                    ),
                )
            )
        analytic_interest = ZERO
    else:
        analytic_interest = interest

    if discount < ZERO:
        issues.append(
            OperationalRevenueIssue(
                type="negative_discount_component",
                severity="DIVERGENT",
                message=(
                    "Desconto negativo é divergente para o KPI operacional e foi excluído "
                    "somente desse cálculo. O dado original foi preservado."
                ),
            )
        )
        analytic_discount = ZERO
    else:
        analytic_discount = discount

    if paid < ZERO:
        issues.append(
            OperationalRevenueIssue(
                type="negative_paid_amount",
                severity="DIVERGENT",
                message=(
                    "Pagamento negativo é divergente para o KPI operacional e foi excluído "
                    "somente desse cálculo. O dado original foi preservado."
                ),
            )
        )
        analytic_paid = ZERO
    else:
        analytic_paid = paid

    realized = realized_revenue_components(
        principal=analytic_principal,
        interest=analytic_interest,
        discount=analytic_discount,
        paid_amount=analytic_paid,
    )
    return OperationalRevenueComponents(
        paid=analytic_paid,
        principal=analytic_principal,
        interest=analytic_interest,
        discount=analytic_discount,
        realized_principal=realized["principal"],
        realized_interest=realized["interest"],
        realized_discount=realized["discount"],
        issues=tuple(issues),
    )


def _highest_quality(left: str, right: str) -> str:
    return max((left, right), key=QUALITY_ORDER.__getitem__)


def _sum(values) -> Decimal:
    return sum((value for value in values if value is not None), start=ZERO)


def _normalized(value: str | None) -> str:
    return value.strip().casefold() if value else ""


def _display_client_name(
    canonical_name: str | None,
    loan_source: tuple[str | None, bool] | None,
) -> tuple[str | None, str | None, bool]:
    canonical = (canonical_name or "").strip() or None
    loan_name, source_divergent = loan_source or (None, False)
    divergent = source_divergent or bool(
        canonical and loan_name and _normalized(canonical) != _normalized(loan_name)
    )
    if canonical:
        return canonical, "CLIENT_CANONICAL", divergent
    if loan_name and not source_divergent:
        return loan_name, "ECON_EMPRESTIMOS", False
    return None, None, divergent


def _date_at_least(value: date | None, minimum: date) -> bool:
    return value is not None and value >= minimum


def _date_at_most(value: date | None, maximum: date) -> bool:
    return value is not None and value <= maximum


def _loan_display_names_query(promotion_id: int):
    source_name = func.nullif(func.btrim(ExcelEconEmprestimosRow.nome_cliente), "")
    return (
        select(
            OperationalLoan.contract_code.label("contract_code"),
            func.min(source_name).label("client_name"),
            func.count(func.distinct(source_name)).label("name_count"),
        )
        .join(
            ExcelEconEmprestimosRow,
            ExcelEconEmprestimosRow.id == OperationalLoan.source_loan_row_id,
        )
        .where(
            OperationalLoan.promotion_id == promotion_id,
            OperationalLoan.contract_code.is_not(None),
            source_name.is_not(None),
        )
        .group_by(OperationalLoan.contract_code)
        .subquery("revenue_loan_names")
    )


def _is_refinanced_expression():
    return (
        select(OperationalDebtRefinancedInstallment.id)
        .join(
            OperationalDebtContinuity,
            OperationalDebtContinuity.id == OperationalDebtRefinancedInstallment.continuity_id,
        )
        .where(
            OperationalDebtRefinancedInstallment.revenue_identity_id
            == OperationalRevenueSnapshot.revenue_identity_id,
            OperationalDebtContinuity.status == "REFIN_CONFIRMED",
        )
        .exists()
    )


def _revenue_quality_expression():
    principal = func.coalesce(OperationalInstallment.principal_component, ZERO)
    interest = func.coalesce(OperationalInstallment.interest_component, ZERO)
    discount = func.coalesce(OperationalInstallment.discount_amount, ZERO)
    paid = func.coalesce(OperationalInstallment.paid_amount, ZERO)
    expected = OperationalInstallment.expected_amount
    reconciles = and_(
        expected.is_not(None),
        func.round(principal + interest, 2) == func.round(expected, 2),
    )
    divergent_component = or_(
        discount < ZERO,
        paid < ZERO,
        and_(principal < ZERO, not_(and_(reconciles, interest >= ZERO))),
        and_(interest < ZERO, not_(and_(reconciles, principal >= ZERO))),
    )
    warning_component = or_(principal < ZERO, interest < ZERO)
    source_quality = OperationalInstallment.data_quality_status
    return case(
        (source_quality == "INVALID", "INVALID"),
        (or_(source_quality == "DIVERGENT", divergent_component), "DIVERGENT"),
        (or_(source_quality == "WARNING", warning_component), "WARNING"),
        else_="VALID",
    )


def _revenue_state_expressions(as_of: date, refinanced):
    paid = func.coalesce(OperationalInstallment.paid_amount, ZERO)
    discount = func.coalesce(OperationalInstallment.discount_amount, ZERO)
    expected = OperationalInstallment.expected_amount
    status = func.coalesce(func.upper(func.btrim(OperationalInstallment.installment_status)), "")
    terminal_statuses = (
        "PAGO",
        "PAGO_ANTEC",
        "LIQ REFIN",
        "REFIN",
        "PREJUÍZO",
        "CANCELADO",
    )
    has_open_balance = and_(
        expected.is_not(None),
        paid + discount < expected,
        not_(status.in_(terminal_statuses)),
    )
    open_exposure = and_(
        not_(refinanced),
        or_(OperationalInstallment.payment_date.is_(None), has_open_balance),
    )
    received = and_(
        OperationalInstallment.payment_date.is_not(None),
        paid > ZERO,
    )
    overdue = and_(
        open_exposure,
        OperationalInstallment.due_date.is_not(None),
        OperationalInstallment.due_date < as_of,
    )
    future = and_(
        open_exposure,
        OperationalInstallment.due_date.is_not(None),
        OperationalInstallment.due_date > as_of,
    )
    return received, open_exposure, overdue, future


def _escaped_contains(column, value: str):
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


def _apply_revenue_filters(
    statement,
    query: RevenueQuery,
    as_of: date,
    loan_names_query,
    refinanced,
):
    canonical_name = func.nullif(func.btrim(OperationalClient.name), "")
    source_name = case(
        (loan_names_query.c.name_count == 1, loan_names_query.c.client_name),
    )
    display_name = func.coalesce(canonical_name, source_name)
    effective_status = case(
        (refinanced, "REFIN"),
        else_=OperationalInstallment.installment_status,
    )
    conditions = []
    if query.search and query.search.strip():
        conditions.append(
            or_(
                _escaped_contains(OperationalInstallment.contract_code, query.search),
                _escaped_contains(display_name, query.search),
                _escaped_contains(OperationalInstallment.installment_code, query.search),
            )
        )
    if query.contract and query.contract.strip():
        conditions.append(_escaped_contains(OperationalInstallment.contract_code, query.contract))
    if query.client and query.client.strip():
        conditions.append(_escaped_contains(display_name, query.client))
    if query.status and query.status.strip():
        conditions.append(func.lower(effective_status) == query.status.strip().casefold())
    if query.due_from is not None:
        conditions.append(OperationalInstallment.due_date >= query.due_from)
    if query.due_to is not None:
        conditions.append(OperationalInstallment.due_date <= query.due_to)
    if query.payment_from is not None:
        conditions.append(OperationalInstallment.payment_date >= query.payment_from)
    if query.payment_to is not None:
        conditions.append(OperationalInstallment.payment_date <= query.payment_to)
    if query.quality is not None:
        conditions.append(_revenue_quality_expression() == query.quality)

    received, open_exposure, overdue, future = _revenue_state_expressions(as_of, refinanced)
    view_condition = {
        "received": received,
        "open": open_exposure,
        "overdue": overdue,
        "future": future,
    }.get(query.view)
    if view_condition is not None:
        conditions.append(view_condition)
    return statement.where(*conditions) if conditions else statement


def _apply_revenue_ordering(statement, query: RevenueQuery, as_of: date, refinanced):
    due_date = OperationalInstallment.due_date
    payment_date = OperationalInstallment.payment_date
    if query.sort_by == "operational_relevance":
        received, open_exposure, overdue, _future = _revenue_state_expressions(as_of, refinanced)
        near_limit = as_of + timedelta(days=30)
        near_due = and_(
            open_exposure,
            due_date.is_not(None),
            due_date >= as_of,
            due_date <= near_limit,
        )
        current = or_(due_date.is_(None), due_date <= near_limit)
        priority = case(
            (overdue, 0),
            (near_due, 1),
            (received, 2),
            (current, 3),
            else_=4,
        )
        return statement.order_by(
            priority.asc(),
            case((overdue, due_date)).asc().nulls_last(),
            case((near_due, due_date)).asc().nulls_last(),
            case((received, payment_date)).desc().nulls_last(),
            case((current, due_date)).desc().nulls_last(),
            due_date.asc().nulls_last(),
            OperationalInstallment.id.asc(),
        )

    attributes = {
        "due_date": due_date,
        "payment_date": payment_date,
        "contract_code": OperationalInstallment.contract_code,
        "expected_amount": OperationalInstallment.expected_amount,
        "paid_amount": OperationalInstallment.paid_amount,
        "quality": _revenue_quality_expression(),
    }
    column = attributes.get(query.sort_by, due_date)
    ordered = column.asc() if query.sort_order == "asc" else column.desc()
    return statement.order_by(ordered.nulls_last(), OperationalInstallment.id.asc())


def _paginate(rows: list[Any], page: int, page_size: int) -> tuple[list[Any], PageMeta]:
    total = len(rows)
    pages = ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    return rows[start : start + page_size], PageMeta(
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


def _sort_sales(
    rows: list[_SaleRecord], sort_by: str, order: Literal["asc", "desc"]
) -> list[_SaleRecord]:
    attributes = {
        "operation_date": "operation_date",
        "contract_code": "contract_code",
        "principal": "principal",
        "released_amount": "released_amount",
        "quality": "data_quality_status",
    }
    attribute = attributes.get(sort_by, "operation_date")
    return sorted(
        rows,
        key=lambda row: (getattr(row.item, attribute) is not None, getattr(row.item, attribute)),
        reverse=order == "desc",
    )
