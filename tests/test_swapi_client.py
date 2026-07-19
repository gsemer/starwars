from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.external.swapi_client import HTTPXSWAPIClient
from tests.support import make_logger


def build_client(handler, max_retries=3, backoff=0.5):
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    semaphore = asyncio.Semaphore(2)
    client = HTTPXSWAPIClient(
        http_client=http_client, semaphore=semaphore,
        base_url="https://swapi.dev/api", logger=make_logger(),
        max_retries=max_retries, backoff_base_seconds=backoff,
    )
    return client, http_client


class SWAPIClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_people_paginates_through_results(self) -> None:
        pages = [
            {"results": [{"name": "Luke", "url": "https://swapi.dev/api/people/1/"}],
             "next": "https://swapi.dev/api/people/?page=2"},
            {"results": [{"name": "Leia", "url": "https://swapi.dev/api/people/5/"}], "next": None},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=pages.pop(0))

        client, http_client = build_client(handler)
        try:
            records = [r async for r in client.fetch_people()]
        finally:
            await http_client.aclose()
        self.assertEqual([r["name"] for r in records], ["Luke", "Leia"])

    async def test_fetch_films_returns_records(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "results": [{"title": "A New Hope", "url": "https://swapi.dev/api/films/1/"}], "next": None})

        client, http_client = build_client(handler)
        try:
            records = [r async for r in client.fetch_films()]
        finally:
            await http_client.aclose()
        self.assertEqual(records[0]["title"], "A New Hope")

    async def test_fetch_starships_returns_records(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "results": [{"name": "X-wing", "url": "https://swapi.dev/api/starships/12/"}], "next": None})

        client, http_client = build_client(handler)
        try:
            records = [r async for r in client.fetch_starships()]
        finally:
            await http_client.aclose()
        self.assertEqual(records[0]["name"], "X-wing")

    async def test_retries_on_transient_failure_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, json={
                "results": [{"name": "Han", "url": "https://swapi.dev/api/people/14/"}], "next": None})

        client, http_client = build_client(handler, max_retries=5, backoff=0.1)
        try:
            with patch("app.infrastructure.external.swapi_client.asyncio.sleep", new=AsyncMock()):
                records = [r async for r in client.fetch_people()]
        finally:
            await http_client.aclose()
        self.assertEqual(records[0]["name"], "Han")
        self.assertEqual(calls["n"], 3)

    async def test_raises_external_service_error_after_exhausting_retries(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client, http_client = build_client(handler, max_retries=2, backoff=0.01)
        try:
            with patch("app.infrastructure.external.swapi_client.asyncio.sleep", new=AsyncMock()):
                with self.assertRaises(ExternalServiceError):
                    [r async for r in client.fetch_starships()]
        finally:
            await http_client.aclose()

    async def test_non_retryable_status_raises_immediately(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client, http_client = build_client(handler, max_retries=3)
        try:
            with self.assertRaises(httpx.HTTPStatusError):
                [r async for r in client.fetch_people()]
        finally:
            await http_client.aclose()


if __name__ == "__main__":
    unittest.main()
