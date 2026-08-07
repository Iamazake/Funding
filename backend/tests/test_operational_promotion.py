from __future__ import annotations

import inspect
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Numeric, UniqueConstraint

from app.cli import build_parser
from app.models.normalized import (
    OperationalContract,
    OperationalInstallment,
    OperationalPaymentMovement,
)
from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
)
from app.services.operational.promotion import (
    ExistingPromotion,
    MirrorBatch,
    OperationalDataset,
    OperationalPromotionBuilder,
    OperationalPromotionService,
    SourceBatchNotFoundError,
    SourceBatchNotSucceededError,
)
from app.services.operational.store import SqlAlchemyOperationalPromotionRepository


class InMemoryPromotionRepository:
    def __init__(self, status: str | None, source: MirrorBatch) -> None:
        self.status = status
        self.source = source
        self.promotions: dict[int, ExistingPromotion] = {}
        self.datasets: list[OperationalDataset] = []
        self.fail_persist = False

    async def get_batch_status(self, batch_id: int) -> str | None:
        return self.status

    async def get_succeeded_promotion(self, batch_id: int) -> ExistingPromotion | None:
        return self.promotions.get(batch_id)

    async def load_batch(self, batch_id: int) -> MirrorBatch:
        return self.source

    async def persist(
        self,
        batch_id: int,
        dataset: OperationalDataset,
        *,
        started_at: datetime,
        started_ns: int,
    ) -> ExistingPromotion:
        before = deepcopy(self.datasets)
        if self.fail_persist:
            self.datasets = before
            raise RuntimeError("synthetic transactional failure")
        promotion = ExistingPromotion(len(self.promotions) + 1, dataset.summary)
        self.datasets.append(dataset)
        self.promotions[batch_id] = promotion
        return promotion


def _meta(
    row_id: int,
    sheet: str,
    *,
    status: str = "valid",
    row_number: int | None = None,
    raw_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "import_batch_id": 2,
        "source_sheet": sheet,
        "source_row_number": row_number or row_id + 1,
        "source_row_hash": f"hash-{row_id}",
        "source_key": f"key-{row_id}",
        "validation_status": status,
        "validation_errors": [],
        "raw_data": raw_data or {},
        "last_seen_batch_id": 2,
        "source_active": True,
    }


def _client(
    row_id: int = 1,
    *,
    code: str = "C1",
    cpf: str | None = "12345678901",
    status: str = "valid",
) -> ExcelBcliCadastroRow:
    return ExcelBcliCadastroRow(
        **_meta(row_id, "BCLI_CADASTRO", status=status),
        cod_cliente_original=code,
        cod_cliente=code,
        cpf_original=cpf or "inválido",
        cpf_normalized=cpf,
        nome_cliente_original="Cliente Sintético",
        nome_cliente="Cliente Sintético",
        dt_nasc_original="2000-01-01",
        dt_nasc=None,
    )


def _contract(row_id: int = 10, *, code: str = "K1") -> ExcelDfenContratoRow:
    return ExcelDfenContratoRow(
        **_meta(row_id, "DFEN_CONTRATO", raw_data={"VL_LIBERADO": "100.005"}),
        cod_cliente="C1",
        cod_contrato=code,
        cpf_original="12345678901",
        cpf_normalized="12345678901",
        principal=Decimal("100.005"),
        iof=Decimal("1.005"),
        vl_financiado=Decimal("101.01"),
        pmt=Decimal("10.00"),
        vl_liberado=Decimal("100.005"),
    )


def _loan(
    row_id: int = 20,
    *,
    code: str = "K1",
    status: str = "valid",
) -> ExcelEconEmprestimosRow:
    return ExcelEconEmprestimosRow(
        **_meta(row_id, "ECON_EMPRESTIMOS", status=status),
        cod_contrato=code,
        cod_cliente="C1",
        cpf_original="12345678901",
        cpf_normalized="12345678901",
        vl_principal=Decimal("100.00"),
        iof=Decimal("1.00"),
        vl_finaciado=Decimal("101.00"),
        pmt=Decimal("10.00"),
        vl_liberado=Decimal("100.00"),
        taxa_juros=Decimal("0.0100000000"),
        taxa_tir=Decimal("0.0200000000"),
        taxa_cet_am=Decimal("0.0300000000"),
        status="ATIVO",
    )


