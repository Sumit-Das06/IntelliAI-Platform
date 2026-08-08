"""Training-data preparation: frozen membership → validated manifest.

The laws pinned here over the real HTTP + Postgres stack: preparation
reads ONLY the immutable membership and pinned transcripts (never
current eligibility, never current transcripts); the manifest is
deterministic — same members, same bytes, same checksum, forever; READY
is terminal and immune to later corrections and new samples; invalid
members FAIL the preparation with named machine-readable reasons, never
a silently smaller artifact; and everything is organization-scoped with
no internal names or storage keys in any public body.
"""

import json
from typing import Any

import pytest
from sqlalchemy import UniqueConstraint, delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from intelliai_api.db.base import Base
from intelliai_api.db.models import (
    DatasetPreparation,
    DatasetVersionSample,
    SpeechSample,
)
from intelliai_api.db.repositories import DatasetRepository
from intelliai_api.db.repositories.datasets import DatasetCriteria
from tests.helpers import client_with_db
from tests.test_collection import _bearer, _tenant
from tests.test_datasets_api import VaryingRuntimeClient, _collect, _correct, install
from tests.test_storage import FakeObjectStorage

pytestmark = pytest.mark.anyio


# ── Schema: the locked design, pinned ────────────────────────────────────


def test_the_preparation_table_is_registered_with_its_laws() -> None:
    table = Base.metadata.tables["dataset_preparations"]
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    # One preparation per version — the citable artifact is singular.
    assert ("dataset_version_id",) in unique_columns
    for column in ("organization_id", "dataset_id", "dataset_version_id"):
        assert next(iter(table.c[column].foreign_keys)).ondelete == "CASCADE"


# ── Full-stack helpers ───────────────────────────────────────────────────


async def _dataset_with_version(
    client: Any, headers: dict[str, str], *, criteria: dict[str, Any] | None = None
) -> tuple[str, str]:
    dataset = await client.post(
        "/v1/datasets",
        headers=headers,
        json={"name": "Prep corpus", "criteria": criteria or {}},
    )
    assert dataset.status_code == 201
    dataset_id: str = dataset.json()["id"]
    version = await client.post(f"/v1/datasets/{dataset_id}/versions", headers=headers)
    assert version.status_code == 201
    version_id: str = version.json()["id"]
    return dataset_id, version_id


def _prepare_path(dataset_id: str, version_id: str) -> str:
    return f"/v1/datasets/{dataset_id}/versions/{version_id}/prepare"


def _preparation_path(dataset_id: str, version_id: str) -> str:
    return f"/v1/datasets/{dataset_id}/versions/{version_id}/preparation"


def _manifest_puts(storage: FakeObjectStorage) -> list[tuple[str, bytes, str | None]]:
    return [entry for entry in storage.puts if entry[0].startswith("datasets/")]


# ── Correctness ──────────────────────────────────────────────────────────


