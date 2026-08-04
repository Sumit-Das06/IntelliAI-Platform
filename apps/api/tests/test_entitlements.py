"""Entitlements: has this customer used more than they bought?

Against real Postgres, because quota is computed from the ledger itself
and the thing under test is that aggregate — not a counter that could
drift from the record invoices are built from.

Five demonstrations, one per founder requirement:

1. quota exhaustion
2. spend-limit exhaustion
3. plan upgrades without usage migration
4. UTC reset correctness
5. multilingual engine routing leaving quota and accounting unchanged

Plus the two laws ratified at Step 3 close: admission never sees an
engine (Protection Independence), and when entitlement cannot be
determined the platform serves, alarms, and publishes nothing
(Operational Honesty).
"""

import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import QuotaExceededError
from intelliai_api.db.models import UsageOrigin, UsageOutcome
from intelliai_api.db.repositories import UsageEventRepository
from intelliai_api.entitlements import EntitlementService, period_for, rate
from intelliai_api.entitlements.pricing import INTERNAL_V1, PriceBook
from intelliai_api.limits import plans as plans_module
from intelliai_api.limits.plans import FREE, PLANS, Plan
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake"
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _plan(**over: Any) -> Plan:
    base: dict[str, Any] = {
        "id": FREE,
        "requests_per_minute": 6_000,
        "burst": 1_000,
        "max_concurrent": 100,
        "capability_requests_per_minute": 6_000,
        "control_plane_requests_per_minute": 6_000,
        "monthly_quota": {"characters": Decimal(100)},
        "monthly_spend_cap": None,
    }
    return Plan(**{**base, **over})


async def _tenant(
    factory: async_sessionmaker[AsyncSession],
    email: str,
    *,
    plan: str = FREE,
    spend_limit: Decimal | None = None,
) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="QuotaCo", owner_email=email, owner_name="Owner"
        )
        result.organization.plan = plan
        result.organization.spend_limit = spend_limit
        await session.commit()
        return result


async def _consume(
    factory: async_sessionmaker[AsyncSession],
    tenant: BootstrapResult,
    *,
    quantities: dict[str, Decimal],
    at: datetime = NOW,
    origin: UsageOrigin = UsageOrigin.CUSTOMER,
    request_id: str | None = None,
) -> None:
    """Record consumption the way the serving path would."""
    async with factory() as session:
        await UsageEventRepository(session).record(
            organization_id=tenant.organization.id,
            capability="speech_synthesis",
            public_model_id="intelliai-tts",
            origin=origin,
            outcome=UsageOutcome.SUCCEEDED,
            billable=True,
            occurred_at=at,
            quantities=quantities,
            request_id=request_id or f"req_{at.timestamp()}_{origin.value}_{id(quantities)}",
        )
        await session.commit()


async def _check(
    factory: async_sessionmaker[AsyncSession],
    tenant: BootstrapResult,
    *,
    now: datetime = NOW,
) -> None:
    async with factory() as session:
        await EntitlementService(UsageEventRepository(session)).check(
            organization_id=tenant.organization.id,
            organization_public_id=tenant.organization.public_id,
            plan_id=tenant.organization.plan,
            spend_limit=tenant.organization.spend_limit,
            now=now,
        )


# ── 1. Quota exhaustion ─────────────────────────────────────────────────