def _amortization(
    row_id: int,
    *,
    code: str = "K1",
    installment: str = "1",
    status: str = "valid",
    discount: Decimal | None = Decimal("0.00"),
    discount_original: str = "0",
) -> ExcelEconAmortizacoesRow:
    return ExcelEconAmortizacoesRow(
        **_meta(
            row_id,
            "ECON_AMORTIZACOES",
            status=status,
            raw_data={"DESCONTO_CONC": discount_original},
        ),
        cod_cliente="C1",
        cpf_original="12345678901",
        cpf_normalized="12345678901",
        cod_contrato=code,
        cod_parcela=installment,
        val_amtz_jur=Decimal("1.005"),
        val_amtz_princ=Decimal("9.005"),
        val_parcela=Decimal("10.005"),
        baixa_total_original="S",
        val_pgto=Decimal("5.005"),
        desconto_conc=discount,
        status_parc="ABERTA",
        situacao="NORMAL",
        chave_referencia=f"REF-{row_id}",
        bol_antecip="N",
        produto_financeiro="TESTE",
    )


def _batch(
    *,
    clients: list[ExcelBcliCadastroRow] | None = None,
    contracts: list[ExcelDfenContratoRow] | None = None,
    loans: list[ExcelEconEmprestimosRow] | None = None,
    amortizations: list[ExcelEconAmortizacoesRow] | None = None,
    inconsistencies: list[DataInconsistency] | None = None,
) -> MirrorBatch:
    return MirrorBatch(
        clients if clients is not None else [_client()],
        contracts if contracts is not None else [_contract()],
        loans if loans is not None else [_loan()],
        amortizations if amortizations is not None else [_amortization(30)],
        inconsistencies or [],
    )


def test_cli_requires_an_explicit_batch_id() -> None:
    args = build_parser().parse_args(["promote-operational-batch", "2"])
    assert args.batch_id == 2
    with pytest.raises(SystemExit):
        build_parser().parse_args(["promote-operational-batch"])


@pytest.mark.asyncio
async def test_promotes_only_a_succeeded_existing_batch() -> None:
    succeeded = InMemoryPromotionRepository("succeeded", _batch())
    report = await OperationalPromotionService(succeeded).promote(2)
    assert report.status == "succeeded"
    assert report.source_batch_id == 2

    with pytest.raises(SourceBatchNotSucceededError):
        await OperationalPromotionService(InMemoryPromotionRepository("failed", _batch())).promote(
            2
        )
    with pytest.raises(SourceBatchNotFoundError):
        await OperationalPromotionService(InMemoryPromotionRepository(None, _batch())).promote(999)


@pytest.mark.asyncio
async def test_same_batch_promotion_is_idempotent() -> None:
    repository = InMemoryPromotionRepository("succeeded", _batch())
    service = OperationalPromotionService(repository)
    first = await service.promote(2)
    second = await service.promote(2)
    assert first.promotion_id == second.promotion_id
    assert second.idempotent is True
    assert len(repository.datasets) == 1


@pytest.mark.asyncio
async def test_successful_new_promotion_preserves_previous_snapshot() -> None:
    repository = InMemoryPromotionRepository("succeeded", _batch())
    previous = OperationalDataset(summary={"source_batch_id": 1})
    repository.datasets.append(previous)
    await OperationalPromotionService(repository).promote(2)
    assert repository.datasets[0] is previous
    assert [item.summary["source_batch_id"] for item in repository.datasets] == [1, 2]


def test_invalid_cpf_client_remains_as_warning_and_is_not_deduplicated() -> None:
    clients = [_client(1, cpf=None, status="warning"), _client(2, cpf=None, status="warning")]
    dataset = OperationalPromotionBuilder().build(2, _batch(clients=clients))
    assert len(dataset.clients) == 2
    assert {record.values["data_quality_status"] for record in dataset.clients} == {"WARNING"}
    assert all(record.values["cpf_normalized"] is None for record in dataset.clients)


def test_ambiguous_client_identity_is_preserved_and_not_silently_linked() -> None:
    clients = [_client(1), _client(2)]
    dataset = OperationalPromotionBuilder().build(2, _batch(clients=clients))
    assert len(dataset.clients) == 2
    assert dataset.contracts[0].values["client_source_row_id"] is None
    assert any(link.issue_type == "ambiguous_client_identity" for link in dataset.quality_links)
    assert any(link.issue_type == "ambiguous_client_relationship" for link in dataset.quality_links)


