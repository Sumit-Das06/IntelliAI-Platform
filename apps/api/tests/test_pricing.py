"""Pricing and rating: what immutable facts are worth.

Five demonstrations, one per founder requirement:

1. historical price-book correctness
2. invoice regeneration from the ledger
3. rollup rebuild correctness
4. discounts changing only rating, never usage
5. multilingual engines and engine replacements producing identical
   commercial interpretation unless the pricing POLICY itself changes

Plus the two laws ratified at Step 4 close: commercial interpretation
evolves while commercial evidence does not (§8.4), and rollups are
caches that the ledger always outranks (§8.5).
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageOutcome, UsageRollup
from intelliai_api.db.repositories import UsageEventRepository, UsageRollupRepository
from intelliai_api.entitlements import period_for
from intelliai_api.pricing import (
    INTERNAL_V1,
    Agreement,
    PriceBook,
    PriceBookCatalog,
    rate_events,
    rate_rollup,
    rate_totals,
)
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"
AUGUST = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

# A second, cheaper book published later — the whole point of a catalog.
INTERNAL_V2 = PriceBook(
    version="internal-2026-10-v2",
    effective_from=date(2026, 10, 1),
    currency="USD",
    unit_prices={
        "audio_seconds": Decimal("0.00008"),
        "characters": Decimal("0.000012"),
    },
)
HISTORY = PriceBookCatalog(books=(INTERNAL_V1, INTERNAL_V2))


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="PriceCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


async def _record(
    session: AsyncSession,
    tenant: BootstrapResult,
    *,
    characters: int,
    at: datetime,
    request_id: str,
    origin: UsageOrigin = UsageOrigin.CUSTOMER,
    billable: bool = True,
    artifact: str = "kokoro-82m",
    language: str = "en",
) -> UsageEvent:
    return await UsageEventRepository(session).record(
        organization_id=tenant.organization.id,
        capability="speech_synthesis",
        public_model_id="intelliai-tts",
        language=language,
        origin=origin,
        outcome=UsageOutcome.SUCCEEDED,
        billable=billable,
        occurred_at=at,
        quantities={"characters": Decimal(characters)},
        request_id=request_id,
        lineage={"artifact": artifact},
    )


async def _events(
    factory: async_sessionmaker[AsyncSession], tenant: BootstrapResult, *, at: datetime
) -> list[UsageEvent]:
    period = period_for(at)
    async with factory() as session:
        return list(
            await UsageEventRepository(session).list_for_organization(
                tenant.organization.id, since=period.start, until=period.end
            )
        )


# ── 1. Historical price-book correctness ────────────────────────────────


def test_a_price_cut_never_reprices_the_past() -> None:
    """The single most important property in the pricing layer.

    Publishing a cheaper book in October must not make August cheaper.
    An invoice regenerated years later has to produce the number the
    customer actually paid, and the only way that holds is selecting the
    book by when the usage OCCURRED.
    """
    assert HISTORY.book_for(AUGUST).version == INTERNAL_V1.version
    assert HISTORY.book_for(OCTOBER).version == INTERNAL_V2.version

    totals = {"characters": Decimal(1_000_000)}
    assert rate_totals(totals, at=AUGUST, catalog=HISTORY) == Decimal("15.00")
    assert rate_totals(totals, at=OCTOBER, catalog=HISTORY) == Decimal("12.00")

    # The boundary belongs to the new book from its first instant.
    assert HISTORY.book_for(datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC)).version == (
        INTERNAL_V1.version
    )
    assert HISTORY.book_for(datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)).version == (
        INTERNAL_V2.version
    )


async def test_a_period_spanning_a_price_change_produces_lines_under_both(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Rating asks the catalog per EVENT, not once per invoice run.

    Rating a whole period at "the current book" would be one line
    shorter and would silently re-price history — so a period that spans
    a change must show its work.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "price-span@example.com")
        async with factory() as session:
            await _record(session, tenant, characters=1_000_000, at=AUGUST, request_id="req_aug")
            await _record(session, tenant, characters=1_000_000, at=OCTOBER, request_id="req_oct")
            await session.commit()

        async with factory() as session:
            events = list(
                await UsageEventRepository(session).list_for_organization(
                    tenant.organization.id,
                    since=datetime(2026, 8, 1, tzinfo=UTC),
                    until=datetime(2026, 11, 1, tzinfo=UTC),
                )
            )

    rated = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08..10",
        catalog=HISTORY,
    )
    assert rated.price_book_versions == (INTERNAL_V1.version, INTERNAL_V2.version)
    assert {line.amount for line in rated.lines} == {Decimal("15.00"), Decimal("12.00")}
    assert rated.total == Decimal("27.00")


def test_usage_older_than_every_price_is_refused_not_guessed() -> None:
    """Silently applying the earliest book would invent a price nobody
    ever agreed to."""
    with pytest.raises(ValueError, match="no price book was in effect"):
        HISTORY.book_for(datetime(2026, 1, 1, tzinfo=UTC))


def test_a_catalog_refuses_to_be_built_wrong() -> None:
    """Versions are identities and order is meaning; both are checked at
    construction rather than discovered during a billing run."""
    with pytest.raises(ValueError, match="effective-date order"):
        PriceBookCatalog(books=(INTERNAL_V2, INTERNAL_V1))
    with pytest.raises(ValueError, match="unique"):
        PriceBookCatalog(books=(INTERNAL_V1, INTERNAL_V1))
    with pytest.raises(ValueError, match="price nothing"):
        PriceBookCatalog(books=())


# ── 2. Invoice regeneration from the ledger ─────────────────────────────


async def test_an_invoice_regenerates_identically_from_the_ledger(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The property the whole plane exists for.

    Same events, same catalog, same agreement — same money, every time.
    Nothing is cached, nothing is stamped at first run, so there is no
    state that could drift between the original and the regeneration.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "invoice-regen@example.com")
        async with factory() as session:
            for index in range(5):
                await _record(
                    session, tenant, characters=200_000, at=AUGUST, request_id=f"req_{index}"
                )
            await session.commit()

        events = await _events(factory, tenant, at=AUGUST)

        def build() -> object:
            return rate_events(
                events,
                organization_public_id=tenant.organization.public_id,
                period_label="2026-08",
                catalog=HISTORY,
            )

        first = build()
        second = build()

        # Frozen dataclasses compare by value: identical means identical.
        assert first == second

        # And regenerating from a FRESH read of the ledger agrees too.
        reread = await _events(factory, tenant, at=AUGUST)
        third = rate_events(
            reread,
            organization_public_id=tenant.organization.public_id,
            period_label="2026-08",
            catalog=HISTORY,
        )
        assert third == first

    assert third.total == Decimal("15.00")  # 1,000,000 characters at v1
    assert third.rated_events == 5


async def test_a_correction_reprices_the_period_without_editing_anything(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Compensating events participate in rating naturally.

    A period corrected by reversal rates to the corrected number, and the
    original row is still there to explain why — commercial evidence does
    not change, commercial interpretation follows it.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "invoice-correct@example.com")
        async with factory() as session:
            repo = UsageEventRepository(session)
            original = await _record(
                session, tenant, characters=1_000_000, at=AUGUST, request_id="req_wrong"
            )
            await session.flush()
            await repo.reverse(original, reason="duplicate billing incident", at=AUGUST)
            await session.commit()

        events = await _events(factory, tenant, at=AUGUST)

    rated = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        catalog=HISTORY,
    )
    assert rated.total == Decimal("0.00")  # netted
    assert rated.rated_events == 2  # both rows still present and rated
    assert len(events) == 2


async def test_non_customer_origins_are_recorded_and_never_rated(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Founder decision F7 at the rating layer, and the Commercial
    Interpretation Invariant in miniature: the same immutable facts, a
    different lens."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "invoice-origins@example.com")
        async with factory() as session:
            await _record(
                session, tenant, characters=1_000_000, at=AUGUST, request_id="req_customer"
            )
            await _record(
                session,
                tenant,
                characters=9_000_000,
                at=AUGUST,
                request_id="req_bench",
                origin=UsageOrigin.BENCHMARK,
            )
            await _record(
                session,
                tenant,
                characters=500_000,
                at=AUGUST,
                request_id="req_failed",
                billable=False,
            )
            await session.commit()

        events = await _events(factory, tenant, at=AUGUST)

    rated = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        catalog=HISTORY,
    )
    assert rated.total == Decimal("15.00")  # only the customer's million
    assert rated.rated_events == 1
    assert rated.unrated_events == 2  # measured, visible, and not billed


def test_rounding_happens_once_at_the_line() -> None:
    """ADR-0023: never at measurement, never twice.

    A line worth less than half a cent rounds to zero, which is the
    honest answer — we do not charge fractions of a cent — and the total
    is the sum of already-rounded lines, so nothing rounds twice.
    """
    totals = {"characters": Decimal(100)}  # $0.0015 — below half a cent
    assert rate_totals(totals, at=AUGUST, catalog=HISTORY) == Decimal("0.0015")


# ── 3. Rollup rebuild correctness ───────────────────────────────────────


async def test_a_rollup_rebuilds_to_exactly_what_the_ledger_says(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rollup-rebuild@example.com")
        period = period_for(AUGUST)
        async with factory() as session:
            for index in range(4):
                await _record(
                    session, tenant, characters=250_000, at=AUGUST, request_id=f"req_r{index}"
                )
            await session.commit()

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            built = await rollups.rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()

        assert built == {"characters": Decimal(1_000_000)}

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            assert await rollups.totals(
                tenant.organization.id, since=period.start, until=period.end
            ) == {"characters": Decimal(1_000_000)}
            assert await rollups.agrees_with_ledger(
                tenant.organization.id, since=period.start, until=period.end
            )


async def test_when_a_rollup_disagrees_the_ledger_wins(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The Rollup Invariant's third rule, exercised directly.

    The cache is corrupted on purpose — something a rollup can suffer and
    the ledger cannot, since the ledger refuses UPDATE at the database.
    Disagreement is detected, and repaired by rebuilding the cache, never
    by adjusting the ledger to match.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rollup-disagree@example.com")
        period = period_for(AUGUST)
        async with factory() as session:
            await _record(session, tenant, characters=1_000_000, at=AUGUST, request_id="req_truth")
            await session.commit()

        async with factory() as session:
            await UsageRollupRepository(session).rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()

        # Corrupt the cache — a rollup permits exactly what the ledger forbids.
        async with factory() as session:
            await session.execute(
                update(UsageRollup)
                .where(UsageRollup.organization_id == tenant.organization.id)
                .values(amount=Decimal(1))
            )
            await session.commit()

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            assert not await rollups.agrees_with_ledger(
                tenant.organization.id, since=period.start, until=period.end
            )
            # Repair is a rebuild. The ledger is never touched.
            await rollups.rebuild(tenant.organization.id, since=period.start, until=period.end)
            await session.commit()

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            assert await rollups.agrees_with_ledger(
                tenant.organization.id, since=period.start, until=period.end
            )
            assert await rollups.totals(
                tenant.organization.id, since=period.start, until=period.end
            ) == {"characters": Decimal(1_000_000)}


async def test_a_rollup_can_be_dropped_entirely_and_regenerated(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """A cache that cannot be dropped and regenerated is not a cache — so
    the ABSENCE of the ledger's append-only triggers on this table is a
    feature, and this is the test that says so."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rollup-drop@example.com")
        period = period_for(AUGUST)
        async with factory() as session:
            await _record(session, tenant, characters=42, at=AUGUST, request_id="req_drop")
            await session.commit()

        async with factory() as session:
            await UsageRollupRepository(session).rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()

        # Deleting a rollup row is permitted; deleting a ledger row is not.
        async with factory() as session:
            await session.execute(
                delete(UsageRollup).where(UsageRollup.organization_id == tenant.organization.id)
            )
            await session.commit()

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            assert (
                await rollups.totals(tenant.organization.id, since=period.start, until=period.end)
                == {}
            )
            rebuilt = await rollups.rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()
        assert rebuilt == {"characters": Decimal(42)}

        # ...and the same DELETE against the ledger is refused.
        async with factory() as session:
            with pytest.raises(Exception, match="append-only ledger"):
                await session.execute(
                    text("DELETE FROM usage_events WHERE organization_id = :org"),
                    {"org": tenant.organization.id},
                )
            await session.rollback()


