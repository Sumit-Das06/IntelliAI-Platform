"""Erasure — the right to be forgotten, proven against the real schema.

The policy under test is docs/DATA_GOVERNANCE.md: objects before rows,
manifests carrying an erased person's text die with the sample, frozen
version statistics stay as frozen (the preparation layer tells the
present-tense truth), the usage ledger and an anonymized org row survive
tenant erasure, and an unreachable store aborts the run — nothing is
ever *recorded* as erased that might still exist.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import ResourceNotFoundError, ServiceUnavailableError
from intelliai_api.db.models import (
    DatasetVersion,
    DatasetVersionSample,
    Membership,
    MembershipRole,
    Organization,
    PreparationStatus,
    SpeechSample,
    SpeechSampleEvent,
)
from intelliai_api.db.repositories import (
    ApiKeyRepository,
    DatasetRepository,
    OrganizationRepository,
    SpeechSampleRepository,
    UserRepository,
)
from intelliai_api.db.repositories.datasets import DatasetCriteria
from intelliai_api.services.erasure import (
    ERASED_ORGANIZATION_NAME,
    REASON_SAMPLE_ERASED,
    ErasureService,
)
from intelliai_api.storage import StorageWriteError
from tests.test_datasets import _sample
from tests.test_storage import FakeObjectStorage

pytestmark = pytest.mark.anyio


async def _org(session: AsyncSession, name: str = "ErasureCo") -> Organization:
    return await OrganizationRepository(session).create(name)


async def _frozen_version_with_preparation(
    session: AsyncSession,
    organization: Organization,
    storage: FakeObjectStorage,
) -> tuple[int, str]:
    """A dataset → frozen version → READY preparation whose manifest
    object exists in the fake store. Returns (version_id, manifest_key)."""
    repository = DatasetRepository(session)
    criteria = DatasetCriteria()
    dataset = await repository.create(
        organization_id=organization.id, name="All speech", description=None, criteria=criteria
    )
    version = await repository.create_version(
        dataset_id=dataset.id, version_number=1, created_by="key_test", criteria=criteria
    )
    await repository.freeze_membership(version.id, organization.id, criteria)
    statistics = await repository.membership_statistics(version.id)
    version.sample_count = statistics.sample_count
    version.duration_seconds = statistics.duration_seconds
    preparation = await repository.create_preparation(
        organization_id=organization.id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        created_by="key_test",
    )
    manifest_key = f"datasets/{organization.public_id}/{dataset.public_id}/v1/manifest.jsonl"
    await storage.put(key=manifest_key, data=b'{"text":"private"}\n', content_type=None)
    preparation.status = PreparationStatus.READY.value
    preparation.artifact_key = manifest_key
    preparation.manifest_checksum = "sha256:deadbeef"
    preparation.manifest_size_bytes = 19
    await session.flush()
    return version.id, manifest_key


# ── Per-sample erasure ───────────────────────────────────────────────────


async def test_erase_sample_removes_row_events_membership_and_audio(
    db_session: AsyncSession,
) -> None:
    organization = await _org(db_session)
    storage = FakeObjectStorage()
    sample = await _sample(db_session, organization, audio_key="speech/o/2026/08/smp_x.wav")
    await storage.put(key=sample.audio_key, data=b"pcm", content_type="audio/wav")
    await SpeechSampleRepository(db_session).record_event(sample.id, "collected")
    version_id, _ = await _frozen_version_with_preparation(db_session, organization, storage)

    report = await ErasureService(db_session, storage).erase_sample(
        organization_public_id=organization.public_id, sample_public_id=sample.public_id
    )

    assert report.samples_erased == 1
    assert report.audio_objects_deleted == 1
    assert sample.audio_key in storage.deletes
    # Row, events, and membership are gone…
    assert (
        await db_session.execute(select(SpeechSample).where(SpeechSample.id == sample.id))
    ).scalar_one_or_none() is None
    events = (
        await db_session.execute(
            select(func.count())
            .select_from(SpeechSampleEvent)
            .where(SpeechSampleEvent.sample_id == sample.id)
        )
    ).scalar_one()
    assert events == 0
    members = (
        await db_session.execute(
            select(func.count())
            .select_from(DatasetVersionSample)
            .where(DatasetVersionSample.dataset_version_id == version_id)
        )
    ).scalar_one()
    assert members == 0
    # …while the frozen aggregate stays as frozen: the honest mismatch
    # the preparation layer will name, never silently rewritten history.
    version = (
        await db_session.execute(select(DatasetVersion).where(DatasetVersion.id == version_id))
    ).scalar_one()
    assert version.sample_count == 1


async def test_erasing_a_member_revokes_the_ready_manifest(db_session: AsyncSession) -> None:
    organization = await _org(db_session)
    storage = FakeObjectStorage()
    sample = await _sample(db_session, organization, audio_key="speech/o/2026/08/smp_m.wav")
    await storage.put(key=sample.audio_key, data=b"pcm", content_type="audio/wav")
    version_id, manifest_key = await _frozen_version_with_preparation(
        db_session, organization, storage
    )

    await ErasureService(db_session, storage).erase_sample(
        organization_public_id=organization.public_id, sample_public_id=sample.public_id
    )

    # The manifest carried the person's transcript — it is gone, and the
    # preparation loudly records why it can never be READY again.
    assert manifest_key in storage.deletes
    preparation = await DatasetRepository(db_session).get_preparation_for_version(version_id)
    assert preparation is not None
    assert preparation.status == PreparationStatus.FAILED.value
    assert preparation.artifact_key is None
    assert preparation.manifest_checksum is None
    assert preparation.manifest_size_bytes is None
    assert {"sample_id": None, "reason": REASON_SAMPLE_ERASED} in preparation.errors


async def test_erase_user_data_targets_only_that_identity(db_session: AsyncSession) -> None:
    organization = await _org(db_session)
    storage = FakeObjectStorage()
    mine = await _sample(
        db_session, organization, user_identifier="key_alice", audio_key="speech/a.wav"
    )
    theirs = await _sample(
        db_session, organization, user_identifier="key_bob", audio_key="speech/b.wav"
    )
    await storage.put(key="speech/a.wav", data=b"a", content_type=None)
    await storage.put(key="speech/b.wav", data=b"b", content_type=None)

    report = await ErasureService(db_session, storage).erase_user_data(
        organization_public_id=organization.public_id, user_identifier="key_alice"
    )

    assert report.samples_erased == 1
    assert report.erased_sample_ids == [mine.public_id]
    remaining = (
        (
            await db_session.execute(
                select(SpeechSample.public_id).where(
                    SpeechSample.organization_id == organization.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert remaining == [theirs.public_id]


async def test_erase_user_data_with_nothing_stored_is_a_clean_zero(
    db_session: AsyncSession,
) -> None:
    # The goal state is "nothing stored", and it already holds — success,
    # not an error, and nothing touches the store.
    organization = await _org(db_session)
    storage = FakeObjectStorage()
    report = await ErasureService(db_session, storage).erase_user_data(
        organization_public_id=organization.public_id, user_identifier="key_ghost"
    )
    assert report.samples_erased == 0
    assert storage.deletes == []


# ── Isolation and honesty ────────────────────────────────────────────────


async def test_cross_org_sample_does_not_exist_for_the_caller(
    db_session: AsyncSession,
) -> None:
    org_a = await _org(db_session, "TenantA")
    org_b = await _org(db_session, "TenantB")
    sample = await _sample(db_session, org_a)
    with pytest.raises(ResourceNotFoundError):
        await ErasureService(db_session, FakeObjectStorage()).erase_sample(
            organization_public_id=org_b.public_id, sample_public_id=sample.public_id
        )


async def test_an_already_erased_sample_is_a_404_on_the_second_run(
    db_session: AsyncSession,
) -> None:
    organization = await _org(db_session)
    storage = FakeObjectStorage()
    sample = await _sample(db_session, organization)
    service = ErasureService(db_session, storage)
    await service.erase_sample(
        organization_public_id=organization.public_id, sample_public_id=sample.public_id
    )
    with pytest.raises(ResourceNotFoundError):
        await service.erase_sample(
            organization_public_id=organization.public_id, sample_public_id=sample.public_id
        )


async def test_unknown_organization_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundError):
        await ErasureService(db_session, FakeObjectStorage()).erase_sample(
            organization_public_id="org_missing", sample_public_id="smp_x"
        )


# ── Storage failure semantics: abort, never "erased" ────────────────────


class DeadDeleteStorage(FakeObjectStorage):
    async def delete(self, *, key: str) -> None:
        raise StorageWriteError(f"delete {key!r} failed: simulated outage")


async def test_unreachable_store_aborts_and_the_row_survives(
    db_session: AsyncSession,
) -> None:
    organization = await _org(db_session)
    storage = DeadDeleteStorage()
    sample = await _sample(db_session, organization, audio_key="speech/dead.wav")
    with pytest.raises(ServiceUnavailableError):
        await ErasureService(db_session, storage).erase_sample(
            organization_public_id=organization.public_id, sample_public_id=sample.public_id
        )
    still_there = (
        await db_session.execute(select(SpeechSample).where(SpeechSample.id == sample.id))
    ).scalar_one_or_none()
    assert still_there is not None


async def test_no_storage_seam_means_erasure_is_honestly_unavailable(
    db_session: AsyncSession,
) -> None:
    organization = await _org(db_session)
    sample = await _sample(db_session, organization)
    with pytest.raises(ServiceUnavailableError):
        await ErasureService(db_session, None).erase_sample(
            organization_public_id=organization.public_id, sample_public_id=sample.public_id
        )


# ── Organization erasure ─────────────────────────────────────────────────


async def test_erase_organization_keeps_the_anonymized_row_and_revokes_keys(
    db_session: AsyncSession,
) -> None:
    organizations = OrganizationRepository(db_session)
    organization = await organizations.create("Doomed Co")
    organization.data_consent = True
    storage = FakeObjectStorage()

    sample = await _sample(db_session, organization, audio_key="speech/doomed.wav")
    await storage.put(key=sample.audio_key, data=b"pcm", content_type=None)
    _version_id, manifest_key = await _frozen_version_with_preparation(
        db_session, organization, storage
    )
    user = await UserRepository(db_session).create("owner@doomed.example", "Owner")
    await organizations.add_member(organization.id, user.id, MembershipRole.OWNER)
    await ApiKeyRepository(db_session).add(
        organization_id=organization.id,
        name="pilot",
        prefix="ik_live_deadbeef",
        last4="beef",
        key_hash="0" * 64,
    )

    report = await ErasureService(db_session, storage).erase_organization(
        organization_public_id=organization.public_id
    )

    assert report.samples_erased == 1
    assert report.manifests_revoked == 1
    assert report.datasets_deleted == 1
    assert report.api_keys_revoked == 1
    assert report.memberships_removed == 1
    assert report.organization_anonymized is True
    assert sample.audio_key in storage.deletes
    assert manifest_key in storage.deletes

    # The org row SURVIVES — anonymized — because the usage ledger's
    # RESTRICT demands it: data dies, the commercial skeleton remains.
    survivor = await organizations.get_by_public_id(organization.public_id)
    assert survivor is not None
    assert survivor.name == ERASED_ORGANIZATION_NAME
    assert survivor.data_consent is False
    assert survivor.consent_reference is None

    memberships = (
        await db_session.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == organization.id)
        )
    ).scalar_one()
    assert memberships == 0
    keys = await ApiKeyRepository(db_session).list_for_organization(organization.id)
    assert all(key.revoked_at is not None for key in keys)
    # The operator's user row is deliberately untouched (may belong to
    # other tenants); documented limitation in DATA_GOVERNANCE.md.
    assert await UserRepository(db_session).get_by_email("owner@doomed.example") is not None
