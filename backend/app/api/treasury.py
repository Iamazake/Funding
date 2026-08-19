from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.core.database import get_session
from app.schemas.treasury import (
    TreasuryMovementResponse,
    TreasuryMovementsResponse,
    TreasurySummaryResponse,
    TreasuryValidationCreate,
    TreasuryValidationHistory,
    TreasuryValidationResponse,
    TreasuryValidationState,
)
from app.services.treasury import (
    TreasuryConflictError,
    TreasuryNotFoundError,
    TreasuryQuery,
    TreasuryRepository,
)

router = APIRouter(prefix="/api/treasury", tags=["treasury"])
MovementTypeFilter = Literal["CONTRIBUTION", "SALE", "REVENUE"]
ValidationStatusFilter = Literal["PENDING", "VALIDATED", "DIVERGENT"]


def get_treasury_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> TreasuryRepository:
    return TreasuryRepository(session, actor_user_id=current_user.id)


Repository = Annotated[TreasuryRepository, Depends(get_treasury_repository)]


def _query(
    *,
    page: int = 1,
    page_size: int = 50,
    period_from: date | None = None,
    period_to: date | None = None,
    movement_type: MovementTypeFilter | None = None,
    search: str | None = None,
    installment: str | None = None,
    investor_id: UUID | None = None,
    validation_status: ValidationStatusFilter | None = None,
    eligible_for_validation: bool = False,
) -> TreasuryQuery:
    if period_from is not None and period_to is not None and period_from > period_to:
        raise HTTPException(status_code=422, detail="A data inicial deve ser anterior à final.")
    return TreasuryQuery(
        page=page,
        page_size=page_size,
        period_from=period_from,
        period_to=period_to,
        movement_type=movement_type,
        search=search,
        installment=installment,
        investor_id=investor_id,
        validation_status=validation_status,
        eligible_for_validation=eligible_for_validation,
    )


@router.get("/summary", response_model=TreasurySummaryResponse)
async def get_treasury_summary(
    repository: Repository,
    period_from: date | None = None,
    period_to: date | None = None,
    movement_type: MovementTypeFilter | None = None,
    search: str | None = None,
    installment: str | None = None,
    investor_id: UUID | None = None,
    validation_status: ValidationStatusFilter | None = None,
    eligible_for_validation: bool = False,
) -> TreasurySummaryResponse:
    return await repository.summary(
        _query(
            period_from=period_from,
            period_to=period_to,
            movement_type=movement_type,
            search=search,
            installment=installment,
            investor_id=investor_id,
            validation_status=validation_status,
            eligible_for_validation=eligible_for_validation,
        )
    )


@router.get("/movements", response_model=TreasuryMovementsResponse)
async def list_treasury_movements(
    repository: Repository,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    period_from: date | None = None,
    period_to: date | None = None,
    movement_type: MovementTypeFilter | None = None,
    search: str | None = None,
    installment: str | None = None,
    investor_id: UUID | None = None,
    validation_status: ValidationStatusFilter | None = None,
    eligible_for_validation: bool = False,
) -> TreasuryMovementsResponse:
    return await repository.movements(
        _query(
            page=page,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
            movement_type=movement_type,
            search=search,
            installment=installment,
            investor_id=investor_id,
            validation_status=validation_status,
            eligible_for_validation=eligible_for_validation,
        )
    )


@router.get("/movements/{movement_id}", response_model=TreasuryMovementResponse)
async def get_treasury_movement(
    movement_id: str,
    repository: Repository,
) -> TreasuryMovementResponse:
    try:
        return await repository.get_movement(movement_id)
    except TreasuryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/movements/{movement_id}/validation",
    response_model=TreasuryValidationState,
)
async def get_movement_validation(
    movement_id: str,
    repository: Repository,
) -> TreasuryValidationState:
    try:
        return await repository.get_validation(movement_id)
    except TreasuryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/movements/{movement_id}/validation",
    response_model=TreasuryValidationResponse,
    status_code=201,
)
async def validate_movement(
    movement_id: str,
    data: TreasuryValidationCreate,
    repository: Repository,
) -> TreasuryValidationResponse:
    try:
        return await repository.validate_movement(movement_id, data)
    except TreasuryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TreasuryConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get(
    "/movements/{movement_id}/validation-history",
    response_model=TreasuryValidationHistory,
)
async def get_movement_validation_history(
    movement_id: str,
    repository: Repository,
) -> TreasuryValidationHistory:
    try:
        return await repository.validation_history(movement_id)
    except TreasuryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
