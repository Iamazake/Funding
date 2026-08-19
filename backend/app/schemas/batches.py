from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BatchUser(BaseModel):
    id: UUID
    name: str


class BatchDataCounts(BaseModel):
    bcli_cadastro: int = 0
    dfen_contrato: int = 0
    econ_emprestimos: int = 0
    econ_amortizacoes: int = 0


class BatchQualityCounts(BaseModel):
    valid: int = 0
    warning: int = 0
    divergent: int = 0
    invalid: int = 0


class BatchPromotionInfo(BaseModel):
    id: int
    is_current: bool
    promoted_at: datetime
    promoted_by: BatchUser | None = None


class OperationalBatchSummary(BaseModel):
    id: int
    sync_run_id: int
    started_at: datetime
    completed_at: datetime | None
    source_type: Literal["LOCAL", "ONEDRIVE"]
    source_name: str | None
    source_size: int | None
    source_sha256: str
    status: str
    data_counts: BatchDataCounts
    quality_counts: BatchQualityCounts
    initiated_by: BatchUser | None = None
    promotion: BatchPromotionInfo | None = None


class BatchCountComparison(BaseModel):
    current: int
    candidate: int
    difference: int


class BatchComparison(BaseModel):
    current_promotion_id: int | None
    current_source_batch_id: int | None
    clients: BatchCountComparison
    contracts: BatchCountComparison
    loans: BatchCountComparison
    installments: BatchCountComparison
    sales: BatchCountComparison
    revenue: BatchCountComparison


class OperationalBatchDetail(OperationalBatchSummary):
    comparison: BatchComparison
    promotion_eligible: bool
    promotion_eligibility_reason: str


class OperationalBatchList(BaseModel):
    items: list[OperationalBatchSummary] = Field(default_factory=list)


class OperationalBatchPromotionResponse(BaseModel):
    promotion_id: int
    source_batch_id: int
    status: str
    idempotent: bool
    summary: dict[str, Any]
