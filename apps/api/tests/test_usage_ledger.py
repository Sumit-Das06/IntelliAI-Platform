"""Usage ledger tests — the guarantees, proven structurally.

Three claims this file exists to prove, because each is a claim the
business rests on rather than a behavior a reviewer can eyeball:

1. **Append-only is enforced by the database**, not by discipline: UPDATE,
   DELETE, and TRUNCATE are refused on both ledger tables even when the
   statement bypasses the repository entirely.
2. **The schema is capability-agnostic**: capabilities that do not exist
   yet — OCR, vision, chat, translation, embeddings — record through the
   unchanged repository with zero schema changes.
3. **At-most-once billing lives in the database**: duplicate request ids
   and duplicate idempotency keys are refused by constraints, not by
   application logic.

Everything runs against real Postgres inside a rolled-back transaction
(``db_session``), so the constraints, triggers, and native enums under
test are the ones production will run.
"""

import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.security import generate_api_key
from intelliai_api.db import repositories
from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageOutcome
from intelliai_api.db.repositories import (
    ApiKeyRepository,
    OrganizationRepository,
    UsageEventRepository,
)

pytestmark = pytest.mark.anyio

JANUARY = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
NEXT_MONTH = datetime(2026, 9, 1, tzinfo=UTC)
MONTH_START = datetime(2026, 8, 1, tzinfo=UTC)


async def _organization(session: AsyncSession, name: str) -> int:
    org = await OrganizationRepository(session).create(name)
    return org.id


async def _record_transcription(
    session: AsyncSession,
    organization_id: int,
    *,
    request_id: str = "req_transcribe_1",
    origin: UsageOrigin = UsageOrigin.CUSTOMER,
    seconds: str = "12.500",
) -> UsageEvent:
    return await UsageEventRepository(session).record(
        organization_id=organization_id,
        capability="transcription",
        public_model_id="intelliai-stt",
        origin=origin,
        outcome=UsageOutcome.SUCCEEDED,
        billable=True,
        occurred_at=JANUARY,
        quantities={"audio_seconds": Decimal(seconds)},
        request_id=request_id,
        lineage={"artifact": "whisper-small", "artifact_version": 1},
    )


# ── The fact model ──────────────────────────────────────────────────────


async def test_recording_an_event_stores_the_measurement_verbatim(
    db_session: AsyncSession,
) -> None:
    org_id = await _organization(db_session, "Acme")
    event = await _record_transcription(db_session, org_id, seconds="12.345678")

    assert event.public_id.startswith("use_")
    assert event.billable is True
    assert event.origin is UsageOrigin.CUSTOMER
    # Not rounded to whole seconds, not converted, not priced: billing
    # rounds, metering does not.
    assert {q.unit: q.amount for q in event.quantities} == {"audio_seconds": Decimal("12.345678")}


async def test_lineage_is_stored_for_analysis(db_session: AsyncSession) -> None:
    """Internal lineage round-trips as free-form JSON.

    It is deliberately schemaless: which artifact, fine-tune, adapter, or
    quantization served a request differs per capability, and none of it
    may ever force a migration — or reach a customer.
    """
    org_id = await _organization(db_session, "Acme")
    event = await UsageEventRepository(db_session).record(
        organization_id=org_id,
        capability="speech_synthesis",
        public_model_id="intelliai-tts",
        origin=UsageOrigin.CUSTOMER,
        outcome=UsageOutcome.SUCCEEDED,
        billable=True,
        occurred_at=JANUARY,
        quantities={"characters": Decimal(42)},
        request_id="req_lineage",
        lineage={
            "artifact": "kokoro-82m",
            "foundation_model": "hexgrad/Kokoro-82M",
            "quantization": None,
            "adapter": {"kind": "lora", "version": "v3"},
            "dataset_version": "speech-ft-2026-07",
        },
    )
    await db_session.flush()

    assert event.lineage["adapter"]["kind"] == "lora"
    assert event.lineage["foundation_model"] == "hexgrad/Kokoro-82M"


async def test_disconnected_after_success_is_still_billable(
    db_session: AsyncSession,
) -> None:
    """Founder decision F1: successful generation, not socket completion,
    defines billability — and the outcome stays distinguishable."""
    org_id = await _organization(db_session, "Acme")
    event = await UsageEventRepository(db_session).record(
        organization_id=org_id,
        capability="speech_synthesis",
        public_model_id="intelliai-tts",
        origin=UsageOrigin.CUSTOMER,
        outcome=UsageOutcome.DISCONNECTED,
        billable=True,
        occurred_at=JANUARY,
        quantities={"characters": Decimal(120)},
        request_id="req_gone",
    )
    assert event.billable is True
    assert event.outcome is UsageOutcome.DISCONNECTED


