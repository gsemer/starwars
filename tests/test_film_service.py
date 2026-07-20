from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from app.domain.entities.film import Film
from app.domain.exceptions import EntityNotFoundError, ImportInProgressError
from app.domain.pagination import PageResult, PaginationParams
from app.services.film_service import FilmServiceImpl, _parse_release_date
from tests.support import (
    FakeSWAPIClient, make_lock_provider, make_logger, make_repository_mock, make_sessionmaker,
)

REPO_PATH = "app.services.film_service.SQLAlchemyFilmRepository"


def build_service(swapi_client=None, lock_provider=None, batch_size=50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    lock_provider = lock_provider or make_lock_provider()
    service = FilmServiceImpl(
        sessionmaker, swapi_client, make_logger(), lock_provider,
        lock_ttl=300, cache_ttl=60, batch_size=batch_size,
    )
    return service, session, lock_provider


class ParseReleaseDateTests(unittest.TestCase):
    def test_valid(self) -> None:
        result = _parse_release_date("1977-05-25")
        self.assertIsNotNone(result)
        self.assertEqual((result.year, result.month, result.day), (1977, 5, 25))

    def test_invalid_returns_none(self) -> None:
        self.assertIsNone(_parse_release_date("not-a-date"))

    def test_none_returns_none(self) -> None:
        self.assertIsNone(_parse_release_date(None))

    def test_non_string_returns_none(self) -> None:
        self.assertIsNone(_parse_release_date(12345))


class ListAndVoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_films_delegates_to_repository(self) -> None:
        repo = make_repository_mock()
        page = PageResult(items=[Film(swapi_id=1, title="A New Hope")], total=1, page=1, page_size=20)
        repo.list_paginated.return_value = page
        service, _, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.list_films(PaginationParams(page=1, page_size=20))
        self.assertIs(result, page)
        repo.list_paginated.assert_awaited_once_with(1, 20)

    async def test_vote_raises_when_film_missing(self) -> None:
        repo = make_repository_mock()
        repo.increment_votes.return_value = None
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            with self.assertRaises(EntityNotFoundError):
                await service.vote(uuid.uuid4())
        session.commit.assert_not_awaited()

    async def test_vote_commits_and_returns_updated_film(self) -> None:
        repo = make_repository_mock()
        film = Film(swapi_id=1, title="Return of the Jedi", votes=7)
        repo.increment_votes.return_value = film
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.vote(film.id)
        self.assertEqual(result.votes, 7)
        session.commit.assert_awaited_once()


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_returns_cached_result_without_locking(self) -> None:
        cached = json.dumps({"resource": "films", "imported": 6, "batches": 1})
        lock = make_lock_provider(cached=cached)
        service, _, _ = build_service(lock_provider=lock)
        result = await service.import_films()
        self.assertEqual(result.imported, 6)
        lock.acquire.assert_not_awaited()

    async def test_import_single_batch_when_lock_acquired(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(films=[{
            "title": "A New Hope", "url": "https://swapi.dev/api/films/1/",
            "episode_id": 4, "release_date": "1977-05-25",
        }])
        lock = make_lock_provider(cached=None, acquired=True)
        service, session, _ = build_service(swapi_client=swapi, lock_provider=lock)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_films()
        self.assertEqual(result.imported, 1)
        self.assertEqual(result.batches, 1)
        lock.set_value.assert_awaited_once()
        lock.release.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_import_splits_into_multiple_batches(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4(), uuid.uuid4()]
        films = [{"title": f"F{i}", "url": f"https://swapi.dev/api/films/{i}/"} for i in range(1, 8)]
        service, _, _ = build_service(swapi_client=FakeSWAPIClient(films=films), batch_size=3)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_films()
        self.assertEqual(result.batches, 3)
        self.assertEqual(repo.bulk_upsert.await_count, 3)

    async def test_import_times_out_when_lock_never_frees(self) -> None:
        lock = make_lock_provider(cached=None, acquired=False)
        lock.get_value = AsyncMock(return_value=None)
        service, _, _ = build_service(lock_provider=lock)
        with patch("app.services.film_service.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ImportInProgressError):
                await service.import_films()


if __name__ == "__main__":
    unittest.main()
