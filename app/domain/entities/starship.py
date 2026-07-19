from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Starship:
    """Domain entity representing a Star Wars starship."""

    swapi_id: int
    name: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    cost_in_credits: Optional[str] = None
    length: Optional[str] = None
    crew: Optional[str] = None
    passengers: Optional[str] = None
    starship_class: Optional[str] = None
    votes: int = 0
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
