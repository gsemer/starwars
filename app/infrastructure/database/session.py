from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings


def create_engine_and_sessionmaker(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker]:
    """Creates the async engine and session factory once at startup.

    The returned session factory is owned by the `Container` and handed
    to each service, which opens/commits/closes its own sessions
    internally per call — there's no per-request session dependency or
    extra wrapper class around it.

    Args:
        settings: Application settings, providing the DB connection URL.

    Returns:
        A tuple of `(engine, sessionmaker)`.
    """
    engine = create_async_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return engine, sessionmaker
