from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock

logging.basicConfig(level="CRITICAL")  # keep test output quiet


def make_repository_mock() -> MagicMock:
    """Builds a mock repository with its async methods explicitly set as
    `AsyncMock`s. Plain `AsyncMock()` does NOT make child attributes
    awaitable by default (they come back as `MagicMock`), so each method
    used by the service layer is wired up here explicitly.
    """
    repo = MagicMock()
    repo.list_paginated = AsyncMock()
    repo.bulk_upsert = AsyncMock(return_value=[])
    repo.link_films = AsyncMock()
    repo.increment_votes = AsyncMock()
    return repo


class FakeSessionContext:
    """A minimal async context manager standing in for the object returned
    by `async_sessionmaker()` (i.e. `sessionmaker()`), so services under
    test can do `async with self._sessionmaker() as session: ...` without
    a real database connection.
    """

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *exc_info: Any) -> bool:
        return False


def make_sessionmaker(session: AsyncMock):
    """Builds a fake `async_sessionmaker`: a plain callable that returns
    a `FakeSessionContext` wrapping the given mock session every time
    it's called (mirroring real `sessionmaker()` semantics, where each
    call opens a fresh session).
    """

    def _sessionmaker() -> FakeSessionContext:
        return FakeSessionContext(session)

    return _sessionmaker


def make_logger() -> logging.Logger:
    """Returns a real (but muted) stdlib logger, since the app's Logger
    contract *is* `logging.Logger` — no interface to mock.
    """
    return logging.getLogger("test")


class FakeSWAPIClient:
    """In-memory `SWAPIClient` double. Yields whatever fixed record lists
    are configured; no network access. Implements the same async-generator
    shape as `HTTPXSWAPIClient` without inheriting from the ABC, since a
    test double only needs to satisfy the interface structurally.
    """

    def __init__(
        self,
        people: List[Dict[str, Any]] | None = None,
        films: List[Dict[str, Any]] | None = None,
        starships: List[Dict[str, Any]] | None = None,
    ) -> None:
        self._people = people or []
        self._films = films or []
        self._starships = starships or []

    async def fetch_people(self) -> AsyncIterator[Dict[str, Any]]:
        for record in self._people:
            yield record

    async def fetch_films(self) -> AsyncIterator[Dict[str, Any]]:
        for record in self._films:
            yield record

    async def fetch_starships(self) -> AsyncIterator[Dict[str, Any]]:
        for record in self._starships:
            yield record
