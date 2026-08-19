from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import CurrentAdmin, get_auth_service
from app.schemas.auth import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.services.auth import AuthService, UserConflictError, UserNotFoundError

router = APIRouter(prefix="/api/admin", tags=["admin"])
Service = Annotated[AuthService, Depends(get_auth_service)]


def _not_found(error: UserNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


@router.get("/users", response_model=list[UserResponse])
async def list_users(_: CurrentAdmin, service: Service) -> list[UserResponse]:
    return await service.list_users()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate, admin: CurrentAdmin, service: Service
) -> UserResponse:
    try:
        return await service.create_user(data, admin)
    except UserConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _: CurrentAdmin, service: Service) -> UserResponse:
    try:
        return UserResponse.model_validate(await service.get_user(user_id))
    except UserNotFoundError as error:
        raise _not_found(error) from error


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID, data: UserUpdate, admin: CurrentAdmin, service: Service
) -> UserResponse:
    try:
        return await service.update_user(user_id, data, admin)
    except UserNotFoundError as error:
        raise _not_found(error) from error
    except UserConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: UUID, data: PasswordReset, admin: CurrentAdmin, service: Service
) -> None:
    try:
        await service.reset_password(user_id, data, admin)
    except UserNotFoundError as error:
        raise _not_found(error) from error
