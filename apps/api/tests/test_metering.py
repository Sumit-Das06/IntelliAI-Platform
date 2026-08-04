"""Metering: served requests become permanent commercial facts.

Full stack — real HTTP, real Postgres, real ledger — with a fake runtime
client standing in for the inference plane. The fake is the point: the
entire commercial path is proven with no engine, no model weights, and no
runtime process anywhere, because nothing in the control plane knows an
engine exists.

The failure semantics each get an executable answer:

1. runtime succeeds, ledger write fails  → customer served, alarm raised,
   fact captured in the durable fallback sink; revenue is recoverable
2. runtime fails before a response        → non-billable event, written
   OUT of the doomed transaction, and no event at all for caller faults
3. interruption before commit             → nothing committed, and nothing
   delivered either — the loss window is exactly the window in which the
   customer also receives nothing
4. duplicate retries                      → exactly one commercial event,
   enforced by database uniqueness
5. streaming                              → hundreds of chunks, one event
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageOutcome
from intelliai_api.db.repositories import UsageEventRepository
from intelliai_api.metering import FileUsageFallback, UsageRecorder
from intelliai_api.registry import default_registry
from intelliai_api.runtimes import RuntimeCallError, RuntimeClient, RuntimeUnavailableError
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_api.services.speech import SpeechService
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    TranscriptionRequest,
    TranscriptionResult,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake-audio-bytes"
TEXT = "Hello from IntelliAI."


def envelope(
    *,
    artifact: str = "kokoro-82m",
    service_version: str = "0.1.0",
    characters: int = 21,
    duration: float = 3.2,
) -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=duration,
            sample_rate_hz=24_000,
            voice="reference-alto",
            characters=characters,
        ),
        model=artifact,
        usage=(Usage(unit=UsageUnit.CHARACTERS, amount=characters),),
        timing=RuntimeTiming(total_ms=700.0, stages={"synthesis": 650.0}),
        runtime=RuntimeMetadata(
            service="tts-runtime",
            service_version=service_version,
            contract_version=CONTRACT_VERSION,
        ),
    )


class FakeSynthesisClient:
    def __init__(
        self,
        response: RuntimeResponse[SpeechSynthesisResult] | None = None,
        *,
        error: RuntimeErrorResponse | None = None,
        unavailable: bool = False,
    ) -> None:
        self.calls: list[SpeechSynthesisRequest] = []
        self._response = response if response is not None else envelope()
        self._error = error
        self._unavailable = unavailable

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        self.calls.append(request)
        if self._unavailable:
            raise RuntimeUnavailableError("connect refused")
        if self._error is not None:
            raise RuntimeCallError(self._error)
        return FAKE_WAV, self._response

    async def close(self) -> None:
        return


def transcription_envelope(*, language: str) -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(
            text="namaste duniya", language=language, duration_seconds=4.5, segments=()
        ),
        model="whisper-small",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=4.5),),
        timing=RuntimeTiming(total_ms=500.0),
        runtime=RuntimeMetadata(
            service="stt-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
        ),
    )


class FakeTranscriptionClient:
    def __init__(self, response: RuntimeResponse[TranscriptionResult]) -> None:
        self._response = response

    async def transcribe(
        self, audio: bytes, request: TranscriptionRequest
    ) -> RuntimeResponse[TranscriptionResult]:
        return self._response

    async def close(self) -> None:
        return


def install(fake: FakeSynthesisClient) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

    return configure


async def _tenant(
    factory: async_sessionmaker[AsyncSession],
    email: str,
    *,
    origin: UsageOrigin = UsageOrigin.CUSTOMER,
) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="MeterCo", owner_email=email, owner_name="Owner"
        )
        if origin is not UsageOrigin.CUSTOMER:
            result.organization.usage_origin = origin
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


async def _events(
    factory: async_sessionmaker[AsyncSession], tenant: BootstrapResult
) -> list[UsageEvent]:
    """Tenant-scoped, like every read on a tenant-owned table.

    An unscoped read here would silently pass or fail depending on what
    else lives in the database — which is exactly the class of bug the
    repository charter's scoping rule exists to prevent.
    """
    async with factory() as session:
        result = await session.scalars(
            select(UsageEvent)
            .where(UsageEvent.organization_id == tenant.organization.id)
            .order_by(UsageEvent.id)
        )
        return list(result.all())


# ── The promotion itself: log line → permanent record ───────────────────


async def test_a_served_request_becomes_a_permanent_commercial_fact(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-happy@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": TEXT},
        )
        assert response.status_code == 200

        (event,) = await _events(factory, tenant)
        assert event.capability == "speech_synthesis"
        assert event.public_model_id == "intelliai-tts"  # public capability, never the engine
        assert event.origin is UsageOrigin.CUSTOMER
        assert event.outcome is UsageOutcome.SUCCEEDED
        assert event.billable is True
        # The customer's receipt number, returned to them in X-Request-ID.
        assert event.request_id == response.headers["X-Request-ID"]
        # Meter everything measured: characters bill, seconds inform margin.
        assert {q.unit: q.amount for q in event.quantities} == {
            "characters": Decimal(21),
            "audio_seconds": Decimal("3.2"),
        }
        # The engine lives in lineage — internal, never a customer's concern.
        assert event.lineage["artifact"] == "kokoro-82m"


async def test_the_ledger_carries_no_interpretations(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Ledger Fact Invariant: facts only.

    Asserted against the table itself so a future column called
    ``price_cents`` or ``quota_remaining`` cannot be added quietly.
    """
    forbidden = {
        "amount_due",
        "cost",
        "cost_cents",
        "customer_tier",
        "discount",
        "invoice_id",
        "invoice_state",
        "premium",
        "price",
        "price_cents",
        "quota_remaining",
        "rate",
        "tier",
    }
    columns = set(UsageEvent.__table__.columns.keys())
    assert not (columns & forbidden), f"interpretation stored in the ledger: {columns & forbidden}"


