"""M57 Smart Correction gateway endpoint: the boundary laws.

The runtime bridge is faked at the httpx seam, so these tests prove the
ROUTE's obligations — auth first, friendly fail-open unavailability,
invalid-input passthrough, and the ai_correction_suggested provenance
event staying DISTINCT from the human corrected event. Real correction
quality lives in the M56/M57 evidence, never in CI.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar
from unittest.mock import patch

import httpx
import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from intelliai_api.db.models import SpeechSample, SpeechSampleEvent
from tests.helpers import client_with_db
from tests.test_corrections_api import (
    SAMPLE_HEADER,
    _bearer,
    _consented_tenant,
    _post_kwargs,
    install,
)
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio

MODULE = "intelliai_api.api.v1.text.corrections"


@pytest.fixture(autouse=True)
def _unbind_logging() -> Iterator[None]:
    yield
    structlog.reset_defaults()


class _FakeAsyncClient:
    """Plays the stt-runtime /v1/correct endpoint at the httpx seam."""

    status_code = 200
    payload: ClassVar[dict[str, Any]] = {"corrected_text": "I went to the office yesterday."}
    raise_transport = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def post(self, route: str, json: dict[str, Any]) -> Any:
        del route, json
        if type(self).raise_transport:
            raise httpx.ConnectError("refused")
        cls = type(self)

        class _Resp:
            status_code = cls.status_code

            @staticmethod
            def json() -> dict[str, Any]:
                return cls.payload

        return _Resp()


def _fake(
    status: int = 200, payload: dict[str, Any] | None = None, transport_error: bool = False
) -> Any:
    _FakeAsyncClient.status_code = status
    _FakeAsyncClient.payload = (
        payload if payload is not None else {"corrected_text": "I went to the office yesterday."}
    )
    _FakeAsyncClient.raise_transport = transport_error
    return patch(f"{MODULE}.httpx.AsyncClient", _FakeAsyncClient)


async def test_requires_authentication(settings: Settings, db_engine: AsyncEngine) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, _factory):
        response = await client.post(
            "/v1/text/corrections", json={"text": "i going office", "language": "en"}
        )
        assert response.status_code == 401


async def test_correction_round_trip_and_suggestion_event(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "smart@example.com")
        secret = tenant.generated.secret
        sample_response = await client.post(
            "/v1/audio/transcriptions", headers=_bearer(secret), **_post_kwargs()
        )
        sample_id = sample_response.headers[SAMPLE_HEADER]

        with _fake():
            response = await client.post(
                "/v1/text/corrections",
                headers=_bearer(secret),
                json={"text": "i going office yesterday", "language": "en", "sample_id": sample_id},
            )
        assert response.status_code == 200
        assert response.json() == {"corrected_text": "I went to the office yesterday."}

        # Provenance: the suggestion is its OWN event kind, and the
        # sample's current transcript did NOT move (only a human moves it).
        async with factory() as session:
            sample = (
                await session.execute(
                    select(SpeechSample).where(SpeechSample.public_id == sample_id)
                )
            ).scalar_one()
            events = (
                (
                    await session.execute(
                        select(SpeechSampleEvent).where(SpeechSampleEvent.sample_id == sample.id)
                    )
                )
                .scalars()
                .all()
            )
        kinds = [event.event for event in events]
        assert "ai_correction_suggested" in kinds
        assert "corrected" not in kinds
        suggestion = next(e for e in events if e.event == "ai_correction_suggested")
        assert suggestion.detail["text"] == "I went to the office yesterday."
        assert sample.current_transcript == sample.original_transcript


async def test_runtime_disabled_is_a_friendly_unavailable(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "smart-off@example.com")
        with _fake(status=503, payload={"type": "not_ready", "message": "x"}):
            response = await client.post(
                "/v1/text/corrections",
                headers=_bearer(tenant.generated.secret),
                json={"text": "hello there", "language": "en"},
            )
        assert response.status_code == 503
        body = response.json()["error"]
        assert body["code"] == "smart_correction_unavailable"
        assert "transcript is unaffected" in body["message"].casefold()


async def test_unreachable_runtime_is_a_friendly_unavailable(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "smart-down@example.com")
        with _fake(transport_error=True):
            response = await client.post(
                "/v1/text/corrections",
                headers=_bearer(tenant.generated.secret),
                json={"text": "hello there", "language": "en"},
            )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "smart_correction_unavailable"


async def test_invalid_input_message_passes_through(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "smart-400@example.com")
        with _fake(
            status=400,
            payload={"type": "invalid_input", "message": "transcript too long for correction"},
        ):
            response = await client.post(
                "/v1/text/corrections",
                headers=_bearer(tenant.generated.secret),
                json={"text": "hello there", "language": "en"},
            )
        assert response.status_code == 400
        assert "too long" in response.json()["error"]["message"]
