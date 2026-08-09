"""The request-body ceiling (14A): refused at READ time, before the
gateway buffers an upload into memory — with the platform's standard
error envelope, never a bare transport reset.

Two layers under test: the pure-ASGI guard itself (both lanes — declared
Content-Length and streamed chunks), and the full application path where
the refusal must render the envelope with this request's id. The STT
runtime's own 25 MiB audio validation is deliberately untouched: this
ceiling exists for memory pressure, not audio semantics.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import Receive, Scope, Send

from intelliai_api.api.middleware import RequestBodySizeLimitMiddleware
from intelliai_api.core.config import Settings
from tests.helpers import client_with_db
from tests.test_collection import _bearer, _post_kwargs, _tenant, install
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio


# ── The guard itself, both lanes ─────────────────────────────────────────


async def _echo_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Reads the whole body (like a route does), then answers 200."""
    if scope["type"] != "http":
        return
    while True:
        message = await receive()
        if message["type"] != "http.request" or not message.get("more_body", False):
            break
    await send(
        {"type": "http.response.start", "status": 200, "headers": [(b"content-length", b"2")]}
    )
    await send({"type": "http.response.body", "body": b"ok"})


def _client(max_bytes: int) -> AsyncClient:
    app = RequestBodySizeLimitMiddleware(_echo_app, max_bytes=max_bytes)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_declared_oversize_body_is_refused_without_reading_it() -> None:
    async with _client(max_bytes=100) as client:
        response = await client.post("/anything", content=b"x" * 101)
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["code"] == "request_too_large"


async def test_a_streamed_body_is_cut_off_at_the_ceiling() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(10):
            yield b"x" * 40  # 400 bytes total, no usable Content-Length

    async with _client(max_bytes=100) as client:
        response = await client.post("/anything", content=chunks())
    # The refusal is the middleware's own response; the echo app's late
    # 200 (it sees a disconnect) is discarded, never interleaved.
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


async def test_a_body_under_the_ceiling_passes_untouched() -> None:
    async with _client(max_bytes=100) as client:
        response = await client.post("/anything", content=b"x" * 100)
    assert response.status_code == 200


async def test_non_http_scopes_pass_through() -> None:
    # Lifespan and websocket scopes must never hit the guard.
    called: list[str] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        called.append(scope["type"])

    guard = RequestBodySizeLimitMiddleware(app, max_bytes=1)
    await guard({"type": "lifespan"}, _unusable_receive, _unusable_send)
    assert called == ["lifespan"]


async def _unusable_receive() -> Any:  # pragma: no cover - never called
    raise AssertionError("receive must not be called")


async def _unusable_send(message: Any) -> None:  # pragma: no cover - never called
    raise AssertionError("send must not be called")


# ── Through the real application: the envelope contract ─────────────────


def _tight_limit(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"limits": settings.limits.model_copy(update={"max_request_bytes": 1024})}
    )


async def test_the_refusal_renders_the_platform_envelope(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(
        _tight_limit(settings), db_engine, install(runtime, FakeObjectStorage())
    ) as (client, factory):
        tenant = await _tenant(factory, "too-large@example.com", consent=False)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            files={"file": ("big.wav", b"\x00" * 2048, "audio/wav")},
            data={"model": "intelliai-stt"},
        )
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["code"] == "request_too_large"
    assert error["request_id"]
    assert response.headers["X-Request-ID"]


async def test_a_legitimate_upload_is_unaffected_by_the_ceiling(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "normal-size@example.com", consent=False)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="en"),
        )
    assert response.status_code == 200
    assert response.json()["text"]
