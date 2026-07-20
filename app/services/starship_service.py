from __future__ import annotations

import logging
import re
import uuid
import asyncio
import json
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.entities.starship import Starship
from app.domain.exceptions import EntityNotFoundError
from app.domain.import_result import ImportResult
from app.domain.interfaces.starship_service import StarshipService as StarshipServiceInterface
from app.domain.interfaces.swapi_client import SWAPIClient
from app.domain.interfaces.lock_provider import LockProvider
from app.domain.exceptions import ImportInProgressError
from app.domain.pagination import PageResult, PaginationParams
from app.infrastructure.repositories.sqlalchemy_starship_repository import (
    SQLAlchemyStarshipRepository,
)

_SWAPI_ID_PATTERN = re.compile(r"/(\d+)/?$")


def _extract_swapi_id(url: str) -> int:
    """Extracts the numeric external id from a SWAPI resource URL.

    Args:
        url: A SWAPI resource URL, e.g. "https://swapi.dev/api/starships/9/".

    Returns:
        The trailing integer id, e.g. `9`.

    Raises:
        ValueError: If no trailing integer id can be found in `url`.
    """
    match = _SWAPI_ID_PATTERN.search(url.rstrip("/") + "/")
    if not match:
        raise ValueError(f"Could not extract swapi_id from url: {url}")
    return int(match.group(1))


class StarshipServiceImpl(StarshipServiceInterface):
    """Concrete `StarshipService`.

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
            swapi_client: Client used to stream starship data from SWAPI.
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

    async def list_starships(
        self, pagination: PaginationParams
    ) -> PageResult[Starship]:
        """See `StarshipService.list_starships`."""
        async with self._sessionmaker() as session:
            return await SQLAlchemyStarshipRepository(session, self._logger).list_paginated(
                pagination.page, pagination.page_size
            )

    async def vote(self, starship_id: uuid.UUID) -> Starship:
        """See `StarshipService.vote`."""
        async with self._sessionmaker() as session:
            updated = await SQLAlchemyStarshipRepository(session, self._logger).increment_votes(starship_id)
            if updated is None:
                raise EntityNotFoundError("Starship", str(starship_id))
            await session.commit()
            self._logger.info("starship_voted id=%s votes=%s", starship_id, updated.votes)
            return updated

    async def import_starships(self) -> ImportResult:
        """See `StarshipService.import_starships`."""
        cache_key = "starships:import_results"

        cached = await self.lock_provider.get_value(cache_key)
        if cached:
            self._logger.info("Import starships: reading from cache")
            return ImportResult.from_dict(json.loads(cached))

        lock_key = "lock:starships:import"
        token = str(uuid.uuid4())

        aquired = await self.lock_provider.acquire(lock_key, token, self.lock_ttl)
        if not aquired:
            # Timeout 30 seconds
            for _ in range(300):
                await asyncio.sleep(0.1)

                cached = await self.lock_provider.get_value(cache_key)
                if cached:
                    self._logger.info("Import starships: reading from cache")
                    return ImportResult.from_dict(json.loads(cached))
            
            raise ImportInProgressError(
                "starships",
            )
        
        try:
            result = ImportResult("starships")
            batch: List[Dict[str, Any]] = []
            async for record in self._swapi_client.fetch_starships():
                batch.append(record)
                if len(batch) >= self._batch_size:
                    await self._upsert_batch(batch, result)
                    batch = []
            if batch:
                await self._upsert_batch(batch, result)

            await self.lock_provider.set_value(cache_key, json.dumps(result.__dict__), self.cache_ttl)

            self._logger.info("import_completed resource=starships imported=%s batches=%s", result.imported, result.batches)
            return result
        
        finally:
            await self.lock_provider.release(lock_key, token)

    async def _upsert_batch(self, batch: List[Dict[str, Any]], result: ImportResult) -> None:
        """Upserts one batch of raw SWAPI starship records and links them
        to already-imported films, all within a single, independent
        transaction.

        Args:
            batch: Raw SWAPI starship records to upsert.
            result: Running `ImportResult`, updated in place with this
                batch's counts.
        """
        async with self._sessionmaker() as session:
            repository = SQLAlchemyStarshipRepository(session, self._logger)
            ids = await repository.bulk_upsert(
                [
                    Starship(
                        swapi_id=_extract_swapi_id(r["url"]),
                        name=r.get("name", ""),
                        model=r.get("model"),
                        manufacturer=r.get("manufacturer"),
                        cost_in_credits=r.get("cost_in_credits"),
                        length=r.get("length"),
                        crew=r.get("crew"),
                        passengers=r.get("passengers"),
                        starship_class=r.get("starship_class"),
                    )
                    for r in batch
                ]
            )

            film_links = {
                _extract_swapi_id(r["url"]): [_extract_swapi_id(u) for u in r["films"]]
                for r in batch
                if r.get("films")
            }
            if film_links:
                await repository.link_films(film_links)

            await session.commit()
            result.imported += len(ids)
            result.batches += 1
