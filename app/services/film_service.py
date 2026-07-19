from __future__ import annotations

import logging
import re
import uuid
import asyncio
import json
from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.entities.film import Film
from app.domain.exceptions import EntityNotFoundError
from app.domain.import_result import ImportResult
from app.domain.interfaces.film_service import FilmService as FilmServiceInterface
from app.domain.interfaces.swapi_client import SWAPIClient
from app.domain.interfaces.lock_provider import LockProvider
from app.domain.exceptions import ExternalServiceError
from app.domain.pagination import PageResult, PaginationParams
from app.infrastructure.repositories.sqlalchemy_film_repository import SQLAlchemyFilmRepository

_SWAPI_ID_PATTERN = re.compile(r"/(\d+)/?$")


def _extract_swapi_id(url: str) -> int:
    """Extracts the numeric external id from a SWAPI resource URL.

    Args:
        url: A SWAPI resource URL, e.g. "https://swapi.dev/api/films/1/".

    Returns:
        The trailing integer id, e.g. `1`.

    Raises:
        ValueError: If no trailing integer id can be found in `url`.
    """
    match = _SWAPI_ID_PATTERN.search(url.rstrip("/") + "/")
    if not match:
        raise ValueError(f"Could not extract swapi_id from url: {url}")
    return int(match.group(1))


def _parse_release_date(value: Any) -> date | None:
    """Parses a SWAPI `release_date` string ("YYYY-MM-DD") into a `date`.

    Args:
        value: The raw value from the SWAPI payload.

    Returns:
        The parsed date, or `None` if `value` is missing/unparseable.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


class FilmServiceImpl(FilmServiceInterface):
    """Concrete `FilmService`.

    Holds no per-request state: it owns a session *factory*, not a
    session, so a single instance is created once at startup (see
    `Container`) and safely reused as a singleton across concurrent
    requests. Every method opens, uses, and closes its own session.
    """

    def __init__(
        self,
        sessionmaker: async_sessionmaker,
        swapi_client: SWAPIClient,
        logger: logging.Logger,
        lock_provider: LockProvider,
        lock_ttl: int,
        cache_ttl: int = 60 * 60 * 24,
        batch_size: int = 50,
    ) -> None:
        """
        Args:
            sessionmaker: Async session factory shared by the whole app.
            swapi_client: Client used to stream film data from SWAPI.
            logger: Shared application logger.
            batch_size: Number of records upserted per DB transaction during import.
        """
        self._sessionmaker = sessionmaker
        self._swapi_client = swapi_client
        self._logger = logger
        self.lock_provider = lock_provider
        self.lock_ttl = lock_ttl
        self.cache_ttl = cache_ttl
        self._batch_size = batch_size

    async def list_films(
        self, pagination: PaginationParams
    ) -> PageResult[Film]:
        """See `FilmService.list_films`."""
        async with self._sessionmaker() as session:
            return await SQLAlchemyFilmRepository(session, self._logger).list_paginated(
                pagination.page, pagination.page_size
            )

    async def vote(self, film_id: uuid.UUID) -> Film:
        """See `FilmService.vote`."""
        async with self._sessionmaker() as session:
            updated = await SQLAlchemyFilmRepository(session, self._logger).increment_votes(film_id)
            if updated is None:
                raise EntityNotFoundError("Film", str(film_id))
            await session.commit()
            self._logger.info("film_voted id=%s votes=%s", film_id, updated.votes)
            return updated

    async def import_films(self) -> ImportResult:
        """See `FilmService.import_films`."""
        cache_key = "films:import_results"

        cached = await self.lock_provider.get_value(cache_key)
        if cached:
            self._logger.info("Import films: reading from cache")
            return ImportResult.from_dict(json.loads(cached))

        lock_key = "lock:films:import"
        token = str(uuid.uuid4())

        aquired = await self.lock_provider.acquire(lock_key, token, self.lock_ttl)
        if not aquired:
            # Timeout 30 seconds
            for _ in range(300):
                await asyncio.sleep(0.1)

                cached = await self.lock_provider.get_value(cache_key)
                if cached:
                    self._logger.info("Import films: reading from cache")
                    return ImportResult.from_dict(json.loads(cached))
            
            raise ExternalServiceError(
                "Starwars API",
                "Timed out waiting for films import",
            )
        
        try:
            result = ImportResult("films")
            batch: List[Dict[str, Any]] = []
            async for record in self._swapi_client.fetch_films():
                batch.append(record)
                if len(batch) >= self._batch_size:
                    await self._upsert_batch(batch, result)
                    batch = []
            if batch:
                await self._upsert_batch(batch, result)

            await self.lock_provider.set_value(cache_key, json.dumps(result.__dict__), self.cache_ttl)

            self._logger.info("import_completed resource=films imported=%s batches=%s", result.imported, result.batches)
            return result
        
        finally:
            await self.lock_provider.release(lock_key, token)

    async def _upsert_batch(self, batch: List[Dict[str, Any]], result: ImportResult) -> None:
        """Upserts one batch of raw SWAPI film records within a single,
        independent transaction.

        Args:
            batch: Raw SWAPI film records to upsert.
            result: Running `ImportResult`, updated in place with this
                batch's counts.
        """
        async with self._sessionmaker() as session:
            ids = await SQLAlchemyFilmRepository(session, self._logger).bulk_upsert(
                [
                    Film(
                        swapi_id=_extract_swapi_id(r["url"]),
                        title=r.get("title", ""),
                        episode_id=r.get("episode_id"),
                        director=r.get("director"),
                        producer=r.get("producer"),
                        release_date=_parse_release_date(r.get("release_date")),
                        opening_crawl=r.get("opening_crawl"),
                    )
                    for r in batch
                ]
            )
            await session.commit()
            result.imported += len(ids)
            result.batches += 1
