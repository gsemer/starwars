from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Character:
    """Domain entity representing a Star Wars character.

    `id` is the internal surrogate primary key used by our system.
    `swapi_id` is the external identifier extracted from the SWAPI `url`
    field (e.g. https://swapi.dev/api/people/1/ -> 1) and is used to keep
    imports idempotent.
    """

    swapi_id: int
    name: str
    height: Optional[str] = None
    mass: Optional[str] = None
    hair_color: Optional[str] = None
    skin_color: Optional[str] = None
    eye_color: Optional[str] = None
    birth_year: Optional[str] = None
    gender: Optional[str] = None
    votes: int = 0
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