async def test_successful_preparation_builds_the_deterministic_manifest(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-success@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        corrected = await _collect(
            client, tenant.generated.secret, runtime, text="machine words", language="hi"
        )
        await _correct(client, tenant.generated.secret, corrected, "सुधारा हुआ पाठ")
        await _collect(
            client, tenant.generated.secret, runtime, text="दूसरा नमूना", language="hi", seconds=6.5
        )
        dataset_id, version_id = await _dataset_with_version(
            client, headers, criteria={"language": "hi"}
        )

        response = await client.post(_prepare_path(dataset_id, version_id), headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "ready"
        assert body["id"].startswith("prep_")
        assert body["dataset_id"] == dataset_id
        assert body["dataset_version_id"] == version_id
        assert body["sample_count"] == 2
        assert body["valid_count"] == 2
        assert body["invalid_count"] == 0
        assert body["duration_seconds"] == 17.5  # 11.0 + 6.5
        assert body["languages"] == {"hi": 2}
        assert body["errors"] == []
        assert body["manifest"]["format"] == "jsonl"
        assert body["manifest"]["example_count"] == 2
        assert body["manifest"]["checksum"].startswith("sha256:")
        assert body["manifest"]["size_bytes"] > 0
        assert body["created_by"].startswith("key_")
        assert body["completed_at"] is not None

        # The stored artifact: version-addressed key, one line per
        # example, sample-id ascending, exactly the five public fields,
        # and the PINNED (corrected) transcript as the training text.
        (key, data, content_type) = _manifest_puts(storage)[0]
        assert key == (
            f"datasets/{tenant.organization.public_id}/{dataset_id}/{version_id}/manifest.jsonl"
        )
        assert content_type == "application/x-ndjson"
        lines = [json.loads(line) for line in data.decode("utf-8").splitlines()]
        assert len(lines) == 2
        assert [line["id"] for line in lines] == sorted(line["id"] for line in lines)
        for line in lines:
            assert list(line.keys()) == ["id", "audio", "text", "language", "duration_seconds"]
            assert line["language"] == "hi"
            assert line["audio"].startswith(f"speech/{tenant.organization.public_id}/")
        by_id = {line["id"]: line for line in lines}
        assert by_id[corrected]["text"] == "सुधारा हुआ पाठ"
        assert by_id[corrected]["duration_seconds"] == 11.0
        assert len(data) == body["manifest"]["size_bytes"]

        # GET returns the same verdict.
        fetched = await client.get(_preparation_path(dataset_id, version_id), headers=headers)
        assert fetched.status_code == 200
        assert fetched.json() == body


async def test_ready_is_terminal_and_immune_to_a_moving_world(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-immutable@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        member = await _collect(client, tenant.generated.secret, runtime, text="the frozen words")
        dataset_id, version_id = await _dataset_with_version(client, headers)
        first = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()

        # The world moves on: the member is corrected, a new sample arrives.
        await _correct(client, tenant.generated.secret, member, "words changed later")
        await _collect(client, tenant.generated.secret, runtime, text="a brand new sample")

        again = await client.post(_prepare_path(dataset_id, version_id), headers=headers)

        assert again.status_code == 201
        assert again.json()["id"] == first["id"]
        assert again.json()["manifest"]["checksum"] == first["manifest"]["checksum"]
        assert again.json()["valid_count"] == 1
        # Exactly one manifest was ever written, and it still carries the
        # text as pinned at the freeze — not the later correction.
        manifest_writes = _manifest_puts(storage)
        assert len(manifest_writes) == 1
        (_key, data, _ct) = manifest_writes[0]
        line = json.loads(data.decode("utf-8").splitlines()[0])
        assert line["text"] == "the frozen words"


async def test_rerunning_from_scratch_reproduces_identical_bytes(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Determinism, the hard way: delete the preparation ROW entirely and
    # prepare again — a new identity must still produce byte-identical
    # content, because content is a pure function of frozen membership.
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-determinism@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        for index in range(3):
            await _collect(
                client, tenant.generated.secret, runtime, text=f"sample {index}", seconds=3.0
            )
        dataset_id, version_id = await _dataset_with_version(client, headers)
        first = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()

        async with factory() as session:
            await session.execute(
                delete(DatasetPreparation).where(DatasetPreparation.public_id == first["id"])
            )
            await session.commit()

        second = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()

        assert second["id"] != first["id"]  # new identity…
        assert second["manifest"]["checksum"] == first["manifest"]["checksum"]  # …same content
        writes = _manifest_puts(storage)
        assert len(writes) == 2
        assert writes[0][1] == writes[1][1]  # byte-identical manifests


async def test_missing_audio_fails_preparation_then_retry_succeeds(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-audio@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        keep = await _collect(client, tenant.generated.secret, runtime, text="kept sample")
        broken = await _collect(client, tenant.generated.secret, runtime, text="broken sample")
        dataset_id, version_id = await _dataset_with_version(client, headers)

        # The broken sample's object vanishes (kill switch era, sweeper
        # bug, operator mistake — the row survives, its bytes do not).
        removed = [entry for entry in storage.puts if broken in entry[0]]
        storage.puts = [entry for entry in storage.puts if broken not in entry[0]]

        failed = await client.post(_prepare_path(dataset_id, version_id), headers=headers)

        assert failed.status_code == 201
        body = failed.json()
        assert body["status"] == "failed"
        assert body["sample_count"] == 2
        assert body["valid_count"] == 1
        assert body["invalid_count"] == 1
        assert body["errors"] == [{"sample_id": broken, "reason": "audio_missing"}]
        assert body["manifest"] is None
        # A failed preparation must never leave a manifest behind.
        assert _manifest_puts(storage) == []
        assert keep not in str(body["errors"])

        # The cause is fixed; retry succeeds IN PLACE — same identity.
        storage.puts.extend(removed)
        retried = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()
        assert retried["id"] == body["id"]
        assert retried["status"] == "ready"
        assert retried["valid_count"] == 2
        assert retried["errors"] == []


async def test_blank_transcript_and_missing_language_are_named(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-fields@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        no_text = await _collect(client, tenant.generated.secret, runtime, text="had text once")
        no_language = await _collect(client, tenant.generated.secret, runtime, text="fine text")
        dataset_id, version_id = await _dataset_with_version(client, headers)

        # Corrupt AFTER the freeze, straight in the database: a blank
        # pinned transcript and a sample with no language facts at all.
        async with factory() as session:
            rows = (
                await session.execute(
                    select(SpeechSample.public_id, SpeechSample.id).where(
                        SpeechSample.public_id.in_([no_text, no_language])
                    )
                )
            ).all()
            sample_ids: dict[str, int] = {public_id: internal for public_id, internal in rows}  # noqa: C416
            await session.execute(
                update(DatasetVersionSample)
                .where(DatasetVersionSample.speech_sample_id == sample_ids[no_text])
                .values(training_transcript="   ")
            )
            await session.execute(
                update(SpeechSample)
                .where(SpeechSample.id == sample_ids[no_language])
                .values(detected_language=None, requested_language=None, routed_language=None)
            )
            await session.commit()

        body = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()

        assert body["status"] == "failed"
        assert body["invalid_count"] == 2
        reasons = {(entry["sample_id"], entry["reason"]) for entry in body["errors"]}
        assert (no_text, "transcript_missing") in reasons
        assert (no_language, "language_missing") in reasons
        assert _manifest_puts(storage) == []


async def test_an_erased_sample_is_a_named_integrity_failure(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Privacy erasure CASCADEs through membership: the version honestly
    # shrinks, and preparation must SAY so rather than produce a smaller
    # artifact under the frozen count's name.
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-erasure@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        erased = await _collect(client, tenant.generated.secret, runtime, text="to be erased")
        await _collect(client, tenant.generated.secret, runtime, text="stays")
        dataset_id, version_id = await _dataset_with_version(client, headers)

        async with factory() as session:
            await session.execute(delete(SpeechSample).where(SpeechSample.public_id == erased))
            await session.commit()

        body = (await client.post(_prepare_path(dataset_id, version_id), headers=headers)).json()

        assert body["status"] == "failed"
        assert body["sample_count"] == 2  # the frozen claim…
        assert body["valid_count"] == 1  # …and what actually remains
        assert {"sample_id": None, "reason": "membership_count_mismatch"} in body["errors"]
        assert _manifest_puts(storage) == []


async def test_an_empty_version_cannot_be_prepared(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-empty@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        dataset = await client.post(
            "/v1/datasets", headers=headers, json={"name": "Empty", "criteria": {}}
        )
        dataset_id = dataset.json()["id"]
        # Versions cannot be born empty through the API (the freeze
        # refuses), so construct the degenerate row directly.
        async with factory() as session:
            repository = DatasetRepository(session)
            row = await repository.get_for_organization(tenant.organization.id, dataset_id)
            assert row is not None
            version = await repository.create_version(
                dataset_id=row.id,
                version_number=1,
                created_by="key_test",
                criteria=DatasetCriteria(),
            )
            version_public_id = version.public_id
            await session.commit()

        response = await client.post(_prepare_path(dataset_id, version_public_id), headers=headers)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "dataset_version_empty"


# ── Security ─────────────────────────────────────────────────────────────


async def test_the_endpoints_require_authentication(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        prepare = await client.post(_prepare_path("ds_x", "dsv_x"))
        fetch = await client.get(_preparation_path("ds_x", "dsv_x"))

    assert prepare.status_code == 401
    assert fetch.status_code == 401


async def test_cross_org_preparation_does_not_exist(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        owner = await _tenant(factory, "prep-owner@example.com", consent=True)
        stranger = await _tenant(factory, "prep-stranger@example.com", consent=True)
        await _collect(client, owner.generated.secret, runtime)
        dataset_id, version_id = await _dataset_with_version(
            client, _bearer(owner.generated.secret)
        )
        prepared = await client.post(
            _prepare_path(dataset_id, version_id), headers=_bearer(owner.generated.secret)
        )
        assert prepared.json()["status"] == "ready"

        foreign_prepare = await client.post(
            _prepare_path(dataset_id, version_id), headers=_bearer(stranger.generated.secret)
        )
        foreign_fetch = await client.get(
            _preparation_path(dataset_id, version_id), headers=_bearer(stranger.generated.secret)
        )

        # A foreign tenant's dataset does not exist here — 404, never 403.
        assert foreign_prepare.status_code == 404
        assert foreign_prepare.json()["error"]["code"] == "dataset_not_found"
        assert foreign_fetch.status_code == 404


async def test_get_before_any_preparation_is_a_404(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-none@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        await _collect(client, tenant.generated.secret, runtime)
        dataset_id, version_id = await _dataset_with_version(client, headers)

        response = await client.get(_preparation_path(dataset_id, version_id), headers=headers)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "preparation_not_found"


async def test_no_internal_names_paths_or_credentials_leak(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = VaryingRuntimeClient()
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "prep-product@example.com", consent=True)
        headers = _bearer(tenant.generated.secret)
        vanishing = await _collect(client, tenant.generated.secret, runtime)
        await _collect(client, tenant.generated.secret, runtime)
        ready_ds, ready_dsv = await _dataset_with_version(client, headers)
        ready = (await client.post(_prepare_path(ready_ds, ready_dsv), headers=headers)).text

        storage.puts = [entry for entry in storage.puts if vanishing not in entry[0]]
        failed_ds, failed_dsv = await _dataset_with_version(client, headers)
        failed = (await client.post(_prepare_path(failed_ds, failed_dsv), headers=headers)).text

        for body in (ready, failed):
            lowered = body.lower()
            # The public product rule and the no-infrastructure rule:
            # engine names, object keys, buckets, endpoints, credentials —
            # none of it exists on this surface.
            for forbidden in (
                "whisper",
                "artifact_key",
                "speech/",
                "datasets/",
                "manifest.jsonl",
                "minio",
                "s3",
                "bucket",
                "secret",
                "audio_key",
            ):
                assert forbidden not in lowered, forbidden
