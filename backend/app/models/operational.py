from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MONEY = Numeric(14, 2)
RATE = Numeric(18, 10)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    forced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_size: Mapped[int | None] = mapped_column(BigInteger)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    counters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    error_type: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalImportBatch(Base):
    __tablename__ = "operational_import_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    counters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataInconsistency(Base):
    __tablename__ = "data_inconsistencies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_import_batches.id", ondelete="CASCADE"), index=True
    )
    source_sheet: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    inconsistency_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    field_name: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    masked_value: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(24), index=True)
    review_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class MirrorRowMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_sheet: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_key: Mapped[str | None] = mapped_column(String(255), index=True)
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    last_seen_batch_id: Mapped[int] = mapped_column(
        ForeignKey("operational_import_batches.id"), nullable=False, index=True
    )
    source_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )


class ExcelBcliCadastroRow(MirrorRowMixin, Base):
    __tablename__ = "excel_bcli_cadastro_rows"

    cod_cliente_original: Mapped[str | None] = mapped_column(Text)
    cod_cliente: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_original: Mapped[str | None] = mapped_column(Text)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    nome_cliente_original: Mapped[str | None] = mapped_column(Text)
    nome_cliente: Mapped[str | None] = mapped_column(Text)
    dt_nasc_original: Mapped[str | None] = mapped_column(Text)
    dt_nasc: Mapped[date | None] = mapped_column(Date)


class ExcelDfenContratoRow(MirrorRowMixin, Base):
    __tablename__ = "excel_dfen_contrato_rows"

    cod_cliente: Mapped[str | None] = mapped_column(String(100), index=True)
    cod_contrato: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_original: Mapped[str | None] = mapped_column(Text)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    dt_operacao: Mapped[date | None] = mapped_column(Date)
    vcto_prim_parc: Mapped[date | None] = mapped_column(Date)
    prazo: Mapped[int | None] = mapped_column(Integer)
    principal: Mapped[Decimal | None] = mapped_column(MONEY)
    iof: Mapped[Decimal | None] = mapped_column(MONEY)
    vl_financiado: Mapped[Decimal | None] = mapped_column(MONEY)
    pmt: Mapped[Decimal | None] = mapped_column(MONEY)
    vl_liberado: Mapped[Decimal | None] = mapped_column(MONEY)
    data_liberacao: Mapped[date | None] = mapped_column(Date)


class ExcelEconEmprestimosRow(MirrorRowMixin, Base):
    __tablename__ = "excel_econ_emprestimos_rows"

    cod_contrato: Mapped[str | None] = mapped_column(String(100), index=True)
    cod_cliente: Mapped[str | None] = mapped_column(String(100), index=True)
    nome_cliente_original: Mapped[str | None] = mapped_column(Text)
    nome_cliente: Mapped[str | None] = mapped_column(Text)
    cpf_original: Mapped[str | None] = mapped_column(Text)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    dt_operacao: Mapped[date | None] = mapped_column(Date)
    vencimento1: Mapped[date | None] = mapped_column(Date)
    vl_principal: Mapped[Decimal | None] = mapped_column(MONEY)
    prazo_pgto: Mapped[int | None] = mapped_column(Integer)
    iof: Mapped[Decimal | None] = mapped_column(MONEY)
    vl_finaciado: Mapped[Decimal | None] = mapped_column(MONEY)
    pmt: Mapped[Decimal | None] = mapped_column(MONEY)
    vl_liberado: Mapped[Decimal | None] = mapped_column(MONEY)
    taxa_juros: Mapped[Decimal | None] = mapped_column(RATE)
    taxa_tir: Mapped[Decimal | None] = mapped_column(RATE)
    taxa_cet_am: Mapped[Decimal | None] = mapped_column(RATE)
    status: Mapped[str | None] = mapped_column(Text)


class ExcelEconAmortizacoesRow(MirrorRowMixin, Base):
    __tablename__ = "excel_econ_amortizacoes_rows"

    cod_cliente: Mapped[str | None] = mapped_column(String(100), index=True)
    cpf_original: Mapped[str | None] = mapped_column(Text)
    cpf_normalized: Mapped[str | None] = mapped_column(String(11), index=True)
    cod_contrato: Mapped[str | None] = mapped_column(String(100), index=True)
    cod_parcela: Mapped[str | None] = mapped_column(String(100))
    vencimento: Mapped[date | None] = mapped_column(Date)
    val_amtz_jur: Mapped[Decimal | None] = mapped_column(MONEY)
    val_amtz_princ: Mapped[Decimal | None] = mapped_column(MONEY)
    val_parcela: Mapped[Decimal | None] = mapped_column(MONEY)
    baixa_total_original: Mapped[str | None] = mapped_column(Text)
    # Legacy numeric interpretation retained only to avoid mutating batch 1.
    baixa_total: Mapped[Decimal | None] = mapped_column(MONEY)
    dt_baixatotal: Mapped[date | None] = mapped_column(Date)
    val_pgto: Mapped[Decimal | None] = mapped_column(MONEY)
    desconto_conc: Mapped[Decimal | None] = mapped_column(MONEY)
    status_parc: Mapped[str | None] = mapped_column(Text)
    situacao: Mapped[str | None] = mapped_column(Text)
    chave_referencia: Mapped[str | None] = mapped_column(Text)
    bol_antecip: Mapped[str | None] = mapped_column(Text)
    produto_financeiro: Mapped[str | None] = mapped_column(Text)


Index(
    "ix_excel_econ_amortizacoes_contract_installment",
    ExcelEconAmortizacoesRow.cod_contrato,
    ExcelEconAmortizacoesRow.cod_parcela,
)
