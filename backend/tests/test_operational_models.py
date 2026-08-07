import inspect

from sqlalchemy import Numeric

from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
    OperationalImportBatch,
    SyncRun,
)
from app.services.excel.store import SqlAlchemyOperationalStore


def test_all_money_columns_use_numeric_14_2() -> None:
    columns = [
        ExcelDfenContratoRow.principal,
        ExcelDfenContratoRow.iof,
        ExcelDfenContratoRow.vl_financiado,
        ExcelDfenContratoRow.pmt,
        ExcelDfenContratoRow.vl_liberado,
        ExcelEconEmprestimosRow.vl_principal,
        ExcelEconEmprestimosRow.iof,
        ExcelEconEmprestimosRow.vl_finaciado,
        ExcelEconEmprestimosRow.pmt,
        ExcelEconEmprestimosRow.vl_liberado,
        ExcelEconAmortizacoesRow.val_amtz_jur,
        ExcelEconAmortizacoesRow.val_amtz_princ,
        ExcelEconAmortizacoesRow.val_parcela,
        ExcelEconAmortizacoesRow.baixa_total,
        ExcelEconAmortizacoesRow.val_pgto,
        ExcelEconAmortizacoesRow.desconto_conc,
    ]
    for attribute in columns:
        column_type = attribute.property.columns[0].type
        assert isinstance(column_type, Numeric)
        assert (column_type.precision, column_type.scale) == (14, 2)


def test_operational_event_timestamps_have_timezone() -> None:
    timestamp_attributes = [
        SyncRun.started_at,
        SyncRun.finished_at,
        OperationalImportBatch.started_at,
        OperationalImportBatch.completed_at,
        DataInconsistency.created_at,
        ExcelBcliCadastroRow.imported_at,
    ]
    for attribute in timestamp_attributes:
        assert attribute.property.columns[0].type.timezone is True


def test_promote_never_mutates_historical_mirror_rows() -> None:
    source = inspect.getsource(SqlAlchemyOperationalStore.promote)

    assert "source_active=False" not in source
    assert "update(model)" not in source
