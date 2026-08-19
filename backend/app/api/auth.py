from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import SESSION_COOKIE_NAME, login_rate_limiter
from app.models.auth import AppUser
from app.schemas.auth import LoginRequest, LoginResponse, PasswordChange, UserResponse
from app.services.auth import AuthenticatedSession, AuthenticationError, AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthService:
    return AuthService(session)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_authenticated_session(
    service: AuthServiceDependency,
    funding_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> AuthenticatedSession:
    if not funding_session:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    try:
        return await service.resolve_session(funding_session)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.") from error


Authenticated = Annotated[AuthenticatedSession, Depends(get_authenticated_session)]


async def get_current_user(authenticated: Authenticated) -> AppUser:
    return authenticated.user


CurrentUser = Annotated[AppUser, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> AppUser:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para ADMIN.")
    return user


CurrentAdmin = Annotated[AppUser, Depends(require_admin)]


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.resolved_auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=settings.resolved_auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    key = login_rate_limiter.key(client_ip, data.email)
    retry_after = login_rate_limiter.retry_after(key)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde antes de tentar novamente.",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        user = await service.authenticate(data.email, data.password)
    except AuthenticationError as error:
        login_rate_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.") from error
    login_rate_limiter.clear(key)
    settings = get_settings()
    lifetime = timedelta(hours=settings.auth_session_hours)
    token, auth_session = await service.create_session(user, lifetime)
    _set_session_cookie(response, token, int(lifetime.total_seconds()))
    return LoginResponse(user=UserResponse.model_validate(user), expires_at=auth_session.expires_at)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    authenticated: Authenticated,
    service: AuthServiceDependency,
) -> None:
    await service.logout(authenticated.session)
    _clear_session_cookie(response)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChange,
    response: Response,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> None:
    try:
        await service.change_password(user, data.current_password, data.new_password)
    except AuthenticationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    _clear_session_cookie(response)