def test_normal_relationships_and_orphans_are_preserved() -> None:
    orphan_loan = _loan(21, code="ORPHAN", status="divergent")
    orphan_amortization = _amortization(31, code="ORPHAN", status="divergent")
    dataset = OperationalPromotionBuilder().build(
        2,
        _batch(
            loans=[_loan(), orphan_loan],
            amortizations=[_amortization(30), orphan_amortization],
        ),
    )
    assert dataset.contracts[0].values["client_source_row_id"] == 1
    assert dataset.installments[0].values["contract_source_row_id"] == 10
    assert dataset.loans[0].values["contract_source_row_id"] == 10
    assert dataset.loans[1].values["contract_source_row_id"] is None
    assert dataset.loans[1].values["data_quality_status"] == "DIVERGENT"
    assert dataset.installments[1].values["contract_source_row_id"] is None
    assert dataset.installments[1].values["data_quality_status"] == "DIVERGENT"


def test_multiple_source_rows_are_preserved_without_forced_payment_movements() -> None:
    rows = [_amortization(30), _amortization(31)]
    dataset = OperationalPromotionBuilder().build(2, _batch(amortizations=rows))
    assert len(dataset.installments) == 2
    assert {row.values["candidate_group_size"] for row in dataset.installments} == {2}
    assert dataset.payment_movements == []
    assert dataset.summary["candidate_installment_groups"] == 1
    assert dataset.summary["payment_movement_strategy"] == "prepared_not_auto_materialized"


def test_money_is_decimal_half_up_and_ambiguous_original_is_preserved() -> None:
    ambiguous = _amortization(
        30, status="warning", discount=None, discount_original="valor ambíguo"
    )
    dataset = OperationalPromotionBuilder().build(2, _batch(amortizations=[ambiguous]))
    contract = dataset.contracts[0].values
    installment = dataset.installments[0].values
    assert contract["principal"] == Decimal("100.01")
    assert installment["expected_amount"] == Decimal("10.01")
    assert installment["discount_amount"] is None
    assert installment["discount_amount_original"] == "valor ambíguo"
    assert not any(isinstance(value, float) for value in contract.values())


def test_source_inconsistency_is_referenced_instead_of_copied() -> None:
    inconsistency = DataInconsistency(
        id=70,
        sync_run_id=2,
        import_batch_id=2,
        source_sheet="ECON_AMORTIZACOES",
        source_row_number=31,
        inconsistency_type="invalid_cpf",
        field_name="NUM_CPF",
        message="synthetic",
        severity="warning",
        review_status="pending",
    )
    dataset = OperationalPromotionBuilder().build(
        2, _batch(amortizations=[_amortization(30)], inconsistencies=[inconsistency])
    )
    link = next(link for link in dataset.quality_links if link.data_inconsistency_id == 70)
    assert link.entity_kind == "installment"
    assert link.issue_type is None
    assert link.message is None


@pytest.mark.asyncio
async def test_transaction_failure_rolls_back_and_previous_state_is_preserved() -> None:
    repository = InMemoryPromotionRepository("succeeded", _batch())
    repository.datasets.append(OperationalDataset(summary={"source_batch_id": 1}))
    previous = deepcopy(repository.datasets)
    repository.fail_persist = True
    with pytest.raises(RuntimeError, match="transactional failure"):
        await OperationalPromotionService(repository).promote(2)
    assert repository.datasets == previous
    assert 2 not in repository.promotions


def test_sqlalchemy_repository_uses_one_transaction_for_the_whole_promotion() -> None:
    source = inspect.getsource(SqlAlchemyOperationalPromotionRepository.persist)
    assert "session.begin()" in source
    assert source.count("session.begin()") == 1


def test_normalized_money_columns_are_numeric_and_movement_relation_is_one_to_many() -> None:
    for attribute in (
        OperationalContract.principal,
        OperationalContract.iof,
        OperationalInstallment.expected_amount,
        OperationalInstallment.paid_amount,
        OperationalPaymentMovement.paid_amount,
    ):
        column_type = attribute.property.columns[0].type
        assert isinstance(column_type, Numeric)
        assert (column_type.precision, column_type.scale) == (14, 2)

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in OperationalPaymentMovement.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("installment_id",) not in unique_columns
