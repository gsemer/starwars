from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_starship_service
from app.api.schemas.common import ErrorResponse, ImportResultSchema, Page, PageMeta
from app.api.schemas.starship import StarshipRead
from app.domain.interfaces.starship_service import StarshipService
from app.domain.pagination import PaginationParams

router = APIRouter(prefix="/starships", tags=["starships"])


@router.post(
    "/import",
    response_model=ImportResultSchema,
    summary="Import starships from SWAPI",
    description=(
        "Streams all starship records from SWAPI, page by page, and "
        "upserts them into the database in batches. Safe to re-run: "
        "existing starships are matched and updated by `swapi_id`, never "
        "duplicated. Import films first so film associations can be "
        "linked."
    ),
)
async def import_starships(
    service: StarshipService = Depends(get_starship_service),
) -> ImportResultSchema:
    """Triggers a full starship import from SWAPI."""
    return ImportResultSchema(**(await service.import_starships()).to_dict())


@router.get(
    "",
    response_model=Page[StarshipRead],
    summary="List or search stored starships",
    description="Returns a paginated page of stored starships, optionally filtered by name.",
)
async def list_starships(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    service: StarshipService = Depends(get_starship_service),
) -> Page[StarshipRead]:
    """Lists/searches starships already stored in the database."""
    result = await service.list_starships(PaginationParams(page=page, page_size=page_size))
    return Page[StarshipRead](
        items=[StarshipRead.model_validate(s) for s in result.items],
        meta=PageMeta(total=result.total, page=result.page, page_size=result.page_size, total_pages=result.total_pages),
    )


@router.post(
    "/{starship_id}/vote",
    response_model=StarshipRead,
    summary="Vote for a starship",
    description="Increments the vote count for the starship with the given id.",
    responses={404: {"model": ErrorResponse, "description": "Starship not found"}},
)
async def vote_starship(
    starship_id: uuid.UUID, service: StarshipService = Depends(get_starship_service)
) -> StarshipRead:
    """Casts a vote for a starship and returns it with its updated count."""
    return StarshipRead.model_validate(await service.vote(starship_id))
