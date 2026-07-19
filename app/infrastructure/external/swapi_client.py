from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict
from asyncio import Semaphore

import httpx

from app.domain.exceptions import ExternalServiceError
from app.domain.interfaces.swapi_client import SWAPIClient

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class HTTPXSWAPIClient(SWAPIClient):
    """HTTPX-based implementation of the `SWAPIClient` contract.

    Encapsulates all HTTP concerns (timeouts, retries with exponential
    backoff, error translation) so the application layer never touches
    HTTPX. Each `fetch_*` method is an async generator that yields raw
    records as they're fetched (page by page), so the caller can
    bulk-insert them in batches without waiting for the entire
    collection.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        semaphore: Semaphore,
        base_url: str,
        logger: logging.Logger,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
    ) -> None:
        """
        Args:
            http_client: A shared `httpx.AsyncClient` (owned by the DI container).
            base_url: SWAPI base URL, e.g. "https://swapi.dev/api".
            logger: Shared application logger.
            max_retries: Max attempts per page before giving up.
            backoff_base_seconds: Base delay for exponential backoff between retries.
        """
        self._client = http_client
        self._semaphore = semaphore
        self._base_url = base_url.rstrip("/")
        self._logger = logger
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    async def fetch_people(self) -> AsyncIterator[Dict[str, Any]]:
        """See `SWAPIClient.fetch_people`."""
        async for record in self._paginate("/people/"):
            yield record

    async def fetch_films(self) -> AsyncIterator[Dict[str, Any]]:
        """See `SWAPIClient.fetch_films`."""
        async for record in self._paginate("/films/"):
            yield record

    async def fetch_starships(self) -> AsyncIterator[Dict[str, Any]]:
        """See `SWAPIClient.fetch_starships`."""
        async for record in self._paginate("/starships/"):
            yield record

    async def _paginate(self, path: str) -> AsyncIterator[Dict[str, Any]]:
        """Follows SWAPI's `next` links, yielding each page's `results`
        one record at a time.

        Args:
            path: Resource path relative to the base URL, e.g. "/people/".
        """
        url: str | None = f"{self._base_url}{path}"
        while url:
            payload = await self._get_with_retry(url)
            for record in payload.get("results", []):
                yield record
            url = payload.get("next")

    async def _get_with_retry(self, url: str) -> Dict[str, Any]:
        """Performs a GET request with retry and exponential backoff on
        transient failures (429/5xx or transport errors).

        Args:
            url: Full URL to fetch.

        Returns:
            The parsed JSON response body.

        Raises:
            ExternalServiceError: If all retry attempts are exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                async with self._semaphore:
                    response = await self._client.get(url)
                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in RETRYABLE_STATUS_CODES:
                    raise

                last_error = exc

            except httpx.TransportError as exc:
                last_error = exc

            self._logger.warning(
                "swapi_request_failed url=%s attempt=%s/%s error=%s",
                url,
                attempt,
                self._max_retries,
                last_error,
            )

            if attempt < self._max_retries:
                await asyncio.sleep(
                    self._backoff_base_seconds * (2 ** (attempt - 1))
                )

        self._logger.error(
            "swapi_request_exhausted url=%s error=%s",
            url,
            last_error,
        )

        raise ExternalServiceError(
            "SWAPI",
            f"Failed to fetch '{url}' after {self._max_retries} attempts: {last_error}",
        )
