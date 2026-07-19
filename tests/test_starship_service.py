from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.domain.entities.starship import Starship
from app.domain.exceptions import EntityNotFoundError
from app.domain.pagination import PageResult, PaginationParams
from app.services.starship_service import StarshipServiceImpl
from tests.conftest import FakeSWAPIClient, make_logger, make_repository_mock, make_sessionmaker


def build_service(repo_mock, swapi_client=None, batch_size: int = 50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    service = StarshipServiceImpl(sessionmaker, swapi_client, make_logger(), batch_size=batch_size)
    return service, session


@pytest.mark.asyncio
async def test_list_starships_delegates_to_repository(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    page = PageResult(items=[Starship(swapi_id=9, name="Millennium Falcon")], total=1, page=1, page_size=20)
    repo_mock.list_paginated.return_value = page
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    service, _ = build_service(repo_mock)

    result = await service.list_starships(PaginationParams(page=1, page_size=20), name="falcon")

    assert result is page
    repo_mock.list_paginated.assert_awaited_once_with(1, 20, "falcon")


@pytest.mark.asyncio
async def test_vote_raises_when_starship_missing(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.increment_votes.return_value = None
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    service, session = build_service(repo_mock)

    with pytest.raises(EntityNotFoundError):
        await service.vote(uuid.uuid4())

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_vote_commits_and_returns_updated_starship(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    starship = Starship(swapi_id=9, name="X-wing", votes=2)
    repo_mock.increment_votes.return_value = starship
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    service, session = build_service(repo_mock)

    result = await service.vote(starship.id)

    assert result.votes == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_starships_single_batch(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    swapi_client = FakeSWAPIClient(starships=[{"name": "TIE Fighter", "url": "https://swapi.dev/api/starships/13/"}])
    service, session = build_service(repo_mock, swapi_client=swapi_client)

    result = await service.import_starships()

    assert result.imported == 1
    assert result.batches == 1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_starships_links_films_when_present(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    swapi_client = FakeSWAPIClient(
        starships=[
            {
                "name": "X-wing",
                "url": "https://swapi.dev/api/starships/12/",
                "films": ["https://swapi.dev/api/films/1/"],
            }
        ]
    )
    service, _ = build_service(repo_mock, swapi_client=swapi_client)

    await service.import_starships()

    repo_mock.link_films.assert_awaited_once_with({12: [1]})


@pytest.mark.asyncio
async def test_import_starships_splits_into_multiple_batches(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr(
        "app.services.starship_service.SQLAlchemyStarshipRepository", lambda session, logger: repo_mock
    )
    starships = [{"name": f"Ship {i}", "url": f"https://swapi.dev/api/starships/{i}/"} for i in range(1, 5)]
    service, _ = build_service(repo_mock, swapi_client=FakeSWAPIClient(starships=starships), batch_size=2)

    result = await service.import_starships()

    assert result.batches == 2
    assert repo_mock.bulk_upsert.await_count == 2
