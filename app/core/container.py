from __future__ import annotations

import logging

import httpx
from asyncio import Semaphore
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from redis.asyncio import from_url as redis_from_url

from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.database.session import create_engine_and_sessionmaker
from app.infrastructure.external.swapi_client import HTTPXSWAPIClient
from app.infrastructure.cache.redis_lock_provider import RedisLockProvider
from app.services.character_service import CharacterServiceImpl
from app.services.film_service import FilmServiceImpl
from app.services.starship_service import StarshipServiceImpl

class Container:
    """Initializes and owns every shared, long-lived object the app
    needs: the DB engine/session factory, the HTTPX client, the SWAPI
    client, and the three singleton services — all wired up here, once,
    at startup (see `app.main` lifespan).

    Each service is created exactly once and reused for the lifetime of
    the process (see `app.state.character_service` etc.), rather than
    being rebuilt on every request.
    """

    def __init__(self, settings: Settings) -> None:
        """Builds every shared dependency and the three services.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.logger: logging.Logger = get_logger("app")

        self.semaphore = Semaphore(settings.max_concurrency)

        self.engine: AsyncEngine
        self.sessionmaker: async_sessionmaker
        self.engine, self.sessionmaker = create_engine_and_sessionmaker(settings)

        self.redis_client = redis_from_url(settings.redis_url)
        self.lock_provider = RedisLockProvider(self.redis_client, self.logger)

        self.http_client = httpx.AsyncClient(timeout=settings.swapi_timeout_seconds)
        self.swapi_client = HTTPXSWAPIClient(
            http_client=self.http_client,
            semaphore=self.semaphore,
            base_url=settings.swapi_base_url,
            logger=self.logger,
            max_retries=settings.swapi_max_retries,
            backoff_base_seconds=settings.swapi_backoff_base_seconds,
        )

        self.character_service = CharacterServiceImpl(
            self.sessionmaker, self.swapi_client, self.logger, self.lock_provider, settings.import_lock_ttl_seconds, settings.import_batch_size
        )
        self.film_service = FilmServiceImpl(
            self.sessionmaker, self.swapi_client, self.logger, self.lock_provider, settings.import_lock_ttl_seconds, settings.import_batch_size
        )
        self.starship_service = StarshipServiceImpl(
            self.sessionmaker, self.swapi_client, self.logger, self.lock_provider, settings.import_lock_ttl_seconds, settings.import_batch_size
        )

    async def dispose(self) -> None:
        """Releases the HTTPX client and DB engine/pool. Called once at
        application shutdown.
        """
        await self.http_client.aclose()
        await self.redis_client.aclose()
        await self.engine.dispose()