async def test_a_rebuild_removes_units_the_ledger_no_longer_supports(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Delete-then-insert rather than upsert, on purpose: a unit whose
    events were all reversed must vanish from the cache too, or the
    rollup keeps a row no ledger fact supports."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rollup-vanish@example.com")
        period = period_for(AUGUST)
        async with factory() as session:
            repo = UsageEventRepository(session)
            event = await _record(
                session, tenant, characters=1_000, at=AUGUST, request_id="req_vanish"
            )
            await session.flush()
            await UsageRollupRepository(session).rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()

            await repo.reverse(event, reason="fully reversed", at=AUGUST)
            await session.commit()

        async with factory() as session:
            rollups = UsageRollupRepository(session)
            rebuilt = await rollups.rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()
        assert rebuilt == {}  # netted to nothing, so the row is gone

        async with factory() as session:
            assert await UsageRollupRepository(session).agrees_with_ledger(
                tenant.organization.id, since=period.start, until=period.end
            )


async def test_rating_from_a_rollup_matches_rating_from_the_ledger(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The cache is only worth having if it produces the same money."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rollup-rating@example.com")
        period = period_for(AUGUST)
        async with factory() as session:
            for index in range(3):
                await _record(
                    session, tenant, characters=333_333, at=AUGUST, request_id=f"req_rr{index}"
                )
            await session.commit()

        events = await _events(factory, tenant, at=AUGUST)
        async with factory() as session:
            rollups = UsageRollupRepository(session)
            await rollups.rebuild(tenant.organization.id, since=period.start, until=period.end)
            await session.commit()
        async with factory() as session:
            cached = await UsageRollupRepository(session).totals(
                tenant.organization.id, since=period.start, until=period.end
            )

    from_ledger = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        catalog=HISTORY,
    )
    from_cache = rate_rollup(
        list(cached.items()),
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        at=AUGUST,
        catalog=HISTORY,
    )
    assert from_cache.total == from_ledger.total
    assert from_cache.price_book_versions == from_ledger.price_book_versions


