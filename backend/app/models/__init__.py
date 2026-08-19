"""SQLAlchemy models for the API, mirror, and normalized operational layer."""

from app.models.auth import AppAuthSession, AppUser, AppUserAuditEvent
from app.models.base import Base
from app.models.debt import (
    OperationalDebtContinuity,
    OperationalDebtContinuityAuditEvent,
    OperationalDebtFundingContinuity,
)
from app.models.funding import (
    FundingAllocation,
    FundingAuditEvent,
    FundingContribution,
    FundingInvestor,
    FundingLedgerEntry,
    FundingRevenueDistribution,
    FundingRevenueDistributionItem,
    FundingSource,
)
from app.models.identity import (
    OperationalIdentityMatchReview,
    OperationalIdentityMigrationManifest,
    OperationalRevenueIdentity,
    OperationalRevenueSnapshot,
    OperationalSaleIdentity,
    OperationalSaleSnapshot,
)
from app.models.integrations import OneDriveOAuthState, OperationalSourceConnection
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
from app.models.treasury import TreasuryBankValidation

__all__ = [
    "AppAuthSession",
    "AppUser",
    "AppUserAuditEvent",
    "Base",
    "OperationalDebtContinuity",
    "OperationalDebtContinuityAuditEvent",
    "OperationalDebtFundingContinuity",
    "FundingAuditEvent",
    "FundingAllocation",
    "FundingContribution",
    "FundingInvestor",
    "FundingLedgerEntry",
    "FundingRevenueDistribution",
    "FundingRevenueDistributionItem",
    "FundingSource",
    "OneDriveOAuthState",
    "OperationalSourceConnection",
    "OperationalIdentityMatchReview",
    "OperationalIdentityMigrationManifest",
    "OperationalRevenueIdentity",
    "OperationalRevenueSnapshot",
    "OperationalSaleIdentity",
    "OperationalSaleSnapshot",
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
    "TreasuryBankValidation",
]
