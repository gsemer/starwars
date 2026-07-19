from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FilmRead(BaseModel):
    """API representation of a stored `Film`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    swapi_id: int
    title: str
    episode_id: int | None = None
    director: str | None = None
    producer: str | None = None
    release_date: date | None = None
    opening_crawl: str | None = None
    votes: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
