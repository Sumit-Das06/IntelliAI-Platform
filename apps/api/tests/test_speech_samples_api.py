"""Speech sample read APIs: org-scoped, public-safe, UI-driven.

The laws pinned here: the list is newest first and org-scoped; the
detail carries the lifecycle timeline; audio returns the ORIGINAL bytes
with the stored content type; and no response ever names a foundation
model — the public product rule applies to API bodies exactly as it
applies to pages.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from tests.helpers import client_with_db
from tests.test_collection import _bearer, _post_kwargs, _tenant, install
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio


async def _collected_sample(client: Any, secret: str, **form: str) -> str:
    """Create one consented sample through the real transcription path."""
    response = await client.post(
        "/v1/audio/transcriptions",
        headers={**_bearer(secret), "X-IntelliAI-Client": "web/1.0"},
        **_post_kwargs(**form),
    )
    assert response.status_code == 200
    sample_id: str = response.headers["X-IntelliAI-Sample"]
    return sample_id


async def test_the_list_is_newest_first_with_public_fields_only(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "samples-list@example.com", consent=True)
        first = await _collected_sample(client, tenant.generated.secret, language="en")
        second = await _collected_sample(client, tenant.generated.secret, language="en")

        body = (
            await client.get("/v1/speech-samples", headers=_bearer(tenant.generated.secret))
        ).json()

        assert [sample["id"] for sample in body["data"]] == [second, first]
        sample = body["data"][0]
        assert sample["status"] == "collected"
        assert sample["client_source"] == "web"
        assert sample["client_version"] == "1.0"
        assert sample["original_transcript"] == "ask not what your country"
        assert sample["current_transcript"] == sample["original_transcript"]
        assert sample["duration_seconds"] == 11.0
        assert sample["mime_type"] == "audio/wav"
        assert sample["consent_reference"] == "cohort-2026-08-consent-v1"
        # The public product rule, applied to API bodies: producer
        # internals never leave the database through this surface.
        for private_field in ("model_name", "model_version", "lineage", "audio_key"):
            assert private_field not in sample
        assert "whisper" not in str(body).lower()


async def test_the_detail_carries_the_lifecycle_timeline(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "samples-detail@example.com", consent=True)
        sample_id = await _collected_sample(client, tenant.generated.secret)
        corrected = await client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers=_bearer(tenant.generated.secret),
            json={"corrected_text": "ask not what your country can do"},
        )
        assert corrected.status_code == 200

        body = (
            await client.get(
                f"/v1/speech-samples/{sample_id}", headers=_bearer(tenant.generated.secret)
            )
        ).json()

        assert body["id"] == sample_id
        assert body["current_transcript"] == "ask not what your country can do"
        assert body["original_transcript"] == "ask not what your country"
        assert [event["event"] for event in body["events"]] == ["collected", "corrected"]
        assert all(event["occurred_at"] for event in body["events"])


async def test_the_audio_returns_the_original_bytes(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "samples-audio@example.com", consent=True)
        sample_id = await _collected_sample(client, tenant.generated.secret)

        response = await client.get(
            f"/v1/speech-samples/{sample_id}/audio", headers=_bearer(tenant.generated.secret)
        )

        assert response.status_code == 200
        assert response.content == b"fake-wav-bytes"
        assert response.headers["content-type"] == "audio/wav"
        # Consented voice data never lingers in a shared cache.
        assert response.headers["cache-control"] == "private, no-store"


async def test_missing_audio_object_is_a_404_not_a_crash(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "samples-orphan@example.com", consent=True)
        sample_id = await _collected_sample(client, tenant.generated.secret)
        storage.puts.clear()  # the row survived; its object did not

        response = await client.get(
            f"/v1/speech-samples/{sample_id}/audio", headers=_bearer(tenant.generated.secret)
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "sample_audio_not_found"


async def test_foreign_and_unknown_samples_do_not_exist(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        owner = await _tenant(factory, "samples-owner@example.com", consent=True)
        stranger = await _tenant(factory, "samples-stranger@example.com", consent=False)
        sample_id = await _collected_sample(client, owner.generated.secret)

        foreign = await client.get(
            f"/v1/speech-samples/{sample_id}", headers=_bearer(stranger.generated.secret)
        )
        unknown = await client.get(
            "/v1/speech-samples/smp_does_not_exist", headers=_bearer(owner.generated.secret)
        )
        foreign_list = (
            await client.get("/v1/speech-samples", headers=_bearer(stranger.generated.secret))
        ).json()

        assert foreign.status_code == 404
        assert foreign.json()["error"]["code"] == "sample_not_found"
        assert unknown.status_code == 404
        assert foreign_list["data"] == []


async def test_the_endpoints_require_authentication(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        for path in (
            "/v1/speech-samples",
            "/v1/speech-samples/smp_x",
            "/v1/speech-samples/smp_x/audio",
        ):
            response = await client.get(path)
            assert response.status_code == 401


async def test_the_limit_is_validated(settings: Settings, db_engine: AsyncEngine) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(runtime)) as (client, factory):
        tenant = await _tenant(factory, "samples-limit@example.com", consent=False)
        over = await client.get(
            "/v1/speech-samples?limit=501", headers=_bearer(tenant.generated.secret)
        )
        # Platform envelope: validation errors are 400, never 422.
        assert over.status_code == 400
