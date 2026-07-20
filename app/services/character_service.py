from __future__ import annotations

import logging
import re
import uuid
import asyncio
import json
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.entities.character import Character
from app.domain.exceptions import EntityNotFoundError
from app.domain.import_result import ImportResult
from app.domain.interfaces.character_service import CharacterService as CharacterServiceInterface
from app.domain.interfaces.swapi_client import SWAPIClient
from app.domain.interfaces.lock_provider import LockProvider
from app.domain.exceptions import ImportInProgressError
from app.domain.pagination import PageResult, PaginationParams
from app.infrastructure.repositories.sqlalchemy_character_repository import (
    SQLAlchemyCharacterRepository,
)

_SWAPI_ID_PATTERN = re.compile(r"/(\d+)/?$")


def _extract_swapi_id(url: str) -> int:
    """Extracts the numeric external id from a SWAPI resource URL.

    Args:
        url: A SWAPI resource URL, e.g. "https://swapi.dev/api/people/1/".

    Returns:
        The trailing integer id, e.g. `1`.

    Raises:
        ValueError: If no trailing integer id can be found in `url`.
    """
    match = _SWAPI_ID_PATTERN.search(url.rstrip("/") + "/")
    if not match:
        raise ValueError(f"Could not extract swapi_id from url: {url}")
    return int(match.group(1))


class CharacterServiceImpl(CharacterServiceInterface):
    """Concrete `CharacterService`.

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
            swapi_client: Client used to stream character data from SWAPI.
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

    async def list_characters(
        self, pagination: PaginationParams
    ) -> PageResult[Character]:
        """See `CharacterService.list_characters`."""
        async with self._sessionmaker() as session:
            return await SQLAlchemyCharacterRepository(session, self._logger).list_paginated(
                pagination.page, pagination.page_size
            )

    async def vote(self, character_id: uuid.UUID) -> Character:
        """See `CharacterService.vote`."""
        async with self._sessionmaker() as session:
            updated = await SQLAlchemyCharacterRepository(session, self._logger).increment_votes(character_id)
            if updated is None:
                raise EntityNotFoundError("Character", str(character_id))
            await session.commit()
            self._logger.info("character_voted id=%s votes=%s", character_id, updated.votes)
            return updated

    async def import_characters(self) -> ImportResult:
        """See `CharacterService.import_characters`."""
        cache_key = "characters:import_results"

        cached = await self.lock_provider.get_value(cache_key)
        if cached:
            self._logger.info("Import characters: reading from cache")
            return ImportResult.from_dict(json.loads(cached))

        lock_key = "lock:characters:import"
        token = str(uuid.uuid4())

        aquired = await self.lock_provider.acquire(lock_key, token, self.lock_ttl)
        if not aquired:
            # Timeout 30 seconds
            for _ in range(300):
                await asyncio.sleep(0.1)

                cached = await self.lock_provider.get_value(cache_key)
                if cached:
                    self._logger.info("Import characters: reading from cache")
                    return ImportResult.from_dict(json.loads(cached))
            
            raise ImportInProgressError(
                "characters",
            )

        try:
            result = ImportResult("characters")
            batch: List[Dict[str, Any]] = []
            async for record in self._swapi_client.fetch_people():
                batch.append(record)
                if len(batch) >= self._batch_size:
                    await self._upsert_batch(batch, result)
                    batch = []
            if batch:
                await self._upsert_batch(batch, result)

            await self.lock_provider.set_value(cache_key, json.dumps(result.__dict__), self.cache_ttl)

            self._logger.info("import_completed resource=characters imported=%s batches=%s", result.imported, result.batches)
            return result
        
        finally:
            await self.lock_provider.release(lock_key, token)

    async def _upsert_batch(self, batch: List[Dict[str, Any]], result: ImportResult) -> None:
        """Upserts one batch of raw SWAPI character records and links
        them to already-imported films, all within a single, independent
        transaction.

        Args:
            batch: Raw SWAPI person records to upsert.
            result: Running `ImportResult`, updated in place with this
                batch's counts.
        """
        async with self._sessionmaker() as session:
            repository = SQLAlchemyCharacterRepository(session, self._logger)
            ids = await repository.bulk_upsert(
                [
                    Character(
                        swapi_id=_extract_swapi_id(r["url"]),
                        name=r.get("name", ""),
                        height=r.get("height"),
                        mass=r.get("mass"),
                        hair_color=r.get("hair_color"),
                        skin_color=r.get("skin_color"),
                        eye_color=r.get("eye_color"),
                        birth_year=r.get("birth_year"),
                        gender=r.get("gender"),
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
