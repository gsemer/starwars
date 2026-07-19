from __future__ import annotations

import logging
import uuid
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.starship import Starship
from app.domain.interfaces.starship_repository import StarshipRepository
from app.domain.pagination import PageResult
from app.infrastructure.database.models import FilmModel, StarshipModel, starship_film_association


def _to_entity(model: StarshipModel) -> Starship:
    """Maps a `StarshipModel` ORM row to a `Starship` domain entity."""
    return Starship(
        id=model.id,
        swapi_id=model.swapi_id,
        name=model.name,
        model=model.model,
        manufacturer=model.manufacturer,
        cost_in_credits=model.cost_in_credits,
        length=model.length,
        crew=model.crew,
        passengers=model.passengers,
        starship_class=model.starship_class,
        votes=model.votes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyStarshipRepository(StarshipRepository):
    """PostgreSQL-backed implementation of `StarshipRepository`."""

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
    ) -> PageResult[Starship]:
        """See `StarshipRepository.list_paginated`."""
        stmt = select(StarshipModel)

        total = (await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

        stmt = stmt.order_by(StarshipModel.name).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return PageResult(
            items=[_to_entity(m) for m in result.scalars().all()],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def bulk_upsert(self, starships: Sequence[Starship]) -> List[uuid.UUID]:
        """See `StarshipRepository.bulk_upsert`."""
        if not starships:
            return []

        stmt = pg_insert(StarshipModel).values(
            [
                {
                    "id": s.id,
                    "swapi_id": s.swapi_id,
                    "name": s.name,
                    "model": s.model,
                    "manufacturer": s.manufacturer,
                    "cost_in_credits": s.cost_in_credits,
                    "length": s.length,
                    "crew": s.crew,
                    "passengers": s.passengers,
                    "starship_class": s.starship_class,
                }
                for s in starships
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[StarshipModel.swapi_id],
            set_={
                "name": stmt.excluded.name,
                "model": stmt.excluded.model,
                "manufacturer": stmt.excluded.manufacturer,
                "cost_in_credits": stmt.excluded.cost_in_credits,
                "length": stmt.excluded.length,
                "crew": stmt.excluded.crew,
                "passengers": stmt.excluded.passengers,
                "starship_class": stmt.excluded.starship_class,
                "updated_at": func.now(),
            },
        ).returning(StarshipModel.id)

        result = await self._session.execute(stmt)
        await self._session.flush()
        self._logger.info("starship_bulk_upsert count=%s", len(starships))
        return [row[0] for row in result.fetchall()]

    async def link_films(self, swapi_id_to_film_swapi_ids: dict[int, Iterable[int]]) -> None:
        """See `StarshipRepository.link_films`."""
        if not swapi_id_to_film_swapi_ids:
            return

        ship_swapi_to_id = {
            row.swapi_id: row.id
            for row in (
                await self._session.execute(
                    select(StarshipModel.id, StarshipModel.swapi_id).where(
                        StarshipModel.swapi_id.in_(swapi_id_to_film_swapi_ids.keys())
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
            {"starship_id": ship_swapi_to_id[ship_swapi_id], "film_id": film_swapi_to_id[film_swapi_id]}
            for ship_swapi_id, film_swapi_ids in swapi_id_to_film_swapi_ids.items()
            if ship_swapi_id in ship_swapi_to_id
            for film_swapi_id in film_swapi_ids
            if film_swapi_id in film_swapi_to_id
        ]
        if not association_rows:
            return

        await self._session.execute(
            pg_insert(starship_film_association)
            .values(association_rows)
            .on_conflict_do_nothing(index_elements=["starship_id", "film_id"])
        )
        await self._session.flush()

    async def increment_votes(self, starship_id: uuid.UUID) -> Optional[Starship]:
        """See `StarshipRepository.increment_votes`."""
        result = await self._session.execute(
            update(StarshipModel)
            .where(StarshipModel.id == starship_id)
            .values(votes=StarshipModel.votes + 1)
            .returning(StarshipModel)
        )
        model = result.scalar_one_or_none()
        await self._session.flush()
        return _to_entity(model) if model else None
