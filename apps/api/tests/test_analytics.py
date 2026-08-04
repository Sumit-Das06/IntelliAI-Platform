"""Production validation of the commercial plane.

Reconciliation, anomaly detection, language analytics, and recovery
behaviour — all against real Postgres, because every one of these is a
query whose correctness IS the guarantee.

The organising question is the one an auditor would ask: *if something
went wrong in the commercial plane, would anybody find out?* Each test
below breaks something specific and checks that the answer is yes.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.analytics import (
    POLICY_LANGUAGES,
    failure_rates,
    language_report,
    reconcile,
    reversal_activity,
    stale_rollups,
    usage_spikes,
)
from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageOutcome, UsageRollup
from intelliai_api.db.repositories import UsageEventRepository, UsageRollupRepository
from intelliai_api.entitlements import period_for
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"
AUGUST = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
PERIOD = period_for(AUGUST)


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="AuditCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


async def _record(
    session: AsyncSession,
    tenant: BootstrapResult,
    *,
    request_id: str,
    characters: int = 1_000,
    at: datetime = AUGUST,
    language: str | None = "en",
    capability: str = "speech_synthesis",
    billable: bool = True,
    origin: UsageOrigin = UsageOrigin.CUSTOMER,
    outcome: UsageOutcome = UsageOutcome.SUCCEEDED,
) -> UsageEvent:
    return await UsageEventRepository(session).record(
        organization_id=tenant.organization.id,
        capability=capability,
        public_model_id="intelliai-tts",
        language=language,
        origin=origin,
        outcome=outcome,
        billable=billable,
        occurred_at=at,
        quantities={"characters": Decimal(characters)} if billable else {},
        request_id=request_id,
        lineage={"artifact": "kokoro-82m"},
    )


async def _rebuild(factory: async_sessionmaker[AsyncSession], tenant: BootstrapResult) -> None:
    async with factory() as session:
        await UsageRollupRepository(session).rebuild(
            tenant.organization.id, since=PERIOD.start, until=PERIOD.end
        )
        await session.commit()


# ── Reconciliation: gateway → ledger → rollups → rating ─────────────────


async def test_a_healthy_period_reconciles_clean(
    settings: Settings, db_engine: AsyncEngine, tmp_path: Path
) -> None:
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recon-clean@example.com")
        async with factory() as session:
            for index in range(5):
                await _record(session, tenant, request_id=f"req_clean_{index}")
            await session.commit()
        await _rebuild(factory, tenant)

        async with factory() as session:
            report = await reconcile(
                session,
                PERIOD,
                fallback_path=tmp_path / "absent.jsonl",
                organization_ids=[tenant.organization.id],
            )

    assert report.clean, [finding.detail for finding in report.findings]
    assert report.events >= 5
    assert report.ledger_total == report.rollup_total
    assert report.ledger_total > 0


async def test_a_rollup_that_drifted_is_caught_and_named(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The Rollup Invariant's auditor. A cache that disagrees is a finding
    with a named repair, not a mystery."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recon-drift@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_drift")
            await session.commit()
        await _rebuild(factory, tenant)

        async with factory() as session:
            await session.execute(
                update(UsageRollup)
                .where(UsageRollup.organization_id == tenant.organization.id)
                .values(amount=Decimal(999))
            )
            await session.commit()

        async with factory() as session:
            report = await reconcile(session, PERIOD, organization_ids=[tenant.organization.id])

    assert not report.clean
    drift = [f for f in report.findings if f.check == "rollup_disagrees_with_ledger"]
    assert drift, [f.check for f in report.findings]
    assert "the ledger is authoritative" in drift[0].detail


async def test_a_non_empty_fallback_sink_fails_reconciliation(
    settings: Settings, db_engine: AsyncEngine, tmp_path: Path
) -> None:
    """A write the ledger refused is a revenue incident WITH a recovery
    path — which is exactly why degrading open was defensible. The sink
    is only a recovery path if somebody is told to empty it."""
    sink = tmp_path / "usage-fallback.jsonl"
    sink.write_text('{"organization_id": "org_x", "capability": "speech_synthesis"}\n')

    async with client_with_db(settings, db_engine) as (_client, factory), factory() as session:
        report = await reconcile(session, PERIOD, fallback_path=sink)

    assert not report.clean
    (finding,) = [f for f in report.findings if f.check == "gateway_to_ledger"]
    assert finding.severity == "critical"
    assert "replay them" in finding.detail


async def test_a_missing_rollup_is_a_warning_not_a_failure(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """A cold cache is not drift. Conflating the two is how alerts get
    ignored."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recon-cold@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_cold")
            await session.commit()

        async with factory() as session:
            report = await reconcile(session, PERIOD, organization_ids=[tenant.organization.id])

    missing = [f for f in report.findings if f.check == "rollup_missing"]
    assert missing
    assert all(f.severity == "warning" for f in missing)


