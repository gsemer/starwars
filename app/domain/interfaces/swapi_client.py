from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict


class SWAPIClient(ABC):
    """Abstract contract for a client that fetches Star Wars data.

    Concrete implementations (e.g. HTTPX-based) live in the
    infrastructure layer. Each `fetch_*` method is an async generator
    that yields raw records (dicts, as returned by the API) page by page,
    so a caller can stream and bulk-insert them in batches without
    waiting for the entire collection to be fetched first.
    """

    @abstractmethod
    def fetch_people(self) -> AsyncIterator[Dict[str, Any]]:
        """Yields raw character/person records from SWAPI, page by page."""
        ...

    @abstractmethod
    def fetch_films(self) -> AsyncIterator[Dict[str, Any]]:
        """Yields raw film records from SWAPI, page by page."""
        ...

    @abstractmethod
    def fetch_starships(self) -> AsyncIterator[Dict[str, Any]]:
        """Yields raw starship records from SWAPI, page by page."""
        ...
