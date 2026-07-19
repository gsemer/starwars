from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StarshipRead(BaseModel):
    """API representation of a stored `Starship`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    swapi_id: int
    name: str
    model: str | None = None
    manufacturer: str | None = None
    cost_in_credits: str | None = None
    length: str | None = None
    crew: str | None = None
    passengers: str | None = None
    starship_class: str | None = None
    votes: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