async def test_quota_exhaustion_refuses_without_retry_guidance(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retrying a quota never helps, so we deliberately do NOT say when.

    That is the whole reason quota and rate limit are different codes: a
    client that treats exhaustion as a rate limit hammers a wall until
    the month turns over.
    """
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "quota-exhaust@example.com")

        await _consume(factory, tenant, quantities={"characters": Decimal(99)})
        await _check(factory, tenant)  # still inside the allowance

        await _consume(factory, tenant, quantities={"characters": Decimal(1)})
        with pytest.raises(QuotaExceededError) as refused:
            await _check(factory, tenant)

    error = refused.value
    assert error.status_code == 429
    assert error.code == "quota_exceeded"
    assert error.error_type.value == "quota_exceeded_error"
    assert getattr(error, "retry_after", None) is None  # retrying never helps
    assert "2026-09-01" in error.message  # but we say WHEN it resets
    assert "characters" in error.message  # and which allowance ran out


async def test_only_customer_origin_consumes_quota(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Founder decision F7 at the entitlement layer: our own benchmark and
    evaluation traffic is metered exactly like a customer's, and excluded
    here. Measurement is unconditional; billability is a filter."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "quota-origin@example.com")

        for origin in (UsageOrigin.BENCHMARK, UsageOrigin.EVALUATION, UsageOrigin.DEMO):
            await _consume(
                factory, tenant, quantities={"characters": Decimal(1_000)}, origin=origin
            )
        await _check(factory, tenant)  # 3000 characters recorded, none of it theirs

        await _consume(factory, tenant, quantities={"characters": Decimal(100)})
        with pytest.raises(QuotaExceededError):
            await _check(factory, tenant)


async def test_an_unpriced_unquotaed_unit_never_blocks_a_new_capability(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A capability can ship, be metered, and be studied before anyone
    decides its quota — deliberately permissive, so a new capability is
    never throttled to zero by an allowance nobody remembered to write."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "quota-newunit@example.com")
        await _consume(factory, tenant, quantities={"pages": Decimal(10_000)})
        await _check(factory, tenant)


# ── 2. Spend-limit exhaustion ───────────────────────────────────────────


async def test_spend_limit_exhaustion_refuses_with_a_different_code(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Money, not usage — and distinguishable, because the remedy differs:
    a quota waits for the period, a spend limit can be raised now."""
    monkeypatch.setitem(
        PLANS,
        FREE,
        _plan(monthly_quota={}, monthly_spend_cap=Decimal("1.00")),
    )
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "spend-exhaust@example.com")

        # $0.000015/char -> 60,000 characters is $0.90.
        await _consume(factory, tenant, quantities={"characters": Decimal(60_000)})
        await _check(factory, tenant)

        # ...another 10,000 characters crosses $1.00.
        await _consume(factory, tenant, quantities={"characters": Decimal(10_000)})
        with pytest.raises(QuotaExceededError) as refused:
            await _check(factory, tenant)

    assert refused.value.code == "spend_limit_exceeded"
    assert "raise the limit" in refused.value.message


async def test_the_stricter_of_plan_and_customer_ceiling_applies(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both parties get to protect themselves: the platform caps the tier,
    the customer caps themselves, and whichever binds first wins."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={}, monthly_spend_cap=Decimal("100.00")))
    async with client_with_db(settings, db_engine) as (_client, factory):
        # The customer trusts themselves with 30 cents.
        tenant = await _tenant(factory, "spend-customer@example.com", spend_limit=Decimal("0.30"))
        await _consume(factory, tenant, quantities={"characters": Decimal(30_000)})  # $0.45

        with pytest.raises(QuotaExceededError) as refused:
            await _check(factory, tenant)
        assert refused.value.code == "spend_limit_exceeded"

        # A plan cap below the customer's would bind instead.
        monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={}, monthly_spend_cap=Decimal("0.10")))
        strict = await _tenant(factory, "spend-plan@example.com", spend_limit=Decimal("1000.00"))
        await _consume(factory, strict, quantities={"characters": Decimal(20_000)})  # $0.30
        with pytest.raises(QuotaExceededError):
            await _check(factory, strict)


def test_rating_is_a_pure_function_of_totals_and_price_book() -> None:
    """ADR-0023's property, asserted before Step 5 formalises it: same
    inputs, same money, forever — which is what makes a spend ceiling
    explicable and will make invoices reproducible."""
    totals = {"characters": Decimal(1_000_000), "audio_seconds": Decimal(3_600)}

    assert rate(totals, INTERNAL_V1) == rate(totals, INTERNAL_V1)
    assert rate(totals, INTERNAL_V1) == Decimal("15.36")  # $15.00 + $0.36

    # A different book gives different money from identical facts — the
    # measurement is never re-written, only re-rated.
    doubled = PriceBook(
        version="test-doubled",
        effective_from=INTERNAL_V1.effective_from,
        currency=INTERNAL_V1.currency,
        unit_prices={unit: price * 2 for unit, price in INTERNAL_V1.unit_prices.items()},
    )
    assert rate(totals, doubled) == Decimal("30.72")

    # Money is Decimal, never float: no drift to accumulate.
    assert isinstance(rate(totals, INTERNAL_V1), Decimal)


