"""Speech sample storage: the flywheel's rows and their append-only history.

Schema-level tests pin the locked design (enums, defaults, indexes,
cascade direction); repository tests pin the behavior every later commit
builds on (org scoping, birth state, event append).
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.time import utc_now
from intelliai_api.db.base import Base
from intelliai_api.db.models import (
    ClientSource,
    Organization,
    SampleStatus,
    SpeechSample,
    SpeechSampleEvent,
)
from intelliai_api.db.repositories import OrganizationRepository, SpeechSampleRepository

pytestmark = pytest.mark.anyio


async def _sample(
    session: AsyncSession, organization: Organization, **overrides: object
) -> SpeechSample:
    defaults: dict[str, object] = {
        "organization_id": organization.id,
        "audio_key": f"{organization.public_id}/2026-08/audio.webm",
        "duration_seconds": Decimal("4.250"),
        "file_size_bytes": 68_412,
        "original_transcript": "hello everyone",
        "model_name": "whisper-small",
        "model_version": "1",
        "client_source": ClientSource.WEB,
        "user_identifier": "key_test",
        "consented_at": utc_now(),
        "consent_reference": "doc-v1",
    }
    defaults.update(overrides)
    return await SpeechSampleRepository(session).create(**defaults)  # type: ignore[arg-type]


# ── Schema: the locked design, pinned ────────────────────────────────────


def test_both_tables_are_registered() -> None:
    assert "speech_samples" in Base.metadata.tables
    assert "speech_sample_events" in Base.metadata.tables


def test_the_status_enum_is_native_and_carries_the_locked_vocabulary() -> None:
    column = Base.metadata.tables["speech_samples"].c.status
    assert column.type.name == "sample_status"  # type: ignore[attr-defined]
    assert set(column.type.enums) == {  # type: ignore[attr-defined]
        "collected",
        "validated",
        "accepted",
        "rejected",
        "training",
        "archived",
    }
    assert [m.value for m in SampleStatus] == list(column.type.enums)  # type: ignore[attr-defined]


def test_the_client_source_enum_is_native_and_closed() -> None:
    # Adding a surface is a REVIEWED diff to this set plus a migration
    # (M27 added ios-keyboard with a3f8c2d94e61) — never drift.
    column = Base.metadata.tables["speech_samples"].c.client_source
    assert column.type.name == "client_source"  # type: ignore[attr-defined]
    assert set(column.type.enums) == {  # type: ignore[attr-defined]
        "web",
        "keyboard",
        "api",
        "ios-keyboard",
    }


def test_samples_cascade_with_their_tenant_and_events_with_their_sample() -> None:
    # CASCADE, deliberately opposite to the billing ledger's RESTRICT:
    # collected data never outlives its tenant.
    samples = Base.metadata.tables["speech_samples"]
    events = Base.metadata.tables["speech_sample_events"]
    (org_fk,) = [fk for fk in samples.foreign_keys if fk.column.table.name == "organizations"]
    assert org_fk.ondelete == "CASCADE"
    (sample_fk,) = [fk for fk in events.foreign_keys if fk.column.table.name == "speech_samples"]
    assert sample_fk.ondelete == "CASCADE"


def test_the_locked_indexes_exist() -> None:
    sample_indexes = {i.name for i in Base.metadata.tables["speech_samples"].indexes}
    event_indexes = {i.name for i in Base.metadata.tables["speech_sample_events"].indexes}
    assert "ix_speech_samples_organization_id_created_at" in sample_indexes
    assert "ix_speech_sample_events_sample_id_occurred_at" in event_indexes


def test_the_event_table_is_deliberately_minimal() -> None:
    # Append-only history: no public_id (never projected), no updated_at
    # (appends have no updates). If this grows columns, it is growing
    # toward a workflow engine — which is banned.
    columns = set(Base.metadata.tables["speech_sample_events"].c.keys())
    assert columns == {"id", "sample_id", "event", "detail", "occurred_at"}


# ── Repository behavior ──────────────────────────────────────────────────


async def test_a_sample_is_born_collected_with_current_equal_to_original(
    db_session: AsyncSession,
) -> None:
    organization = await OrganizationRepository(db_session).create("FlywheelCo")
    sample = await _sample(db_session, organization)

    assert sample.public_id.startswith("smp_")
    assert sample.status is SampleStatus.COLLECTED
    assert sample.original_transcript == "hello everyone"
    assert sample.current_transcript == "hello everyone"  # by rule, not by caller
    assert sample.last_modified_at is None
    assert sample.lineage == {}
    assert sample.consent_reference == "doc-v1"


async def test_fetch_is_organization_scoped(db_session: AsyncSession) -> None:
    organizations = OrganizationRepository(db_session)
    mine = await organizations.create("Mine")
    theirs = await organizations.create("Theirs")
    sample = await _sample(db_session, mine)

    repository = SpeechSampleRepository(db_session)
    assert await repository.get_for_organization(mine.id, sample.public_id) is not None
    # A foreign org's sample does not exist from this caller's view:
    assert await repository.get_for_organization(theirs.id, sample.public_id) is None


async def test_listing_returns_newest_first_and_respects_the_limit(
    db_session: AsyncSession,
) -> None:
    organization = await OrganizationRepository(db_session).create("ListCo")
    first = await _sample(db_session, organization)
    second = await _sample(db_session, organization)
    third = await _sample(db_session, organization)

    listed = await SpeechSampleRepository(db_session).list_for_organization(
        organization.id, limit=2
    )
    assert [s.public_id for s in listed] == [third.public_id, second.public_id]
    assert first.public_id not in {s.public_id for s in listed}


async def test_events_append_in_order_with_defaults(db_session: AsyncSession) -> None:
    organization = await OrganizationRepository(db_session).create("EventCo")
    sample = await _sample(db_session, organization)
    repository = SpeechSampleRepository(db_session)

    collected = await repository.record_event(sample.id, "collected")
    corrected = await repository.record_event(
        sample.id, "corrected", detail={"by": "user", "length": 14}
    )

    assert collected.detail == {}
    assert collected.occurred_at is not None
    assert corrected.detail == {"by": "user", "length": 14}
    rows = (
        (
            await db_session.execute(
                select(SpeechSampleEvent)
                .where(SpeechSampleEvent.sample_id == sample.id)
                .order_by(SpeechSampleEvent.occurred_at)
            )
        )
        .scalars()
        .all()
    )
    assert [row.event for row in rows] == ["collected", "corrected"]


async def test_deleting_the_tenant_cascades_through_samples_and_events(
    db_session: AsyncSession,
) -> None:
    # Privacy-first: collected data must never outlive its tenant. The
    # cascade is database-enforced, not ORM politeness.
    organization = await OrganizationRepository(db_session).create("GoneCo")
    sample = await _sample(db_session, organization)
    await SpeechSampleRepository(db_session).record_event(sample.id, "collected")
    sample_id = sample.id

    await db_session.delete(organization)
    await db_session.flush()
    db_session.expunge_all()

    remaining_samples = (
        (await db_session.execute(select(SpeechSample).where(SpeechSample.id == sample_id)))
        .scalars()
        .all()
    )
    remaining_events = (
        (
            await db_session.execute(
                select(SpeechSampleEvent).where(SpeechSampleEvent.sample_id == sample_id)
            )
        )
        .scalars()
        .all()
    )
    assert remaining_samples == []
    assert remaining_events == []
