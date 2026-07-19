from __future__ import annotations

import unittest
import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_character_service, get_film_service, get_starship_service
from app.api.error_handlers import register_exception_handlers
from app.domain.entities.character import Character
from app.domain.entities.film import Film
from app.domain.entities.starship import Starship
from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult
from app.main import create_app


def make_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


class CharacterEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    async def test_list_characters_returns_mapped_page(self) -> None:
        service = AsyncMock()
        service.list_characters.return_value = PageResult(
            items=[Character(swapi_id=1, name="Luke Skywalker")], total=1, page=1, page_size=20)
        self.app.dependency_overrides[get_character_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.get("/api/v1/characters")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"][0]["name"], "Luke Skywalker")
        self.assertEqual(body["meta"]["total"], 1)

    async def test_list_characters_passes_pagination(self) -> None:
        service = AsyncMock()
        service.list_characters.return_value = PageResult(items=[], total=0, page=2, page_size=5)
        self.app.dependency_overrides[get_character_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.get("/api/v1/characters", params={"page": 2, "page_size": 5})
        self.assertEqual(response.status_code, 200)
        pagination = service.list_characters.call_args.args[0]
        self.assertEqual((pagination.page, pagination.page_size), (2, 5))

    async def test_vote_character_returns_updated_votes(self) -> None:
        character = Character(swapi_id=1, name="Leia Organa", votes=3)
        service = AsyncMock()
        service.vote.return_value = character
        self.app.dependency_overrides[get_character_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post(f"/api/v1/characters/{character.id}/vote")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["votes"], 3)

    async def test_vote_character_not_found_returns_404(self) -> None:
        service = AsyncMock()
        service.vote.side_effect = EntityNotFoundError("Character", "abc")
        self.app.dependency_overrides[get_character_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post(f"/api/v1/characters/{uuid.uuid4()}/vote")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "ENTITY_NOT_FOUND")

    async def test_import_characters_returns_result(self) -> None:
        service = AsyncMock()
        result = ImportResult("characters")
        result.imported = 6
        result.batches = 1
        service.import_characters.return_value = result
        self.app.dependency_overrides[get_character_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post("/api/v1/characters/import")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"resource": "characters", "imported": 6, "batches": 1})

    async def test_invalid_uuid_returns_422(self) -> None:
        self.app.dependency_overrides[get_character_service] = lambda: AsyncMock()
        async with make_client(self.app) as client:
            response = await client.post("/api/v1/characters/not-a-uuid/vote")
        self.assertEqual(response.status_code, 422)

    async def test_pagination_out_of_range_returns_422(self) -> None:
        self.app.dependency_overrides[get_character_service] = lambda: AsyncMock()
        async with make_client(self.app) as client:
            response = await client.get("/api/v1/characters", params={"page_size": 1000})
        self.assertEqual(response.status_code, 422)


class FilmEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    async def test_list_films_returns_mapped_page(self) -> None:
        service = AsyncMock()
        service.list_films.return_value = PageResult(
            items=[Film(swapi_id=1, title="A New Hope")], total=1, page=1, page_size=20)
        self.app.dependency_overrides[get_film_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.get("/api/v1/films")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["title"], "A New Hope")

    async def test_vote_film_not_found_returns_404(self) -> None:
        service = AsyncMock()
        service.vote.side_effect = EntityNotFoundError("Film", "abc")
        self.app.dependency_overrides[get_film_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post(f"/api/v1/films/{uuid.uuid4()}/vote")
        self.assertEqual(response.status_code, 404)

    async def test_import_films_endpoint(self) -> None:
        service = AsyncMock()
        result = ImportResult("films")
        result.imported = 6
        result.batches = 1
        service.import_films.return_value = result
        self.app.dependency_overrides[get_film_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post("/api/v1/films/import")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resource"], "films")


class StarshipEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    async def test_list_starships_returns_mapped_page(self) -> None:
        service = AsyncMock()
        service.list_starships.return_value = PageResult(
            items=[Starship(swapi_id=9, name="Millennium Falcon")], total=1, page=1, page_size=20)
        self.app.dependency_overrides[get_starship_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.get("/api/v1/starships")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["name"], "Millennium Falcon")

    async def test_vote_starship_not_found_returns_404(self) -> None:
        service = AsyncMock()
        service.vote.side_effect = EntityNotFoundError("Starship", "abc")
        self.app.dependency_overrides[get_starship_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post(f"/api/v1/starships/{uuid.uuid4()}/vote")
        self.assertEqual(response.status_code, 404)

    async def test_import_starships_endpoint(self) -> None:
        service = AsyncMock()
        service.import_starships.return_value = ImportResult("starships")
        self.app.dependency_overrides[get_starship_service] = lambda: service
        async with make_client(self.app) as client:
            response = await client.post("/api/v1/starships/import")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resource"], "starships")


class DocsAndErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_swagger_docs_available(self) -> None:
        app = create_app()
        async with make_client(app) as client:
            response = await client.get("/docs")
        self.assertEqual(response.status_code, 200)

    async def test_openapi_lists_all_endpoints(self) -> None:
        app = create_app()
        async with make_client(app) as client:
            response = await client.get("/openapi.json")
        paths = set(response.json()["paths"].keys())
        self.assertEqual(paths, {
            "/api/v1/characters/import", "/api/v1/characters", "/api/v1/characters/{character_id}/vote",
            "/api/v1/films/import", "/api/v1/films", "/api/v1/films/{film_id}/vote",
            "/api/v1/starships/import", "/api/v1/starships", "/api/v1/starships/{starship_id}/vote",
        })

    async def test_unhandled_exception_returns_500(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise RuntimeError("boom")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/boom")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error_code"], "INTERNAL_SERVER_ERROR")

    async def test_external_service_error_returns_502(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/down")
        async def down():
            raise ExternalServiceError("SWAPI", "timed out")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/down")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error_code"], "EXTERNAL_SERVICE_ERROR")

    async def test_domain_error_returns_400(self) -> None:
        from app.domain.exceptions import DomainError

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/bad")
        async def bad():
            raise DomainError("bad thing")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/bad")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "DOMAIN_ERROR")


if __name__ == "__main__":
    unittest.main()
