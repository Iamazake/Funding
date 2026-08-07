from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import ceil
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPromotion,
    OperationalQualityLink,
)
from app.models.operational import DataInconsistency
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

QUALITY_ORDER = {"VALID": 0, "WARNING": 1, "DIVERGENT": 2, "INVALID": 3}
ZERO = Decimal("0.00")

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
    sort_by: str = "due_date"
    sort_order: Literal["asc", "desc"] = "desc"


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
            divergent_contracts=sum(
                row.item.data_quality_status == "DIVERGENT" for row in rows
            ),
        )
        page_rows, meta = _paginate(rows, query.page, query.page_size)
        quality = await self._quality_for_sales(page_rows)
        items = [self._sale_with_counts(row, quality) for row in page_rows]
        return SalesPage(items=items, pagination=meta, summary=summary)

    async def get_sale(self, sale_id: str) -> SaleDetail | None:
        row = next((item for item in await self._load_sales() if item.item.id == sale_id), None)
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
        rows = self._filter_revenue(await self._load_revenue(), query)
        rows = _sort_revenue(rows, query.sort_by, query.sort_order)
        summary = RevenueSummary(
            total_records=len(rows),
            expected_amount=_sum(row.item.expected_amount for row in rows),
            paid_amount=_sum(row.item.paid_amount for row in rows),
            principal_received=_sum(row.item.principal_component for row in rows),
            interest_amount=_sum(row.item.interest_component for row in rows),
            discount_amount=_sum(row.item.discount_amount for row in rows),
            pending_records=sum(row.item.payment_date is None for row in rows),
            warning_records=sum(row.item.data_quality_status == "WARNING" for row in rows),
            divergent_records=sum(
                row.item.data_quality_status == "DIVERGENT" for row in rows
            ),
        )
        page_rows, meta = _paginate(rows, query.page, query.page_size)
        quality = await self._quality_for_installments(page_rows)
        items = [self._revenue_with_counts(row, quality) for row in page_rows]
        return RevenuePage(items=items, pagination=meta, summary=summary)

    async def get_revenue(self, revenue_id: int) -> RevenueDetail | None:
        row = next(
            (item for item in await self._load_revenue() if item.installment_id == revenue_id),
            None,
        )
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

    async def _load_sales(self) -> list[_SaleRecord]:
        promotion_id = await self._current_promotion_id()
        contract_rows = (
            await self._session.execute(
                select(OperationalContract, OperationalClient)
                .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
                .where(OperationalContract.promotion_id == promotion_id)
            )
        ).all()
        loan_rows = (
            await self._session.execute(
                select(OperationalLoan, OperationalClient)
                .outerjoin(OperationalClient, OperationalClient.id == OperationalLoan.client_id)
                .where(OperationalLoan.promotion_id == promotion_id)
            )
        ).all()
        loans_by_contract: dict[int, tuple[OperationalLoan, OperationalClient | None]] = {}
        orphan_loans: list[tuple[OperationalLoan, OperationalClient | None]] = []
        for loan, client in loan_rows:
            if loan.contract_id is None:
                orphan_loans.append((loan, client))
            else:
                loans_by_contract[loan.contract_id] = (loan, client)

        records = []
        for contract, client in contract_rows:
            matched = loans_by_contract.get(contract.id)
            loan = matched[0] if matched else None
            quality = _highest_quality(
                contract.data_quality_status,
                loan.data_quality_status if loan is not None else "VALID",
            )
            records.append(
                _SaleRecord(
                    SaleItem(
                        id=f"contract:{contract.id}",
                        contract_code=contract.contract_code,
                        client_name=client.name if client else None,
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
        for loan, client in orphan_loans:
            records.append(
                _SaleRecord(
                    SaleItem(
                        id=f"loan:{loan.id}",
                        contract_code=loan.contract_code,
                        client_name=client.name if client else None,
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
        return records

    async def _load_revenue(self) -> list[_RevenueRecord]:
        promotion_id = await self._current_promotion_id()
        rows = (
            await self._session.execute(
                select(OperationalInstallment, OperationalContract, OperationalClient)
                .outerjoin(
                    OperationalContract,
                    OperationalContract.id == OperationalInstallment.contract_id,
                )
                .outerjoin(OperationalClient, OperationalClient.id == OperationalContract.client_id)
                .where(OperationalInstallment.promotion_id == promotion_id)
            )
        ).all()
        return [
            _RevenueRecord(
                RevenueItem(
                    id=installment.id,
                    contract_code=installment.contract_code,
                    client_name=client.name if client else None,
                    installment_code=installment.installment_code,
                    due_date=installment.due_date,
                    payment_date=installment.payment_date,
                    expected_amount=installment.expected_amount,
                    paid_amount=installment.paid_amount,
                    principal_component=installment.principal_component,
                    interest_component=installment.interest_component,
                    discount_amount=installment.discount_amount,
                    installment_status=installment.installment_status,
                    situation=installment.situation,
                    anticipation_marker=installment.anticipation_marker,
                    data_quality_status=installment.data_quality_status,
                ),
                installment.id,
                installment.payment_marker_original,
                installment.source_key,
            )
            for installment, _contract, client in rows
        ]

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

    @staticmethod
    def _filter_revenue(rows: list[_RevenueRecord], query: RevenueQuery) -> list[_RevenueRecord]:
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
                            _normalized(row.item.installment_code),
                        ),
                    )
                )
            )
            and (not contract or contract in _normalized(row.item.contract_code))
            and (not client or client in _normalized(row.item.client_name))
            and (not status or status == _normalized(row.item.installment_status))
            and (query.due_from is None or _date_at_least(row.item.due_date, query.due_from))
            and (query.due_to is None or _date_at_most(row.item.due_date, query.due_to))
            and (
                query.payment_from is None
                or _date_at_least(row.item.payment_date, query.payment_from)
            )
            and (
                query.payment_to is None or _date_at_most(row.item.payment_date, query.payment_to)
            )
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
        return await self._load_quality(
            {"installment": {row.installment_id for row in rows}}
        )

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
                "divergence_count": sum(
                    message.severity == "DIVERGENT" for message in messages
                ),
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
                "divergence_count": sum(
                    message.severity == "DIVERGENT" for message in messages
                ),
            }
        )