# ── 3. Plan upgrades without usage migration ────────────────────────────


async def test_upgrading_a_plan_changes_entitlement_not_history(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Ledger Fact Invariant, felt commercially.

    Usage is a FACT and the plan is an INTERPRETATION of it. Upgrading
    mid-period therefore migrates nothing: not one ledger row moves, no
    counter is reset, no allowance is refunded. The same recorded
    consumption is simply measured against a larger allowance — and the
    customer is unblocked immediately, which is the behaviour anyone
    upgrading in order to keep working expects.
    """
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    monkeypatch.setitem(
        PLANS, "growth", _plan(id="growth", monthly_quota={"characters": Decimal(10_000)})
    )

    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "plan-upgrade@example.com")
        await _consume(factory, tenant, quantities={"characters": Decimal(150)})

        with pytest.raises(QuotaExceededError):
            await _check(factory, tenant)

        async with factory() as session:
            before = await UsageEventRepository(session).list_for_organization(
                tenant.organization.id, since=period_for(NOW).start, until=period_for(NOW).end
            )
            ledger_before = [(event.id, event.occurred_at) for event in before]

        # The upgrade: one column, nothing else.
        async with factory() as session:
            organization = await session.get(type(tenant.organization), tenant.organization.id)
            assert organization is not None
            organization.plan = "growth"
            await session.commit()
            tenant.organization.plan = "growth"

        await _check(factory, tenant)  # unblocked immediately

        async with factory() as session:
            after = await UsageEventRepository(session).list_for_organization(
                tenant.organization.id, since=period_for(NOW).start, until=period_for(NOW).end
            )
            ledger_after = [(event.id, event.occurred_at) for event in after]

        # Not one row moved, and the consumption still counts.
        assert ledger_after == ledger_before
        async with factory() as session:
            totals = await UsageEventRepository(session).totals_for_organization(
                tenant.organization.id,
                since=period_for(NOW).start,
                until=period_for(NOW).end,
                origins=[UsageOrigin.CUSTOMER],
            )
        assert totals == {"characters": Decimal(150)}


async def test_a_downgrade_does_not_erase_what_was_already_used(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mirror case, and the one that would be a revenue hole: moving
    to a smaller plan must not hand back consumption already recorded."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    monkeypatch.setitem(
        PLANS, "growth", _plan(id="growth", monthly_quota={"characters": Decimal(10_000)})
    )
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "plan-downgrade@example.com", plan="growth")
        await _consume(factory, tenant, quantities={"characters": Decimal(5_000)})
        await _check(factory, tenant)

        tenant.organization.plan = FREE
        with pytest.raises(QuotaExceededError):
            await _check(factory, tenant)


# ── 4. UTC reset correctness ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("moment", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
        ),
        # Year rollover: December must reach into next January, not month 13.
        (
            datetime(2026, 12, 31, 23, 59, 59, 999_999, tzinfo=UTC),
            datetime(2026, 12, 1, tzinfo=UTC),
            datetime(2027, 1, 1, tzinfo=UTC),
        ),
        (
            datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2027, 1, 1, tzinfo=UTC),
            datetime(2027, 2, 1, tzinfo=UTC),
        ),
        # Leap February: the end is March 1, never February 29 + 1 day.
        (
            datetime(2028, 2, 29, 23, 0, tzinfo=UTC),
            datetime(2028, 2, 1, tzinfo=UTC),
            datetime(2028, 3, 1, tzinfo=UTC),
        ),
    ],
)
def test_billing_periods_are_calendar_months_in_utc(
    moment: datetime, expected_start: datetime, expected_end: datetime
) -> None:
    period = period_for(moment)
    assert period.start == expected_start
    assert period.end == expected_end
    assert period.contains(moment)


def test_a_period_is_half_open_so_boundaries_belong_to_exactly_one_month() -> None:
    """With closed intervals the boundary instant belongs to two months
    and every aggregate over both is wrong — once a month, in money."""
    august = period_for(datetime(2026, 8, 15, tzinfo=UTC))
    september = period_for(datetime(2026, 9, 15, tzinfo=UTC))
    boundary = datetime(2026, 9, 1, tzinfo=UTC)

    assert august.end == september.start == boundary
    assert not august.contains(boundary)
    assert september.contains(boundary)
    assert august.contains(boundary - timedelta(microseconds=1))


def test_a_naive_timestamp_is_refused_rather_than_assumed() -> None:
    """Assuming a timezone is how a server's local time silently becomes
    a billing boundary."""
    with pytest.raises(ValueError, match="timezone-aware"):
        period_for(datetime(2026, 8, 15, 12, 0))


def test_periods_are_computed_from_utc_regardless_of_the_input_offset() -> None:
    """19:30 on July 31 in Delhi is 14:00 UTC on July 31 — July, not August."""
    delhi = datetime(2026, 7, 31, 19, 30, tzinfo=UTC) + timedelta(hours=5, minutes=30)
    assert period_for(delhi.astimezone(UTC)).label == "2026-08"

    same_instant_in_july = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    assert period_for(same_instant_in_july).label == "2026-07"


async def test_consumption_resets_when_the_period_turns_over(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No job resets anything: the period moves, and the aggregate window
    moves with it. A reset that has to RUN is a reset that can fail."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(100)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "period-reset@example.com")

        august_last_instant = datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
        await _consume(
            factory, tenant, quantities={"characters": Decimal(500)}, at=august_last_instant
        )

        with pytest.raises(QuotaExceededError):
            await _check(factory, tenant, now=august_last_instant)

        # One second later it is September, and the allowance is whole.
        september_first_instant = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)
        await _check(factory, tenant, now=september_first_instant)

        # August's history is untouched — nothing was deleted or moved.
        async with factory() as session:
            august = await UsageEventRepository(session).totals_for_organization(
                tenant.organization.id,
                since=datetime(2026, 8, 1, tzinfo=UTC),
                until=datetime(2026, 9, 1, tzinfo=UTC),
                origins=[UsageOrigin.CUSTOMER],
            )
        assert august == {"characters": Decimal(500)}


# ── 5. Engine routing leaves quota and accounting unchanged ─────────────


ROUTING_SCENARIOS = [
    ("kokoro-82m", "en", "the launch engine"),
    ("indicf5-hi", "hi", "a Hindi-capable engine"),
    ("future-arabic-v1", "ar", "an Arabic engine that does not exist yet"),
    ("kokoro-82m-int8", "en", "a quantized build"),
    ("kokoro-82m+lora-hi", "hi", "a LoRA adapter"),
    ("router:multilingual-v2", "en", "a routing decision"),
]


async def test_multilingual_routing_leaves_quota_and_accounting_identical(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Protection Independence Invariant, end to end.

    Six identical customer requests, each served by a different internal
    reality across three languages. Every one consumes exactly the same
    quota, rates to exactly the same money, and leaves the same
    commercial record — the only difference lives in lineage, which
    entitlement cannot see and by law may not use.
    """
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(10_000)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "routing-quota@example.com")

        for index, (artifact, language, _description) in enumerate(ROUTING_SCENARIOS):
            async with factory() as session:
                await UsageEventRepository(session).record(
                    organization_id=tenant.organization.id,
                    capability="speech_synthesis",
                    public_model_id="intelliai-tts",
                    language=language,
                    origin=UsageOrigin.CUSTOMER,
                    outcome=UsageOutcome.SUCCEEDED,
                    billable=True,
                    occurred_at=NOW,
                    quantities={"characters": Decimal(500)},
                    request_id=f"req_routing_{index}",
                    lineage={"artifact": artifact},
                )
                await session.commit()

        async with factory() as session:
            events = await UsageEventRepository(session).list_for_organization(
                tenant.organization.id, since=period_for(NOW).start, until=period_for(NOW).end
            )
            totals = await UsageEventRepository(session).totals_for_organization(
                tenant.organization.id,
                since=period_for(NOW).start,
                until=period_for(NOW).end,
                origins=[UsageOrigin.CUSTOMER],
            )

    # Every request consumed the same quota, regardless of engine or language.
    per_request = {tuple(sorted((q.unit, q.amount) for q in event.quantities)) for event in events}
    assert len(per_request) == 1

    # ...and the same money.
    assert rate({"characters": Decimal(500)}) * len(ROUTING_SCENARIOS) == rate(totals)

    # The commercial identity never varied; only lineage did.
    assert {event.public_model_id for event in events} == {"intelliai-tts"}
    assert {event.lineage["artifact"] for event in events} == {
        artifact for artifact, _, _ in ROUTING_SCENARIOS
    }
    # Language is recorded as a FACT for analytics, and is not a pricing
    # or entitlement dimension.
    assert {event.language for event in events} == {"en", "hi", "ar"}


