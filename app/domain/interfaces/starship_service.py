from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.starship import Starship
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult, PaginationParams


class StarshipService(ABC):
    """Abstract contract for starship use cases.

    Endpoints depend only on this abstraction. The concrete
    implementation owns its own DB session lifecycle internally, so a
    single instance can be safely reused (as a singleton) across
    concurrent requests.
    """

    @abstractmethod
    async def list_starships(
        self, pagination: PaginationParams
    ) -> PageResult[Starship]:
        """Lists/searches stored starships.

        Args:
            pagination: Requested page and page size.

        Returns:
            A `PageResult` with the matching page of starships.
        """
        ...

    @abstractmethod
    async def vote(self, starship_id: uuid.UUID) -> Starship:
        """Casts a vote for a starship.

        Args:
            starship_id: Internal UUID of the starship.

        Returns:
            The starship with its updated vote count.

        Raises:
            EntityNotFoundError: If no starship exists with that id.
        """
        ...

    @abstractmethod
    async def import_starships(self) -> ImportResult:
        """Streams starships from SWAPI and upserts them in batches.

        Returns:
            An `ImportResult` summarizing how many starships were
            imported and in how many batches.
        """
        ...
