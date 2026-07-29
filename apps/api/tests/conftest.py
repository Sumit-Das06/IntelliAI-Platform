"""Shared test fixtures.

Tests never read the developer's ``.env`` or process environment: every
settings object is built explicitly (``_env_file=None``) so the suite is
deterministic on any machine, including CI with no environment at all.
"""

import pytest

from intelliai_api.core.config import (
    DatabaseSettings,
    Environment,
    RedisSettings,
    Settings,
    StorageSettings,
)


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env=Environment.TEST,
        database=DatabaseSettings(
            _env_file=None,
            url="postgresql+asyncpg://test:test-password@localhost:5432/test",
        ),
        redis=RedisSettings(_env_file=None, url="redis://localhost:6379/9"),
        storage=StorageSettings(
            _env_file=None,
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="test-secret",
        ),
    )
