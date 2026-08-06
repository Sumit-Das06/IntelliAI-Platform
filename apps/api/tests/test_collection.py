"""Data collection: consent-gated, fail-open, and invisible to customers.

The laws pinned here: collection happens only after a successful
transcription; nothing is stored without consent; no collection failure
may ever fail the customer's request; the only public trace is one
additive header.
"""

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import CollectionSettings, Settings
from intelliai_api.db.models import (
    ClientSource,
    SampleStatus,
    SpeechSample,
    SpeechSampleEvent,
    UsageEvent,
)
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_api.storage import StorageWriteError
from tests.helpers import client_with_db
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings

SAMPLE_HEADER = "X-IntelliAI-Sample"


@pytest.fixture(autouse=True)
def _unbind_logging() -> Iterator[None]:
    yield
    structlog.reset_defaults()


class FailingObjectStorage:
    """Every put fails the way a dead store fails: with the one type."""

    async def put(self, *, key: str, data: bytes, content_type: str | None) -> None:
        raise StorageWriteError(f"put {key!r} failed: simulated outage")

    async def close(self) -> None:
        return


def install(runtime: FakeRuntimeClient, storage: object | None = None) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"stt-runtime": runtime}
        if storage is not None:
            app.state.object_storage = storage

    return configure


async def _tenant(
    factory: async_sessionmaker[AsyncSession], email: str, *, consent: bool
) -> BootstrapResult:
    async with factory() as session:
        service = IdentityService(session, pepper=PEPPER)
        result = await service.bootstrap_organization(
            organization_name="FlywheelCo", owner_email=email, owner_name="Owner"
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


async def _rows(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[list[SpeechSample], list[SpeechSampleEvent]]:
    async with factory() as session:
        samples = (await session.execute(select(SpeechSample))).scalars().all()
        events = (await session.execute(select(SpeechSampleEvent))).scalars().all()
        return list(samples), list(events)


async def test_consented_request_stores_object_row_event_and_header(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "collect-on@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="en"),
        )

        assert response.status_code == 200
        # The OpenAI-mirror body is untouched; the header is the only trace.
        assert response.json() == {"text": "ask not what your country"}
        sample_id = response.headers[SAMPLE_HEADER]
        assert sample_id.startswith("smp_")

        # Object: original bytes exactly as received, deterministic key
        # embedding the sample id.
        (put_key, put_data, put_content_type) = storage.puts[0]
        assert put_key.startswith(f"speech/{tenant.organization.public_id}/")
        assert put_key.endswith(f"/{sample_id}.wav")
        assert put_data == b"fake-wav-bytes"
        assert put_content_type == "audio/wav"

        # Row: birth state with every locked fact.
        (sample,), (event,) = await _rows(factory)
        assert sample.public_id == sample_id
        assert sample.status is SampleStatus.COLLECTED
        assert sample.audio_key == put_key
        assert sample.original_transcript == "ask not what your country"
        assert sample.current_transcript == sample.original_transcript
        assert sample.file_size_bytes == len(b"fake-wav-bytes")
        assert float(sample.duration_seconds) == 11.0
        assert sample.mime_type == "audio/wav"
        assert sample.requested_language == "en"
        assert sample.routed_language == "en"
        assert sample.detected_language == "en"
        # Producer: SQL-filterable columns + the full provenance object.
        assert sample.model_name == "whisper-small"
        assert sample.model_version == "1"
        assert sample.lineage["service"] == "stt-runtime"
        assert sample.lineage["routed_artifact"] == "whisper-small"
        assert sample.client_source is ClientSource.API
        assert sample.user_identifier == tenant.api_key.public_id
        # Consent snapshot copied at capture:
        assert sample.consented_at is not None
        assert sample.consent_reference == "cohort-2026-08-consent-v1"

        # Event: the lifecycle history began, carrying the operational
        # processing time (metadata, not a metric).
        assert event.event == "collected"
        assert event.detail["processing_time_ms"] >= 0
        assert event.detail["client_source"] == "api"


async def test_without_consent_transcription_succeeds_and_nothing_is_stored(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "collect-off@example.com", consent=False)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(),
        )

        assert response.status_code == 200
        assert SAMPLE_HEADER not in response.headers
        assert storage.puts == []
        samples, events = await _rows(factory)
        assert samples == [] and events == []


async def test_the_kill_switch_disables_collection_despite_consent(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    disabled = settings.model_copy(
        update={"collection": CollectionSettings(_env_file=None, enabled=False)}
    )
    runtime = FakeRuntimeClient(envelope=make_envelope())
    # No storage installed: with the switch off the factory builds None,
    # and the service must no-op on the flag alone regardless.
    async with client_with_db(disabled, db_engine, install(runtime)) as (client, factory):
        tenant = await _tenant(factory, "kill-switch@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(),
        )

        assert response.status_code == 200
        assert SAMPLE_HEADER not in response.headers
        samples, events = await _rows(factory)
        assert samples == [] and events == []


async def test_storage_failure_never_fails_the_customer_request(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(runtime, FailingObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "store-down@example.com", consent=True)
        with structlog.testing.capture_logs() as logs:
            response = await client.post(
                "/v1/audio/transcriptions",
                headers=_bearer(tenant.generated.secret),
                **_post_kwargs(),
            )

        # Customer success is more important than dataset collection:
        assert response.status_code == 200
        assert response.json() == {"text": "ask not what your country"}
        assert SAMPLE_HEADER not in response.headers
        assert any(log["event"] == "collection.store_failed" for log in logs)

        samples, events = await _rows(factory)
        assert samples == [] and events == []
        # Billing independence: the usage event was written regardless.
        async with factory() as session:
            billed = await session.scalar(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.organization_id == tenant.organization.id
                )
            )
        assert billed == 1
