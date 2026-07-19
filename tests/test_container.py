from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.container import Container
from app.services.character_service import CharacterServiceImpl
from app.services.film_service import FilmServiceImpl
from app.services.starship_service import StarshipServiceImpl


@pytest.mark.asyncio
async def test_container_wires_up_all_singleton_services() -> None:
    """`create_async_engine`/`httpx.AsyncClient` don't connect eagerly, so
    building a `Container` doesn't require a live database or network —
    only actually running a query/request would.
    """
    settings = Settings(database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb")

    container = Container(settings)
    try:
        assert isinstance(container.character_service, CharacterServiceImpl)
        assert isinstance(container.film_service, FilmServiceImpl)
        assert isinstance(container.starship_service, StarshipServiceImpl)
        # All three services share the same session factory and logger.
        assert container.character_service._sessionmaker is container.sessionmaker
        assert container.film_service._logger is container.logger
        assert container.starship_service._swapi_client is container.swapi_client
    finally:
        await container.dispose()
