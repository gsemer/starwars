from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.domain.entities.film import Film
from app.domain.exceptions import EntityNotFoundError
from app.domain.pagination import PageResult, PaginationParams
from app.services.film_service import FilmServiceImpl, _parse_release_date
from tests.conftest import FakeSWAPIClient, make_logger, make_repository_mock, make_sessionmaker


def build_service(repo_mock, swapi_client=None, batch_size: int = 50):
    session = AsyncMock()
    sessionmaker = make_sessionmaker(session)
    swapi_client = swapi_client or FakeSWAPIClient()
    service = FilmServiceImpl(sessionmaker, swapi_client, make_logger(), batch_size=batch_size)
    return service, session


@pytest.mark.asyncio
async def test_list_films_delegates_to_repository(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    page = PageResult(items=[Film(swapi_id=1, title="A New Hope")], total=1, page=1, page_size=20)
    repo_mock.list_paginated.return_value = page
    monkeypatch.setattr("app.services.film_service.SQLAlchemyFilmRepository", lambda session, logger: repo_mock)
    service, _ = build_service(repo_mock)

    result = await service.list_films(PaginationParams(page=1, page_size=20), title="hope")

    assert result is page
    repo_mock.list_paginated.assert_awaited_once_with(1, 20, "hope")


@pytest.mark.asyncio
async def test_vote_raises_when_film_missing(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.increment_votes.return_value = None
    monkeypatch.setattr("app.services.film_service.SQLAlchemyFilmRepository", lambda session, logger: repo_mock)
    service, session = build_service(repo_mock)

    with pytest.raises(EntityNotFoundError):
        await service.vote(uuid.uuid4())

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_vote_commits_and_returns_updated_film(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    film = Film(swapi_id=1, title="Return of the Jedi", votes=7)
    repo_mock.increment_votes.return_value = film
    monkeypatch.setattr("app.services.film_service.SQLAlchemyFilmRepository", lambda session, logger: repo_mock)
    service, session = build_service(repo_mock)

    result = await service.vote(film.id)

    assert result.votes == 7
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_films_single_batch(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()]
    monkeypatch.setattr("app.services.film_service.SQLAlchemyFilmRepository", lambda session, logger: repo_mock)
    swapi_client = FakeSWAPIClient(
        films=[
            {
                "title": "A New Hope",
                "url": "https://swapi.dev/api/films/1/",
                "episode_id": 4,
                "release_date": "1977-05-25",
            }
        ]
    )
    service, session = build_service(repo_mock, swapi_client=swapi_client)

    result = await service.import_films()

    assert result.imported == 1
    assert result.batches == 1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_films_splits_into_multiple_batches(monkeypatch) -> None:
    repo_mock = make_repository_mock()
    repo_mock.bulk_upsert.return_value = [uuid.uuid4()] * 2
    monkeypatch.setattr("app.services.film_service.SQLAlchemyFilmRepository", lambda session, logger: repo_mock)
    films = [{"title": f"Film {i}", "url": f"https://swapi.dev/api/films/{i}/"} for i in range(1, 8)]
    service, _ = build_service(repo_mock, swapi_client=FakeSWAPIClient(films=films), batch_size=3)

    result = await service.import_films()

    assert result.batches == 3  # 3 + 3 + 1
    assert repo_mock.bulk_upsert.await_count == 3


def test_parse_release_date_valid() -> None:
    result = _parse_release_date("1977-05-25")
    assert result is not None
    assert (result.year, result.month, result.day) == (1977, 5, 25)


def test_parse_release_date_invalid_returns_none() -> None:
    assert _parse_release_date("not-a-date") is None


def test_parse_release_date_none_returns_none() -> None:
    assert _parse_release_date(None) is None


def test_parse_release_date_non_string_returns_none() -> None:
    assert _parse_release_date(12345) is None
