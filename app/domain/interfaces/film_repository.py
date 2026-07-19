from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from app.domain.entities.film import Film
from app.domain.pagination import PageResult


class FilmRepository(ABC):
    """Abstract persistence contract for `Film`."""

    @abstractmethod
    async def list_paginated(
        self, page: int, page_size: int
    ) -> PageResult[Film]:
        """Lists films, optionally filtered by a case-insensitive substring
        match on `title`, using database-side pagination.

        Args:
            page: 1-indexed page number.
            page_size: Number of items per page.

        Returns:
            A `PageResult` with the matching page of films.
        """
        ...

    @abstractmethod
    async def bulk_upsert(self, films: Sequence[Film]) -> List[uuid.UUID]:
        """Inserts or updates films keyed by `swapi_id`, atomically, using
        a conflict-safe upsert (PostgreSQL `ON CONFLICT`).

        Args:
            films: Films to insert/update.

        Returns:
            Internal UUIDs of the affected rows.
        """
        ...

    @abstractmethod
    async def increment_votes(self, film_id: uuid.UUID) -> Optional[Film]:
        """Atomically increments a film's vote count.

        Args:
            film_id: Internal UUID of the film.

        Returns:
            The updated film, or `None` if it doesn't exist.
        """
        ...
