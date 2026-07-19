from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.domain.entities.character import Character
from app.domain.exceptions import EntityNotFoundError
from app.domain.pagination import PageResult, PaginationParams
from app.services.character_service import CharacterServiceImpl
from tests.conftest import FakeSWAPIClient, make_logger, make_repository_mock, make_sessionmaker


def build_service(repo_mock, swapi_client=None, batch_size: int = 50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    service = CharacterServiceImpl(sessionmaker, swapi_client, make_logger(), batch_size=batch_size)
    return service, session


@pytest.mark.asyncio
async def test_list_characters_delegates_to_repository(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    page = PageResult(items=[Character(swapi_id=1, name="Luke")], total=1, page=1, page_size=20)
    repo_mock.list_paginated.return_value = page
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    service, _ = build_service(repo_mock)

    result = await service.list_characters(PaginationParams(page=1, page_size=20), name="luke")

    assert result is page
    repo_mock.list_paginated.assert_awaited_once_with(1, 20, "luke")


@pytest.mark.asyncio
async def test_vote_raises_when_character_missing(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.increment_votes.return_value = None
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    service, session = build_service(repo_mock)

    with pytest.raises(EntityNotFoundError):
        await service.vote(uuid.uuid4())

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_vote_commits_and_returns_updated_character(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    character = Character(swapi_id=1, name="Leia", votes=3)
    repo_mock.increment_votes.return_value = character
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    service, session = build_service(repo_mock)

    result = await service.vote(character.id)

    assert result.votes == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_characters_single_batch(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    swapi_client = FakeSWAPIClient(people=[{"name": "Luke Skywalker", "url": "https://swapi.dev/api/people/1/"}])
    service, session = build_service(repo_mock, swapi_client=swapi_client, batch_size=50)

    result = await service.import_characters()

    assert result.imported == 1
    assert result.batches == 1
    repo_mock.bulk_upsert.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_characters_splits_into_multiple_batches(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()] * 2
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    people = [{"name": f"Char {i}", "url": f"https://swapi.dev/api/people/{i}/"} for i in range(1, 6)]
    swapi_client = FakeSWAPIClient(people=people)
    service, _ = build_service(repo_mock, swapi_client=swapi_client, batch_size=2)

    result = await service.import_characters()

    assert result.batches == 3  # 2 + 2 + 1
    assert repo_mock.bulk_upsert.await_count == 3


@pytest.mark.asyncio
async def test_import_characters_links_films_when_present(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    swapi_client = FakeSWAPIClient(
        people=[
            {
                "name": "Luke Skywalker",
                "url": "https://swapi.dev/api/people/1/",
                "films": ["https://swapi.dev/api/films/1/", "https://swapi.dev/api/films/2/"],
            }
        ]
    )
    service, _ = build_service(repo_mock, swapi_client=swapi_client)

    await service.import_characters()

    repo_mock.link_films.assert_awaited_once_with({1: [1, 2]})


@pytest.mark.asyncio
async def test_import_characters_skips_link_films_when_absent(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    swapi_client = FakeSWAPIClient(people=[{"name": "Han Solo", "url": "https://swapi.dev/api/people/14/"}])
    service, _ = build_service(repo_mock, swapi_client=swapi_client)

    await service.import_characters()

    repo_mock.link_films.assert_not_called()


@pytest.mark.asyncio
async def test_import_characters_with_no_records_produces_zero_result(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    monkeypatch.setattr(
        "app.services.character_service.SQLAlchemyCharacterRepository", lambda session, logger: repo_mock
    )
    service, _ = build_service(repo_mock, swapi_client=FakeSWAPIClient(people=[]))

    result = await service.import_characters()

    assert result.imported == 0
    assert result.batches == 0
    repo_mock.bulk_upsert.assert_not_called()
