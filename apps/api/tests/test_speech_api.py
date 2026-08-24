"""/v1/audio/speech + /v1/audio/voices: the full gateway flow over real
HTTP + Postgres, with a fake RuntimeClient standing in for the runtime.

The fake is not just a CI convenience — it is the engine-independence
proof: the ENTIRE public synthesis surface passes with no Kokoro (and no
engine at all) in the process, because nothing above the runtime's engine
module knows an engine exists.
"""

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
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings

META = RuntimeMetadata(
    service="tts-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
)

FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake-audio-bytes"


def make_envelope(
    voice: str = "reference-alto", characters: int = 21, artifact: str = "kokoro-82m"
) -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=3.2, sample_rate_hz=24_000, voice=voice, characters=characters
        ),
        model=artifact,
        usage=(Usage(unit=UsageUnit.CHARACTERS, amount=characters),),
        timing=RuntimeTiming(total_ms=700.0, stages={"synthesis": 650.0}),
        runtime=META,
    )


class FakeSynthesisClient:
    """Records the contract-level call; answers as instructed."""

    def __init__(
        self,
        envelope: RuntimeResponse[SpeechSynthesisResult] | None = None,
        error: RuntimeErrorResponse | None = None,
        unavailable: bool = False,
        audio: bytes = FAKE_WAV,
    ) -> None:
        self.calls: list[SpeechSynthesisRequest] = []
        self._envelope = envelope
        self._error = error
        self._unavailable = unavailable
        self._audio = audio

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        self.calls.append(request)
        if self._unavailable:
            raise RuntimeUnavailableError("connect refused")
        if self._error is not None:
            raise RuntimeCallError(self._error)
        assert self._envelope is not None
        return self._audio, self._envelope

    async def close(self) -> None:
        return


def install(fake: FakeSynthesisClient) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

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


def body(**over: object) -> dict[str, Any]:
    return {"model": "intelliai-tts", "input": "Hello from IntelliAI.", **over}


