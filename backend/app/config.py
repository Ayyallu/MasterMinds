from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
