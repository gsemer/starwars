from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterRead(BaseModel):
    """API representation of a stored `Character`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    swapi_id: int
    name: str
    height: str | None = None
    mass: str | None = None
    hair_color: str | None = None
    skin_color: str | None = None
    eye_color: str | None = None
    birth_year: str | None = None
    gender: str | None = None
    votes: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
