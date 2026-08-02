"""Shared fixtures: a lifespan-managed app and deterministic WAV builders."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings(console_logs=True, max_concurrency=2, max_queue=2))
    # The context manager runs the lifespan: engines load before the first
    # request and unload after the last — exactly like production.
    with TestClient(app) as test_client:
        yield test_client