async def test_reconciliation_survives_a_period_with_no_usage(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The quiet month must not look like a broken month."""
    async with client_with_db(settings, db_engine) as (_client, factory), factory() as session:
        empty = period_for(datetime(2019, 3, 15, tzinfo=UTC))
        report = await reconcile(session, empty)

    assert report.clean
    assert report.events == 0
    assert report.ledger_total == Decimal(0)


# ── Anomaly queries: commercial consistency ─────────────────────────────


async def test_a_usage_spike_is_measured_against_the_tenants_own_history(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Relative, never global: a global threshold is useless for a small
    customer and noisy for a large one, and both train people to ignore
    alerts."""
    now = datetime(2026, 8, 20, tzinfo=UTC)
    async with client_with_db(settings, db_engine) as (_client, factory):
        steady = await _tenant(factory, "spike-steady@example.com")
        surging = await _tenant(factory, "spike-surge@example.com")

        async with factory() as session:
            for day in range(1, 8):
                at = now - timedelta(days=day)
                await _record(
                    session, steady, request_id=f"req_steady_{day}", characters=1_000, at=at
                )
                await _record(
                    session, surging, request_id=f"req_base_{day}", characters=1_000, at=at
                )
            # ...and today one of them goes twentyfold.
            await _record(
                session,
                steady,
                request_id="req_steady_today",
                characters=1_000,
                at=now - timedelta(hours=1),
            )
            await _record(
                session,
                surging,
                request_id="req_surge_today",
                characters=20_000,
                at=now - timedelta(hours=1),
            )
            await session.commit()

        async with factory() as session:
            spikes = await usage_spikes(
                session,
                now=now,
                organization_ids=[steady.organization.id, surging.organization.id],
            )

    flagged = {spike.organization_id for spike in spikes}
    assert surging.organization.id in flagged
    assert steady.organization.id not in flagged  # same absolute size, normal for them


async def test_failure_rate_surfaces_capacity_burned_on_unbillable_work(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "failures@example.com")
        async with factory() as session:
            for index in range(2):
                await _record(session, tenant, request_id=f"req_ok_{index}")
            for index in range(3):
                await _record(
                    session,
                    tenant,
                    request_id=f"req_bad_{index}",
                    billable=False,
                    outcome=UsageOutcome.FAILED,
                )
            await session.commit()

        async with factory() as session:
            rates = await failure_rates(session, since=PERIOD.start, until=PERIOD.end)

    mine = [rate for rate in rates if rate.organization_id == tenant.organization.id]
    assert mine and mine[0].failed == 3
    assert mine[0].failure_share == pytest.approx(0.6)


async def test_reversal_activity_and_stale_rollups_are_observable(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Reversals are healthy; a RISING count is the signal. And an old
    computed_at is the first thing to check when a total surprises you."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "reversals@example.com")
        async with factory() as session:
            repo = UsageEventRepository(session)
            await _record(session, tenant, request_id="req_kept")
            event = await _record(session, tenant, request_id="req_reversed")
            await session.flush()
            # One charge stands and one is reversed, so the period nets to
            # a real total — a fully-netted period would leave no rollup
            # row at all, which is correct and would prove nothing here.
            await repo.reverse(event, reason="incident 42", at=AUGUST)
            await session.commit()
        await _rebuild(factory, tenant)

        async with factory() as session:
            count = await reversal_activity(session, since=PERIOD.start, until=PERIOD.end)
            stale = await stale_rollups(session, older_than=datetime(2099, 1, 1, tzinfo=UTC))

    assert count >= 1
    assert any(row[0] == tenant.organization.id for row in stale)


# ── Language analytics: the Core Speech Language Policy ─────────────────


async def test_language_adoption_counts_organizations_not_requests(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The roadmap question is how many CUSTOMERS need a language. One
    enthusiastic tenant looks like adoption in a request count and does
    not in this one."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        enthusiast = await _tenant(factory, "lang-enthusiast@example.com")
        hindi_one = await _tenant(factory, "lang-hi-1@example.com")
        hindi_two = await _tenant(factory, "lang-hi-2@example.com")

        async with factory() as session:
            for index in range(20):
                await _record(session, enthusiast, request_id=f"req_en_{index}", language="en")
            await _record(session, hindi_one, request_id="req_hi_1", language="hi")
            await _record(session, hindi_two, request_id="req_hi_2", language="hi")
            await session.commit()

        async with factory() as session:
            report = await language_report(
                session,
                since=PERIOD.start,
                until=PERIOD.end,
                organization_ids=[
                    enthusiast.organization.id,
                    hindi_one.organization.id,
                    hindi_two.organization.id,
                ],
            )

    adoption = report.adoption()
    assert adoption["en"] == 1  # twenty requests, one customer
    assert adoption["hi"] == 2  # two requests, two customers
    assert set(adoption) == set(POLICY_LANGUAGES)


async def test_language_report_separates_policy_from_unserved_demand(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Demand outside the policy is the evidence that should drive engine
    research, rather than intuition about which language matters next."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "lang-demand@example.com")
        async with factory() as session:
            for index, language in enumerate(("en", "hi", "ar", "fr", "ta")):
                await _record(session, tenant, request_id=f"req_lang_{index}", language=language)
            await session.commit()

        async with factory() as session:
            report = await language_report(
                session,
                since=PERIOD.start,
                until=PERIOD.end,
                organization_ids=[tenant.organization.id],
            )

    assert {row.language for row in report.policy_rows} == {"en", "hi", "ar"}
    assert report.unserved_demand() == ("fr", "ta")


async def test_language_analytics_carry_measured_quantities(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Adoption is requests AND volume: one huge Hindi customer and a
    hundred tiny ones are different roadmap facts."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "lang-volume@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_v1", language="hi", characters=5_000)
            await _record(session, tenant, request_id="req_v2", language="hi", characters=7_000)
            await session.commit()

        async with factory() as session:
            report = await language_report(
                session,
                since=PERIOD.start,
                until=PERIOD.end,
                organization_ids=[tenant.organization.id],
            )

    (hindi,) = [row for row in report.rows if row.language == "hi"]
    assert hindi.requests == 2
    assert hindi.quantities["characters"] == Decimal(12_000)
    assert hindi.in_policy


async def test_regional_language_tags_still_count_toward_the_policy(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """``hi-IN`` is Hindi. A policy that only recognises bare codes would
    under-report the adoption it exists to track."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "lang-regional@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_hi_in", language="hi-IN")
            await _record(session, tenant, request_id="req_ar_eg", language="ar-EG")
            await session.commit()

        async with factory() as session:
            report = await language_report(
                session,
                since=PERIOD.start,
                until=PERIOD.end,
                organization_ids=[tenant.organization.id],
            )

    assert report.adoption()["hi"] == 1
    assert report.adoption()["ar"] == 1
    assert report.unserved_demand() == ()


async def test_language_never_reaches_pricing_or_quota(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Operational Measurement Independence (§10.1c): language is a fact
    for analytics, never a commercial dimension."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "lang-neutral@example.com")
        async with factory() as session:
            for index, language in enumerate(("en", "hi", "ar")):
                await _record(
                    session,
                    tenant,
                    request_id=f"req_neutral_{index}",
                    language=language,
                    characters=1_000,
                )
            await session.commit()

        async with factory() as session:
            events = await UsageEventRepository(session).list_for_organization(
                tenant.organization.id, since=PERIOD.start, until=PERIOD.end
            )

    per_language_quantities = {
        event.language: tuple(sorted((q.unit, q.amount) for q in event.quantities))
        for event in events
    }
    assert len(set(per_language_quantities.values())) == 1  # identical consumption


# ── Recovery under infrastructure failure ───────────────────────────────


async def test_a_corrupted_cache_recovers_by_rebuilding_and_reconciles_clean(
    settings: Settings, db_engine: AsyncEngine, tmp_path: Path
) -> None:
    """The full recovery loop: detect, repair, re-audit.

    Recovery is only real if the audit that found the problem also
    confirms the fix — otherwise 'repaired' is a hope.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recovery-cache@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_recovery", characters=4_242)
            await session.commit()
        await _rebuild(factory, tenant)

        async with factory() as session:
            await session.execute(
                update(UsageRollup)
                .where(UsageRollup.organization_id == tenant.organization.id)
                .values(amount=Decimal(-1))
            )
            await session.commit()

        async with factory() as session:
            broken = await reconcile(
                session,
                PERIOD,
                fallback_path=tmp_path / "none.jsonl",
                organization_ids=[tenant.organization.id],
            )
        assert not broken.clean

        await _rebuild(factory, tenant)  # the repair

        async with factory() as session:
            healed = await reconcile(
                session,
                PERIOD,
                fallback_path=tmp_path / "none.jsonl",
                organization_ids=[tenant.organization.id],
            )

    assert healed.clean, [f.detail for f in healed.findings]
    assert healed.ledger_total == healed.rollup_total


async def test_the_ledger_is_untouched_by_cache_corruption_and_repair(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The point of the hierarchy: whatever happens to the cache, the
    facts are exactly where they were."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recovery-ledger@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_untouched", characters=777)
            await session.commit()

        async def fingerprint() -> list[tuple[int, str, Decimal]]:
            async with factory() as session:
                events = await UsageEventRepository(session).list_for_organization(
                    tenant.organization.id, since=PERIOD.start, until=PERIOD.end
                )
                return [
                    (event.id, quantity.unit, quantity.amount)
                    for event in events
                    for quantity in event.quantities
                ]

        before = await fingerprint()
        await _rebuild(factory, tenant)
        async with factory() as session:
            await session.execute(
                update(UsageRollup)
                .where(UsageRollup.organization_id == tenant.organization.id)
                .values(amount=Decimal(0))
            )
            await session.commit()
        await _rebuild(factory, tenant)
        after = await fingerprint()

    assert before == after


async def test_reconciliation_needs_no_redis_at_all(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The audit path shares fate with the ledger, not with the limiter.

    A Redis outage degrades protection (§10.3); it must not prevent us
    from finding out whether the books are right.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "recovery-noredis@example.com")
        async with factory() as session:
            await _record(session, tenant, request_id="req_noredis")
            await session.commit()
        await _rebuild(factory, tenant)

        # No limiter is constructed, contacted, or required anywhere here.
        async with factory() as session:
            report = await reconcile(session, PERIOD, organization_ids=[tenant.organization.id])

    assert report.clean, [f.detail for f in report.findings]
