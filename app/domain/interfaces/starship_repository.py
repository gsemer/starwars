from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Sequence

from app.domain.entities.starship import Starship
from app.domain.pagination import PageResult


class StarshipRepository(ABC):
    """Abstract persistence contract for `Starship`."""

    @abstractmethod
    async def list_paginated(
        self, page: int, page_size: int, name: Optional[str] = None
    ) -> PageResult[Starship]:
        """Lists starships, optionally filtered by a case-insensitive
        substring match on `name`, using database-side pagination.

        Args:
            page: 1-indexed page number.
            page_size: Number of items per page.
            name: Optional case-insensitive substring to filter by name.

        Returns:
            A `PageResult` with the matching page of starships.
        """
        ...

    @abstractmethod
    async def bulk_upsert(self, starships: Sequence[Starship]) -> List[uuid.UUID]:
        """Inserts or updates starships keyed by `swapi_id`, atomically,
        using a conflict-safe upsert (PostgreSQL `ON CONFLICT`).

        Args:
            starships: Starships to insert/update.

        Returns:
            Internal UUIDs of the affected rows.
        """
        ...

    @abstractmethod
    async def link_films(self, swapi_id_to_film_swapi_ids: dict[int, Iterable[int]]) -> None:
        """Associates starships with films using their `swapi_id`s.

        Args:
            swapi_id_to_film_swapi_ids: Maps a starship's `swapi_id` to
                the `swapi_id`s of the films it appears in.

        Idempotent: safe to call repeatedly, including concurrently.
        """
        ...

    @abstractmethod
    async def increment_votes(self, starship_id: uuid.UUID) -> Optional[Starship]:
        """Atomically increments a starship's vote count.

        Args:
            starship_id: Internal UUID of the starship.

        Returns:
            The updated starship, or `None` if it doesn't exist.
        """
        ...
