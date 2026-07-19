from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Sequence

from app.domain.entities.character import Character
from app.domain.pagination import PageResult


class CharacterRepository(ABC):
    """Abstract persistence contract for `Character`.

    Concrete implementations live in the infrastructure layer (e.g. a
    SQLAlchemy-backed implementation). Services depend only on this
    abstraction, never on the concrete technology behind it.
    """

    @abstractmethod
    async def list_paginated(
        self, page: int, page_size: int, name: Optional[str] = None
    ) -> PageResult[Character]:
        """Lists characters, optionally filtered by a case-insensitive
        substring match on `name`, using database-side pagination.

        Args:
            page: 1-indexed page number.
            page_size: Number of items per page.
            name: Optional case-insensitive substring to filter by name.

        Returns:
            A `PageResult` with the matching page of characters.
        """
        ...

    @abstractmethod
    async def bulk_upsert(self, characters: Sequence[Character]) -> List[uuid.UUID]:
        """Inserts or updates characters keyed by `swapi_id`, atomically,
        using a conflict-safe upsert (PostgreSQL `ON CONFLICT`) so
        concurrent imports never create duplicate rows.

        Args:
            characters: Characters to insert/update.

        Returns:
            Internal UUIDs of the affected rows.
        """
        ...

    @abstractmethod
    async def link_films(self, swapi_id_to_film_swapi_ids: dict[int, Iterable[int]]) -> None:
        """Associates characters with films using their `swapi_id`s.

        Args:
            swapi_id_to_film_swapi_ids: Maps a character's `swapi_id` to
                the `swapi_id`s of the films it appears in.

        Idempotent: safe to call repeatedly, including concurrently.
        """
        ...

    @abstractmethod
    async def increment_votes(self, character_id: uuid.UUID) -> Optional[Character]:
        """Atomically increments a character's vote count.

        Args:
            character_id: Internal UUID of the character.

        Returns:
            The updated character, or `None` if it doesn't exist.
        """
        ...