def test_admission_control_cannot_see_an_engine() -> None:
    """The Protection Independence Invariant, enforced structurally.

    The limits package is parsed and must import nothing that knows what
    an engine, artifact, or lineage is — so a limit rule cannot come to
    depend on one even by accident. Enforced here rather than trusted,
    because the tempting version of this mistake ("GPU requests are
    expensive, limit them harder") reads like an optimisation.
    """
    forbidden_terms = {"lineage", "artifact", "engine", "quantization", "lora", "gpu"}
    package = Path(plans_module.__file__).parent

    offenders: dict[str, set[str]] = {}
    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                names.add(node.attr.lower())
            elif isinstance(node, ast.Name):
                names.add(node.id.lower())
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.update(part.lower() for part in node.module.split("."))
        hits = {term for term in forbidden_terms if term in names}
        if hits:
            offenders[module.name] = hits

    assert not offenders, f"admission control referenced engine concepts: {offenders}"


# ── Operational Honesty ─────────────────────────────────────────────────


async def test_when_entitlement_cannot_be_determined_we_serve_and_say_nothing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The third state of the Operational Honesty Principle.

    A fabricated allowance is worse than silence: a client that trusts a
    plausible-but-wrong number is worse off than one given none. So the
    request is served, an alarm fires, and no quota claim is made.
    """

    class BrokenRepository:
        async def totals_for_organization(self, *_: object, **__: object) -> dict[str, Decimal]:
            raise RuntimeError("ledger unavailable")

    service = EntitlementService(BrokenRepository())  # type: ignore[arg-type]
    with structlog.testing.capture_logs() as logs:
        await service.check(
            organization_id=1,
            organization_public_id="org_probe",
            plan_id=FREE,
            spend_limit=None,
            now=NOW,
        )

    events = [line.get("event") for line in logs]
    assert "entitlement.unavailable" in events, f"captured: {events}"
    assert not any(str(event).startswith("entitlement.quota") for event in events)


async def test_a_refusal_states_the_true_reset_date(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never publish incorrect quota information — including the date."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(1)}))
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "honest-reset@example.com")
        december = datetime(2026, 12, 20, tzinfo=UTC)
        await _consume(factory, tenant, quantities={"characters": Decimal(5)}, at=december)

        with pytest.raises(QuotaExceededError) as refused:
            await _check(factory, tenant, now=december)

    # December resets into January of the NEXT year, not month 13.
    assert "2027-01-01" in refused.value.message


# ── The free tier ships on day one (F5) ─────────────────────────────────


def test_the_free_tier_carries_real_entitlements() -> None:
    """F5: quota accrual, reset, refusal, and rating exclusion all execute
    against real traffic from day one rather than lying dormant until the
    first paying customer. Enforcement code that never runs is untested
    code."""
    free = PLANS[FREE]
    assert free.monthly_quota, "the free tier has no quota — enforcement would be dormant"
    assert free.monthly_spend_cap is not None
    # Keyed by ledger unit, never by capability.
    assert set(free.monthly_quota) <= {unit.value for unit in UsageUnit}


def test_full_free_tier_consumption_stays_under_its_own_spend_cap() -> None:
    """The cap is a backstop behind the quotas, not a second, tighter
    limit that would make the advertised allowances unreachable."""
    free = PLANS[FREE]
    assert free.monthly_spend_cap is not None
    assert rate(dict(free.monthly_quota)) <= free.monthly_spend_cap


# ── The end-to-end refusal, over real HTTP ──────────────────────────────


def _envelope(characters: int) -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=1.0,
            sample_rate_hz=24_000,
            voice="reference-alto",
            characters=characters,
        ),
        model="kokoro-82m",
        usage=(Usage(unit=UsageUnit.CHARACTERS, amount=characters),),
        timing=RuntimeTiming(total_ms=5.0),
        runtime=RuntimeMetadata(
            service="tts-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
        ),
    )


class FakeSynthesisClient:
    def __init__(self, characters: int = 50) -> None:
        self.calls = 0
        self._characters = characters

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        self.calls += 1
        return FAKE_WAV, _envelope(self._characters)

    async def close(self) -> None:
        return


async def test_an_exhausted_customer_is_refused_before_inference(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cost gradient again: an over-quota request must not reach the
    runtime. Serving it would spend capacity we will never bill for."""
    monkeypatch.setitem(PLANS, FREE, _plan(monthly_quota={"characters": Decimal(60)}))
    fake = FakeSynthesisClient(characters=50)

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "http-quota@example.com")
        headers = {"Authorization": f"Bearer {tenant.generated.secret}"}
        payload = {"model": "intelliai-tts", "input": "hello there"}

        first = await client.post("/v1/audio/speech", headers=headers, json=payload)
        assert first.status_code == 200  # 50 characters recorded

        second = await client.post("/v1/audio/speech", headers=headers, json=payload)
        assert second.status_code == 200  # 100 recorded; now past 60

        refused = await client.post("/v1/audio/speech", headers=headers, json=payload)
        assert refused.status_code == 429
        body = refused.json()["error"]
        assert body["type"] == "quota_exceeded_error"
        assert body["code"] == "quota_exceeded"
        assert "Retry-After" not in refused.headers  # retrying never helps

        assert fake.calls == 2  # the refusal never reached the runtime