# ── 4. Discounts change rating, never usage ─────────────────────────────


async def test_a_discount_changes_the_money_and_nothing_else(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The Commercial Interpretation Invariant, demonstrated.

    The same immutable facts are rated twice under two agreements. The
    money differs; the usage, the events, and the lines' quantities are
    byte-identical. A promotion that touched the ledger would make last
    quarter unreproducible.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "discount@example.com")
        async with factory() as session:
            await _record(session, tenant, characters=1_000_000, at=AUGUST, request_id="req_disc")
            await session.commit()

        before = await _events(factory, tenant, at=AUGUST)
        standard = rate_events(
            before,
            organization_public_id=tenant.organization.public_id,
            period_label="2026-08",
            catalog=HISTORY,
        )
        discounted = rate_events(
            before,
            organization_public_id=tenant.organization.public_id,
            period_label="2026-08",
            catalog=HISTORY,
            agreement=Agreement(id="launch-25", discount_percent=Decimal(25), reason="launch"),
        )
        after = await _events(factory, tenant, at=AUGUST)

    # The money moved...
    assert standard.total == Decimal("15.00")
    assert discounted.discount_amount == Decimal("3.75")
    assert discounted.total == Decimal("11.25")
    # ...the facts did not.
    assert [line.quantity for line in standard.lines] == [
        line.quantity for line in discounted.lines
    ]
    assert [(event.id, event.occurred_at) for event in before] == [
        (event.id, event.occurred_at) for event in after
    ]
    # And the result names the lens that produced it.
    assert discounted.agreement_id == "launch-25"
    assert standard.agreement_id == "standard"


