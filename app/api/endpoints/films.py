from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_film_service
from app.api.schemas.common import ErrorResponse, ImportResultSchema, Page, PageMeta
from app.api.schemas.film import FilmRead
from app.domain.interfaces.film_service import FilmService
from app.domain.pagination import PaginationParams

router = APIRouter(prefix="/films", tags=["films"])


@router.post(
    "/import",
    response_model=ImportResultSchema,
    summary="Import films from SWAPI",
    description=(
        "Streams all film records from SWAPI, page by page, and upserts "
        "them into the database in batches. Safe to re-run: existing "
        "films are matched and updated by `swapi_id`, never duplicated."
    ),
)
async def import_films(service: FilmService = Depends(get_film_service)) -> ImportResultSchema:
    """Triggers a full film import from SWAPI."""
    return ImportResultSchema(**(await service.import_films()).to_dict())


@router.get(
    "",
    response_model=Page[FilmRead],
    summary="List or search stored films",
    description="Returns a paginated page of stored films, optionally filtered by title.",
)
async def list_films(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    title: str | None = Query(None, description="Case-insensitive substring match on title"),
    service: FilmService = Depends(get_film_service),
) -> Page[FilmRead]:
    """Lists/searches films already stored in the database."""
    result = await service.list_films(PaginationParams(page=page, page_size=page_size), title)
    return Page[FilmRead](
        items=[FilmRead.model_validate(f) for f in result.items],
        meta=PageMeta(total=result.total, page=result.page, page_size=result.page_size, total_pages=result.total_pages),
    )


@router.post(
    "/{film_id}/vote",
    response_model=FilmRead,
    summary="Vote for a film",
    description="Increments the vote count for the film with the given id.",
    responses={404: {"model": ErrorResponse, "description": "Film not found"}},
)
async def vote_film(film_id: uuid.UUID, service: FilmService = Depends(get_film_service)) -> FilmRead:
    """Casts a vote for a film and returns it with its updated count."""
    return FilmRead.model_validate(await service.vote(film_id))
