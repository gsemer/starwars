from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities.character import Character
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult, PaginationParams


class CharacterService(ABC):
    """Abstract contract for character use cases.

    Endpoints depend only on this abstraction. The concrete
    implementation owns its own DB session lifecycle internally, so a
    single instance can be safely reused (as a singleton) across
    concurrent requests.
    """

    @abstractmethod
    async def list_characters(
        self, pagination: PaginationParams
    ) -> PageResult[Character]:
        """Lists/searches stored characters.

        Args:
            pagination: Requested page and page size.

        Returns:
            A `PageResult` with the matching page of characters.
        """
        ...

    @abstractmethod
    async def vote(self, character_id: uuid.UUID) -> Character:
        """Casts a vote for a character.

        Args:
            character_id: Internal UUID of the character.

        Returns:
            The character with its updated vote count.

        Raises:
            EntityNotFoundError: If no character exists with that id.
        """
        ...

    @abstractmethod
    async def import_characters(self) -> ImportResult:
        """Streams characters from SWAPI and upserts them in batches.

        Returns:
            An `ImportResult` summarizing how many characters were
            imported and in how many batches.
        """
        ...