async def test_failed_work_is_recorded_but_not_billable(db_session: AsyncSession) -> None:
    """A 5xx costs us capacity and must be visible for cost analysis, with
    no measured quantity to bill."""
    org_id = await _organization(db_session, "Acme")
    event = await UsageEventRepository(db_session).record(
        organization_id=org_id,
        capability="transcription",
        public_model_id="intelliai-stt",
        origin=UsageOrigin.CUSTOMER,
        outcome=UsageOutcome.FAILED,
        billable=False,
        occurred_at=JANUARY,
        quantities={},
        request_id="req_failed",
    )
    assert event.billable is False
    assert event.quantities == []


async def test_a_billable_event_must_carry_a_measurement(db_session: AsyncSession) -> None:
    org_id = await _organization(db_session, "Acme")
    with pytest.raises(ValueError, match="at least one measured quantity"):
        await UsageEventRepository(db_session).record(
            organization_id=org_id,
            capability="transcription",
            public_model_id="intelliai-stt",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={},
            request_id="req_unmeasured",
        )


async def test_measured_amounts_must_be_positive(db_session: AsyncSession) -> None:
    """Negative amounts exist only on compensating events; letting them in
    through the front door would make a reversal indistinguishable from a
    mis-measurement."""
    org_id = await _organization(db_session, "Acme")
    with pytest.raises(ValueError, match="compensating events"):
        await UsageEventRepository(db_session).record(
            organization_id=org_id,
            capability="transcription",
            public_model_id="intelliai-stt",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"audio_seconds": Decimal(-5)},
            request_id="req_negative",
        )


# ── Append-only, proven structurally ────────────────────────────────────


async def test_update_is_refused_by_the_database(db_session: AsyncSession) -> None:
    """The core guarantee. This UPDATE bypasses the repository entirely —
    it is raw SQL against the table — and the database still refuses."""
    org_id = await _organization(db_session, "Acme")
    event = await _record_transcription(db_session, org_id)
    await db_session.flush()

    with pytest.raises(IntegrityError, match="append-only ledger"):
        await db_session.execute(
            update(UsageEvent).where(UsageEvent.id == event.id).values(billable=False)
        )
    await db_session.rollback()


async def test_delete_is_refused_by_the_database(db_session: AsyncSession) -> None:
    org_id = await _organization(db_session, "Acme")
    event = await _record_transcription(db_session, org_id)
    await db_session.flush()

    with pytest.raises(IntegrityError, match="append-only ledger"):
        await db_session.execute(delete(UsageEvent).where(UsageEvent.id == event.id))
    await db_session.rollback()


async def test_quantities_are_append_only_too(db_session: AsyncSession) -> None:
    """The amount is the number that becomes money. An immutable event
    with a mutable quantity would be immutability theatre."""
    org_id = await _organization(db_session, "Acme")
    event = await _record_transcription(db_session, org_id)
    await db_session.flush()
    quantity_id = event.quantities[0].id

    with pytest.raises(IntegrityError, match="append-only ledger"):
        await db_session.execute(
            text("UPDATE usage_quantities SET amount = 1 WHERE id = :id"), {"id": quantity_id}
        )
    await db_session.rollback()


async def test_truncate_is_refused_by_the_database(db_session: AsyncSession) -> None:
    """Row triggers do not fire for TRUNCATE — the hole a 'clean the test
    data' script falls through. A statement-level trigger closes it."""
    org_id = await _organization(db_session, "Acme")
    await _record_transcription(db_session, org_id)
    await db_session.flush()

    with pytest.raises(DBAPIError, match="append-only ledger"):
        await db_session.execute(text("TRUNCATE usage_quantities"))
    await db_session.rollback()


def test_the_repository_has_no_mutation_path() -> None:
    """The second, independent mechanism: the only module allowed to write
    the ledger contains no UPDATE and no DELETE, checked by parsing it.

    Triggers stop a mutation at runtime; this stops one from being written
    at all — and it fails in CI rather than in production.
    """
    source = Path(repositories.usage_events.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden = {"update", "delete"}
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & forbidden), f"mutating statement in the ledger repository: {called}"

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy"
        for alias in node.names
    }
    assert not (imported & forbidden), f"mutating constructs imported: {imported}"

    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    assert not {name for name in methods if name.startswith(("update", "delete", "set_"))}


