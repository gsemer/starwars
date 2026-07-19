from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.film import Film
from app.domain.interfaces.film_repository import FilmRepository
from app.domain.pagination import PageResult
from app.infrastructure.database.models import FilmModel


def _to_entity(model: FilmModel) -> Film:
    """Maps a `FilmModel` ORM row to a `Film` domain entity."""
    return Film(
        id=model.id,
        swapi_id=model.swapi_id,
        title=model.title,
        episode_id=model.episode_id,
        director=model.director,
        producer=model.producer,
        release_date=model.release_date,
        opening_crawl=model.opening_crawl,
        votes=model.votes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyFilmRepository(FilmRepository):
    """PostgreSQL-backed implementation of `FilmRepository`."""

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
    ) -> PageResult[Film]:
        """See `FilmRepository.list_paginated`."""
        stmt = select(FilmModel)

        total = (await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

        stmt = stmt.order_by(FilmModel.title).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return PageResult(
            items=[_to_entity(m) for m in result.scalars().all()],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def bulk_upsert(self, films: Sequence[Film]) -> List[uuid.UUID]:
        """See `FilmRepository.bulk_upsert`."""
        if not films:
            return []

        stmt = pg_insert(FilmModel).values(
            [
                {
                    "id": f.id,
                    "swapi_id": f.swapi_id,
                    "title": f.title,
                    "episode_id": f.episode_id,
                    "director": f.director,
                    "producer": f.producer,
                    "release_date": f.release_date,
                    "opening_crawl": f.opening_crawl,
                }
                for f in films
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[FilmModel.swapi_id],
            set_={
                "title": stmt.excluded.title,
                "episode_id": stmt.excluded.episode_id,
                "director": stmt.excluded.director,
                "producer": stmt.excluded.producer,
                "release_date": stmt.excluded.release_date,
                "opening_crawl": stmt.excluded.opening_crawl,
                "updated_at": func.now(),
            },
        ).returning(FilmModel.id)

        result = await self._session.execute(stmt)
        await self._session.flush()
        self._logger.info("film_bulk_upsert count=%s", len(films))
        return [row[0] for row in result.fetchall()]

    async def increment_votes(self, film_id: uuid.UUID) -> Optional[Film]:
        """See `FilmRepository.increment_votes`."""
        result = await self._session.execute(
            update(FilmModel)
            .where(FilmModel.id == film_id)
            .values(votes=FilmModel.votes + 1)
            .returning(FilmModel)
        )
        model = result.scalar_one_or_none()
        await self._session.flush()
        return _to_entity(model) if model else None
