from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.container import Container
from app.core.logging import configure_logging

OPENAPI_TAGS = [
    {"name": "characters", "description": "Import, browse, search, and vote for Star Wars characters."},
    {"name": "films", "description": "Import, browse, search, and vote for Star Wars films."},
    {"name": "starships", "description": "Import, browse, search, and vote for Star Wars starships."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Builds the `Container` (DB engine/session factory, HTTPX client,
    SWAPI client, and the three singleton services) once at startup, and
    disposes of it once at shutdown.

    The three services are stored directly on `app.state` so dependency
    functions can hand them straight to endpoints without rebuilding
    anything per request.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level)

    container = Container(settings)
    app.state.container = container
    app.state.character_service = container.character_service
    app.state.film_service = container.film_service
    app.state.starship_service = container.starship_service

    container.logger.info("application_startup")
    try:
        yield
    finally:
        container.logger.info("application_shutdown")
        await container.dispose()


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application: metadata, routes,
    and exception handlers. Does not start the DI container — that
    happens in `lifespan`, once the app actually starts serving.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "A RESTful API providing information about Star Wars characters, films, "
            "and starships, sourced from [SWAPI](https://swapi.dev/), with voting support.\n\n"
            "Each resource exposes three endpoints: **import** (fetch from SWAPI and store), "
            "**list/search** (paginated), and **vote**."
        ),
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
