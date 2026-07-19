from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Film:
    """Domain entity representing a Star Wars film."""

    swapi_id: int
    title: str
    episode_id: Optional[int] = None
    director: Optional[str] = None
    producer: Optional[str] = None
    release_date: Optional[date] = None
    opening_crawl: Optional[str] = None
    votes: int = 0
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
