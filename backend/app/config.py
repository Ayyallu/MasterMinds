from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Async SQLAlchemy connection string, e.g.
    # postgresql+asyncpg://user:password@localhost:5432/masterminds
    database_url: str = (
        "postgresql+asyncpg://masterminds:masterminds@localhost:5432/masterminds"
    )

    # Explicit frontend origin allowed by CORS. Never a wildcard while
    # credentials are allowed.
    frontend_origin: str = "http://localhost:3000"

    # Seconds allowed for the database readiness probe before it is treated
    # as unhealthy.
    health_db_timeout_seconds: float = 3.0

    environment: str = "development"

    # --- Auth / security ---
    # JWT signing secret for access tokens. The default is a development-only
    # value and is rejected at startup when environment == "production".
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    password_reset_ttl_minutes: int = 30

    # Login rate limiting (per identifier+IP, in-process window).
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    # TOTP issuer label shown in authenticator apps.
    totp_issuer: str = "MasterMinds"

    _DEV_SECRET_DEFAULTS = frozenset({"dev-insecure-change-me", "", "changeme"})

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_production_secrets(self) -> None:
        """Raise if insecure development defaults are used in production."""
        if self.is_production and self.jwt_secret in self._DEV_SECRET_DEFAULTS:
            raise RuntimeError(
                "jwt_secret must be set to a strong value in production; "
                "the development default is not allowed."
            )

    @field_validator("frontend_origin")
    @classmethod
    def _no_wildcard_origin(cls, value: str) -> str:
        # Credentials are always allowed on the CORS middleware, so a wildcard
        # origin would be both invalid and insecure. Reject it explicitly.
        if value.strip() == "*":
            raise ValueError(
                "frontend_origin must be an explicit origin, not '*', "
                "because CORS credentials are enabled."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
