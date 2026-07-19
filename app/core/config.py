from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application configuration, loaded from environment
    variables / a `.env` file. See `.env.example` for all supported keys.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SWAPI Explorer API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+asyncpg://swapi:swapi@localhost:5433/swapi",
        description="Async SQLAlchemy connection string (asyncpg driver).",
    )
    db_echo: bool = False

    redis_url: str = Field(default="redis://localhost:6381/0")
    import_lock_ttl_seconds: int = 30

    swapi_base_url: str = Field(default="https://swapi.dev/api")
    swapi_timeout_seconds: float = 10.0
    swapi_max_retries: int = 3
    swapi_backoff_base_seconds: float = 0.5

    import_batch_size: int = 50

    log_level: str = "INFO"

    default_page_size: int = 20
    max_page_size: int = 100

    max_concurrency: int = 1


@lru_cache
def get_settings() -> Settings:
    """Returns the cached, process-wide `Settings` instance.

    Cached so repeated calls (e.g. from multiple DI entry points) don't
    re-parse the environment.
    """
    return Settings()