async def test_returns_raw_audio_with_no_internal_headers(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-happy@example.com")
        response = await client.post(
            "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body()
        )
        assert response.status_code == 200
        assert response.content == FAKE_WAV  # playable bytes, untouched
        assert response.headers["content-type"] == "audio/wav"
        # The runtime envelope is gateway food, never customer surface.
        assert "x-runtime-envelope" not in {k.lower() for k in response.headers}
        # The contract call carried the ARTIFACT id and the raw text.
        (call,) = fake.calls
        assert call.model == "kokoro-82m"
        assert call.text == "Hello from IntelliAI."
        assert call.voice is None  # None = the runtime's default voice


async def test_voice_and_speed_forwarded_and_event_emitted(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope(voice="reference-bass"))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-event@example.com")
        with structlog.testing.capture_logs() as logs:
            response = await client.post(
                "/v1/audio/speech",
                headers=_bearer(tenant.generated.secret),
                json=body(voice="reference-bass", speed=1.5),
            )
        assert response.status_code == 200
        (call,) = fake.calls
        assert call.voice == "reference-bass"
        assert call.speed == 1.5
        (event,) = [entry for entry in logs if entry["event"] == "speech.completed"]
        assert event["model"] == "intelliai-tts"  # public name, never artifact
        assert event["voice"] == "reference-bass"  # public voice, never engine token
        assert event["characters"] == 21
        assert event["audio_seconds"] == 3.2
        assert event["organization_id"].startswith("org_")


async def test_unknown_model_is_404(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-404@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=body(model="gpt-4o-tts"),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "model_not_found"
        assert fake.calls == []


async def test_capability_mismatch_both_directions(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-mismatch@example.com")
        headers = _bearer(tenant.generated.secret)
        # An STT model cannot speak...
        speech = await client.post(
            "/v1/audio/speech", headers=headers, json=body(model="intelliai-stt")
        )
        assert speech.status_code == 400
        assert speech.json()["error"]["code"] == "capability_mismatch"
        # ...and a TTS model cannot listen. (The guard fires before any
        # client lookup, so no stt client is needed here.)
        transcription = await client.post(
            "/v1/audio/transcriptions",
            headers=headers,
            files={"file": ("clip.wav", b"x", "audio/wav")},
            data={"model": "intelliai-tts"},
        )
        assert transcription.status_code == 400
        assert transcription.json()["error"]["code"] == "capability_mismatch"
        assert fake.calls == []


async def test_unknown_voice_refused_on_the_product_plane(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-voice@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=body(voice="aurora"),
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "voice_not_found"
        assert error["param"] == "voice"
        assert fake.calls == []  # the catalog said no BEFORE crossing planes


async def test_runtime_invalid_input_passes_through(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(
        error=RuntimeErrorResponse(
            type=RuntimeErrorType.INVALID_INPUT,
            message="text exceeds the 2000-character limit",
            param="text",
            runtime=META,
        )
    )
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-badtext@example.com")
        response = await client.post(
            "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body()
        )
        assert response.status_code == 400
        assert response.json()["error"]["param"] == "text"


@pytest.mark.parametrize(
    ("error_type", "expected_code", "expected_status"),
    [
        (RuntimeErrorType.NOT_READY, "model_loading", 503),
        (RuntimeErrorType.OVERLOADED, "overloaded", 503),
        (RuntimeErrorType.INTERNAL, None, 500),
    ],
)
async def test_runtime_failures_translate_totally(
    settings: Settings,
    db_engine: AsyncEngine,
    error_type: RuntimeErrorType,
    expected_code: str | None,
    expected_status: int,
) -> None:
    fake = FakeSynthesisClient(
        error=RuntimeErrorResponse(type=error_type, message="internal detail", runtime=META)
    )
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, f"tts-{error_type.value}@example.com")
        response = await client.post(
            "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body()
        )
        assert response.status_code == expected_status
        if expected_code is not None:
            assert response.json()["error"]["code"] == expected_code
        assert "internal detail" not in response.text  # internals stay opaque


async def test_runtime_unavailable_is_503(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeSynthesisClient(unavailable=True)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-down@example.com")
        response = await client.post(
            "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body()
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "runtime_unavailable"


async def test_invalid_public_requests_never_cross_planes(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-invalid@example.com")
        headers = _bearer(tenant.generated.secret)
        assert (
            await client.post("/v1/audio/speech", headers=headers, json=body(input=""))
        ).status_code == 400
        assert (
            await client.post("/v1/audio/speech", headers=headers, json=body(response_format="mp3"))
        ).status_code == 400
        assert (
            await client.post("/v1/audio/speech", headers=headers, json=body(speed=0))
        ).status_code == 400
        assert fake.calls == []


async def test_auth_is_required(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        assert (await client.post("/v1/audio/speech", json=body())).status_code == 401
        assert (await client.get("/v1/audio/voices")).status_code == 401


async def test_voices_is_a_product_catalog(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "tts-voices@example.com")
        response = await client.get("/v1/audio/voices", headers=_bearer(tenant.generated.secret))
        assert response.status_code == 200
        payload = response.json()
        assert payload["object"] == "list"
        voices = {voice["id"]: voice for voice in payload["data"]}
        # The M42 promotion added the Hindi pair; the English launch
        # names and their permanent legacy aliases are unchanged.
        assert set(voices) == {
            "english-female",
            "english-male",
            "reference-alto",
            "reference-bass",
            "hindi-female",
            "hindi-male",
        }
        for voice_id, voice in voices.items():
            assert voice["object"] == "voice"
            assert voice["model"] == "intelliai-tts"
            assert voice["languages"] == (["hi"] if voice_id.startswith("hindi-") else ["en"])
            assert isinstance(voice["created"], int) and voice["created"] > 0


async def test_public_surface_never_leaks_engine_vocabulary(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The voice-identity law, enforced: engine names, engine voice tokens,
    # and dependency names must never appear in any public speech surface.
    forbidden = ("kokoro", "af_heart", "am_michael", "hexgrad", "misaki", "espeak", "torch")
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "tts-leak@example.com")
        headers = _bearer(tenant.generated.secret)
        surfaces = [
            (await client.get("/v1/audio/voices", headers=headers)).text,
            (await client.get("/v1/models", headers=headers)).text,
            (
                await client.post("/v1/audio/speech", headers=headers, json=body(voice="af_heart"))
            ).text,  # even naming an engine token back at us stays clean
        ]
        for surface in surfaces:
            lowered = surface.lower()
            for term in forbidden:
                if term == "af_heart":
                    continue  # the customer's own (rejected) input is echoed as param context
                assert term not in lowered, f"public surface leaks {term!r}"


async def test_engine_replacement_is_customer_invisible(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The demonstration: swap the artifact behind intelliai-tts (as a
    registry/deployment change would) and the customer-visible response is
    byte-identical — same route, same request, same body, same headers.
    Replacing Kokoro = a new engine module in the runtime + one catalog
    row edit; NOTHING here would change."""
    responses = []
    for artifact in ("kokoro-82m", "successor-tts-v2"):
        fake = FakeSynthesisClient(envelope=make_envelope(artifact=artifact))
        async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
            tenant = await _tenant(factory, f"tts-swap-{artifact}@example.com")
            response = await client.post(
                "/v1/audio/speech", headers=_bearer(tenant.generated.secret), json=body()
            )
            assert response.status_code == 200
            responses.append((response.content, response.headers["content-type"]))
    assert responses[0] == responses[1]