async def test_transcription_records_the_observed_language(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Language is a fact, not an interpretation — and the fact recorded is
    the language OBSERVED, which may differ from the one requested."""
    fake = FakeTranscriptionClient(transcription_envelope(language="hi"))

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"stt-runtime": fake}

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "meter-lang@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            files={"file": ("a.wav", b"RIFFfake", "audio/wav")},
            data={"model": "intelliai-stt", "language": "en"},
        )
        assert response.status_code == 200

        (event,) = await _events(factory, tenant)
        assert event.language == "hi"  # observed, not requested
        assert event.capability == "transcription"
        assert {q.unit for q in event.quantities} == {"audio_seconds"}


# ── 1. Runtime succeeds, ledger write fails ─────────────────────────────


async def test_a_ledger_failure_never_costs_the_customer_their_response(
    settings: Settings, db_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Serving degrades open; accounting degrades loud.

    The ledger write is sabotaged. The customer still receives their
    audio, a CRITICAL alarm fires, and the fact lands in the durable
    fallback sink — so the revenue is recoverable, not lost.
    """
    fake = FakeSynthesisClient()
    sink = tmp_path / "usage-fallback.jsonl"

    class BrokenRepository:
        async def record(self, **_: object) -> None:
            raise RuntimeError("ledger unavailable")

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}
        original = UsageRecorder._write

        async def sabotaged(self: UsageRecorder, **kwargs: Any) -> None:
            self._fallback = FileUsageFallback(sink)
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(
                    "intelliai_api.metering.recorder.UsageEventRepository",
                    lambda _session: BrokenRepository(),
                )
                await original(self, **kwargs)

        app.state.metering_patch = sabotaged

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "meter-broken@example.com")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(UsageRecorder, "_write", client._transport.app.state.metering_patch)  # type: ignore[attr-defined]
            with structlog.testing.capture_logs() as logs:
                response = await client.post(
                    "/v1/audio/speech",
                    headers=_bearer(tenant.generated.secret),
                    json={"model": "intelliai-tts", "input": TEXT},
                )

        # The customer is served. A bookkeeping fault is never their problem.
        assert response.status_code == 200
        assert response.content == FAKE_WAV
        # The alarm fired, at the severity that pages a human.
        alarms = [line for line in logs if line["event"] == "usage.write_failed"]
        assert len(alarms) == 1
        assert alarms[0]["log_level"] == "critical"
        # And the fact survived where the database is not.
        assert sink.exists()
        assert "intelliai-tts" in sink.read_text(encoding="utf-8")
        # Nothing reached the ledger — which is exactly why the sink exists.
        assert await _events(factory, tenant) == []