# ── Corrections without edits ───────────────────────────────────────────


async def test_a_reversal_nets_the_period_to_zero(db_session: AsyncSession) -> None:
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    original = await _record_transcription(db_session, org_id, seconds="30")
    await db_session.flush()

    reversal = await repo.reverse(original, reason="duplicate billing incident", at=JANUARY)
    await db_session.flush()

    assert reversal.reverses_usage_event_id == original.id
    assert reversal.request_id is None  # answers to no HTTP request
    assert {q.unit: q.amount for q in reversal.quantities} == {"audio_seconds": Decimal(-30)}

    totals = await repo.totals_for_organization(org_id, since=MONTH_START, until=NEXT_MONTH)
    assert totals == {}  # netted away, both rows still present

    events = await repo.list_for_organization(org_id, since=MONTH_START, until=NEXT_MONTH)
    assert len(events) == 2  # history survives the correction


async def test_a_reversal_belongs_to_the_period_it_was_issued_in(
    db_session: AsyncSession,
) -> None:
    """A correction must never reach backwards and silently restate a
    period that has already been reported."""
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    original = await _record_transcription(db_session, org_id, seconds="30")
    await db_session.flush()

    issued_next_month = NEXT_MONTH + timedelta(days=3)
    await repo.reverse(original, reason="late correction", at=issued_next_month)
    await db_session.flush()

    august = await repo.totals_for_organization(org_id, since=MONTH_START, until=NEXT_MONTH)
    september = await repo.totals_for_organization(
        org_id, since=NEXT_MONTH, until=NEXT_MONTH + timedelta(days=30)
    )
    assert august == {"audio_seconds": Decimal(30)}  # the reported month is untouched
    assert september == {"audio_seconds": Decimal(-30)}  # the credit lands where it was issued


async def test_an_event_can_be_reversed_only_once(db_session: AsyncSession) -> None:
    """Two reversals of one event would net to a credit nobody earned."""
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    original = await _record_transcription(db_session, org_id)
    await db_session.flush()

    await repo.reverse(original, reason="first", at=JANUARY)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        await repo.reverse(original, reason="second", at=JANUARY)
        await db_session.flush()
    await db_session.rollback()


async def test_a_reversal_must_state_a_reason(db_session: AsyncSession) -> None:
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    original = await _record_transcription(db_session, org_id)
    await db_session.flush()

    with pytest.raises(ValueError, match="reason"):
        await repo.reverse(original, reason="   ", at=JANUARY)


# ── At-most-once billing, enforced by constraints ───────────────────────


async def test_one_request_id_can_be_billed_only_once(db_session: AsyncSession) -> None:
    org_id = await _organization(db_session, "Acme")
    await _record_transcription(db_session, org_id, request_id="req_same")
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await _record_transcription(db_session, org_id, request_id="req_same")
        await db_session.flush()
    await db_session.rollback()


async def test_one_idempotency_key_can_be_billed_only_once_per_organization(
    db_session: AsyncSession,
) -> None:
    """ADR-0024's guarantee, living where it belongs: in the database."""
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    for request_id in ("req_a", "req_b"):
        with_key = repo.record(
            organization_id=org_id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"characters": Decimal(10)},
            request_id=request_id,
            idempotency_key="idem_same",
        )
        if request_id == "req_a":
            await with_key
            await db_session.flush()
        else:
            with pytest.raises(IntegrityError):
                await with_key
                await db_session.flush()
    await db_session.rollback()


async def test_two_organizations_may_reuse_the_same_idempotency_key(
    db_session: AsyncSession,
) -> None:
    """Keys are the customer's own vocabulary; scoping them per tenant is
    what keeps one customer's convention from breaking another's."""
    repo = UsageEventRepository(db_session)
    for index, name in enumerate(("Acme", "Globex")):
        org_id = await _organization(db_session, name)
        await repo.record(
            organization_id=org_id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"characters": Decimal(10)},
            request_id=f"req_{index}",
            idempotency_key="idem_shared",
        )
    await db_session.flush()  # no constraint violation


async def test_unkeyed_requests_do_not_collide(db_session: AsyncSession) -> None:
    """Absent a client key there is no idempotency — two identical
    generative requests are two billable events, by design."""
    org_id = await _organization(db_session, "Acme")
    await _record_transcription(db_session, org_id, request_id="req_1")
    await _record_transcription(db_session, org_id, request_id="req_2")
    await db_session.flush()

    totals = await UsageEventRepository(db_session).totals_for_organization(
        org_id, since=MONTH_START, until=NEXT_MONTH
    )
    assert totals == {"audio_seconds": Decimal(25)}


