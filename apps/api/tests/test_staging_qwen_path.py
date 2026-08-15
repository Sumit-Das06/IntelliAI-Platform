"""Milestone 18: the staging profile drives the REAL product path to Qwen.

Full-stack tests over the actual app — real auth, real usage ledger
(rolled back), real admission, real collection seam — with the ONE
staging difference installed: ``staging_registry()`` instead of the
live catalog. The runtime is the standard contract-level fake, which is
the point: everything ABOVE the runtime must treat the candidate as
just another artifact, and these tests would catch any place it does
not. The live-model half of the proof (real Qwen decoding through the
real gateway) is the Milestone 18 drill evidence, not a unit test.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import SpeechSample, UsageEvent, UsageQuantity
from intelliai_api.registry.proposals import staging_registry
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionResult,
    TranscriptionSegment,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import META, FakeRuntimeClient

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"
SAMPLE_HEADER = "X-IntelliAI-Sample"

HINDI_TEXT = "नमस्ते दुनिया यह एक परीक्षण है"


def qwen_envelope(duration: float = 8.2) -> RuntimeResponse[TranscriptionResult]:
    """What the qwen3 slot actually returns: ONE utterance-spanning segment."""
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(
            text=HINDI_TEXT,
            language="hi",
            duration_seconds=duration,
            segments=(
                TranscriptionSegment(start_seconds=0.0, end_seconds=duration, text=HINDI_TEXT),
            ),
        ),
        model="qwen3-asr-0.6b",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=duration),),
        timing=RuntimeTiming(total_ms=1450.0, stages={"inference": 1300.0}),
        runtime=META,
    )


def ceiling_refusal() -> RuntimeErrorResponse:
    """The runtime's real ceiling-guard envelope, verbatim shape.

    600 s since M19 Phase 18 (120-600 s chunks inside the engine; the
    refusal beyond the ceiling is unchanged in shape and honesty).
    """
    return RuntimeErrorResponse(
        type=RuntimeErrorType.INVALID_INPUT,
        message="audio longer than 600 seconds is not supported by the requested model",
        param="file",
        runtime=META,
    )


def install(runtime: FakeRuntimeClient) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.registry = staging_registry()
        app.state.runtime_clients = {"stt-runtime": runtime}
        app.state.object_storage = FakeObjectStorage()

    return configure


async def _tenant(
    factory: async_sessionmaker[AsyncSession], email: str, *, consent: bool = False
) -> BootstrapResult:
    async with factory() as session:
        service = IdentityService(session, pepper=PEPPER)
        result = await service.bootstrap_organization(
            organization_name="StagingCo", owner_email=email, owner_name="Owner"
        )
        if consent:
            await service.grant_data_consent(
                organization_public_id=result.organization.public_id,
                reference="cohort-2026-08-consent-v1",
            )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _post_kwargs(**form: str) -> dict[str, Any]:
    return {
        "files": {"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        "data": {"model": "intelliai-stt", **form},
    }


async def _usage_events(
    factory: async_sessionmaker[AsyncSession], organization_id: int
) -> list[UsageEvent]:
    async with factory() as session:
        rows = await session.execute(
            select(UsageEvent).where(UsageEvent.organization_id == organization_id)
        )
        return list(rows.scalars().all())


async def _samples(
    factory: async_sessionmaker[AsyncSession], organization_id: int
) -> list[SpeechSample]:
    async with factory() as session:
        rows = await session.execute(
            select(SpeechSample).where(SpeechSample.organization_id == organization_id)
        )
        return list(rows.scalars().all())


# ── Routing through the real gateway ─────────────────────────────────────


@pytest.mark.parametrize(
    ("form", "artifact"),
    [
        ({"language": "hi"}, "qwen3-asr-0.6b"),
        ({"language": "hi-IN"}, "qwen3-asr-0.6b"),
        ({"language": "en"}, "whisper-small"),
        ({}, "whisper-small"),
    ],
)
async def test_staging_routes_by_language(
    settings: Settings,
    db_engine: AsyncEngine,
    form: dict[str, str],
    artifact: str,
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, f"stage-{artifact}-{len(form)}@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(**form),
        )
        assert response.status_code == 200
        (call,) = fake.calls
        assert call[1].model == artifact


async def test_verbose_json_carries_one_clean_segment_and_no_internal_names(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-verbose@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi", response_format="verbose_json"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["text"] == HINDI_TEXT
        assert body["language"] == "hi"
        assert [set(segment) for segment in body["segments"]] == [{"id", "start", "end", "text"}]
        assert body["segments"][0]["start"] == 0.0
        assert body["segments"][0]["end"] == body["duration"]
        lowered = response.text.lower()
        for marker in ("qwen", "llama", "gguf", "whisper"):
            assert marker not in lowered


async def test_one_usage_event_with_the_measured_amount(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope(duration=8.2))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-usage@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        assert response.status_code == 200
        events = await _usage_events(factory, tenant.organization.id)
        assert len(events) == 1
        async with factory() as session:
            quantities = (
                (
                    await session.execute(
                        select(UsageQuantity).where(UsageQuantity.usage_event_id == events[0].id)
                    )
                )
                .scalars()
                .all()
            )
        assert len(quantities) == 1
        assert quantities[0].unit == "audio_seconds"
        assert float(quantities[0].amount) == pytest.approx(8.2)
        # The public usage surface names public models, never artifacts.
        summary = await client.get("/v1/usage/summary", headers=_bearer(tenant.generated.secret))
        assert summary.status_code == 200
        assert "qwen" not in summary.text.lower()
        assert "intelliai-stt" in summary.text


async def test_consented_hindi_request_collects_a_sample(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-collect@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        assert response.status_code == 200
        assert response.headers.get(SAMPLE_HEADER)
        samples = await _samples(factory, tenant.organization.id)
        assert len(samples) == 1
        assert samples[0].requested_language == "hi"
        # The stored transcript is the model's output, verbatim.
        assert samples[0].original_transcript == HINDI_TEXT
        assert samples[0].current_transcript == HINDI_TEXT


async def test_contribution_off_prevents_collection_but_not_transcription(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-optout@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                **_bearer(tenant.generated.secret),
                "X-IntelliAI-Contribution": "off",
            },
            **_post_kwargs(language="hi"),
        )
        assert response.status_code == 200
        assert response.json()["text"] == HINDI_TEXT
        assert SAMPLE_HEADER not in response.headers
        assert await _samples(factory, tenant.organization.id) == []
        # Metering is unaffected by the contribution choice.
        assert len(await _usage_events(factory, tenant.organization.id)) == 1


async def test_correction_flows_through_the_existing_endpoint(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-correct@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        response = await client.post(
            "/v1/audio/transcriptions", headers=headers, **_post_kwargs(language="hi")
        )
        sample_id = response.headers[SAMPLE_HEADER]
        corrected = await client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers=headers,
            json={"corrected_text": "नमस्ते दुनिया, यह एक परीक्षण है।"},
        )
        assert corrected.status_code == 200
        assert corrected.json()["corrected_text"] == "नमस्ते दुनिया, यह एक परीक्षण है।"
        # Correction evolves current_transcript; the original is immutable.
        (sample,) = await _samples(factory, tenant.organization.id)
        assert sample.original_transcript == HINDI_TEXT
        assert sample.current_transcript == "नमस्ते दुनिया, यह एक परीक्षण है।"


# ── The runtime's safety refusals, through the gateway ───────────────────


async def test_the_ceiling_refusal_passes_through_cleanly(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(error=ceiling_refusal())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-toolong@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["param"] == "file"
        assert "600 seconds" in body["error"]["message"]
        lowered = response.text.lower()
        for marker in ("qwen", "llama", "gguf", "ctx"):
            assert marker not in lowered
        # A refused request is not billed and never collected.
        assert await _usage_events(factory, tenant.organization.id) == []
        assert await _samples(factory, tenant.organization.id) == []


async def test_unavailable_runtime_fails_safely_with_no_fallback(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(unavailable=True)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "stage-down@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        assert response.status_code >= 500
        lowered = response.text.lower()
        for marker in ("qwen", "llama", "gguf"):
            assert marker not in lowered
        # NO automatic fallback (Milestone 16 decision): exactly one
        # runtime call was made, and nothing re-routed to the incumbent.
        assert len(fake.calls) == 1
        assert fake.calls[0][1].model == "qwen3-asr-0.6b"
        # A failed request is not billed.
        assert await _usage_events(factory, tenant.organization.id) == []


async def test_auth_is_unchanged_on_the_staging_profile(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=qwen_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, _factory):
        missing = await client.post("/v1/audio/transcriptions", **_post_kwargs(language="hi"))
        assert missing.status_code == 401
        invalid = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer("sk-not-a-real-key"),
            **_post_kwargs(language="hi"),
        )
        assert invalid.status_code == 401
        assert fake.calls == []
