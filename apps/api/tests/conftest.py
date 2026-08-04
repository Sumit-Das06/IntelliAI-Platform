"""Shared test fixtures.

Two worlds, deliberately separate:

- **Hermetic settings** (``settings``): built explicitly, never reading the
  developer's ``.env`` — deterministic on any machine.
- **Real-database fixtures** (``db_engine``, ``db_session``): integration
  tests against the compose/CI Postgres, auto-skipping when it's absent.
  ``db_session`` gives every test SAVEPOINT-rollback isolation: everything
  the test does — including ``commit()`` — happens inside an outer
  transaction that is rolled back afterward. Fast, isolated, zero cleanup
  code, and the database is bit-for-bit untouched between tests.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import (
    AuthSettings,
    DatabaseSettings,
    Environment,
    LimitsSettings,
    RedisSettings,
    Settings,
    StorageSettings,
)
from intelliai_api.db.engine import create_engine


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def settings() -> Settings:
    # A fresh limits namespace per test: buckets and leases are shared
    # state in Redis, and without isolation one test's traffic would
    # consume another's allowance — a suite that fails by ORDER rather
    # than by defect.
    return Settings(
        _env_file=None,
        env=Environment.TEST,
        auth=AuthSettings(_env_file=None, key_pepper="test-pepper"),
        limits=LimitsSettings(_env_file=None, namespace=f"test-{uuid.uuid4().hex}"),
        database=DatabaseSettings(
            _env_file=None,
            url="postgresql+asyncpg://test:test-password@localhost:5432/test",
        ),
        # 127.0.0.1, never "localhost": on a dual-stack host "localhost"
        # resolves to ::1 first, and a service listening only on IPv4
        # costs a failover that can exceed the limiter's deliberately
        # short fail-fast budget — silently turning every test into a
        # fail-open test.
        redis=RedisSettings(_env_file=None, url="redis://127.0.0.1:6379/9"),
        storage=StorageSettings(
            _env_file=None,
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="test-secret",
        ),
    )


@pytest.fixture()
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Engine against the real dev/CI Postgres; skips cleanly without infra."""
    engine = create_engine(Settings())  # real env: .env locally, env vars in CI
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("requires running infrastructure (make up)")
    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose entire life happens inside one rolled-back transaction.

    ``join_transaction_mode="create_savepoint"`` turns every ``commit()``
    inside the test into a SAVEPOINT release, all discarded by the outer
    rollback — tests exercise real commit semantics, the database keeps
    nothing.
    """
    async with db_engine.connect() as connection:
        outer = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        session = factory()
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()