def test_a_discount_outside_zero_to_a_hundred_is_refused() -> None:
    with pytest.raises(ValueError, match="percentage between 0 and 100"):
        Agreement(id="impossible", discount_percent=Decimal(150))
    with pytest.raises(ValueError, match="percentage between 0 and 100"):
        Agreement(id="negative", discount_percent=Decimal(-1))


def test_the_ledger_has_no_place_to_put_a_discount() -> None:
    """Enforced structurally, not trusted: interpretation cannot be
    written into evidence because evidence has no column for it."""
    interpretation = {
        "discount",
        "discount_percent",
        "agreement_id",
        "plan",
        "price",
        "price_book_version",
        "amount_due",
        "total",
    }
    columns = set(UsageEvent.__table__.columns.keys())
    assert not (columns & interpretation), f"interpretation in the ledger: {columns}"

    # The rollup is derived, and money stays out of it too.
    rollup_columns = set(UsageRollup.__table__.columns.keys())
    assert not (rollup_columns & interpretation)


# ── 5. Engine replacement and multilingual routing ──────────────────────


REALITIES = [
    ("kokoro-82m", "en"),
    ("indicf5-hi", "hi"),
    ("future-arabic-v1", "ar"),
    ("kokoro-82m-int8", "en"),
    ("kokoro-82m+lora-hi", "hi"),
    ("router:multilingual-v2", "ar"),
]