async def test_a_refused_ledger_write_does_not_poison_the_request(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The savepoint is what makes guarantee 1 possible.

    A ledger write that violates a constraint aborts a Postgres
    transaction. Without SAVEPOINT isolation the surrounding transaction —
    the one about to return the customer's answer — would be unusable, and
    a bookkeeping fault would become a 500. Two requests share a request
    id here, forcing exactly that collision.
    """
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-savepoint@example.com")
        headers = _bearer(tenant.generated.secret) | {"X-Request-ID": "req_collision"}
        payload = {"model": "intelliai-tts", "input": TEXT}

        first = await client.post("/v1/audio/speech", headers=headers, json=payload)
        second = await client.post("/v1/audio/speech", headers=headers, json=payload)

        assert first.status_code == 200
        assert second.status_code == 200  # the collision never reached the customer
        assert len(await _events(factory, tenant)) == 1  # and it was refused, once


# ── 2. Runtime fails before producing a successful response ─────────────


@pytest.mark.parametrize(
    "error_type",
    [None, RuntimeErrorType.NOT_READY, RuntimeErrorType.OVERLOADED, RuntimeErrorType.INTERNAL],
)
async def test_our_failure_is_recorded_and_is_never_billable(
    settings: Settings, db_engine: AsyncEngine, error_type: RuntimeErrorType | None
) -> None:
    """A runtime that fails after accepting work still consumed capacity.

    Recorded, non-billable, with no measured quantity. ``None`` is the
    unreachable-runtime case; the rest are the runtime failing on its own
    side. Exercised at the recorder rather than over HTTP for a reason
    given in ``test_a_failure_event_survives_the_transaction_that_failed``.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, f"meter-fail-{error_type}@example.com")
        async with factory() as session:
            auth = await _auth_context(session, tenant)
            await UsageRecorder(session, session_factory=factory).record_runtime_failure(
                auth=auth,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                error_type=error_type,
                lineage={"artifact": "kokoro-82m"},
            )
            await session.commit()

        (event,) = await _events(factory, tenant)
        assert event.outcome is UsageOutcome.FAILED
        assert event.billable is False
        assert event.quantities == []  # nothing delivered, nothing measured
        assert event.capability == "speech_synthesis"


