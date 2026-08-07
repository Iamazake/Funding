from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic_ns
from typing import Any, Protocol

from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
)
from app.services.excel.parsers import round_money

QUALITY_ORDER = {"VALID": 0, "WARNING": 1, "DIVERGENT": 2, "INVALID": 3}

CONTRACT_LOAN_COMPARISONS = {
    "source_client_code": ("cod_cliente", "cod_cliente"),
    "cpf_normalized": ("cpf_normalized", "cpf_normalized"),
    "operation_date": ("dt_operacao", "dt_operacao"),
    "first_due_date": ("vcto_prim_parc", "vencimento1"),
    "term": ("prazo", "prazo_pgto"),
    "principal": ("principal", "vl_principal"),
    "iof": ("iof", "iof"),
    "financed_amount": ("vl_financiado", "vl_finaciado"),
    "installment_amount": ("pmt", "pmt"),
    "released_amount": ("vl_liberado", "vl_liberado"),
}


class OperationalPromotionError(RuntimeError):
    """Safe, user-facing failure in normalized operational promotion."""


class SourceBatchNotFoundError(OperationalPromotionError):
    pass


class SourceBatchNotSucceededError(OperationalPromotionError):
    pass


@dataclass(frozen=True, slots=True)
class ExistingPromotion:
    id: int
    summary: dict[str, Any]


@dataclass(slots=True)
class MirrorBatch:
    clients: list[ExcelBcliCadastroRow]
    contracts: list[ExcelDfenContratoRow]
    loans: list[ExcelEconEmprestimosRow]
    amortizations: list[ExcelEconAmortizacoesRow]
    inconsistencies: list[DataInconsistency]


@dataclass(slots=True)
class RecordDraft:
    source_row_id: int
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class QualityLinkDraft:
    entity_kind: str
    entity_source_row_id: int
    data_inconsistency_id: int | None = None
    issue_type: str | None = None
    severity: str | None = None
    message: str | None = None


@dataclass(slots=True)
class OperationalDataset:
    clients: list[RecordDraft] = field(default_factory=list)
    contracts: list[RecordDraft] = field(default_factory=list)
    loans: list[RecordDraft] = field(default_factory=list)
    installments: list[RecordDraft] = field(default_factory=list)
    payment_movements: list[RecordDraft] = field(default_factory=list)
    quality_links: list[QualityLinkDraft] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromotionReport:
    promotion_id: int
    source_batch_id: int
    status: str
    idempotent: bool
    summary: dict[str, Any]


class PromotionRepository(Protocol):
    async def get_batch_status(self, batch_id: int) -> str | None: ...

    async def get_succeeded_promotion(self, batch_id: int) -> ExistingPromotion | None: ...

    async def load_batch(self, batch_id: int) -> MirrorBatch: ...

    async def persist(
        self,
        batch_id: int,
        dataset: OperationalDataset,
        *,
        started_at: datetime,
        started_ns: int,
    ) -> ExistingPromotion: ...


