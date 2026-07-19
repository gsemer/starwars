from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.film import Film
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult, PaginationParams


class FilmService(ABC):
    """Abstract contract for film use cases.

    Endpoints depend only on this abstraction. The concrete
    implementation owns its own DB session lifecycle internally, so a
    single instance can be safely reused (as a singleton) across
    concurrent requests.
    """

    @abstractmethod
    async def list_films(
        self, pagination: PaginationParams
    ) -> PageResult[Film]:
        """Lists/searches stored films.

        Args:
            pagination: Requested page and page size.
            title: Optional case-insensitive substring to filter by title.

        Returns:
            A `PageResult` with the matching page of films.
        """
        ...

    @abstractmethod
    async def vote(self, film_id: uuid.UUID) -> Film:
        """Casts a vote for a film.

        Args:
            film_id: Internal UUID of the film.

        Returns:
            The film with its updated vote count.

        Raises:
            EntityNotFoundError: If no film exists with that id.
        """
        ...

    @abstractmethod
    async def import_films(self) -> ImportResult:
        """Streams films from SWAPI and upserts them in batches.

        Returns:
            An `ImportResult` summarizing how many films were imported
            and in how many batches.
        """
        ...
