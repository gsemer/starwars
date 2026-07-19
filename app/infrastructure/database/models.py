from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String, Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

# Many-to-many association between characters and films. A unique
# constraint on (character_id, film_id) prevents duplicate associations
# from being created when concurrent imports process overlapping data.
character_film_association = Table(
    "character_films",
    Base.metadata,
    Column("character_id", UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True),
    Column("film_id", UUID(as_uuid=True), ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("character_id", "film_id", name="uq_character_film"),
)

# Many-to-many association between starships and films.
starship_film_association = Table(
    "starship_films",
    Base.metadata,
    Column("starship_id", UUID(as_uuid=True), ForeignKey("starships.id", ondelete="CASCADE"), primary_key=True),
    Column("film_id", UUID(as_uuid=True), ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("starship_id", "film_id", name="uq_starship_film"),
)


class CharacterModel(Base):
    __tablename__ = "characters"
    __table_args__ = (
        Index("ix_characters_name", "name"),
        Index("ix_characters_swapi_id", "swapi_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    swapi_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    height: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mass: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hair_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skin_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eye_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    birth_year: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    films = relationship("FilmModel", secondary=character_film_association, back_populates="characters")


class FilmModel(Base):
    __tablename__ = "films"
    __table_args__ = (
        Index("ix_films_title", "title"),
        Index("ix_films_swapi_id", "swapi_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    swapi_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    director: Mapped[str | None] = mapped_column(String(255), nullable=True)
    producer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_crawl: Mapped[str | None] = mapped_column(String, nullable=True)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    characters = relationship("CharacterModel", secondary=character_film_association, back_populates="films")
    starships = relationship("StarshipModel", secondary=starship_film_association, back_populates="films")


class StarshipModel(Base):
    __tablename__ = "starships"
    __table_args__ = (
        Index("ix_starships_name", "name"),
        Index("ix_starships_swapi_id", "swapi_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    swapi_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_in_credits: Mapped[str | None] = mapped_column(String(64), nullable=True)
    length: Mapped[str | None] = mapped_column(String(64), nullable=True)
    crew: Mapped[str | None] = mapped_column(String(64), nullable=True)
    passengers: Mapped[str | None] = mapped_column(String(64), nullable=True)
    starship_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    films = relationship("FilmModel", secondary=starship_film_association, back_populates="starships")
