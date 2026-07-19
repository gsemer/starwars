from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PageMeta(BaseModel):
    """Pagination metadata accompanying a page of results."""

    total: int
    page: int
    page_size: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    """A generic page of items plus pagination metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: List[T]
    meta: PageMeta


class ErrorResponse(BaseModel):
    """Standard error response shape returned for all failed requests."""

    detail: str
    error_code: str | None = None


class ImportResultSchema(BaseModel):
    """Summary of an import operation from SWAPI."""

    resource: str
    imported: int
    batches: int