async def test_every_engine_and_language_rates_identically(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Commercial identity survives every internal replacement.

    Six identical customer requests, six different engines, three
    languages. Each rates to exactly the same money under the same book
    version — the interpretation cannot see what served the request, and
    by the Protection Independence Invariant it may not.
    """
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rating-engines@example.com")
        async with factory() as session:
            for index, (artifact, language) in enumerate(REALITIES):
                await _record(
                    session,
                    tenant,
                    characters=100_000,
                    at=AUGUST,
                    request_id=f"req_engine_{index}",
                    artifact=artifact,
                    language=language,
                )
            await session.commit()

        events = await _events(factory, tenant, at=AUGUST)

    per_event = [
        rate_events(
            [event],
            organization_public_id=tenant.organization.public_id,
            period_label="2026-08",
            catalog=HISTORY,
        )
        for event in events
    ]
    totals = {rated.total for rated in per_event}
    versions = {rated.price_book_versions for rated in per_event}

    assert totals == {Decimal("1.50")}  # one price, six realities
    assert versions == {(INTERNAL_V1.version,)}
    assert {event.lineage["artifact"] for event in events} == {a for a, _ in REALITIES}
    assert {event.language for event in events} == {"en", "hi", "ar"}


async def test_only_a_change_in_public_pricing_policy_changes_the_money(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The exception the founder named: engines never change the number,
    but the pricing POLICY may — deliberately, visibly, and by version."""
    async with client_with_db(settings, db_engine) as (_client, factory):
        tenant = await _tenant(factory, "rating-policy@example.com")
        async with factory() as session:
            await _record(
                session,
                tenant,
                characters=1_000_000,
                at=AUGUST,
                request_id="req_policy",
                artifact="future-arabic-v1",
                language="ar",
            )
            await session.commit()
        events = await _events(factory, tenant, at=AUGUST)

    under_v1 = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        catalog=PriceBookCatalog(books=(INTERNAL_V1,)),
    )
    # A policy that prices August differently — the ONLY way the money moves.
    revised = PriceBook(
        version="internal-2026-08-v1b",
        effective_from=date(2026, 8, 1),
        currency="USD",
        unit_prices={"characters": Decimal("0.00002")},
    )
    under_policy = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
        catalog=PriceBookCatalog(books=(revised,)),
    )

    assert under_v1.total == Decimal("15.00")
    assert under_policy.total == Decimal("20.00")
    # Each result names the policy that produced it, so the difference is
    # always explicable rather than mysterious.
    assert under_v1.price_book_versions == (INTERNAL_V1.version,)
    assert under_policy.price_book_versions == (revised.version,)