def _quality_target(link: OperationalQualityLink) -> tuple[str, int]:
    for kind in ("client", "contract", "loan", "installment"):
        entity_id = getattr(link, f"{kind}_id")
        if entity_id is not None:
            return kind, entity_id
    raise RuntimeError("Vínculo de qualidade sem registro operacional.")


def _highest_quality(left: str, right: str) -> str:
    return max((left, right), key=QUALITY_ORDER.__getitem__)


def _sum(values) -> Decimal:
    return sum((value for value in values if value is not None), start=ZERO)


def _normalized(value: str | None) -> str:
    return value.strip().casefold() if value else ""


def _date_at_least(value: date | None, minimum: date) -> bool:
    return value is not None and value >= minimum


def _date_at_most(value: date | None, maximum: date) -> bool:
    return value is not None and value <= maximum


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


def _sort_revenue(
    rows: list[_RevenueRecord], sort_by: str, order: Literal["asc", "desc"]
) -> list[_RevenueRecord]:
    attributes = {
        "due_date": "due_date",
        "payment_date": "payment_date",
        "contract_code": "contract_code",
        "expected_amount": "expected_amount",
        "paid_amount": "paid_amount",
        "quality": "data_quality_status",
    }
    attribute = attributes.get(sort_by, "due_date")
    return sorted(
        rows,
        key=lambda row: (getattr(row.item, attribute) is not None, getattr(row.item, attribute)),
        reverse=order == "desc",
    )