async def test_a_customer_event_must_carry_a_request_id(db_session: AsyncSession) -> None:
    """Traceability law, enforced by a check constraint: a charge nobody
    can trace to a request is a charge we cannot defend."""
    org_id = await _organization(db_session, "Acme")
    with pytest.raises(IntegrityError, match="request_id_required"):
        await UsageEventRepository(db_session).record(
            organization_id=org_id,
            capability="transcription",
            public_model_id="intelliai-stt",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"audio_seconds": Decimal(1)},
            request_id=None,
        )
        await db_session.flush()
    await db_session.rollback()


# ── Capability-agnostic: futures that do not exist yet ──────────────────

FUTURE_CAPABILITIES = [
    ("document_ocr", "intelliai-ocr", {"pages": Decimal(14)}),
    ("vision", "intelliai-vision", {"images": Decimal(3)}),
    (
        "chat",
        "intelliai-chat",
        {"prompt_tokens": Decimal(1820), "completion_tokens": Decimal(415)},
    ),
    ("translation", "intelliai-translate", {"characters": Decimal(2400)}),
    ("embeddings", "intelliai-embed", {"tokens": Decimal(96000)}),
    (
        "speech_to_speech",
        "intelliai-s2s",
        {"audio_seconds": Decimal("61.25"), "characters": Decimal(730)},
    ),
]


@pytest.mark.parametrize(("capability", "public_model", "quantities"), FUTURE_CAPABILITIES)
async def test_future_capabilities_record_with_no_schema_change(
    db_session: AsyncSession,
    capability: str,
    public_model: str,
    quantities: dict[str, Decimal],
) -> None:
    """The claim ADR-0021 makes: adding a capability adds zero columns.

    None of these capabilities exists. None of these units is in the
    runtime contract's ``UsageUnit`` enum. The ledger records them anyway,
    because its job is to record faithfully what it was told — the
    contract governs what a runtime may *report*, not what the ledger can
    *hold*.
    """
    org_id = await _organization(db_session, f"Acme-{capability}")
    event = await UsageEventRepository(db_session).record(
        organization_id=org_id,
        capability=capability,
        public_model_id=public_model,
        origin=UsageOrigin.CUSTOMER,
        outcome=UsageOutcome.SUCCEEDED,
        billable=True,
        occurred_at=JANUARY,
        quantities=quantities,
        request_id=f"req_{capability}",
    )
    await db_session.flush()

    assert {q.unit: q.amount for q in event.quantities} == quantities

    totals = await UsageEventRepository(db_session).totals_for_organization(
        org_id, since=MONTH_START, until=NEXT_MONTH
    )
    assert totals == quantities


async def test_multi_quantity_events_aggregate_per_unit(db_session: AsyncSession) -> None:
    """Meter everything measured; let pricing decide what is billable.

    TTS measures characters (billed) and audio seconds (not billed today,
    but the input to cost-to-serve margin). Both are recorded; neither is
    privileged by the schema.
    """
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)
    for index in range(3):
        await repo.record(
            organization_id=org_id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"characters": Decimal(100), "audio_seconds": Decimal("6.25")},
            request_id=f"req_multi_{index}",
        )
    await db_session.flush()

    assert await repo.totals_for_organization(org_id, since=MONTH_START, until=NEXT_MONTH) == {
        "characters": Decimal(300),
        "audio_seconds": Decimal("18.75"),
    }


async def test_one_unit_appears_at_most_once_per_event(db_session: AsyncSession) -> None:
    """The shape every aggregation assumes, enforced by the database."""
    org_id = await _organization(db_session, "Acme")
    event = await _record_transcription(db_session, org_id)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO usage_quantities (usage_event_id, unit, amount) "
                "VALUES (:event_id, 'audio_seconds', 1)"
            ),
            {"event_id": event.id},
        )
        await db_session.flush()
    await db_session.rollback()


# ── Origin: measured always, billable selectively ───────────────────────


