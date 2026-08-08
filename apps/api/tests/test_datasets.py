"""Dataset storage: definitions, immutable versions, frozen membership.

Schema tests pin the locked design (enum, cascades, uniqueness);
repository tests pin the laws every later commit builds on: ONE
eligibility query feeding both preview and freeze, membership frozen
with pinned training text, later corrections and new samples changing
nothing behind an existing version, and sample-side lineage events.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.time import utc_now
from intelliai_api.db.base import Base
from intelliai_api.db.models import (
    ClientSource,
    DatasetStatus,
    Organization,
    SampleStatus,
    SpeechSample,
    SpeechSampleEvent,
)
from intelliai_api.db.repositories import (
    DatasetRepository,
    OrganizationRepository,
    SpeechSampleRepository,
)
from intelliai_api.db.repositories.datasets import INCLUDED_IN_DATASET, DatasetCriteria

pytestmark = pytest.mark.anyio


async def _sample(
    session: AsyncSession, organization: Organization, **overrides: object
) -> SpeechSample:
    # Birth state is the repository's law (collected, current == original);
    # status and current_transcript overrides are applied as the later
    # lifecycle transitions they would really be.
    status = overrides.pop("status", None)
    current_transcript = overrides.pop("current_transcript", None)
    defaults: dict[str, object] = {
        "organization_id": organization.id,
        "audio_key": f"{organization.public_id}/2026-08/audio.webm",
        "duration_seconds": Decimal("4.250"),
        "file_size_bytes": 68_412,
        "original_transcript": "hello everyone",
        "model_name": "whisper-small",
        "client_source": ClientSource.WEB,
        "user_identifier": "key_test",
        "consented_at": utc_now(),
        "consent_reference": "doc-v1",
    }
    defaults.update(overrides)
    sample = await SpeechSampleRepository(session).create(**defaults)  # type: ignore[arg-type]
    if status is not None:
        assert isinstance(status, SampleStatus)
        sample.status = status
    if current_transcript is not None:
        assert isinstance(current_transcript, str)
        sample.current_transcript = current_transcript
    if status is not None or current_transcript is not None:
        await session.flush()
    return sample


async def _corrected(session: AsyncSession, sample: SpeechSample, text: str) -> None:
    sample.current_transcript = text
    sample.last_modified_at = utc_now()
    await session.flush()


# ── Schema: the locked design, pinned ────────────────────────────────────


def test_the_three_tables_are_registered() -> None:
    for table in ("datasets", "dataset_versions", "dataset_version_samples"):
        assert table in Base.metadata.tables


def test_the_dataset_status_enum_is_native_and_closed() -> None:
    column = Base.metadata.tables["datasets"].c.status
    assert column.type.name == "dataset_status"  # type: ignore[attr-defined]
    assert set(column.type.enums) == {"active", "archived"}  # type: ignore[attr-defined]
    assert [m.value for m in DatasetStatus] == list(column.type.enums)  # type: ignore[attr-defined]


def test_everything_cascades_toward_the_tenant() -> None:
    # Derived views of collected data never outlive their tenant, their
    # dataset, or their sample — erasure anywhere shrinks honestly.
    datasets = Base.metadata.tables["datasets"]
    versions = Base.metadata.tables["dataset_versions"]
    membership = Base.metadata.tables["dataset_version_samples"]
    assert next(iter(datasets.c.organization_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(versions.c.dataset_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(membership.c.dataset_version_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(membership.c.speech_sample_id.foreign_keys)).ondelete == "CASCADE"


def test_membership_and_version_numbers_are_unique() -> None:
    # The same sample cannot join a version twice, and a version number
    # is citable forever — both enforced by the database, not by hope.
    versions = Base.metadata.tables["dataset_versions"]
    membership = Base.metadata.tables["dataset_version_samples"]
    version_uniques = {
        tuple(constraint.columns.keys())
        for constraint in versions.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    member_uniques = {
        tuple(constraint.columns.keys())
        for constraint in membership.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("dataset_id", "version_number") in version_uniques
    assert ("dataset_version_id", "speech_sample_id") in member_uniques


# ── Eligibility: one query, computed from database state only ───────────


async def test_eligibility_excludes_what_cannot_be_trained_on(db_session: AsyncSession) -> None:
    organization = await OrganizationRepository(db_session).create("EligibilityCo")
    good = await _sample(db_session, organization)
    for status in (SampleStatus.VALIDATED, SampleStatus.ACCEPTED, SampleStatus.TRAINING):
        await _sample(db_session, organization, status=status)
    await _sample(db_session, organization, status=SampleStatus.REJECTED)
    await _sample(db_session, organization, status=SampleStatus.ARCHIVED)
    await _sample(db_session, organization, current_transcript="   ")  # no usable text
    await _sample(db_session, organization, file_size_bytes=0)  # no audio bytes
    await _sample(db_session, organization, duration_seconds=Decimal("0"))  # no audio time
    empty_current = await _sample(db_session, organization)
    await _corrected(db_session, empty_current, "")  # corrected INTO uselessness

    repository = DatasetRepository(db_session)
    preview = await repository.preview(organization.id, DatasetCriteria())

    # collected + validated + accepted + training survive; rejected,
    # archived, blank-transcript, zero-byte and zero-second audio do not.
    assert preview.eligible_samples == 4
    assert preview.matching_samples == 10  # everything matched the (empty) criteria
    assert preview.duration_seconds == Decimal("17.000")
    assert good.status is SampleStatus.COLLECTED


async def test_criteria_filter_language_client_corrected_and_dates(
    db_session: AsyncSession,
) -> None:
    organization = await OrganizationRepository(db_session).create("CriteriaCo")
    hindi_keyboard = await _sample(
        db_session,
        organization,
        detected_language="hi",
        client_source=ClientSource.KEYBOARD,
    )
    await _corrected(db_session, hindi_keyboard, "नमस्ते सब")
    await _sample(db_session, organization, detected_language="hi", client_source=ClientSource.WEB)
    # No detected language: the requested one is the honest fallback —
    # exactly how the console presents a sample's language.
    await _sample(
        db_session,
        organization,
        detected_language=None,
        requested_language="hi",
        client_source=ClientSource.KEYBOARD,
    )
    await _sample(
        db_session, organization, detected_language="en", client_source=ClientSource.KEYBOARD
    )

    repository = DatasetRepository(db_session)

    hindi = await repository.preview(organization.id, DatasetCriteria(language="hi"))
    assert hindi.eligible_samples == 3

    hindi_kb = await repository.preview(
        organization.id,
        DatasetCriteria(language="hi", client_source=ClientSource.KEYBOARD),
    )
    assert hindi_kb.eligible_samples == 2

    corrected_only = await repository.preview(organization.id, DatasetCriteria(corrected=True))
    assert corrected_only.eligible_samples == 1
    uncorrected_only = await repository.preview(organization.id, DatasetCriteria(corrected=False))
    assert uncorrected_only.eligible_samples == 3

    # Date criteria read as whole UTC days, boundaries included.
    old = await _sample(db_session, organization, detected_language="en")
    old.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    await db_session.flush()
    january = await repository.preview(
        organization.id,
        DatasetCriteria(collected_from=date(2026, 1, 1), collected_until=date(2026, 1, 31)),
    )
    assert january.eligible_samples == 1


async def test_preview_and_freeze_are_the_same_truth(db_session: AsyncSession) -> None:
    # The consistency law: what the preview promises is exactly what the
    # freeze delivers, because both are built from ONE eligibility query.
    organization = await OrganizationRepository(db_session).create("ConsistencyCo")
    for language in ("hi", "hi", "en"):
        await _sample(db_session, organization, detected_language=language)
    await _sample(db_session, organization, detected_language="hi", file_size_bytes=0)

    repository = DatasetRepository(db_session)
    criteria = DatasetCriteria(language="hi")
    preview = await repository.preview(organization.id, criteria)

    dataset = await repository.create(
        organization_id=organization.id, name="Hindi v1", description=None, criteria=criteria
    )
    version = await repository.create_version(
        dataset_id=dataset.id, version_number=1, created_by="key_test", criteria=criteria
    )
    await repository.freeze_membership(version.id, organization.id, criteria)
    statistics = await repository.membership_statistics(version.id)

    assert preview.eligible_samples == 2
    assert statistics.sample_count == preview.eligible_samples
    assert statistics.duration_seconds == preview.duration_seconds
    assert [(s.key, s.samples) for s in statistics.languages] == [
        (s.key, s.samples) for s in preview.languages
    ]


async def test_a_frozen_version_never_changes(db_session: AsyncSession) -> None:
    # THE immutability law. New eligible samples and later corrections
    # leave the old version's membership and pinned text untouched; the
    # next version picks both up.
    organization = await OrganizationRepository(db_session).create("FrozenCo")
    original = await _sample(db_session, organization, original_transcript="hello everyone")

    repository = DatasetRepository(db_session)
    criteria = DatasetCriteria()
    dataset = await repository.create(
        organization_id=organization.id, name="All speech", description=None, criteria=criteria
    )
    v1 = await repository.create_version(
        dataset_id=dataset.id, version_number=1, created_by="key_test", criteria=criteria
    )
    await repository.freeze_membership(v1.id, organization.id, criteria)

    # The world moves on: a new sample arrives, the old one is corrected.
    await _sample(db_session, organization, original_transcript="a new sample")
    await _corrected(db_session, original, "hello everyone, corrected")

    v1_members = await repository.sample_ids_for_version(v1.id)
    v1_stats = await repository.membership_statistics(v1.id)
    assert v1_members == [original.id]
    assert v1_stats.sample_count == 1
    # The pinned training text is the text at freeze time — the later
    # correction did not rewrite history…
    pinned = (
        await db_session.execute(
            select(Base.metadata.tables["dataset_version_samples"].c.training_transcript).where(
                Base.metadata.tables["dataset_version_samples"].c.dataset_version_id == v1.id
            )
        )
    ).scalar_one()
    assert pinned == "hello everyone"
    # …and the frozen corrected-count still reads the FROZEN text, so it
    # reports 0 even though the sample is corrected NOW.
    assert v1_stats.corrected_samples == 0

    v2 = await repository.create_version(
        dataset_id=dataset.id, version_number=2, created_by="key_test", criteria=criteria
    )
    await repository.freeze_membership(v2.id, organization.id, criteria)
    v2_stats = await repository.membership_statistics(v2.id)
    v2_texts = set(
        (
            await db_session.execute(
                select(Base.metadata.tables["dataset_version_samples"].c.training_transcript).where(
                    Base.metadata.tables["dataset_version_samples"].c.dataset_version_id == v2.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert v2_stats.sample_count == 2
    assert v2_stats.corrected_samples == 1
    assert "hello everyone, corrected" in v2_texts


async def test_freezing_appends_lineage_to_each_member_sample(db_session: AsyncSession) -> None:
    organization = await OrganizationRepository(db_session).create("LineageCo")
    sample = await _sample(db_session, organization)

    repository = DatasetRepository(db_session)
    criteria = DatasetCriteria()
    dataset = await repository.create(
        organization_id=organization.id, name="Lineage", description=None, criteria=criteria
    )
    version = await repository.create_version(
        dataset_id=dataset.id, version_number=1, created_by="key_test", criteria=criteria
    )
    await repository.freeze_membership(version.id, organization.id, criteria)
    await repository.record_inclusion_events(
        version.id,
        detail={
            "dataset_id": dataset.public_id,
            "dataset_version_id": version.public_id,
            "version_number": 1,
        },
        occurred_at=utc_now(),
    )

    events = (
        (
            await db_session.execute(
                select(SpeechSampleEvent).where(
                    SpeechSampleEvent.sample_id == sample.id,
                    SpeechSampleEvent.event == INCLUDED_IN_DATASET,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].detail["dataset_version_id"] == version.public_id
    # Participation is an EVENT; the sample's status is deliberately not
    # rewritten — ``training`` belongs to actual future training runs.
    assert sample.status is SampleStatus.COLLECTED


async def test_datasets_and_eligibility_are_organization_scoped(
    db_session: AsyncSession,
) -> None:
    organizations = OrganizationRepository(db_session)
    mine = await organizations.create("MineCo")
    theirs = await organizations.create("TheirsCo")
    await _sample(db_session, mine)
    await _sample(db_session, theirs)
    await _sample(db_session, theirs)

    repository = DatasetRepository(db_session)
    dataset = await repository.create(
        organization_id=mine.id, name="Mine", description=None, criteria=DatasetCriteria()
    )

    # A foreign org's dataset does not exist here…
    assert await repository.get_for_organization(theirs.id, dataset.public_id) is None
    assert [d.id for d in await repository.list_for_organization(mine.id)] == [dataset.id]

    # …and a freeze can only ever contain the owner's samples.
    version = await repository.create_version(
        dataset_id=dataset.id, version_number=1, created_by="key_test", criteria=DatasetCriteria()
    )
    await repository.freeze_membership(version.id, mine.id, DatasetCriteria())
    members = await repository.sample_ids_for_version(version.id)
    owners = (
        (
            await db_session.execute(
                select(SpeechSample.organization_id).where(SpeechSample.id.in_(members))
            )
        )
        .scalars()
        .all()
    )
    assert len(members) == 1
    assert set(owners) == {mine.id}


def test_criteria_round_trip_through_storage() -> None:
    # to_dict/from_dict is how criteria survive the JSONB column; the
    # round trip must be lossless or versions would freeze the wrong set.
    criteria = DatasetCriteria(
        language="hi",
        client_source=ClientSource.KEYBOARD,
        corrected=True,
        collected_from=date(2026, 1, 1),
        collected_until=date(2026, 6, 30),
    )
    assert DatasetCriteria.from_dict(criteria.to_dict()) == criteria
    assert DatasetCriteria.from_dict({}) == DatasetCriteria()
    # Unset criteria are omitted from storage, never null-padded.
    assert DatasetCriteria(language="hi").to_dict() == {"language": "hi"}
