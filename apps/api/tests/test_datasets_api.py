"""Dataset APIs: org-scoped definitions, immutable versions, one truth.

The laws pinned here over the real HTTP + Postgres stack: datasets are
created and read only within their organization; the preview and the
freeze agree exactly (one eligibility implementation); a frozen version
never changes when the world does; corrections select the right
training text version-by-version; and no response ever names a
foundation model.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
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
from tests.test_collection import _bearer, _tenant
from tests.test_storage import FakeObjectStorage

pytestmark = pytest.mark.anyio

META = RuntimeMetadata(
    service="stt-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
)


def _envelope(
    text: str = "ask not what your country", language: str = "en", seconds: float = 11.0
) -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(
            text=text,
            language=language,
            duration_seconds=seconds,
            segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=seconds, text=text),),
        ),
        model="whisper-small",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=seconds),),
        timing=RuntimeTiming(total_ms=900.0, stages={"inference": 800.0}),
        runtime=META,
    )


class VaryingRuntimeClient:
    """A fake whose next answer is settable — dataset tests need samples
    that differ in language, text, and duration."""

    def __init__(self) -> None:
        self.envelope = _envelope()

    async def transcribe(
        self, audio: bytes, request: TranscriptionRequest
    ) -> RuntimeResponse[TranscriptionResult]:
        return self.envelope

    async def close(self) -> None:
        return


def install(runtime: VaryingRuntimeClient, storage: FakeObjectStorage) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"stt-runtime": runtime}
        app.state.object_storage = storage

    return configure


async def _collect(
    client: Any,
    secret: str,
    runtime: VaryingRuntimeClient,
    *,
    text: str = "ask not what your country",
    language: str = "en",
    seconds: float = 11.0,
    client_header: str = "web/1.0",
) -> str:
    """One consented sample through the real transcription path."""
    runtime.envelope = _envelope(text=text, language=language, seconds=seconds)
    response = await client.post(
        "/v1/audio/transcriptions",
        headers={**_bearer(secret), "X-IntelliAI-Client": client_header},
        files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        data={"model": "intelliai-stt", "language": language},
    )
    assert response.status_code == 200
    sample_id: str = response.headers["X-IntelliAI-Sample"]
    return sample_id


async def _correct(client: Any, secret: str, sample_id: str, text: str) -> None:
    response = await client.post(
        f"/v1/audio/transcriptions/{sample_id}/correction",
        headers=_bearer(secret),
        json={"corrected_text": text},
    )
    assert response.status_code == 200


async def test_create_list_and_get_a_dataset(settings: Settings, db_engine: AsyncEngine) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-crud@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)

        created = await client.post(
            "/v1/datasets",
            headers=headers,
            json={
                "name": "Hindi Keyboard Fine-tuning v1",
                "description": "Consent-approved corrected Hindi keyboard speech",
                "criteria": {"language": "hi", "client_source": "keyboard", "corrected": True},
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["id"].startswith("ds_")
        assert body["status"] == "active"
        assert body["criteria"] == {
            "language": "hi",
            "client_source": "keyboard",
            "corrected": True,
        }
        assert body["version_count"] == 0
        assert body["latest_version"] is None

        listed = (await client.get("/v1/datasets", headers=headers)).json()
        assert [d["id"] for d in listed["data"]] == [body["id"]]

        fetched = (await client.get(f"/v1/datasets/{body['id']}", headers=headers)).json()
        assert fetched["name"] == "Hindi Keyboard Fine-tuning v1"
        assert fetched["criteria"]["language"] == "hi"


async def test_invalid_criteria_are_refused_not_ignored(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-criteria@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)

        unknown = await client.post(
            "/v1/datasets",
            headers=headers,
            json={"name": "Bad", "criteria": {"speaker_gender": "any"}},
        )
        malformed_language = await client.post(
            "/v1/datasets",
            headers=headers,
            json={"name": "Bad", "criteria": {"language": "not a code!"}},
        )
        unknown_client = await client.post(
            "/v1/datasets",
            headers=headers,
            json={"name": "Bad", "criteria": {"client_source": "telepathy"}},
        )
        nameless = await client.post(
            "/v1/datasets", headers=headers, json={"name": "", "criteria": {}}
        )

        # Platform envelope: validation errors are 400, never 422 — and a
        # criterion the backend cannot enforce is an error, not a shrug.
        for response in (unknown, malformed_language, unknown_client, nameless):
            assert response.status_code == 400


async def test_the_endpoints_require_authentication(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        for method, path in (
            ("GET", "/v1/datasets"),
            ("POST", "/v1/datasets"),
            ("GET", "/v1/datasets/ds_x"),
            ("GET", "/v1/datasets/ds_x/preview"),
            ("POST", "/v1/datasets/ds_x/archive"),
            ("POST", "/v1/datasets/ds_x/versions"),
            ("GET", "/v1/datasets/ds_x/versions"),
            ("GET", "/v1/datasets/ds_x/versions/dsv_x"),
        ):
            response = await client.request(method, path)
            assert response.status_code == 401, path


async def test_foreign_and_unknown_datasets_do_not_exist(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        owner = await _tenant(factory, "datasets-owner@example.com", consent=True)
        stranger = await _tenant(factory, "datasets-stranger@example.com", consent=True)
        created = await client.post(
            "/v1/datasets",
            headers=_bearer(owner.generated.secret),
            json={"name": "Private", "criteria": {}},
        )
        dataset_id = created.json()["id"]

        foreign = await client.get(
            f"/v1/datasets/{dataset_id}", headers=_bearer(stranger.generated.secret)
        )
        foreign_version = await client.post(
            f"/v1/datasets/{dataset_id}/versions", headers=_bearer(stranger.generated.secret)
        )
        unknown = await client.get(
            "/v1/datasets/ds_does_not_exist", headers=_bearer(owner.generated.secret)
        )
        foreign_list = (
            await client.get("/v1/datasets", headers=_bearer(stranger.generated.secret))
        ).json()

        assert foreign.status_code == 404
        assert foreign.json()["error"]["code"] == "dataset_not_found"
        assert foreign_version.status_code == 404
        assert unknown.status_code == 404
        assert foreign_list["data"] == []


async def test_preview_counts_only_this_organizations_eligible_samples(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        mine = await _tenant(factory, "datasets-mine@example.com", consent=True)
        theirs = await _tenant(factory, "datasets-theirs@example.com", consent=True)
        await _collect(client, mine.generated.secret, runtime, language="hi")
        corrected = await _collect(client, mine.generated.secret, runtime, language="hi")
        await _correct(client, mine.generated.secret, corrected, "सुधारा हुआ पाठ")
        await _collect(client, theirs.generated.secret, runtime, language="hi")

        created = await client.post(
            "/v1/datasets",
            headers=_bearer(mine.generated.secret),
            json={"name": "Hindi", "criteria": {"language": "hi"}},
        )
        preview = (
            await client.get(
                f"/v1/datasets/{created.json()['id']}/preview",
                headers=_bearer(mine.generated.secret),
            )
        ).json()

        # The stranger's Hindi sample is invisible: two eligible, one
        # corrected, 22 measured seconds — all MINE.
        assert preview["eligible_samples"] == 2
        assert preview["matching_samples"] == 2
        assert preview["corrected_samples"] == 1
        assert preview["duration_seconds"] == 22.0
        assert preview["languages"] == [{"key": "hi", "samples": 2, "duration_seconds": 22.0}]
        assert preview["client_sources"] == [{"key": "web", "samples": 2, "duration_seconds": 22.0}]


async def test_the_preview_and_the_frozen_version_agree_exactly(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # THE consistency law: the UI must never promise 1,500 samples and
    # freeze 1,372. Preview and freeze run the same eligibility query.
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-consistency@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        for index in range(3):
            await _collect(
                client, tenant.generated.secret, runtime, language="hi", seconds=5.0 + index
            )
        await _collect(client, tenant.generated.secret, runtime, language="en")

        dataset_id = (
            await client.post(
                "/v1/datasets",
                headers=headers,
                json={"name": "Hindi", "criteria": {"language": "hi"}},
            )
        ).json()["id"]

        preview = (await client.get(f"/v1/datasets/{dataset_id}/preview", headers=headers)).json()
        version = (await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()

        assert version["sample_count"] == preview["eligible_samples"] == 3
        assert version["duration_seconds"] == preview["duration_seconds"]
        assert version["languages"] == preview["languages"]
        assert version["client_sources"] == preview["client_sources"]


async def test_versions_freeze_number_and_never_mutate(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-immutable@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        first = await _collect(client, tenant.generated.secret, runtime, text="the original words")

        dataset_id = (
            await client.post(
                "/v1/datasets", headers=headers, json={"name": "All speech", "criteria": {}}
            )
        ).json()["id"]

        v1 = (await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()
        assert v1["version_number"] == 1
        assert v1["sample_count"] == 1
        assert v1["corrected_samples"] == 0
        assert v1["created_by"].startswith("key_")

        # The world moves on: a new sample arrives, the old one is corrected.
        await _collect(client, tenant.generated.secret, runtime, text="a second sample")
        await _correct(client, tenant.generated.secret, first, "the corrected words")

        # Version 1, re-read: exactly as frozen.
        v1_again = (
            await client.get(f"/v1/datasets/{dataset_id}/versions/{v1['id']}", headers=headers)
        ).json()
        assert v1_again["sample_count"] == 1
        assert v1_again["corrected_samples"] == 0
        assert v1_again["duration_seconds"] == v1["duration_seconds"]

        # Version 2 sees the new world: two samples, one corrected.
        v2 = (await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()
        assert v2["version_number"] == 2
        assert v2["sample_count"] == 2
        assert v2["corrected_samples"] == 1

        versions = (await client.get(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()
        assert [v["version_number"] for v in versions["data"]] == [2, 1]

        # The dataset row now carries the latest version summary.
        dataset = (await client.get(f"/v1/datasets/{dataset_id}", headers=headers)).json()
        assert dataset["version_count"] == 2
        assert dataset["latest_version"]["version_number"] == 2


async def test_an_empty_freeze_is_refused(settings: Settings, db_engine: AsyncEngine) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-empty@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        dataset_id = (
            await client.post(
                "/v1/datasets",
                headers=headers,
                json={"name": "Nothing yet", "criteria": {"language": "zu"}},
            )
        ).json()["id"]

        refused = await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)

        assert refused.status_code == 400
        assert refused.json()["error"]["code"] == "dataset_version_empty"
        versions = (await client.get(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()
        assert versions["data"] == []


async def test_consent_law_is_visible_through_the_dataset_lens(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # An organization without consent stores nothing, so its datasets
    # can never have eligible samples — the opt-in gate holds end to end.
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-noconsent@example.com", consent=False)
        headers = _bearer(tenant.generated.secret)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={**headers, "X-IntelliAI-Client": "web/1.0"},
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
            data={"model": "intelliai-stt"},
        )
        assert response.status_code == 200
        assert "X-IntelliAI-Sample" not in response.headers  # nothing stored

        dataset_id = (
            await client.post(
                "/v1/datasets", headers=headers, json={"name": "Empty by law", "criteria": {}}
            )
        ).json()["id"]
        preview = (await client.get(f"/v1/datasets/{dataset_id}/preview", headers=headers)).json()

        assert preview["eligible_samples"] == 0
        assert preview["matching_samples"] == 0


async def test_archive_is_idempotent_and_keeps_versions_readable(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-archive@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        await _collect(client, tenant.generated.secret, runtime)
        dataset_id = (
            await client.post(
                "/v1/datasets", headers=headers, json={"name": "Retiring", "criteria": {}}
            )
        ).json()["id"]
        version = (await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)).json()

        once = await client.post(f"/v1/datasets/{dataset_id}/archive", headers=headers)
        twice = await client.post(f"/v1/datasets/{dataset_id}/archive", headers=headers)

        assert once.status_code == 200
        assert once.json()["status"] == "archived"
        assert twice.status_code == 200
        assert twice.json()["status"] == "archived"
        # Lineage is forever: the frozen version is still readable.
        still = await client.get(
            f"/v1/datasets/{dataset_id}/versions/{version['id']}", headers=headers
        )
        assert still.status_code == 200
        assert still.json()["sample_count"] == 1


async def test_no_dataset_response_ever_names_a_foundation_model(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The public product rule, applied to this API exactly as everywhere:
    # producer internals never leave the database through this surface.
    runtime = VaryingRuntimeClient()
    async with client_with_db(settings, db_engine, install(runtime, FakeObjectStorage())) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "datasets-product@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        await _collect(client, tenant.generated.secret, runtime, language="hi")
        dataset_id = (
            await client.post(
                "/v1/datasets",
                headers=headers,
                json={"name": "Product rule", "criteria": {"language": "hi"}},
            )
        ).json()["id"]
        await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)

        surfaces = [
            (await client.get("/v1/datasets", headers=headers)).text,
            (await client.get(f"/v1/datasets/{dataset_id}", headers=headers)).text,
            (await client.get(f"/v1/datasets/{dataset_id}/preview", headers=headers)).text,
            (await client.get(f"/v1/datasets/{dataset_id}/versions", headers=headers)).text,
        ]
        for body in surfaces:
            lowered = body.lower()
            assert "whisper" not in lowered
            assert "model_name" not in lowered
            assert "audio_key" not in lowered
            assert "lineage" not in lowered