class OperationalPromotionBuilder:
    def build(self, batch_id: int, source: MirrorBatch) -> OperationalDataset:
        dataset = OperationalDataset()
        issues_by_row: dict[tuple[str, int], list[DataInconsistency]] = defaultdict(list)
        for issue in source.inconsistencies:
            if issue.source_row_number is not None:
                issues_by_row[(issue.source_sheet, issue.source_row_number)].append(issue)

        clients_by_code: dict[str, list[ExcelBcliCadastroRow]] = defaultdict(list)
        clients_by_cpf: dict[str, list[ExcelBcliCadastroRow]] = defaultdict(list)
        for row in source.clients:
            if row.cod_cliente:
                clients_by_code[row.cod_cliente].append(row)
            if row.cpf_normalized:
                clients_by_cpf[row.cpf_normalized].append(row)

        for row in source.clients:
            quality = _quality(row.validation_status)
            duplicate_identity = (
                bool(row.cod_cliente and len(clients_by_code[row.cod_cliente]) > 1)
                or bool(row.cpf_normalized and len(clients_by_cpf[row.cpf_normalized]) > 1)
            )
            if duplicate_identity:
                quality = _highest_quality(quality, "WARNING")
                dataset.quality_links.append(
                    QualityLinkDraft(
                        "client",
                        row.id,
                        issue_type="ambiguous_client_identity",
                        severity="WARNING",
                        message=(
                            "Identidade operacional aparece em múltiplas linhas; "
                            "preservada sem fusão."
                        ),
                    )
                )
            dataset.clients.append(
                RecordDraft(
                    row.id,
                    _snapshot_values(
                        batch_id,
                        quality,
                        source_bcli_row_id=row.id,
                        source_client_code=row.cod_cliente,
                        cpf_original=row.cpf_original,
                        cpf_normalized=row.cpf_normalized,
                        name=row.nome_cliente,
                        birth_date=row.dt_nasc,
                    ),
                )
            )
            self._link_source_issues(dataset, "client", row, issues_by_row)

        contract_by_code = {
            row.cod_contrato: row for row in source.contracts if row.cod_contrato is not None
        }
        loan_by_code = {
            row.cod_contrato: row for row in source.loans if row.cod_contrato is not None
        }
        difference_counts: Counter[str] = Counter()

        for row in source.contracts:
            client_row, ambiguous = _resolve_client(
                row.cod_cliente, row.cpf_normalized, clients_by_code, clients_by_cpf
            )
            quality = _quality(row.validation_status)
            if ambiguous:
                quality = _highest_quality(quality, "WARNING")
                dataset.quality_links.append(_ambiguous_relationship("contract", row.id))
            matched_loan = loan_by_code.get(row.cod_contrato)
            if matched_loan is not None:
                for field_name, (dfen_name, loan_name) in CONTRACT_LOAN_COMPARISONS.items():
                    if getattr(row, dfen_name) != getattr(matched_loan, loan_name):
                        difference_counts[field_name] += 1
            dataset.contracts.append(
                RecordDraft(
                    row.id,
                    _snapshot_values(
                        batch_id,
                        quality,
                        source_dfen_row_id=row.id,
                        client_source_row_id=client_row.id if client_row else None,
                        contract_code=row.cod_contrato,
                        source_client_code=row.cod_cliente,
                        cpf_normalized=row.cpf_normalized,
                        operation_date=row.dt_operacao,
                        first_due_date=row.vcto_prim_parc,
                        term=row.prazo,
                        principal=_money(row.principal),
                        iof=_money(row.iof),
                        financed_amount=_money(row.vl_financiado),
                        installment_amount=_money(row.pmt),
                        released_amount=_money(row.vl_liberado),
                        released_amount_original=_raw_text(row.raw_data, "VL_LIBERADO"),
                        release_date=row.data_liberacao,
                        operational_status=matched_loan.status if matched_loan else None,
                    ),
                )
            )
            self._link_source_issues(dataset, "contract", row, issues_by_row)

        for row in source.loans:
            client_row, ambiguous = _resolve_client(
                row.cod_cliente, row.cpf_normalized, clients_by_code, clients_by_cpf
            )
            quality = _quality(row.validation_status)
            if ambiguous:
                quality = _highest_quality(quality, "WARNING")
                dataset.quality_links.append(_ambiguous_relationship("loan", row.id))
            contract_row = contract_by_code.get(row.cod_contrato)
            dataset.loans.append(
                RecordDraft(
                    row.id,
                    _snapshot_values(
                        batch_id,
                        quality,
                        source_loan_row_id=row.id,
                        contract_source_row_id=contract_row.id if contract_row else None,
                        client_source_row_id=client_row.id if client_row else None,
                        contract_code=row.cod_contrato,
                        source_client_code=row.cod_cliente,
                        cpf_normalized=row.cpf_normalized,
                        operation_date=row.dt_operacao,
                        first_due_date=row.vencimento1,
                        term=row.prazo_pgto,
                        principal=_money(row.vl_principal),
                        iof=_money(row.iof),
                        financed_amount=_money(row.vl_finaciado),
                        installment_amount=_money(row.pmt),
                        released_amount=_money(row.vl_liberado),
                        released_amount_original=_raw_text(row.raw_data, "VL_LIBERADO"),
                        interest_rate=row.taxa_juros,
                        irr_rate=row.taxa_tir,
                        cet_monthly_rate=row.taxa_cet_am,
                        operational_status=row.status,
                    ),
                )
            )
            self._link_source_issues(dataset, "loan", row, issues_by_row)

        group_sizes = Counter(
            (row.cod_contrato, row.cod_parcela)
            for row in source.amortizations
            if row.cod_contrato and row.cod_parcela
        )
        for row in source.amortizations:
            contract_row = contract_by_code.get(row.cod_contrato)
            group_key = (
                f"{row.cod_contrato}|{row.cod_parcela}"
                if row.cod_contrato and row.cod_parcela
                else None
            )
            dataset.installments.append(
                RecordDraft(
                    row.id,
                    _snapshot_values(
                        batch_id,
                        _quality(row.validation_status),
                        source_amortization_row_id=row.id,
                        contract_source_row_id=contract_row.id if contract_row else None,
                        contract_code=row.cod_contrato,
                        installment_code=row.cod_parcela,
                        candidate_group_key=group_key,
                        candidate_group_size=group_sizes.get(
                            (row.cod_contrato, row.cod_parcela), 1
                        ),
                        due_date=row.vencimento,
                        expected_amount=_money(row.val_parcela),
                        principal_component=_money(row.val_amtz_princ),
                        interest_component=_money(row.val_amtz_jur),
                        paid_amount=_money(row.val_pgto),
                        payment_date=row.dt_baixatotal,
                        discount_amount=_money(row.desconto_conc),
                        discount_amount_original=_raw_text(row.raw_data, "DESCONTO_CONC"),
                        payment_marker_original=row.baixa_total_original,
                        installment_status=row.status_parc,
                        situation=row.situacao,
                        anticipation_marker=row.bol_antecip,
                        source_key=row.chave_referencia,
                        financial_product=row.produto_financeiro,
                    ),
                )
            )
            self._link_source_issues(dataset, "installment", row, issues_by_row)

        dataset.summary = {
            "source_batch_id": batch_id,
            "records": {
                "clients": len(dataset.clients),
                "contracts": len(dataset.contracts),
                "loans": len(dataset.loans),
                "installments": len(dataset.installments),
                "payment_movements": 0,
            },
            "quality": _quality_summary(dataset),
            "contract_loan_field_differences": dict(sorted(difference_counts.items())),
            "candidate_installment_groups": sum(size > 1 for size in group_sizes.values()),
            "candidate_installment_rows": sum(
                size for size in group_sizes.values() if size > 1
            ),
            "payment_movement_strategy": "prepared_not_auto_materialized",
        }
        return dataset

    @staticmethod
    def _link_source_issues(
        dataset: OperationalDataset,
        entity_kind: str,
        row: Any,
        issues_by_row: dict[tuple[str, int], list[DataInconsistency]],
    ) -> None:
        for issue in issues_by_row.get((row.source_sheet, row.source_row_number), []):
            dataset.quality_links.append(
                QualityLinkDraft(
                    entity_kind,
                    row.id,
                    data_inconsistency_id=issue.id,
                )
            )


