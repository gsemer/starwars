from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from app.domain.entities.starship import Starship
from app.domain.exceptions import EntityNotFoundError, ImportInProgressError
from app.domain.pagination import PageResult, PaginationParams
from app.services.starship_service import StarshipServiceImpl
from tests.support import (
    FakeSWAPIClient, make_lock_provider, make_logger, make_repository_mock, make_sessionmaker,
)

REPO_PATH = "app.services.starship_service.SQLAlchemyStarshipRepository"


def build_service(swapi_client=None, lock_provider=None, batch_size=50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    lock_provider = lock_provider or make_lock_provider()
    service = StarshipServiceImpl(
        sessionmaker, swapi_client, make_logger(), lock_provider,
        lock_ttl=300, cache_ttl=60, batch_size=batch_size,
    )
    return service, session, lock_provider


class ListAndVoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_starships_delegates_to_repository(self) -> None:
        repo = make_repository_mock()
        page = PageResult(items=[Starship(swapi_id=9, name="Millennium Falcon")], total=1, page=1, page_size=20)
        repo.list_paginated.return_value = page
        service, _, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.list_starships(PaginationParams(page=1, page_size=20))
        self.assertIs(result, page)
        repo.list_paginated.assert_awaited_once_with(1, 20)

    async def test_vote_raises_when_starship_missing(self) -> None:
        repo = make_repository_mock()
        repo.increment_votes.return_value = None
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            with self.assertRaises(EntityNotFoundError):
                await service.vote(uuid.uuid4())
        session.commit.assert_not_awaited()

    async def test_vote_commits_and_returns_updated_starship(self) -> None:
        repo = make_repository_mock()
        starship = Starship(swapi_id=9, name="X-wing", votes=2)
        repo.increment_votes.return_value = starship
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.vote(starship.id)
        self.assertEqual(result.votes, 2)
        session.commit.assert_awaited_once()


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_returns_cached_result_without_locking(self) -> None:
        cached = json.dumps({"resource": "starships", "imported": 36, "batches": 1})
        lock = make_lock_provider(cached=cached)
        service, _, _ = build_service(lock_provider=lock)
        result = await service.import_starships()
        self.assertEqual(result.imported, 36)
        lock.acquire.assert_not_awaited()

    async def test_import_single_batch_when_lock_acquired(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(starships=[{"name": "TIE Fighter", "url": "https://swapi.dev/api/starships/13/"}])
        lock = make_lock_provider(cached=None, acquired=True)
        service, session, _ = build_service(swapi_client=swapi, lock_provider=lock)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_starships()
        self.assertEqual(result.imported, 1)
        self.assertEqual(result.batches, 1)
        lock.set_value.assert_awaited_once()
        lock.release.assert_awaited_once()

    async def test_import_links_films_when_present(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(starships=[{
            "name": "X-wing", "url": "https://swapi.dev/api/starships/12/",
            "films": ["https://swapi.dev/api/films/1/"],
        }])
        service, _, _ = build_service(swapi_client=swapi)
        with patch(REPO_PATH, return_value=repo):
            await service.import_starships()
        repo.link_films.assert_awaited_once_with({12: [1]})

    async def test_import_splits_into_multiple_batches(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        starships = [{"name": f"S{i}", "url": f"https://swapi.dev/api/starships/{i}/"} for i in range(1, 5)]
        service, _, _ = build_service(swapi_client=FakeSWAPIClient(starships=starships), batch_size=2)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_starships()
        self.assertEqual(result.batches, 2)
        self.assertEqual(repo.bulk_upsert.await_count, 2)

    async def test_import_times_out_when_lock_never_frees(self) -> None:
        lock = make_lock_provider(cached=None, acquired=False)
        lock.get_value = AsyncMock(return_value=None)
        service, _, _ = build_service(lock_provider=lock)
        with patch("app.services.starship_service.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ImportInProgressError):
                await service.import_starships()


if __name__ == "__main__":
    unittest.main()
