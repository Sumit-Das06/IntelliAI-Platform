"""Shared test helpers (not collected as tests)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.main import create_app


@asynccontextmanager
async def client_with_db(
    settings: Settings,
    db_engine: AsyncEngine,
    configure: Callable[[FastAPI], None] | None = None,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    """The real app over in-process HTTP, its sessions joined to one
    rolled-back transaction: full-stack tests, zero database residue.

    ``configure`` runs after the factory builds the app — tests use it to
    swap factory-built collaborators (e.g. fake runtime clients)."""
    async with db_engine.connect() as connection:
        outer = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        app = create_app(settings)
        app.state.session_factory = factory
        if configure is not None:
            configure(app)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory
        await outer.rollback()