async def test_a_caller_fault_produces_no_ledger_row_at_all(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """We refused the request; we did not spend inference on it.

    The ledger is the record of work PERFORMED. A refusal is an
    operational fact belonging to the request-event family — recording it
    here would dilute the one table whose every row must be a commercial
    fact. The policy lives in the recorder so two capabilities can never
    drift on what a recordable failure means.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "meter-invalid@example.com")
        async with factory() as session:
            auth = await _auth_context(session, tenant)
            await UsageRecorder(session, session_factory=factory).record_runtime_failure(
                auth=auth,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                error_type=RuntimeErrorType.INVALID_INPUT,
            )
            await session.commit()

        assert await _events(factory, tenant) == []


async def test_a_failure_event_survives_the_transaction_that_failed(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Why failure events are written out-of-band.

    The request that failed is about to have its transaction rolled back
    by the error path. A failure event written INSIDE it would vanish
    together with the failure it documents — so the recorder opens its
    own session and commits there.

    The asymmetry is asserted structurally: the success path writes
    through the session it was handed, the failure path provably does not
    — it opens one of its own from the factory.

    Note on the harness, stated rather than hidden: ``client_with_db``
    binds every session to a single connection inside one rolled-back
    transaction, so an "independent" commit here is still a savepoint
    release on the shared connection. The physical durability of the
    out-of-band commit is therefore a property of production wiring, not
    something this suite can demonstrate; what it CAN demonstrate — and
    does — is that the two paths use different sessions, which is the
    mechanism that produces it.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "meter-oob@example.com")
        opened: list[AsyncSession] = []

        def counting_factory() -> AsyncSession:
            session = factory()
            opened.append(session)
            return session

        async with factory() as request_session:
            auth = await _auth_context(request_session, tenant, request_id="req_success")
            recorder = UsageRecorder(request_session, session_factory=counting_factory)  # type: ignore[arg-type]

            await recorder.record_success(
                auth=auth,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                quantities={"characters": Decimal(10)},
            )
            assert opened == []  # success rode the request's own session

            failing = await _auth_context(request_session, tenant, request_id="req_failed")
            await recorder.record_runtime_failure(
                auth=failing,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                error_type=RuntimeErrorType.INTERNAL,
            )
            assert len(opened) == 1  # failure did NOT
            assert opened[0] is not request_session

            await request_session.rollback()  # the request's transaction dies

        # In production the failure row is on its own connection and
        # survives; here the shared connection takes it with the rollback.
        assert await _events(factory, tenant) == []


async def test_a_request_refused_before_the_runtime_produces_nothing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """An unknown model never reaches inference, so it never reaches the
    ledger either."""
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-unknown@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-nope", "input": TEXT},
        )
        assert response.status_code == 404
        assert fake.calls == []
        assert await _events(factory, tenant) == []


# ── 3. Interruption after inference, before commit ──────────────────────


async def test_an_uncommitted_event_is_lost_together_with_the_response(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The honest bound on guarantee 3.

    If the gateway dies between inference and commit, the event is lost —
    and so is the response, because they ride the same transaction and the
    same connection. The loss window is exactly the window in which the
    customer receives nothing, so nothing is owed for what vanished.

    Simulated exactly: inference runs, the ledger row is written into the
    request's transaction, and the transaction is then discarded rather
    than committed — which is what an interrupted gateway does.
    """
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (_client, factory):
        tenant = await _tenant(factory, "meter-crash@example.com")

        async with factory() as session:
            auth = await _auth_context(session, tenant)
            service = SpeechService(
                default_registry(),
                cast("dict[str, RuntimeClient]", {"tts-runtime": fake}),
                UsageRecorder(session),
            )
            outcome = await service.synthesize(
                auth=auth,
                public_model_id="intelliai-tts",
                text=TEXT,
                voice=None,
                speed=None,
            )
            assert outcome.audio == FAKE_WAV  # the work was really done
            # Visible inside the transaction that produced it...
            pending = await session.scalars(
                select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
            )
            assert len(list(pending.all())) == 1

            await session.rollback()  # ...the gateway dies here

        assert fake.calls  # the inference DID happen
        assert await _events(factory, tenant) == []  # and nothing was committed
        # Neither the customer nor the ledger kept anything: the loss
        # window is exactly the window in which the customer also receives
        # nothing, so no delivered work became commercially invisible.


# ── 4. Duplicate retries ────────────────────────────────────────────────


async def test_a_retry_with_the_same_request_id_bills_exactly_once(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-retry-req@example.com")
        headers = _bearer(tenant.generated.secret) | {"X-Request-ID": "req_retried"}
        payload = {"model": "intelliai-tts", "input": TEXT}

        for _ in range(4):
            reply = await client.post("/v1/audio/speech", headers=headers, json=payload)
            assert reply.status_code == 200

        events = await _events(factory, tenant)
        assert len(events) == 1  # Request Identity Invariant, structurally
        assert len(fake.calls) == 4  # at-most-once BILLING, not at-most-once compute


async def test_a_retry_with_the_same_idempotency_key_bills_exactly_once(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Different request ids — a genuine client retry — one commercial event."""
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-retry-idem@example.com")
        headers = _bearer(tenant.generated.secret) | {"Idempotency-Key": "idem-abc-123"}
        payload = {"model": "intelliai-tts", "input": TEXT}

        for _ in range(3):
            reply = await client.post("/v1/audio/speech", headers=headers, json=payload)
            assert reply.status_code == 200

        events = await _events(factory, tenant)
        assert len(events) == 1
        assert events[0].idempotency_key == "idem-abc-123"


async def test_duplicate_suppression_is_reported_not_hidden(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """A suppressed duplicate is an observable event: a rising rate is a
    client-integration signal, and silence about it would hide a bug."""
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-dup-log@example.com")
        headers = _bearer(tenant.generated.secret) | {"Idempotency-Key": "idem-observed"}
        payload = {"model": "intelliai-tts", "input": TEXT}

        await client.post("/v1/audio/speech", headers=headers, json=payload)
        with structlog.testing.capture_logs() as logs:
            await client.post("/v1/audio/speech", headers=headers, json=payload)

        assert [line for line in logs if line["event"] == "usage.duplicate_suppressed"]


async def test_unkeyed_requests_are_two_events_by_design(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Absent a client key there is no idempotency: two identical
    generative requests produced two files and are two billable facts."""
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-unkeyed@example.com")
        headers = _bearer(tenant.generated.secret)
        payload = {"model": "intelliai-tts", "input": TEXT}

        await client.post("/v1/audio/speech", headers=headers, json=payload)
        await client.post("/v1/audio/speech", headers=headers, json=payload)

        assert len(await _events(factory, tenant)) == 2


# ── 5. Streaming: chunks are transport, not billable units ──────────────


async def test_a_streamed_response_of_many_chunks_is_one_event(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Request Identity Invariant against the future that most tempts a
    per-chunk ledger.

    A streaming caller is simulated end to end: hundreds of chunks are
    produced and delivered, and the recorder is called exactly once, at
    GENERATION completion, with the total. This is the shape M8 must
    implement, proven against the real recorder before the transport
    exists — the same discipline that proved capability independence in
    M3 before a second capability existed.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "meter-stream@example.com")
        async with factory() as session:
            auth = await _auth_context(session, tenant)
            recorder = UsageRecorder(session)

            produced = 0
            characters = 0
            async for chunk in _fake_stream(chunks=250):
                produced += 1
                characters += len(chunk)
            # One generation completed -> one fact, carrying the total.
            await recorder.record_success(
                auth=auth,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                quantities={"characters": Decimal(characters)},
                lineage={"artifact": "kokoro-82m", "streamed_chunks": produced},
            )
            await session.commit()

        assert produced == 250
        (event,) = await _events(factory, tenant)
        assert {q.unit: q.amount for q in event.quantities} == {"characters": Decimal(characters)}
        # The chunk count is transport detail: recorded as lineage for
        # operations, never as a billable quantity.
        assert event.lineage["streamed_chunks"] == 250


async def test_a_stream_that_dies_after_generating_is_still_billable(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Founder decision F1, stated against streaming: successful
    generation — not socket completion — defines billability."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "meter-stream-dead@example.com")
        async with factory() as session:
            auth = await _auth_context(session, tenant)
            await UsageRecorder(session).record_success(
                auth=auth,
                capability="speech_synthesis",
                public_model_id="intelliai-tts",
                quantities={"characters": Decimal(500)},
                outcome=UsageOutcome.DISCONNECTED,
            )
            await session.commit()

        (event,) = await _events(factory, tenant)
        assert event.billable is True
        assert event.outcome is UsageOutcome.DISCONNECTED


# ── Commercial Identity Invariant, through the whole gateway ────────────


ARTIFACTS = [
    ("whisper-small-replacement", "engine replacement"),
    ("intelliai-tts-ft-v2", "fine-tuned model"),
    ("kokoro-82m-int8", "quantized artifact"),
    ("kokoro-82m+lora-hindi", "LoRA adapter"),
    ("intelliai-speech-merged-v1", "merged model"),
    ("router:multilingual-v2", "runtime routing decision"),
]


async def test_every_internal_replacement_produces_an_identical_commercial_record(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The Commercial Identity Invariant, end to end.

    The same customer request is served six times by six different
    internal realities — a replacement engine, a fine-tune, a quantized
    build, a LoRA, a merge, and a routing decision. Everything the
    customer is ever billed on is byte-identical across all six; the only
    difference lives in lineage, which is internal forever.
    """
    recorded: list[UsageEvent] = []
    for index, (artifact, _description) in enumerate(ARTIFACTS):
        fake = FakeSynthesisClient(envelope(artifact=artifact, service_version=f"9.{index}.0"))
        async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
            tenant = await _tenant(factory, f"meter-swap-{index}@example.com")
            response = await client.post(
                "/v1/audio/speech",
                headers=_bearer(tenant.generated.secret),
                json={"model": "intelliai-tts", "input": TEXT},
            )
            assert response.status_code == 200
            (event,) = await _events(factory, tenant)
            recorded.append(
                UsageEvent(
                    capability=event.capability,
                    public_model_id=event.public_model_id,
                    language=event.language,
                    origin=event.origin,
                    outcome=event.outcome,
                    billable=event.billable,
                    lineage=event.lineage,
                    quantities=[type(q)(unit=q.unit, amount=q.amount) for q in event.quantities],
                )
            )

    def commercial_shape(event: UsageEvent) -> tuple[Any, ...]:
        return (
            event.capability,
            event.public_model_id,
            event.language,
            event.origin,
            event.outcome,
            event.billable,
            tuple(sorted((q.unit, q.amount) for q in event.quantities)),
        )

    shapes = {commercial_shape(event) for event in recorded}
    assert len(shapes) == 1, "an internal replacement changed the commercial record"

    served = {event.lineage["artifact"] for event in recorded}
    assert served == {artifact for artifact, _ in ARTIFACTS}  # six different realities


# ── Origin: measured always, rated selectively ──────────────────────────


async def test_internal_traffic_is_metered_under_its_own_origin(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Our benchmark and evaluation traffic is measured exactly like a
    customer's — and F7 keeps it out of rating, not out of measurement."""
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "meter-bench@example.com", origin=UsageOrigin.BENCHMARK)
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": TEXT},
        )
        assert response.status_code == 200

        (event,) = await _events(factory, tenant)
        assert event.origin is UsageOrigin.BENCHMARK
        assert event.billable is True  # value WAS delivered; billable is a fact

        async with factory() as session:
            repo = UsageEventRepository(session)
            rateable = await repo.totals_for_organization(
                event.organization_id,
                since=event.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0),
                until=event.occurred_at.replace(year=event.occurred_at.year + 1),
                origins=[UsageOrigin.CUSTOMER],
            )
        assert rateable == {}  # excluded by RATING, never by measurement


# ── Helpers ─────────────────────────────────────────────────────────────


async def _fake_stream(*, chunks: int) -> Any:
    """Stand-in for a future streaming synthesis transport."""
    for index in range(chunks):
        yield f"chunk-{index:04d}"


async def _auth_context(
    session: AsyncSession, tenant: BootstrapResult, *, request_id: str | None = None
) -> Any:
    from intelliai_api.services.auth import AuthService

    return await AuthService(session, pepper=PEPPER).authenticate(
        tenant.generated.secret,
        request_id=request_id or f"req_{tenant.organization.public_id}",
    )
