from __future__ import annotations

import httpx
import pytest

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.external.swapi_client import HTTPXSWAPIClient
from tests.conftest import make_logger


@pytest.mark.asyncio
async def test_fetch_people_paginates_through_results() -> None:
    pages = [
        {
            "results": [{"name": "Luke Skywalker", "url": "https://swapi.dev/api/people/1/"}],
            "next": "https://swapi.dev/api/people/?page=2",
        },
        {
            "results": [{"name": "Leia Organa", "url": "https://swapi.dev/api/people/5/"}],
            "next": None,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages.pop(0))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(http_client, "https://swapi.dev/api", make_logger())
        records = [r async for r in client.fetch_people()]

    assert [r["name"] for r in records] == ["Luke Skywalker", "Leia Organa"]


@pytest.mark.asyncio
async def test_fetch_films_returns_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"title": "A New Hope", "url": "https://swapi.dev/api/films/1/"}], "next": None},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(http_client, "https://swapi.dev/api", make_logger())
        records = [r async for r in client.fetch_films()]

    assert records[0]["title"] == "A New Hope"


@pytest.mark.asyncio
async def test_fetch_starships_returns_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"name": "X-wing", "url": "https://swapi.dev/api/starships/12/"}], "next": None},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(http_client, "https://swapi.dev/api", make_logger())
        records = [r async for r in client.fetch_starships()]

    assert records[0]["name"] == "X-wing"


@pytest.mark.asyncio
async def test_retries_on_transient_failure_then_succeeds(monkeypatch) -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(
            200, json={"results": [{"name": "Han Solo", "url": "https://swapi.dev/api/people/14/"}], "next": None}
        )

    sleeps = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.infrastructure.external.swapi_client.asyncio.sleep", fake_sleep)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(
            http_client, "https://swapi.dev/api", make_logger(), max_retries=5, backoff_base_seconds=0.1
        )
        records = [r async for r in client.fetch_people()]

    assert records[0]["name"] == "Han Solo"
    assert call_count["n"] == 3
    assert sleeps == [0.1, 0.2]


@pytest.mark.asyncio
async def test_raises_external_service_error_after_exhausting_retries(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr("app.infrastructure.external.swapi_client.asyncio.sleep", fake_sleep)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(
            http_client, "https://swapi.dev/api", make_logger(), max_retries=2, backoff_base_seconds=0.01
        )
        with pytest.raises(ExternalServiceError):
            [r async for r in client.fetch_starships()]


@pytest.mark.asyncio
async def test_non_retryable_error_still_raises_external_service_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HTTPXSWAPIClient(http_client, "https://swapi.dev/api", make_logger(), max_retries=2)
        with pytest.raises(ExternalServiceError):
            [r async for r in client.fetch_people()]
