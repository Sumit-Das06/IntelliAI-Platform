"""M36 gateway streaming laws: same product rules, audio early.

A fake streaming runtime client proves the gateway half end to end:
chunked audio out, the billing law (characters once delivery starts —
including the customer who walks away), the accepted-then-failed law
for mid-stream runtime breaks, and JSON errors for everything that
fails before audio begins.
"""

from collections.abc import AsyncIterator, Callable
from decimal import Decimal

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageOutcome
from intelliai_api.runtimes import RuntimeUnavailableError
from intelliai_runtime_contract import (
    RuntimeResponse,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
)
from tests.helpers import client_with_db
from tests.test_speech_api import _bearer, _tenant, make_envelope
from tests.test_tts_billing import _tts_events

pytestmark = pytest.mark.anyio

_HEADER = b"RIFF" + b"\x00" * 40  # 44-byte stand-in for the streaming preamble


def stream_envelope(characters: int) -> RuntimeResponse[SpeechSynthesisResult]:
    envelope = make_envelope(voice="english-female", characters=characters)
    return envelope.model_copy(
        update={"output": envelope.output.model_copy(update={"duration_seconds": 0.0})}
    )


class FakeStreamingClient:
    """Streams three PCM chunks after the WAV preamble; can break mid-way
    or refuse before the stream begins."""

    def __init__(
        self,
        chunks: list[bytes] | None = None,
        break_after: int | None = None,
        unavailable: bool = False,
    ) -> None:
        self.chunks = chunks if chunks is not None else [b"a" * 4800, b"b" * 4800, b"c" * 4800]
        self.break_after = break_after
        self.unavailable = unavailable
        self.calls: list[SpeechSynthesisRequest] = []

    async def synthesize_stream(
        self, request: SpeechSynthesisRequest
    ) -> tuple[AsyncIterator[bytes], RuntimeResponse[SpeechSynthesisResult]]:
        self.calls.append(request)
        if self.unavailable:
            raise RuntimeUnavailableError("connect refused")

        async def body() -> AsyncIterator[bytes]:
            yield _HEADER
            for index, chunk in enumerate(self.chunks):
                if self.break_after is not None and index >= self.break_after:
                    raise RuntimeUnavailableError("runtime died mid-stream")
                yield chunk

        return body(), stream_envelope(characters=len(request.text))

    async def close(self) -> None:
        return


def install(fake: FakeStreamingClient) -> Callable[[FastAPI], None]:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

    return configure


async def test_streaming_delivers_chunked_audio_with_the_public_shape(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeStreamingClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stream-happy@example.com")
        async with client.stream(
            "POST",
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": "stream me", "stream": True},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("audio/wav")
            assert "x-runtime-envelope" not in {k.lower() for k in response.headers}
            body = b"".join([chunk async for chunk in response.aiter_bytes()])
        assert body == _HEADER + b"a" * 4800 + b"b" * 4800 + b"c" * 4800
        (call,) = fake.calls
        assert call.stream is True
        assert call.model == "kokoro-82m"

        (event,) = await _tts_events(factory, tenant)
        assert event.billable is True
        assert {q.unit: q.amount for q in event.quantities} == {
            "characters": Decimal(len("stream me"))
        }
        assert event.lineage["delivery"] == "streamed"
        # Delivered bytes -> measured seconds: 3*4800 bytes / 48000 B/s.
        assert event.lineage["measured_audio_seconds"] == pytest.approx(0.3, abs=1e-6)


async def test_midstream_runtime_break_records_the_nonbillable_capacity_row(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeStreamingClient(break_after=1)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stream-broken@example.com")
        async with client.stream(
            "POST",
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": "will break", "stream": True},
        ) as response:
            assert response.status_code == 200  # headers were already sent
            body = b"".join([chunk async for chunk in response.aiter_bytes()])
        # Truncated audio, never a misleading JSON tail.
        assert body == _HEADER + b"a" * 4800

        (event,) = await _tts_events(factory, tenant)
        assert event.billable is False
        assert event.outcome is UsageOutcome.FAILED
        assert not event.quantities


async def test_prestream_failure_is_an_ordinary_json_error_and_bills_nothing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeStreamingClient(unavailable=True)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stream-down@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": "hello", "stream": True},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "runtime_unavailable"

        events = await _tts_events(factory, tenant)
        assert all(event.billable is False for event in events)


async def test_stream_false_and_absent_keep_the_whole_body_path(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    from tests.test_speech_api import FakeSynthesisClient
    from tests.test_speech_api import install as install_whole

    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install_whole(fake)) as (client, factory):
        tenant = await _tenant(factory, "stream-default@example.com")
        for body in (
            {"model": "intelliai-tts", "input": "Hello from IntelliAI."},
            {"model": "intelliai-tts", "input": "Hello from IntelliAI.", "stream": False},
        ):
            response = await client.post(
                "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body
            )
            assert response.status_code == 200
        # The whole-body client seam served both — no streaming call made.
        assert len(fake.calls) == 2
        assert all(call.stream is False for call in fake.calls)
