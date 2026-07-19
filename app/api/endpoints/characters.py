from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_character_service
from app.api.schemas.character import CharacterRead
from app.api.schemas.common import ErrorResponse, ImportResultSchema, Page, PageMeta
from app.domain.interfaces.character_service import CharacterService
from app.domain.pagination import PaginationParams

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post(
    "/import",
    response_model=ImportResultSchema,
    summary="Import characters from SWAPI",
    description=(
        "Streams all character records from SWAPI, page by page, and "
        "upserts them into the database in batches. Safe to re-run: "
        "existing characters are matched and updated by `swapi_id`, "
        "never duplicated. Import films first so film associations can "
        "be linked."
    ),
)
async def import_characters(
    service: CharacterService = Depends(get_character_service),
) -> ImportResultSchema:
    """Triggers a full character import from SWAPI."""
    return ImportResultSchema(**(await service.import_characters()).to_dict())


@router.get(
    "",
    response_model=Page[CharacterRead],
    summary="List or search stored characters",
    description="Returns a paginated page of stored characters, optionally filtered by name.",
)
async def list_characters(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    service: CharacterService = Depends(get_character_service),
) -> Page[CharacterRead]:
    """Lists/searches characters already stored in the database."""
    result = await service.list_characters(PaginationParams(page=page, page_size=page_size))
    return Page[CharacterRead](
        items=[CharacterRead.model_validate(c) for c in result.items],
        meta=PageMeta(total=result.total, page=result.page, page_size=result.page_size, total_pages=result.total_pages),
    )


@router.post(
    "/{character_id}/vote",
    response_model=CharacterRead,
    summary="Vote for a character",
    description="Increments the vote count for the character with the given id.",
    responses={404: {"model": ErrorResponse, "description": "Character not found"}},
)
async def vote_character(
    character_id: uuid.UUID, service: CharacterService = Depends(get_character_service)
) -> CharacterRead:
    """Casts a vote for a character and returns it with its updated count."""
    return CharacterRead.model_validate(await service.vote(character_id))
