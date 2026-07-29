"""Async engine and session-factory construction.

One engine per application instance, created in the factory (lazily — no
connection happens until first use) and disposed in the lifespan shutdown.
The engine owns the connection pool; nothing else in the codebase may open a
database connection any other way.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from intelliai_api.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    db = settings.database
    return create_async_engine(
        db.url.get_secret_value(),
        pool_size=db.pool_size,
        max_overflow=db.pool_max_overflow,
        pool_pre_ping=True,  # dead connections are detected, not served
        echo=db.echo,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: committed objects stay usable for response
    # serialization without surprise re-loading queries.
    return async_sessionmaker(engine, expire_on_commit=False)
