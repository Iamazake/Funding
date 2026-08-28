from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentAdmin
from app.core.database import get_session
from app.schemas.debt_continuity import (
    DebtContinuityConfirm,
    DebtContinuityReject,
    DebtContinuityResponse,
    DebtContinuityReviewCreate,
    RefinancingCorrection,
    RefinancingCreate,
)
from app.services.operational.debt_continuity import (
    DebtContinuityConflictError,
    DebtContinuityNotFoundError,
    DebtContinuityRepository,
)

router = APIRouter(
    prefix="/api/operational/debt-continuities",
    tags=["operational-debt-continuity"],
)


def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: CurrentAdmin,
) -> DebtContinuityRepository:
    return DebtContinuityRepository(session, admin.id)


Repository = Annotated[DebtContinuityRepository, Depends(get_repository)]


@router.get("", response_model=list[DebtContinuityResponse])
async def list_debt_continuities(repository: Repository) -> list[DebtContinuityResponse]:
    return await repository.list()


@router.post(
    "/reviews",
    response_model=DebtContinuityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_debt_continuity_review(
    data: DebtContinuityReviewCreate,
    repository: Repository,
) -> DebtContinuityResponse:
    try:
        return await repository.create_review(data)
    except DebtContinuityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DebtContinuityConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/refinancings",
    response_model=DebtContinuityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_refinancing(
    data: RefinancingCreate,
    repository: Repository,
) -> DebtContinuityResponse:
    try:
        return await repository.create_refinancing(data)
    except DebtContinuityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DebtContinuityConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.patch("/{continuity_id}/refinancing", response_model=DebtContinuityResponse)
async def correct_refinancing(
    continuity_id: UUID,
    data: RefinancingCorrection,
    repository: Repository,
) -> DebtContinuityResponse:
    try:
        return await repository.correct_refinancing(continuity_id, data)
    except DebtContinuityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DebtContinuityConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{continuity_id}/confirm", response_model=DebtContinuityResponse)
async def confirm_debt_continuity(
    continuity_id: UUID,
    data: DebtContinuityConfirm,
    repository: Repository,
) -> DebtContinuityResponse:
    try:
        return await repository.confirm(continuity_id, data)
    except DebtContinuityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DebtContinuityConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{continuity_id}/reject", response_model=DebtContinuityResponse)
async def reject_debt_continuity(
    continuity_id: UUID,
    data: DebtContinuityReject,
    repository: Repository,
) -> DebtContinuityResponse:
    try:
        return await repository.reject(continuity_id, data)
    except DebtContinuityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DebtContinuityConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
