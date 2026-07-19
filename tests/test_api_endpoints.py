from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_character_service, get_film_service, get_starship_service
from app.domain.entities.character import Character
from app.domain.entities.film import Film
from app.domain.entities.starship import Starship
from app.domain.exceptions import EntityNotFoundError
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


# --- characters --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_characters_returns_mapped_page(app, client) -> None:
    character = Character(swapi_id=1, name="Luke Skywalker")
    service = AsyncMock()
    service.list_characters.return_value = PageResult(items=[character], total=1, page=1, page_size=20)
    app.dependency_overrides[get_character_service] = lambda: service

    response = await client.get("/api/v1/characters")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["name"] == "Luke Skywalker"
    assert body["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_search_characters_passes_name_filter(app, client) -> None:
    service = AsyncMock()
    service.list_characters.return_value = PageResult(items=[], total=0, page=1, page_size=20)
    app.dependency_overrides[get_character_service] = lambda: service

    response = await client.get("/api/v1/characters", params={"name": "luke"})

    assert response.status_code == 200
    args, _ = service.list_characters.call_args
    assert args[1] == "luke"


@pytest.mark.asyncio
async def test_vote_character_returns_updated_votes(app, client) -> None:
    character = Character(swapi_id=1, name="Leia Organa", votes=3)
    service = AsyncMock()
    service.vote.return_value = character
    app.dependency_overrides[get_character_service] = lambda: service

    response = await client.post(f"/api/v1/characters/{character.id}/vote")

    assert response.status_code == 200
    assert response.json()["votes"] == 3


@pytest.mark.asyncio
async def test_vote_character_not_found_returns_404(app, client) -> None:
    service = AsyncMock()
    service.vote.side_effect = EntityNotFoundError("Character", "abc")
    app.dependency_overrides[get_character_service] = lambda: service

    response = await client.post(f"/api/v1/characters/{uuid.uuid4()}/vote")

    assert response.status_code == 404
    assert response.json()["error_code"] == "ENTITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_import_characters_endpoint_returns_result(app, client) -> None:
    service = AsyncMock()
    result = ImportResult("characters")
    result.imported = 6
    result.batches = 1
    service.import_characters.return_value = result
    app.dependency_overrides[get_character_service] = lambda: service

    response = await client.post("/api/v1/characters/import")

    assert response.status_code == 200
    assert response.json() == {"resource": "characters", "imported": 6, "batches": 1}


@pytest.mark.asyncio
async def test_invalid_uuid_returns_422(app, client) -> None:
    app.dependency_overrides[get_character_service] = lambda: AsyncMock()

    response = await client.post("/api/v1/characters/not-a-uuid/vote")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pagination_out_of_range_returns_422(app, client) -> None:
    app.dependency_overrides[get_character_service] = lambda: AsyncMock()

    response = await client.get("/api/v1/characters", params={"page_size": 1000})

    assert response.status_code == 422


# --- films ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_films_returns_mapped_page(app, client) -> None:
    film = Film(swapi_id=1, title="A New Hope")
    service = AsyncMock()
    service.list_films.return_value = PageResult(items=[film], total=1, page=1, page_size=20)
    app.dependency_overrides[get_film_service] = lambda: service

    response = await client.get("/api/v1/films")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "A New Hope"


@pytest.mark.asyncio
async def test_vote_film_not_found_returns_404(app, client) -> None:
    service = AsyncMock()
    service.vote.side_effect = EntityNotFoundError("Film", "abc")
    app.dependency_overrides[get_film_service] = lambda: service

    response = await client.post(f"/api/v1/films/{uuid.uuid4()}/vote")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_import_films_endpoint(app, client) -> None:
    service = AsyncMock()
    result = ImportResult("films")
    result.imported = 6
    result.batches = 1
    service.import_films.return_value = result
    app.dependency_overrides[get_film_service] = lambda: service

    response = await client.post("/api/v1/films/import")

    assert response.status_code == 200
    assert response.json()["resource"] == "films"


# --- starships -------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_starships_search_by_name(app, client) -> None:
    starship = Starship(swapi_id=9, name="Millennium Falcon")
    service = AsyncMock()
    service.list_starships.return_value = PageResult(items=[starship], total=1, page=1, page_size=20)
    app.dependency_overrides[get_starship_service] = lambda: service

    response = await client.get("/api/v1/starships", params={"name": "falcon"})

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Millennium Falcon"


@pytest.mark.asyncio
async def test_vote_starship_not_found_returns_404(app, client) -> None:
    service = AsyncMock()
    service.vote.side_effect = EntityNotFoundError("Starship", "abc")
    app.dependency_overrides[get_starship_service] = lambda: service

    response = await client.post(f"/api/v1/starships/{uuid.uuid4()}/vote")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_import_starships_endpoint(app, client) -> None:
    service = AsyncMock()
    result = ImportResult("starships")
    service.import_starships.return_value = result
    app.dependency_overrides[get_starship_service] = lambda: service

    response = await client.post("/api/v1/starships/import")

    assert response.status_code == 200
    assert response.json()["resource"] == "starships"


# --- docs / cross-cutting ---------------------------------------------------


@pytest.mark.asyncio
async def test_swagger_docs_available(client) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_schema_lists_all_endpoints(client) -> None:
    response = await client.get("/openapi.json")
    paths = set(response.json()["paths"].keys())
    assert paths == {
        "/api/v1/characters/import",
        "/api/v1/characters",
        "/api/v1/characters/{character_id}/vote",
        "/api/v1/films/import",
        "/api/v1/films",
        "/api/v1/films/{film_id}/vote",
        "/api/v1/starships/import",
        "/api/v1/starships",
        "/api/v1/starships/{starship_id}/vote",
    }


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500() -> None:
    from fastapi import FastAPI

    from app.api.error_handlers import register_exception_handlers

    probe_app = FastAPI()
    register_exception_handlers(probe_app)

    @probe_app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as probe_client:
        response = await probe_client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"


@pytest.mark.asyncio
async def test_external_service_error_returns_502() -> None:
    from fastapi import FastAPI

    from app.api.error_handlers import register_exception_handlers
    from app.domain.exceptions import ExternalServiceError

    probe_app = FastAPI()
    register_exception_handlers(probe_app)

    @probe_app.get("/swapi-down")
    async def swapi_down():
        raise ExternalServiceError("SWAPI", "timed out")

    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as probe_client:
        response = await probe_client.get("/swapi-down")

    assert response.status_code == 502
    assert response.json()["error_code"] == "EXTERNAL_SERVICE_ERROR"
