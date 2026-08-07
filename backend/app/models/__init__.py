"""SQLAlchemy models for the API, mirror, and normalized operational layer."""

from app.models.base import Base
from app.models.normalized import (
    OperationalClient,
    OperationalContract,
    OperationalInstallment,
    OperationalLoan,
    OperationalPaymentMovement,
    OperationalPromotion,
    OperationalQualityLink,
)
from app.models.operational import (
    DataInconsistency,
    ExcelBcliCadastroRow,
    ExcelDfenContratoRow,
    ExcelEconAmortizacoesRow,
    ExcelEconEmprestimosRow,
    OperationalImportBatch,
    SyncRun,
)

__all__ = [
    "Base",
    "DataInconsistency",
    "ExcelBcliCadastroRow",
    "ExcelDfenContratoRow",
    "ExcelEconAmortizacoesRow",
    "ExcelEconEmprestimosRow",
    "OperationalImportBatch",
    "OperationalClient",
    "OperationalContract",
    "OperationalInstallment",
    "OperationalLoan",
    "OperationalPaymentMovement",
    "OperationalPromotion",
    "OperationalQualityLink",
    "SyncRun",
]
