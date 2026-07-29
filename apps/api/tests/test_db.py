"""Persistence integration tests — run against the real compose Postgres.

Per our testing strategy there is no SQLite stand-in: dialect behavior
(timestamptz, JSONB, SKIP LOCKED) must be tested against the engine we ship
on. When infrastructure is not running, these tests skip with a clear
message instead of failing.
"""

import pytest
from sqlalchemy import text

from intelliai_api.core.config import Settings
from intelliai_api.db.engine import create_engine, create_session_factory

pytestmark = pytest.mark.anyio


@pytest.fixture()
async def engine():
    settings = Settings()  # real .env → the compose Postgres
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("requires running infrastructure (make up)")
    yield engine
    await engine.dispose()


async def test_pooled_connection_round_trip(engine) -> None:
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1


async def test_commit_persists_and_rollback_discards(engine) -> None:
    factory = create_session_factory(engine)

    async with factory() as session:
        await session.execute(
            text("CREATE TABLE IF NOT EXISTS _step7_tx_probe (id int)")
        )
        await session.commit()

    # Rolled-back insert must leave no trace.
    async with factory() as session:
        await session.execute(text("INSERT INTO _step7_tx_probe VALUES (1)"))
        await session.rollback()

    async with factory() as session:
        count = (
            await session.execute(text("SELECT count(*) FROM _step7_tx_probe"))
        ).scalar_one()
        await session.execute(text("DROP TABLE _step7_tx_probe"))
        await session.commit()

    assert count == 0


async def test_migration_pipeline_has_run(engine) -> None:
    """`make migrate` must have stamped the database (alembic_version)."""
    async with engine.connect() as conn:
        version = (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
    assert version is not None
