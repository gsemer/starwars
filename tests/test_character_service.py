from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from app.domain.entities.character import Character
from app.domain.exceptions import EntityNotFoundError, ImportInProgressError
from app.domain.import_result import ImportResult
from app.domain.pagination import PageResult, PaginationParams
from app.services.character_service import CharacterServiceImpl
from tests.support import (
    FakeSWAPIClient,
    make_lock_provider,
    make_logger,
    make_repository_mock,
    make_sessionmaker,
)

REPO_PATH = "app.services.character_service.SQLAlchemyCharacterRepository"


def build_service(swapi_client=None, lock_provider=None, batch_size=50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    lock_provider = lock_provider or make_lock_provider()
    service = CharacterServiceImpl(
        sessionmaker, swapi_client, make_logger(), lock_provider,
        lock_ttl=300, cache_ttl=60, batch_size=batch_size,
    )
    return service, session, lock_provider


class ListAndVoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_characters_delegates_to_repository(self) -> None:
        repo = make_repository_mock()
        page = PageResult(items=[Character(swapi_id=1, name="Luke")], total=1, page=1, page_size=20)
        repo.list_paginated.return_value = page
        service, _, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.list_characters(PaginationParams(page=1, page_size=20))
        self.assertIs(result, page)
        repo.list_paginated.assert_awaited_once_with(1, 20)

    async def test_vote_raises_when_character_missing(self) -> None:
        repo = make_repository_mock()
        repo.increment_votes.return_value = None
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            with self.assertRaises(EntityNotFoundError):
                await service.vote(uuid.uuid4())
        session.commit.assert_not_awaited()

    async def test_vote_commits_and_returns_updated_character(self) -> None:
        repo = make_repository_mock()
        character = Character(swapi_id=1, name="Leia", votes=3)
        repo.increment_votes.return_value = character
        service, session, _ = build_service()
        with patch(REPO_PATH, return_value=repo):
            result = await service.vote(character.id)
        self.assertEqual(result.votes, 3)
        session.commit.assert_awaited_once()


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_returns_cached_result_without_locking(self) -> None:
        cached = json.dumps({"resource": "characters", "imported": 9, "batches": 1})
        lock = make_lock_provider(cached=cached)
        service, _, _ = build_service(lock_provider=lock)
        result = await service.import_characters()
        self.assertEqual(result.imported, 9)
        lock.acquire.assert_not_awaited()

    async def test_import_single_batch_when_lock_acquired(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(people=[{"name": "Luke", "url": "https://swapi.dev/api/people/1/"}])
        lock = make_lock_provider(cached=None, acquired=True)
        service, session, _ = build_service(swapi_client=swapi, lock_provider=lock)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_characters()
        self.assertEqual(result.imported, 1)
        self.assertEqual(result.batches, 1)
        lock.set_value.assert_awaited_once()
        lock.release.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_import_splits_into_multiple_batches(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4(), uuid.uuid4()]
        people = [{"name": f"C{i}", "url": f"https://swapi.dev/api/people/{i}/"} for i in range(1, 6)]
        service, _, _ = build_service(swapi_client=FakeSWAPIClient(people=people), batch_size=2)
        with patch(REPO_PATH, return_value=repo):
            result = await service.import_characters()
        self.assertEqual(result.batches, 3)
        self.assertEqual(repo.bulk_upsert.await_count, 3)

    async def test_import_links_films_when_present(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(people=[{
            "name": "Luke", "url": "https://swapi.dev/api/people/1/",
            "films": ["https://swapi.dev/api/films/1/", "https://swapi.dev/api/films/2/"],
        }])
        service, _, _ = build_service(swapi_client=swapi)
        with patch(REPO_PATH, return_value=repo):
            await service.import_characters()
        repo.link_films.assert_awaited_once_with({1: [1, 2]})

    async def test_import_skips_link_films_when_absent(self) -> None:
        repo = make_repository_mock()
        repo.bulk_upsert.return_value = [uuid.uuid4()]
        swapi = FakeSWAPIClient(people=[{"name": "Han", "url": "https://swapi.dev/api/people/14/"}])
        service, _, _ = build_service(swapi_client=swapi)
        with patch(REPO_PATH, return_value=repo):
            await service.import_characters()
        repo.link_films.assert_not_called()

    async def test_import_waits_then_reads_cache_when_lock_contended(self) -> None:
        cached = json.dumps({"resource": "characters", "imported": 9, "batches": 1})
        lock = make_lock_provider(cached=None, acquired=False)
        lock.get_value = AsyncMock(side_effect=[None, cached])
        service, _, _ = build_service(lock_provider=lock)
        with patch("app.services.character_service.asyncio.sleep", new=AsyncMock()):
            result = await service.import_characters()
        self.assertEqual(result.imported, 9)

    async def test_import_times_out_when_lock_never_frees(self) -> None:
        lock = make_lock_provider(cached=None, acquired=False)
        lock.get_value = AsyncMock(return_value=None)
        service, _, _ = build_service(lock_provider=lock)
        with patch("app.services.character_service.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ImportInProgressError):
                await service.import_characters()


if __name__ == "__main__":
    unittest.main()