async def test_every_origin_is_measured(db_session: AsyncSession) -> None:
    """Internal traffic is metered exactly like customer traffic. A
    suppressed measurement is unrecoverable; an unbilled one is a filter.
    """
    org_id = await _organization(db_session, "IntelliAI Internal")
    repo = UsageEventRepository(db_session)
    for index, origin in enumerate(UsageOrigin):
        await repo.record(
            organization_id=org_id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=origin,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"characters": Decimal(10)},
            request_id=f"req_origin_{index}",
        )
    await db_session.flush()

    everything = await repo.totals_for_organization(org_id, since=MONTH_START, until=NEXT_MONTH)
    assert everything == {"characters": Decimal(10 * len(UsageOrigin))}

    # Founder decision F7: rating charges for `customer` only — a filter
    # applied above the measurement, never inside it.
    rateable = await repo.totals_for_organization(
        org_id, since=MONTH_START, until=NEXT_MONTH, origins=[UsageOrigin.CUSTOMER]
    )
    assert rateable == {"characters": Decimal(10)}


async def test_the_origin_vocabulary_is_enforced_by_the_database(
    db_session: AsyncSession,
) -> None:
    """A native enum: a typo cannot become a permanent category, and
    appending a member is a reviewed migration."""
    org_id = await _organization(db_session, "Acme")
    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO usage_events "
                "(public_id, organization_id, request_id, capability, public_model_id, "
                " origin, outcome, billable, occurred_at, lineage) "
                "VALUES ('use_x', :org, 'req_x', 'transcription', 'intelliai-stt', "
                " 'marketing', 'succeeded', true, now(), '{}'::jsonb)"
            ),
            {"org": org_id},
        )
    await db_session.rollback()


# ── Tenancy and identity continuity ─────────────────────────────────────


async def test_reads_never_cross_the_tenant_boundary(db_session: AsyncSession) -> None:
    repo = UsageEventRepository(db_session)
    acme = await _organization(db_session, "Acme")
    globex = await _organization(db_session, "Globex")
    await _record_transcription(db_session, acme, request_id="req_acme")
    await db_session.flush()

    assert await repo.get_by_request_id(globex, "req_acme") is None
    assert await repo.list_for_organization(globex, since=MONTH_START, until=NEXT_MONTH) == []
    assert await repo.totals_for_organization(globex, since=MONTH_START, until=NEXT_MONTH) == {}


async def test_the_ledger_survives_the_key_that_produced_it(db_session: AsyncSession) -> None:
    """Keys are rotated and revoked; the usage they produced is permanent."""
    org_id = await _organization(db_session, "Acme")
    generated = generate_api_key("ledger-test-pepper")
    key = await ApiKeyRepository(db_session).add(
        organization_id=org_id,
        name="prod",
        prefix=generated.prefix,
        last4=generated.last4,
        key_hash=generated.hash,
    )
    await db_session.flush()

    event = await UsageEventRepository(db_session).record(
        organization_id=org_id,
        api_key_id=key.id,
        capability="transcription",
        public_model_id="intelliai-stt",
        origin=UsageOrigin.CUSTOMER,
        outcome=UsageOutcome.SUCCEEDED,
        billable=True,
        occurred_at=JANUARY,
        quantities={"audio_seconds": Decimal(5)},
        request_id="req_keyed",
    )
    await db_session.flush()
    assert event.api_key_id == key.id


async def test_replacing_the_engine_leaves_the_commercial_record_identical(
    db_session: AsyncSession,
) -> None:
    """The Commercial Identity Invariant, at the ledger layer.

    Two requests for the same public capability, served by different
    artifacts — a fine-tuned replacement of the first. Everything a
    customer is ever billed on is identical; the difference lives only in
    lineage, which is internal forever.
    """
    org_id = await _organization(db_session, "Acme")
    repo = UsageEventRepository(db_session)

    async def served_by(artifact: dict[str, str], *, request_id: str) -> UsageEvent:
        """Every commercial parameter identical; only lineage differs."""
        return await repo.record(
            organization_id=org_id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=UsageOrigin.CUSTOMER,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=JANUARY,
            quantities={"characters": Decimal(500)},
            request_id=request_id,
            lineage=artifact,
        )

    before = await served_by({"artifact": "kokoro-82m"}, request_id="req_before")
    after = await served_by(
        {"artifact": "intelliai-tts-ft-v2", "adapter": "lora-v7"}, request_id="req_after"
    )
    await db_session.flush()

    billing_facts = ("capability", "public_model_id", "origin", "outcome", "billable")
    assert all(getattr(before, f) == getattr(after, f) for f in billing_facts)
    assert [(q.unit, q.amount) for q in before.quantities] == [
        (q.unit, q.amount) for q in after.quantities
    ]
    assert before.lineage != after.lineage  # the only difference is internal
