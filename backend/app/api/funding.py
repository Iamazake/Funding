from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.core.database import get_session
from app.schemas.contribution_analysis import ContributionAnalysisResponse
from app.schemas.funding import (
    ContributionCreate,
    ContributionResponse,
    ContributionUpdate,
    InvestorCreate,
    InvestorResponse,
    InvestorUpdate,
)
from app.schemas.funding_ledger import (
    AllocationCreate,
    AllocationReverse,
    FundingSourceResponse,
    LedgerEntryResponse,
    RemoCapitalEntryCreate,
    SaleCompositionResponse,
    SourceBalanceResponse,
)
from app.schemas.revenue_distribution import (
    RevenueDistributionProcess,
    RevenueDistributionResponse,
    RevenueDistributionReverse,
)
from app.services.funding.analysis import ContributionAnalysisRepository
from app.services.funding.ledger import FundingLedgerRepository
from app.services.funding.repository import (
    FundingConflictError,
    FundingNotFoundError,
    FundingRepository,
)
from app.services.funding.revenue import RevenueDistributionRepository

router = APIRouter(prefix="/api/funding", tags=["funding"])


def _revenue_reference(value: str) -> str | int:
    """Keep numeric snapshot routes working while canonical UUID routes take over."""

    try:
        return int(value)
    except ValueError:
        return value


def get_funding_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> FundingRepository:
    return FundingRepository(
        session,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )


Repository = Annotated[FundingRepository, Depends(get_funding_repository)]


def get_funding_ledger_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> FundingLedgerRepository:
    return FundingLedgerRepository(
        session,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )


LedgerRepository = Annotated[FundingLedgerRepository, Depends(get_funding_ledger_repository)]


def get_revenue_distribution_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> RevenueDistributionRepository:
    return RevenueDistributionRepository(
        session,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )


RevenueRepository = Annotated[
    RevenueDistributionRepository,
    Depends(get_revenue_distribution_repository),
]


def get_contribution_analysis_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContributionAnalysisRepository:
    return ContributionAnalysisRepository(session)


AnalysisRepository = Annotated[
    ContributionAnalysisRepository,
    Depends(get_contribution_analysis_repository),
]


def _not_found(error: FundingNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


@router.get("/investors", response_model=list[InvestorResponse])
async def list_investors(repository: Repository) -> list[InvestorResponse]:
    return await repository.list_investors()


@router.get("/investors/{investor_id}", response_model=InvestorResponse)
async def get_investor(investor_id: UUID, repository: Repository) -> InvestorResponse:
    try:
        return await repository.get_investor(investor_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.post("/investors", response_model=InvestorResponse, status_code=status.HTTP_201_CREATED)
async def create_investor(data: InvestorCreate, repository: Repository) -> InvestorResponse:
    return await repository.create_investor(data)


@router.patch("/investors/{investor_id}", response_model=InvestorResponse)
async def update_investor(
    investor_id: UUID, data: InvestorUpdate, repository: Repository
) -> InvestorResponse:
    try:
        return await repository.update_investor(investor_id, data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get("/contributions", response_model=list[ContributionResponse])
async def list_contributions(
    repository: Repository,
    investor_id: Annotated[UUID | None, Query()] = None,
) -> list[ContributionResponse]:
    try:
        return await repository.list_contributions(investor_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get("/investors/{investor_id}/contributions", response_model=list[ContributionResponse])
async def list_investor_contributions(
    investor_id: UUID, repository: Repository
) -> list[ContributionResponse]:
    try:
        return await repository.list_contributions(investor_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get("/contributions/{contribution_id}", response_model=ContributionResponse)
async def get_contribution(contribution_id: UUID, repository: Repository) -> ContributionResponse:
    try:
        return await repository.get_contribution(contribution_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/contributions/{contribution_id}/analysis",
    response_model=ContributionAnalysisResponse,
)
async def get_contribution_analysis(
    contribution_id: UUID,
    repository: AnalysisRepository,
) -> ContributionAnalysisResponse:
    try:
        return await repository.get_analysis(contribution_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/contributions",
    response_model=ContributionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contribution(
    data: ContributionCreate, repository: Repository
) -> ContributionResponse:
    try:
        return await repository.create_contribution(data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.patch("/contributions/{contribution_id}", response_model=ContributionResponse)
async def update_contribution(
    contribution_id: UUID, data: ContributionUpdate, repository: Repository
) -> ContributionResponse:
    try:
        return await repository.update_contribution(contribution_id, data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/sources", response_model=list[FundingSourceResponse])
async def list_sources(repository: LedgerRepository) -> list[FundingSourceResponse]:
    return await repository.list_sources()


@router.get("/sources/{source_id}", response_model=FundingSourceResponse)
async def get_source(source_id: UUID, repository: LedgerRepository) -> FundingSourceResponse:
    try:
        return await repository.get_source(source_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get("/sources/{source_id}/ledger", response_model=list[LedgerEntryResponse])
async def list_source_ledger(
    source_id: UUID, repository: LedgerRepository
) -> list[LedgerEntryResponse]:
    try:
        return await repository.list_ledger(source_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.get("/sources/{source_id}/balance", response_model=SourceBalanceResponse)
async def get_source_balance(
    source_id: UUID,
    repository: LedgerRepository,
    as_of: Annotated[date | None, Query()] = None,
) -> SourceBalanceResponse:
    try:
        return await repository.get_balance(source_id, as_of)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/sources/remo-capital/entries",
    response_model=LedgerEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_remo_capital(
    data: RemoCapitalEntryCreate, repository: LedgerRepository
) -> LedgerEntryResponse:
    try:
        return await repository.register_remo_capital(data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/sales/{sale_id}/composition", response_model=SaleCompositionResponse)
async def get_sale_composition(
    sale_id: str, repository: LedgerRepository
) -> SaleCompositionResponse:
    try:
        return await repository.get_composition(sale_id)
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/sales/{sale_id}/allocations",
    response_model=SaleCompositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sale_allocation(
    sale_id: str, data: AllocationCreate, repository: LedgerRepository
) -> SaleCompositionResponse:
    try:
        return await repository.create_allocation(sale_id, data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/allocations/{allocation_id}/reversal",
    response_model=SaleCompositionResponse,
)
async def reverse_sale_allocation(
    allocation_id: UUID,
    data: AllocationReverse,
    repository: LedgerRepository,
) -> SaleCompositionResponse:
    try:
        return await repository.reverse_allocation(allocation_id, data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get(
    "/revenue/{revenue_id}/distribution",
    response_model=RevenueDistributionResponse,
)
async def get_revenue_distribution(
    revenue_id: str,
    repository: RevenueRepository,
) -> RevenueDistributionResponse:
    try:
        return await repository.get_distribution(_revenue_reference(revenue_id))
    except FundingNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/revenue/{revenue_id}/distribute",
    response_model=RevenueDistributionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def distribute_revenue(
    revenue_id: str,
    data: RevenueDistributionProcess,
    repository: RevenueRepository,
) -> RevenueDistributionResponse:
    try:
        return await repository.distribute(_revenue_reference(revenue_id), data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/revenue/distributions/{distribution_id}/reversal",
    response_model=RevenueDistributionResponse,
)
async def reverse_revenue_distribution(
    distribution_id: UUID,
    data: RevenueDistributionReverse,
    repository: RevenueRepository,
) -> RevenueDistributionResponse:
    try:
        return await repository.reverse(distribution_id, data)
    except FundingNotFoundError as error:
        raise _not_found(error) from error
    except FundingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
