from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    new_session_token,
    session_token_hash,
    verify_password,
)
from app.models.auth import AppAuthSession, AppUser, AppUserAuditEvent
from app.models.operational import utc_now
from app.schemas.auth import PasswordReset, UserCreate, UserResponse, UserUpdate, normalize_email


class AuthenticationError(RuntimeError):
    pass


class AuthorizationError(RuntimeError):
    pass


class UserConflictError(RuntimeError):
    pass


class UserNotFoundError(LookupError):
    pass


class BootstrapConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthenticatedSession:
    user: AppUser
    session: AppAuthSession


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authenticate(self, email: str, password: str) -> AppUser:
        normalized = normalize_email(email)
        user = await self._session.scalar(select(AppUser).where(AppUser.email == normalized))
        if user is None:
            verify_password(DUMMY_PASSWORD_HASH, password)
            raise AuthenticationError("E-mail ou senha inválidos.")
        if not verify_password(user.password_hash, password):
            raise AuthenticationError("E-mail ou senha inválidos.")
        if user.status != "ACTIVE":
            raise AuthenticationError("E-mail ou senha inválidos.")
        user.last_login_at = utc_now()
        user.updated_at = utc_now()
        self.audit("LOGIN_SUCCEEDED", actor_user_id=user.id, target_user_id=user.id)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_session(
        self, user: AppUser, lifetime: timedelta
    ) -> tuple[str, AppAuthSession]:
        token, token_hash = new_session_token()
        entity = AppAuthSession(
            id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + lifetime,
        )
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return token, entity

    async def resolve_session(self, token: str) -> AuthenticatedSession:
        now = datetime.now(UTC)
        row = (
            await self._session.execute(
                select(AppAuthSession, AppUser)
                .join(AppUser, AppUser.id == AppAuthSession.user_id)
                .where(AppAuthSession.token_hash == session_token_hash(token))
            )
        ).one_or_none()
        if row is None:
            raise AuthenticationError("Sessão inválida ou expirada.")
        auth_session, user = row
        if (
            auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or user.status != "ACTIVE"
        ):
            raise AuthenticationError("Sessão inválida ou expirada.")
        auth_session.last_seen_at = now
        return AuthenticatedSession(user=user, session=auth_session)

    async def logout(self, auth_session: AppAuthSession) -> None:
        auth_session.revoked_at = utc_now()
        await self._session.commit()

    async def change_password(
        self, user: AppUser, current_password: str, new_password: str
    ) -> None:
        if not verify_password(user.password_hash, current_password):
            raise AuthenticationError("Senha atual inválida.")
        user.password_hash = hash_password(new_password)
        user.updated_at = utc_now()
        await self._revoke_sessions(user.id)
        self.audit("PASSWORD_CHANGED", actor_user_id=user.id, target_user_id=user.id)
        await self._session.commit()

    async def list_users(self) -> list[UserResponse]:
        rows = await self._session.scalars(select(AppUser).order_by(AppUser.name, AppUser.id))
        return [UserResponse.model_validate(row) for row in rows]

    async def get_user(self, user_id: UUID) -> AppUser:
        user = await self._session.get(AppUser, user_id)
        if user is None:
            raise UserNotFoundError("Usuário não encontrado.")
        return user

    async def create_user(self, data: UserCreate, actor: AppUser) -> UserResponse:
        user = AppUser(
            id=uuid4(),
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            status="ACTIVE",
        )
        self._session.add(user)
        self.audit(
            "USER_CREATED",
            actor_user_id=actor.id,
            target_user_id=user.id,
            details={"role": user.role, "status": user.status},
        )
        try:
            await self._session.commit()
            await self._session.refresh(user)
        except IntegrityError as error:
            await self._session.rollback()
            raise UserConflictError("Já existe um usuário com este e-mail.") from error
        return UserResponse.model_validate(user)

    async def update_user(
        self, user_id: UUID, data: UserUpdate, actor: AppUser
    ) -> UserResponse:
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext("app-users-active-admin")))
        )
        user = await self._locked_user(user_id)
        values = data.model_dump(exclude_unset=True, exclude_none=True)
        next_role = values.get("role", user.role)
        next_status = values.get("status", user.status)
        if user.role == "ADMIN" and user.status == "ACTIVE" and (
            next_role != "ADMIN" or next_status != "ACTIVE"
        ):
            await self._require_another_active_admin(user.id)
        changes: dict[str, object] = {}
        for field, value in values.items():
            previous = getattr(user, field)
            if value != previous:
                changes[field] = {"from": previous, "to": value}
                setattr(user, field, value)
        if changes:
            user.updated_at = utc_now()
            action = "USER_STATUS_CHANGED" if set(changes) == {"status"} else "USER_UPDATED"
            self.audit(action, actor_user_id=actor.id, target_user_id=user.id, details=changes)
            if user.status == "INACTIVE":
                await self._revoke_sessions(user.id)
        await self._session.commit()
        await self._session.refresh(user)
        return UserResponse.model_validate(user)

    async def reset_password(
        self, user_id: UUID, data: PasswordReset, actor: AppUser
    ) -> None:
        user = await self._locked_user(user_id)
        user.password_hash = hash_password(data.new_password)
        user.updated_at = utc_now()
        await self._revoke_sessions(user.id)
        self.audit("PASSWORD_RESET", actor_user_id=actor.id, target_user_id=user.id)
        await self._session.commit()

    async def bootstrap_admin(self, name: str, email: str, password: str) -> tuple[AppUser, bool]:
        normalized = normalize_email(email)
        existing = await self._session.scalar(select(AppUser).where(AppUser.email == normalized))
        if existing is not None:
            return existing, False
        user = AppUser(
            id=uuid4(),
            name=name.strip(),
            email=normalized,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )
        self._session.add(user)
        self.audit("ADMIN_BOOTSTRAPPED", target_user_id=user.id)
        try:
            await self._session.commit()
            await self._session.refresh(user)
        except IntegrityError:
            await self._session.rollback()
            existing = await self._session.scalar(
                select(AppUser).where(AppUser.email == normalized)
            )
            if existing is None:
                raise
            return existing, False
        return user, True

    async def _locked_user(self, user_id: UUID) -> AppUser:
        user = await self._session.scalar(
            select(AppUser).where(AppUser.id == user_id).with_for_update()
        )
        if user is None:
            raise UserNotFoundError("Usuário não encontrado.")
        return user

    async def _require_another_active_admin(self, excluded_user_id: UUID) -> None:
        count = await self._session.scalar(
            select(func.count())
            .select_from(AppUser)
            .where(
                AppUser.role == "ADMIN",
                AppUser.status == "ACTIVE",
                AppUser.id != excluded_user_id,
            )
        )
        if not count:
            raise UserConflictError("O sistema deve manter pelo menos um ADMIN ativo.")

    async def _revoke_sessions(self, user_id: UUID) -> None:
        await self._session.execute(
            update(AppAuthSession)
            .where(AppAuthSession.user_id == user_id, AppAuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )

    def audit(
        self,
        action: str,
        *,
        actor_user_id: UUID | None = None,
        target_user_id: UUID | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            AppUserAuditEvent(
                actor_user_id=actor_user_id,
                target_user_id=target_user_id,
                action=action,
                details=details or {},
            )
        )
