from __future__ import annotations

import logging
import uuid
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.character import Character
from app.domain.interfaces.character_repository import CharacterRepository
from app.domain.pagination import PageResult
from app.infrastructure.database.models import CharacterModel, FilmModel, character_film_association


def _to_entity(model: CharacterModel) -> Character:
    """Maps a `CharacterModel` ORM row to a `Character` domain entity."""
    return Character(
        id=model.id,
        swapi_id=model.swapi_id,
        name=model.name,
        height=model.height,
        mass=model.mass,
        hair_color=model.hair_color,
        skin_color=model.skin_color,
        eye_color=model.eye_color,
        birth_year=model.birth_year,
        gender=model.gender,
        votes=model.votes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyCharacterRepository(CharacterRepository):
    """PostgreSQL-backed implementation of `CharacterRepository`.

    Uses `INSERT ... ON CONFLICT (swapi_id) DO UPDATE` for imports so that
    concurrent import jobs never create duplicate rows and never need a
    racy "check-then-insert".
    """

    def __init__(self, session: AsyncSession, logger: logging.Logger) -> None:
        """
        Args:
            session: The active DB session this repository operates on.
            logger: Shared application logger.
        """
        self._session = session
        self._logger = logger

    async def list_paginated(
        self, page: int, page_size: int
    ) -> PageResult[Character]:
        """See `CharacterRepository.list_paginated`."""
        stmt = select(CharacterModel)

        total = (await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

        stmt = stmt.order_by(CharacterModel.name).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        
        items=[_to_entity(m) for m in result.scalars().all()]
        self._logger.info("character_list_paginated count=%s", len(items))
        
        return PageResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def bulk_upsert(self, characters: Sequence[Character]) -> List[uuid.UUID]:
        """See `CharacterRepository.bulk_upsert`."""
        if not characters:
            return []

        stmt = pg_insert(CharacterModel).values(
            [
                {
                    "id": c.id,
                    "swapi_id": c.swapi_id,
                    "name": c.name,
                    "height": c.height,
                    "mass": c.mass,
                    "hair_color": c.hair_color,
                    "skin_color": c.skin_color,
                    "eye_color": c.eye_color,
                    "birth_year": c.birth_year,
                    "gender": c.gender,
                }
                for c in characters
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CharacterModel.swapi_id],
            set_={
                "name": stmt.excluded.name,
                "height": stmt.excluded.height,
                "mass": stmt.excluded.mass,
                "hair_color": stmt.excluded.hair_color,
                "skin_color": stmt.excluded.skin_color,
                "eye_color": stmt.excluded.eye_color,
                "birth_year": stmt.excluded.birth_year,
                "gender": stmt.excluded.gender,
                "updated_at": func.now(),
            },
        ).returning(CharacterModel.id)

        result = await self._session.execute(stmt)
        await self._session.flush()
        self._logger.info("character_bulk_upsert count=%s", len(characters))
        return [row[0] for row in result.fetchall()]

    async def link_films(self, swapi_id_to_film_swapi_ids: dict[int, Iterable[int]]) -> None:
        """See `CharacterRepository.link_films`."""
        if not swapi_id_to_film_swapi_ids:
            return

        char_swapi_to_id = {
            row.swapi_id: row.id
            for row in (
                await self._session.execute(
                    select(CharacterModel.id, CharacterModel.swapi_id).where(
                        CharacterModel.swapi_id.in_(swapi_id_to_film_swapi_ids.keys())
                    )
                )
            ).all()
        }

        all_film_swapi_ids = {fid for fids in swapi_id_to_film_swapi_ids.values() for fid in fids}
        if not all_film_swapi_ids:
            return

        film_swapi_to_id = {
            row.swapi_id: row.id
            for row in (
                await self._session.execute(
                    select(FilmModel.id, FilmModel.swapi_id).where(FilmModel.swapi_id.in_(all_film_swapi_ids))
                )
            ).all()
        }

        association_rows = [
            {"character_id": char_swapi_to_id[char_swapi_id], "film_id": film_swapi_to_id[film_swapi_id]}
            for char_swapi_id, film_swapi_ids in swapi_id_to_film_swapi_ids.items()
            if char_swapi_id in char_swapi_to_id
            for film_swapi_id in film_swapi_ids
            if film_swapi_id in film_swapi_to_id
        ]
        if not association_rows:
            return

        await self._session.execute(
            pg_insert(character_film_association)
            .values(association_rows)
            .on_conflict_do_nothing(index_elements=["character_id", "film_id"])
        )
        await self._session.flush()

    async def increment_votes(self, character_id: uuid.UUID) -> Optional[Character]:
        """See `CharacterRepository.increment_votes`."""
        result = await self._session.execute(
            update(CharacterModel)
            .where(CharacterModel.id == character_id)
            .values(votes=CharacterModel.votes + 1)
            .returning(CharacterModel)
        )
        model = result.scalar_one_or_none()
        await self._session.flush()
        return _to_entity(model) if model else None