class OperationalPromotionService:
    def __init__(
        self,
        repository: PromotionRepository,
        builder: OperationalPromotionBuilder | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], int] | None = None,
    ) -> None:
        self._repository = repository
        self._builder = builder or OperationalPromotionBuilder()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic_clock = monotonic_clock or monotonic_ns

    async def promote(self, batch_id: int) -> PromotionReport:
        if batch_id <= 0:
            raise SourceBatchNotFoundError("O batch informado não existe.")
        status = await self._repository.get_batch_status(batch_id)
        if status is None:
            raise SourceBatchNotFoundError("O batch informado não existe.")
        if status != "succeeded":
            raise SourceBatchNotSucceededError("Somente batches sucedidos podem ser promovidos.")

        existing = await self._repository.get_succeeded_promotion(batch_id)
        if existing is not None:
            return PromotionReport(
                existing.id, batch_id, "already_promoted", True, existing.summary
            )

        started_at = self._clock()
        started_ns = self._monotonic_clock()
        source = await self._repository.load_batch(batch_id)
        dataset = self._builder.build(batch_id, source)
        promotion = await self._repository.persist(
            batch_id,
            dataset,
            started_at=started_at,
            started_ns=started_ns,
        )
        return PromotionReport(promotion.id, batch_id, "succeeded", False, promotion.summary)


def _resolve_client(
    code: str | None,
    cpf: str | None,
    by_code: dict[str, list[ExcelBcliCadastroRow]],
    by_cpf: dict[str, list[ExcelBcliCadastroRow]],
) -> tuple[ExcelBcliCadastroRow | None, bool]:
    code_candidates = by_code.get(code, []) if code else []
    cpf_candidates = by_cpf.get(cpf, []) if cpf else []
    if code and cpf:
        cpf_ids = {candidate.id for candidate in cpf_candidates}
        intersection = [candidate for candidate in code_candidates if candidate.id in cpf_ids]
        if len(intersection) == 1:
            return intersection[0], False
        if len(code_candidates) == 1 and not cpf_candidates:
            return code_candidates[0], False
        return None, bool(code_candidates or cpf_candidates)
    candidates = code_candidates or cpf_candidates
    if len(candidates) == 1:
        return candidates[0], False
    return None, len(candidates) > 1


def _snapshot_values(batch_id: int, quality: str, **values: Any) -> dict[str, Any]:
    return {
        **values,
        "data_quality_status": quality,
        "current_source_batch_id": batch_id,
        "first_seen_batch_id": batch_id,
        "last_seen_batch_id": batch_id,
        "active_in_source": True,
    }


def _quality(value: str) -> str:
    normalized = value.upper()
    if normalized not in QUALITY_ORDER:
        raise ValueError(f"Unsupported data quality status: {value}")
    return normalized


def _highest_quality(left: str, right: str) -> str:
    return max((left, right), key=QUALITY_ORDER.__getitem__)


def _money(value: Decimal | None) -> Decimal | None:
    return round_money(value) if value is not None else None


def _raw_text(raw_data: dict[str, Any], field_name: str) -> str | None:
    value = raw_data.get(field_name)
    return None if value is None or value == "" else str(value)


def _ambiguous_relationship(entity_kind: str, source_row_id: int) -> QualityLinkDraft:
    return QualityLinkDraft(
        entity_kind,
        source_row_id,
        issue_type="ambiguous_client_relationship",
        severity="WARNING",
        message="Relação com cliente não resolvida porque há mais de um candidato possível.",
    )


def _quality_summary(dataset: OperationalDataset) -> dict[str, dict[str, int]]:
    return {
        name: dict(
            sorted(Counter(record.values["data_quality_status"] for record in records).items())
        )
        for name, records in (
            ("clients", dataset.clients),
            ("contracts", dataset.contracts),
            ("loans", dataset.loans),
            ("installments", dataset.installments),
        )
    }
