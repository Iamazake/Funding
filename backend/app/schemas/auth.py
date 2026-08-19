from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["ADMIN", "ANALYST"]
UserStatus = Literal["ACTIVE", "INACTIVE"]


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("E-mail inválido.")
    return normalized


class AuthSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(AuthSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        return normalize_email(value)


class UserResponse(AuthSchema):
    id: UUID
    name: str
    email: str
    role: UserRole
    status: UserStatus
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(AuthSchema):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=1024)
    role: UserRole = "ANALYST"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        return normalize_email(value)


class UserUpdate(AuthSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    role: UserRole | None = None
    status: UserStatus | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PasswordReset(AuthSchema):
    new_password: str = Field(min_length=10, max_length=1024)


class PasswordChange(AuthSchema):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=10, max_length=1024)


class LoginResponse(AuthSchema):
    user: UserResponse
    expires_at: datetime
