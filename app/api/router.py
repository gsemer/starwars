from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import characters, films, starships

api_router = APIRouter()
"""Aggregates all resource routers into a single router mounted by `app.main`."""

api_router.include_router(characters.router)
api_router.include_router(films.router)
api_router.include_router(starships.router)
