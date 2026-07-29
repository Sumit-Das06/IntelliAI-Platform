"""Alembic environment: async engine, settings-driven URL, metadata-aware.

The URL comes from the application's validated Settings (env vars / .env),
never from alembic.ini — one source of configuration truth. Autogenerate
diffs against ``Base.metadata``, so any model imported into the metadata is
seen by ``make migration``.
"""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from intelliai_api.core.config import get_settings
from intelliai_api.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return get_settings().database.url.get_secret_value()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing (``alembic upgrade head --sql``).

    Used for DBA review of production migrations before they run.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # detect column type changes, not just add/drop
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
