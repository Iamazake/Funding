from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

DEVELOPMENT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class Settings(BaseSettings):
    database_url: SecretStr = Field(alias="DATABASE_URL")
    app_environment: str = Field(default="development", alias="APP_ENV")
    cors_allowed_origins: str | None = Field(default=None, alias="CORS_ALLOWED_ORIGINS")
    trusted_hosts: str | None = Field(default=None, alias="TRUSTED_HOSTS")
    enable_api_docs: bool | None = Field(default=None, alias="ENABLE_API_DOCS")
    db_pool_size: int = Field(default=5, ge=1, le=50, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=5, ge=0, le=50, alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(
        default=30, ge=1, le=120, alias="DB_POOL_TIMEOUT_SECONDS"
    )
    db_pool_recycle_seconds: int = Field(
        default=900, ge=60, le=3600, alias="DB_POOL_RECYCLE_SECONDS"
    )
    funding_allow_historical_allocation_for_tests: bool = Field(
        default=False,
        alias="FUNDING_ALLOW_HISTORICAL_ALLOCATION_FOR_TESTS",
    )
    operational_excel_path: Path | None = Field(
        default=None,
        alias="OPERATIONAL_EXCEL_PATH",
    )
    operational_source: str = Field(default="local", alias="OPERATIONAL_SOURCE")
    onedrive_client_id: str | None = Field(default=None, alias="ONEDRIVE_CLIENT_ID")
    onedrive_client_secret: SecretStr | None = Field(default=None, alias="ONEDRIVE_CLIENT_SECRET")
    onedrive_redirect_uri: str | None = Field(default=None, alias="ONEDRIVE_REDIRECT_URI")
    frontend_base_url: str | None = Field(default=None, alias="FRONTEND_BASE_URL")
    onedrive_authority: str = Field(
        default="https://login.microsoftonline.com/consumers",
        alias="ONEDRIVE_AUTHORITY",
    )
    onedrive_file_path: str | None = Field(default=None, alias="ONEDRIVE_FILE_PATH")
    onedrive_token_encryption_key: SecretStr | None = Field(
        default=None, alias="ONEDRIVE_TOKEN_ENCRYPTION_KEY"
    )
    onedrive_oauth_state_minutes: int = Field(
        default=10, ge=2, le=30, alias="ONEDRIVE_OAUTH_STATE_MINUTES"
    )
    auth_session_hours: int = Field(default=8, ge=1, le=168, alias="AUTH_SESSION_HOURS")
    auth_cookie_secure: bool | None = Field(default=None, alias="AUTH_COOKIE_SECURE")
    funding_bootstrap_admin_email: str | None = Field(
        default=None, alias="FUNDING_BOOTSTRAP_ADMIN_EMAIL"
    )
    funding_bootstrap_admin_password: SecretStr | None = Field(
        default=None, alias="FUNDING_BOOTSTRAP_ADMIN_PASSWORD"
    )
    funding_bootstrap_admin_name: str | None = Field(
        default=None, alias="FUNDING_BOOTSTRAP_ADMIN_NAME"
    )

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_async_postgresql_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg:// scheme")
        return value

    @field_validator("app_environment")
    @classmethod
    def validate_app_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        return normalized

    @field_validator("operational_excel_path", mode="before")
    @classmethod
    def empty_operational_path_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("operational_source")
    @classmethod
    def validate_operational_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "onedrive"}:
            raise ValueError("OPERATIONAL_SOURCE must be local or onedrive")
        return normalized

    @field_validator("onedrive_authority")
    @classmethod
    def validate_onedrive_authority(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if normalized != "https://login.microsoftonline.com/consumers":
            raise ValueError("ONEDRIVE_AUTHORITY must use the consumers authority")
        return normalized

    @field_validator("onedrive_file_path")
    @classmethod
    def validate_onedrive_file_path(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = "/" + value.strip().strip("/")
        if not normalized.endswith("/Cadastro de Clientes.xlsm"):
            raise ValueError("ONEDRIVE_FILE_PATH must target Cadastro de Clientes.xlsm exactly")
        return normalized

    @field_validator("frontend_base_url")
    @classmethod
    def validate_frontend_base_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("FRONTEND_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("FRONTEND_BASE_URL must not contain query or fragment")
        return normalized

    @field_validator("onedrive_redirect_uri")
    @classmethod
    def validate_onedrive_redirect_uri(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ONEDRIVE_REDIRECT_URI must be an absolute HTTP(S) URL")
        if parsed.path != "/api/integrations/onedrive/callback":
            raise ValueError(
                "ONEDRIVE_REDIRECT_URI must end at /api/integrations/onedrive/callback"
            )
        if parsed.query or parsed.fragment:
            raise ValueError("ONEDRIVE_REDIRECT_URI must not contain query or fragment")
        return normalized

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        for origin in value.split(","):
            normalized = origin.strip().rstrip("/")
            if "*" in normalized:
                raise ValueError("CORS_ALLOWED_ORIGINS must not contain wildcard origins")
            parsed = urlsplit(normalized)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ALLOWED_ORIGINS must contain only HTTP(S) origins")
        return value

    @field_validator("trusted_hosts")
    @classmethod
    def validate_trusted_hosts(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        for host in value.split(","):
            normalized = host.strip()
            if not normalized or "*" in normalized or "://" in normalized or "/" in normalized:
                raise ValueError("TRUSTED_HOSTS must contain explicit host names only")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if not self.is_production:
            return self
        database = urlsplit(self.database_url.get_secret_value())
        query = parse_qs(database.query)
        ssl_values = [
            item.casefold()
            for key in ("ssl", "sslmode")
            for item in query.get(key, [])
        ]
        allowed_ssl_modes = {"require", "verify-ca", "verify-full", "true", "1"}
        if not ssl_values or any(item not in allowed_ssl_modes for item in ssl_values):
            raise ValueError("DATABASE_URL must explicitly require SSL in production")
        if self.auth_cookie_secure is False:
            raise ValueError("AUTH_COOKIE_SECURE cannot be false in production")
        if self.funding_allow_historical_allocation_for_tests:
            raise ValueError(
                "FUNDING_ALLOW_HISTORICAL_ALLOCATION_FOR_TESTS must be false in production"
            )
        if self.frontend_base_url is None:
            raise ValueError("FRONTEND_BASE_URL must be configured in production")
        if urlsplit(self.frontend_base_url).scheme != "https":
            raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
        if not self.trusted_hosts:
            raise ValueError("TRUSTED_HOSTS must be configured in production")
        if any(
            urlsplit(origin).scheme != "https" for origin in self.resolved_cors_origins
        ):
            raise ValueError("CORS_ALLOWED_ORIGINS must use HTTPS in production")
        if self.onedrive_redirect_uri and urlsplit(self.onedrive_redirect_uri).scheme != "https":
            raise ValueError("ONEDRIVE_REDIRECT_URI must use HTTPS in production")
        if self.operational_source == "onedrive":
            required = {
                "ONEDRIVE_CLIENT_ID": self.onedrive_client_id,
                "ONEDRIVE_CLIENT_SECRET": self.onedrive_client_secret,
                "ONEDRIVE_REDIRECT_URI": self.onedrive_redirect_uri,
                "ONEDRIVE_FILE_PATH": self.onedrive_file_path,
                "ONEDRIVE_TOKEN_ENCRYPTION_KEY": self.onedrive_token_encryption_key,
            }
            missing = [
                name
                for name, value in required.items()
                if value is None
                or not (
                    value.get_secret_value().strip()
                    if isinstance(value, SecretStr)
                    else str(value).strip()
                )
            ]
            if missing:
                raise ValueError(
                    "Missing production OneDrive settings: " + ", ".join(sorted(missing))
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_environment == "production"

    @property
    def resolved_frontend_base_url(self) -> str:
        if self.frontend_base_url:
            return self.frontend_base_url
        if not self.is_production:
            return DEVELOPMENT_CORS_ORIGINS[0]
        raise ValueError("FRONTEND_BASE_URL must be configured outside development")

    @property
    def resolved_cors_origins(self) -> list[str]:
        configured = [
            origin.strip().rstrip("/")
            for origin in (self.cors_allowed_origins or "").split(",")
            if origin.strip()
        ]
        if not self.is_production:
            configured.extend(DEVELOPMENT_CORS_ORIGINS)
        return list(dict.fromkeys(configured))

    @property
    def resolved_trusted_hosts(self) -> list[str]:
        if self.trusted_hosts:
            return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
        return ["localhost", "127.0.0.1", "testserver"]

    @property
    def resolved_enable_api_docs(self) -> bool:
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return not self.is_production

    @property
    def allow_historical_allocation_for_tests(self) -> bool:
        return not self.is_production and self.funding_allow_historical_allocation_for_tests

    @property
    def resolved_auth_cookie_secure(self) -> bool:
        if self.is_production:
            return True
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
