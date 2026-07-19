from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.entities.character import Character
from app.domain.entities.film import Film
from app.domain.entities.starship import Starship
from app.infrastructure.repositories.sqlalchemy_character_repository import (
    SQLAlchemyCharacterRepository,
)
from app.infrastructure.repositories.sqlalchemy_film_repository import SQLAlchemyFilmRepository
from app.infrastructure.repositories.sqlalchemy_starship_repository import (
    SQLAlchemyStarshipRepository,
)
from tests.conftest import make_logger


def make_execute_result(scalar_one_or_none=None, scalars_all=None, scalar_one=None, all_rows=None, fetchall=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar_one.return_value = scalar_one
    result.all.return_value = all_rows or []
    result.fetchall.return_value = fetchall or []
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_all or []
    result.scalars.return_value = scalars_mock
    return result


def make_model(**overrides) -> MagicMock:
    model = MagicMock()
    for key, value in overrides.items():
        setattr(model, key, value)
    return model


# --- CharacterRepository ---------------------------------------------------


@pytest.mark.asyncio
async def test_character_list_paginated_maps_and_wraps_in_page_result() -> None:
    model = make_model(
        id=uuid.uuid4(), swapi_id=1, name="Luke", height="172", mass="77", hair_color="blond",
        skin_color="fair", eye_color="blue", birth_year="19BBY", gender="male", votes=0,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.side_effect = [make_execute_result(scalar_one=1), make_execute_result(scalars_all=[model])]
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    page = await repo.list_paginated(page=1, page_size=20)

    assert page.total == 1
    assert page.items[0].name == "Luke"


@pytest.mark.asyncio
async def test_character_bulk_upsert_empty_list_short_circuits() -> None:
    session = AsyncMock()
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    result = await repo.bulk_upsert([])

    assert result == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_character_bulk_upsert_returns_ids() -> None:
    session = AsyncMock()
    new_id = uuid.uuid4()
    session.execute.return_value = make_execute_result(fetchall=[(new_id,)])
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    result = await repo.bulk_upsert([Character(swapi_id=1, name="Han Solo")])

    assert result == [new_id]
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_character_link_films_empty_mapping_short_circuits() -> None:
    session = AsyncMock()
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    await repo.link_films({})

    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_character_link_films_skips_unresolved_films() -> None:
    session = AsyncMock()
    char_id = uuid.uuid4()
    session.execute.side_effect = [
        make_execute_result(all_rows=[make_model(swapi_id=1, id=char_id)]),
        make_execute_result(all_rows=[]),  # no matching film found
    ]
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    await repo.link_films({1: [99]})

    assert session.execute.await_count == 2  # only the two lookups, no association insert


@pytest.mark.asyncio
async def test_character_increment_votes_returns_none_when_missing() -> None:
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    assert await repo.increment_votes(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_character_increment_votes_returns_updated_entity() -> None:
    model = make_model(
        id=uuid.uuid4(), swapi_id=1, name="Leia", height=None, mass=None, hair_color=None,
        skin_color=None, eye_color=None, birth_year=None, gender=None, votes=4,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=model)
    repo = SQLAlchemyCharacterRepository(session, make_logger())

    result = await repo.increment_votes(model.id)

    assert result.votes == 4


# --- FilmRepository ---------------------------------------------------------


@pytest.mark.asyncio
async def test_film_list_paginated_maps_results() -> None:
    model = make_model(
        id=uuid.uuid4(), swapi_id=1, title="A New Hope", episode_id=4, director="George Lucas",
        producer="Gary Kurtz", release_date=None, opening_crawl="...", votes=0,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.side_effect = [make_execute_result(scalar_one=1), make_execute_result(scalars_all=[model])]
    repo = SQLAlchemyFilmRepository(session, make_logger())

    page = await repo.list_paginated(1, 10, "hope")

    assert page.total == 1
    assert page.items[0].title == "A New Hope"


@pytest.mark.asyncio
async def test_film_bulk_upsert_empty_list_short_circuits() -> None:
    session = AsyncMock()
    repo = SQLAlchemyFilmRepository(session, make_logger())

    result = await repo.bulk_upsert([])

    assert result == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_film_increment_votes_returns_none_when_missing() -> None:
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    repo = SQLAlchemyFilmRepository(session, make_logger())

    assert await repo.increment_votes(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_film_increment_votes_returns_updated_entity() -> None:
    model = make_model(
        id=uuid.uuid4(), swapi_id=1, title="Empire Strikes Back", episode_id=5, director=None,
        producer=None, release_date=None, opening_crawl=None, votes=9,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=model)
    repo = SQLAlchemyFilmRepository(session, make_logger())

    result = await repo.increment_votes(model.id)

    assert result.votes == 9


@pytest.mark.asyncio
async def test_film_bulk_upsert_returns_ids() -> None:
    session = AsyncMock()
    new_id = uuid.uuid4()
    session.execute.return_value = make_execute_result(fetchall=[(new_id,)])
    repo = SQLAlchemyFilmRepository(session, make_logger())

    result = await repo.bulk_upsert([Film(swapi_id=1, title="A New Hope")])

    assert result == [new_id]
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_film_list_paginated_without_name_filter() -> None:
    session = AsyncMock()
    session.execute.side_effect = [make_execute_result(scalar_one=0), make_execute_result(scalars_all=[])]
    repo = SQLAlchemyFilmRepository(session, make_logger())

    page = await repo.list_paginated(1, 10)

    assert page.items == []
    assert page.total == 0


# --- StarshipRepository ------------------------------------------------------


@pytest.mark.asyncio
async def test_starship_list_paginated_maps_results() -> None:
    model = make_model(
        id=uuid.uuid4(), swapi_id=9, name="Millennium Falcon", model="YT-1300",
        manufacturer="Corellian Engineering Corporation", cost_in_credits="100000", length="34.37",
        crew="4", passengers="6", starship_class="Light freighter", votes=0,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.side_effect = [make_execute_result(scalar_one=1), make_execute_result(scalars_all=[model])]
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    page = await repo.list_paginated(1, 20)

    assert page.total == 1
    assert page.items[0].name == "Millennium Falcon"


@pytest.mark.asyncio
async def test_starship_bulk_upsert_empty_list_short_circuits() -> None:
    session = AsyncMock()
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    result = await repo.bulk_upsert([])

    assert result == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_starship_link_films_empty_mapping_short_circuits() -> None:
    session = AsyncMock()
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    await repo.link_films({})

    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_starship_bulk_upsert_returns_ids() -> None:
    session = AsyncMock()
    new_id = uuid.uuid4()
    session.execute.return_value = make_execute_result(fetchall=[(new_id,)])
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    result = await repo.bulk_upsert([Starship(swapi_id=9, name="X-wing")])

    assert result == [new_id]
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_starship_link_films_creates_associations() -> None:
    session = AsyncMock()
    ship_id = uuid.uuid4()
    film_id = uuid.uuid4()
    session.execute.side_effect = [
        make_execute_result(all_rows=[make_model(swapi_id=9, id=ship_id)]),
        make_execute_result(all_rows=[make_model(swapi_id=1, id=film_id)]),
        make_execute_result(),  # the association insert itself
    ]
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    await repo.link_films({9: [1]})

    assert session.execute.await_count == 3
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_starship_link_films_no_matching_films_short_circuits_before_insert() -> None:
    session = AsyncMock()
    ship_id = uuid.uuid4()
    session.execute.side_effect = [
        make_execute_result(all_rows=[make_model(swapi_id=9, id=ship_id)]),
        make_execute_result(all_rows=[]),
    ]
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    await repo.link_films({9: [999]})

    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_starship_increment_votes_returns_none_when_missing() -> None:
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    assert await repo.increment_votes(uuid.uuid4()) is None
    model = make_model(
        id=uuid.uuid4(), swapi_id=9, name="X-wing", model=None, manufacturer=None,
        cost_in_credits=None, length=None, crew=None, passengers=None, starship_class=None, votes=2,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute.return_value = make_execute_result(scalar_one_or_none=model)
    repo = SQLAlchemyStarshipRepository(session, make_logger())

    result = await repo.increment_votes(model.id)

    assert result.votes == 2
