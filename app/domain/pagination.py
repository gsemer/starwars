from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PaginationParams:
    """Validated, clamped pagination input.

    Used both when a caller requests a page from the API and when a
    repository fetches a page from the database (via `LIMIT`/`OFFSET`),
    so the same clamping rules apply everywhere a page is requested.
    """

    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        """Clamps `page` to at least 1 and `page_size` to the [1, 100] range."""
        if self.page < 1:
            object.__setattr__(self, "page", 1)
        if self.page_size < 1:
            object.__setattr__(self, "page_size", 1)
        if self.page_size > 100:
            object.__setattr__(self, "page_size", 100)


@dataclass
class PageResult(Generic[T]):
    """A single page of results plus the metadata needed to render
    pagination controls (total count, current page, total pages).
    """

    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Total number of pages available for the current `page_size`."""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
