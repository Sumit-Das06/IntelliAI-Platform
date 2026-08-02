"""/v1/audio/transcriptions: the full gateway flow over real HTTP + Postgres,
with a fake RuntimeClient standing in for the runtime (CI has no models)."""

from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.runtimes import RuntimeCallError, RuntimeUnavailableError
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings

META = RuntimeMetadata(
    service="stt-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
)


def make_envelope(text: str = "ask not what your country") -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(
            text=text,
            language="en",
            duration_seconds=11.0,
            segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=11.0, text=text),),
        ),
        model="whisper-small",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=11.0),),
        timing=RuntimeTiming(total_ms=900.0, stages={"inference": 800.0}),
        runtime=META,
    )


class FakeRuntimeClient:
    """Records the contract-level call; answers as instructed."""

    def __init__(
        self,
        envelope: RuntimeResponse[TranscriptionResult] | None = None,
        error: RuntimeErrorResponse | None = None,
        unavailable: bool = False,
    ) -> None:
        self.calls: list[tuple[bytes, TranscriptionRequest]] = []
        self._envelope = envelope
        self._error = error
        self._unavailable = unavailable

    async def transcribe(
        self, audio: bytes, request: TranscriptionRequest
    ) -> RuntimeResponse[TranscriptionResult]:
        self.calls.append((audio, request))
        if self._unavailable:
            raise RuntimeUnavailableError("connect refused")
        if self._error is not None:
            raise RuntimeCallError(self._error)
        assert self._envelope is not None
        return self._envelope

    async def close(self) -> None:
        return


def install(fake: FakeRuntimeClient) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"stt-runtime": fake}

    return configure


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="SpeechCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def post_kwargs(**form: str) -> dict[str, Any]:
    return {
        "files": {"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        "data": {"model": "intelliai-stt", **form},
    }


async def test_json_response_and_contract_call(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-json@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="en"),
        )
        assert response.status_code == 200
        assert response.json() == {"text": "ask not what your country"}
        # The gateway translated public -> internal: artifact id, never
        # the public name, crossed the plane boundary.
        (call,) = fake.calls
        assert call[1].model == "whisper-small"
        assert call[1].language == "en"
        assert call[0] == b"fake-wav-bytes"


async def test_verbose_json_shape(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-verbose@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(response_format="verbose_json"),
        )
        body = response.json()
        assert body["task"] == "transcribe"
        assert body["language"] == "en"
        assert body["duration"] == 11.0
        assert body["segments"] == [
            {"id": 0, "start": 0.0, "end": 11.0, "text": "ask not what your country"}
        ]


async def test_text_format(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope("plain words"))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-text@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(response_format="text"),
        )
        assert response.headers["content-type"].startswith("text/plain")
        assert response.text == "plain words"


async def test_usage_event_is_emitted_in_public_vocabulary(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-usage@example.com")
        with structlog.testing.capture_logs() as logs:
            await client.post(
                "/v1/audio/transcriptions",
                headers=_bearer(tenant.generated.secret),
                **post_kwargs(),
            )
        (event,) = [entry for entry in logs if entry["event"] == "transcription.completed"]
        assert event["model"] == "intelliai-stt"  # public name, never artifact
        assert event["audio_seconds"] == 11.0
        assert event["organization_id"].startswith("org_")


async def test_unknown_model_is_404_model_not_found(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-404@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            files={"file": ("clip.wav", b"x", "audio/wav")},
            data={"model": "gpt-4o"},
        )
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "model_not_found"
        assert error["param"] == "model"
        assert fake.calls == []  # rejected before any runtime work


async def test_runtime_invalid_input_translates_to_400(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(
        error=RuntimeErrorResponse(
            type=RuntimeErrorType.INVALID_INPUT,
            message="audio must be a WAV file (further containers arrive with the media pipeline)",
            param="file",
            runtime=META,
        )
    )
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-400@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(),
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["type"] == "invalid_request_error"
        assert error["param"] == "file"


async def test_overloaded_translates_to_503_with_retry_after(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(
        error=RuntimeErrorResponse(
            type=RuntimeErrorType.OVERLOADED,
            message="runtime is at capacity; retry shortly",
            runtime=META,
        )
    )
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-503@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(),
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "overloaded"
        assert "Retry-After" in response.headers


async def test_unreachable_runtime_translates_to_503(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(unavailable=True)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stt-down@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(),
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "runtime_unavailable"


async def test_auth_is_required(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, _factory):
        response = await client.post("/v1/audio/transcriptions", **post_kwargs())
        assert response.status_code == 401
        assert fake.calls == []