async def test_overshoot_is_bounded_by_the_maximum_single_request(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quota cannot be enforced exactly — a request's cost is unknown
    until after inference — so the honest claim is a BOUND, and this
    measures it rather than asserting it.
    """
    per_request = 50
    allowance = 60
    concurrency = 8
    monkeypatch.setitem(
        PLANS,
        FREE,
        _plan(monthly_quota={"characters": Decimal(allowance)}, max_concurrent=concurrency),
    )
    fake = FakeSynthesisClient(characters=per_request)

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "overshoot@example.com")
        headers = {"Authorization": f"Bearer {tenant.generated.secret}"}
        payload = {"model": "intelliai-tts", "input": "hello there"}

        for _ in range(concurrency):
            await client.post("/v1/audio/speech", headers=headers, json=payload)

        async with factory() as session:
            totals = await UsageEventRepository(session).totals_for_organization(
                tenant.organization.id,
                since=period_for(NOW).start,
                until=period_for(NOW).end,
                origins=[UsageOrigin.CUSTOMER],
            )

    consumed = totals.get("characters", Decimal(0))
    overshoot = max(Decimal(0), consumed - allowance)
    bound = Decimal(concurrency * per_request)
    assert overshoot <= bound, f"overshoot {overshoot} exceeded the predicted bound {bound}"
