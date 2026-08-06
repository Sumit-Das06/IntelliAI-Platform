"""Transcript corrections: the first human-labelled data in the flywheel.

Laws pinned here: the machine's original transcript is immutable forever;
the current transcript evolves last-write-wins; history gains a
``corrected`` event carrying its source; foreign tenants see 404, never
403; validation and auth guard the door.
"""

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import SpeechSample, SpeechSampleEvent
from intelliai_api.services.identity import BootstrapResult, IdentityService
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


def install(runtime: FakeRuntimeClient, storage: FakeObjectStorage) -> Any:
    from fastapi import FastAPI

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"stt-runtime": runtime}
        app.state.object_storage = storage

    return configure


async def _consented_tenant(
    factory: async_sessionmaker[AsyncSession], email: str
) -> BootstrapResult:
    async with factory() as session:
        service = IdentityService(session, pepper=PEPPER)
        result = await service.bootstrap_organization(
            organization_name="CorrectCo", owner_email=email, owner_name="Owner"
        )
        await service.grant_data_consent(
            organization_public_id=result.organization.public_id, reference="doc-v1"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _post_kwargs() -> dict[str, Any]:
    return {
        "files": {"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        "data": {"model": "intelliai-stt", "language": "en"},
    }


async def _collected_sample(client: Any, secret: str) -> str:
    response = await client.post(
        "/v1/audio/transcriptions", headers=_bearer(secret), **_post_kwargs()
    )
    assert response.status_code == 200
    sample_id: str = response.headers[SAMPLE_HEADER]
    return sample_id


async def _row(factory: async_sessionmaker[AsyncSession], public_id: str) -> SpeechSample:
    async with factory() as session:
        result = await session.execute(
            select(SpeechSample).where(SpeechSample.public_id == public_id)
        )
        return result.scalar_one()


async def test_a_correction_evolves_current_and_never_the_original(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "correct@example.com")
        sample_id = await _collected_sample(client, tenant.generated.secret)

        response = await client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers=_bearer(tenant.generated.secret),
            json={"corrected_text": "ask not what your country can do"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == sample_id
        assert body["corrected_text"] == "ask not what your country can do"
        assert body["last_modified_at"] is not None

        sample = await _row(factory, sample_id)
        # The machine's output is immutable forever:
        assert sample.original_transcript == "ask not what your country"
        # The living transcript evolved:
        assert sample.current_transcript == "ask not what your country can do"
        assert sample.last_modified_at is not None

        async with factory() as session:
            events = (
                (
                    await session.execute(
                        select(SpeechSampleEvent)
                        .where(SpeechSampleEvent.sample_id == sample.id)
                        .order_by(SpeechSampleEvent.occurred_at)
                    )
                )
                .scalars()
                .all()
            )
        assert [event.event for event in events] == ["collected", "corrected"]
        # Vocabulary reserved now so review tooling needs no migration:
        assert events[-1].detail["correction_source"] == "user"


async def test_a_second_correction_wins_and_appends_its_own_event(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "twice@example.com")
        sample_id = await _collected_sample(client, tenant.generated.secret)
        headers = _bearer(tenant.generated.secret)
        url = f"/v1/audio/transcriptions/{sample_id}/correction"

        first = await client.post(url, headers=headers, json={"corrected_text": "first pass"})
        second = await client.post(url, headers=headers, json={"corrected_text": "second pass"})

        assert first.status_code == second.status_code == 200
        sample = await _row(factory, sample_id)
        assert sample.current_transcript == "second pass"  # last write wins
        assert sample.original_transcript == "ask not what your country"  # still immutable
        async with factory() as session:
            corrected_events = (
                (
                    await session.execute(
                        select(SpeechSampleEvent).where(
                            SpeechSampleEvent.sample_id == sample.id,
                            SpeechSampleEvent.event == "corrected",
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(corrected_events) == 2  # history keeps both acts


async def test_a_foreign_tenants_sample_does_not_exist_here(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        owner = await _consented_tenant(factory, "owner@example.com")
        intruder = await _consented_tenant(factory, "intruder@example.com")
        sample_id = await _collected_sample(client, owner.generated.secret)

        response = await client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers=_bearer(intruder.generated.secret),
            json={"corrected_text": "should never land"},
        )

        # 404, never 403: no existence disclosure across tenants.
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "sample_not_found"
        sample = await _row(factory, sample_id)
        assert sample.current_transcript == "ask not what your country"  # untouched


async def test_an_unknown_sample_is_404(settings: Settings, db_engine: AsyncEngine) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "unknown@example.com")
        response = await client.post(
            "/v1/audio/transcriptions/smp_doesnotexist/correction",
            headers=_bearer(tenant.generated.secret),
            json={"corrected_text": "nothing to correct"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "sample_not_found"


async def test_validation_refuses_empty_and_oversized_corrections(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, factory):
        tenant = await _consented_tenant(factory, "validate@example.com")
        sample_id = await _collected_sample(client, tenant.generated.secret)
        headers = _bearer(tenant.generated.secret)
        url = f"/v1/audio/transcriptions/{sample_id}/correction"

        empty = await client.post(url, headers=headers, json={"corrected_text": ""})
        oversized = await client.post(url, headers=headers, json={"corrected_text": "x" * 20_001})
        missing = await client.post(url, headers=headers, json={})

        # 400, deliberately: the platform renders validation through its
        # own envelope, never FastAPI's nonstandard 422 shape.
        assert empty.status_code == 400
        assert oversized.status_code == 400
        assert missing.status_code == 400
        sample = await _row(factory, sample_id)
        assert sample.current_transcript == "ask not what your country"  # untouched
        assert sample.last_modified_at is None


async def test_an_unauthenticated_correction_is_401(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fixture = install(FakeRuntimeClient(envelope=make_envelope()), FakeObjectStorage())
    async with client_with_db(settings, db_engine, fixture) as (client, _factory):
        response = await client.post(
            "/v1/audio/transcriptions/smp_whatever/correction",
            json={"corrected_text": "no key, no entry"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_api_key"
