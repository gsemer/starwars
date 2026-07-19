from __future__ import annotations

from fastapi import Request

from app.domain.interfaces.character_service import CharacterService
from app.domain.interfaces.film_service import FilmService
from app.domain.interfaces.starship_service import StarshipService


def get_character_service(request: Request) -> CharacterService:
    """Returns the singleton `CharacterService`, created once at startup
    by `Container` and stored on `app.state.character_service`. Never
    constructs a new instance per request.
    """
    return request.app.state.character_service


def get_film_service(request: Request) -> FilmService:
    """Returns the singleton `FilmService`, created once at startup by
    `Container` and stored on `app.state.film_service`. Never constructs
    a new instance per request.
    """
    return request.app.state.film_service


def get_starship_service(request: Request) -> StarshipService:
    """Returns the singleton `StarshipService`, created once at startup
    by `Container` and stored on `app.state.starship_service`. Never
    constructs a new instance per request.
    """
    return request.app.state.starship_service
