"""M35 billing law: synthesis bills CHARACTERS — exactly, and only.

The M32/M33 audit found the dual-unit trap: `audio_seconds` carries a
book price (it is STT's billable unit) and `rate_events` prices every
priced unit on a billable event, so a synthesis row carrying both
quantities would charge a customer twice for one response. These tests
pin the fix at every layer: the ledger row, the rated invoice, and the
failure paths.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent
from intelliai_api.pricing import CATALOG
from intelliai_api.pricing.rating import rate_events
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db
from tests.test_speech_api import PEPPER, FakeSynthesisClient, install, make_envelope

pytestmark = pytest.mark.anyio


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="TTS Billing Co", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


async def _tts_events(
    factory: async_sessionmaker[AsyncSession], tenant: BootstrapResult
) -> list[UsageEvent]:
    """Tenant-scoped, like every read on a tenant-owned table — an
    unscoped read would pass or fail depending on what else the test
    database holds."""
    async with factory() as session:
        rows = await session.execute(
            select(UsageEvent)
            .where(UsageEvent.organization_id == tenant.organization.id)
            .where(UsageEvent.capability == "speech_synthesis")
        )
        events = list(rows.scalars().unique())
        for event in events:
            _ = [(quantity.unit, quantity.amount) for quantity in event.quantities]
        return events


async def test_exactly_one_thousand_characters_bills_exactly_one_thousand_units(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope(characters=1000))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "chars-1000@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": "a" * 1000},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 200

        (event,) = await _tts_events(factory, tenant)
        assert event.billable is True
        # The whole law in one line: one unit, the right amount, nothing else.
        assert {q.unit: q.amount for q in event.quantities} == {"characters": Decimal(1000)}
        # The measured duration is telemetry beside the lineage — metered,
        # never rated.
        assert event.lineage is not None
        assert event.lineage["measured_audio_seconds"] == 3.2


async def test_rating_a_synthesis_event_produces_a_characters_line_only(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope(characters=1000))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "rated@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": "a" * 1000},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 200
        events = await _tts_events(factory, tenant)

    rated = rate_events(
        events,
        organization_public_id=tenant.organization.public_id,
        period_label="2026-08",
    )
    assert [line.unit for line in rated.lines] == ["characters"]
    book = CATALOG.book_for(datetime(2026, 8, 20, tzinfo=UTC))
    price = book.price_of("characters")
    assert price is not None
    assert rated.lines[0].quantity == Decimal(1000)
    # The counterfactual that WOULD have fired under the old row shape:
    # audio_seconds is priced in the book (STT bills it), so its absence
    # from the synthesis row is exactly what prevents the double charge.
    assert book.price_of("audio_seconds") is not None


async def test_same_text_at_different_speeds_bills_identically(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    text = "The invoice total is 1247 dollars."
    observed: list[UsageEvent] = []
    for index, (speed, duration) in enumerate(((0.75, 4.5), (1.0, 3.2), (1.5, 2.1))):
        envelope = make_envelope(characters=len(text))
        envelope = envelope.model_copy(
            update={"output": envelope.output.model_copy(update={"duration_seconds": duration})}
        )
        fake = FakeSynthesisClient(envelope=envelope)
        async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
            tenant = await _tenant(factory, f"speed-{index}@example.com")
            response = await client.post(
                "/v1/audio/speech",
                json={"model": "intelliai-tts", "input": text, "speed": speed},
                headers={"Authorization": f"Bearer {tenant.generated.secret}"},
            )
            assert response.status_code == 200
            observed.extend(await _tts_events(factory, tenant))

    assert len(observed) == 3
    for event in observed:
        # Speed changes the audio duration, never the bill.
        assert {q.unit: q.amount for q in event.quantities} == {"characters": Decimal(len(text))}


async def test_failed_synthesis_and_validation_errors_bill_nothing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(unavailable=True)
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "failures@example.com")
        headers = {"Authorization": f"Bearer {tenant.generated.secret}"}
        # Runtime down: 503; at most a NON-billable capacity row.
        down = await client.post(
            "/v1/audio/speech", json={"model": "intelliai-tts", "input": "hello"}, headers=headers
        )
        assert down.status_code == 503
        # Empty input: refused before any plane crossing; never billable.
        empty = await client.post(
            "/v1/audio/speech", json={"model": "intelliai-tts", "input": ""}, headers=headers
        )
        assert empty.status_code in (400, 422)

        events = await _tts_events(factory, tenant)
    assert all(event.billable is False for event in events)
    assert all(not event.quantities for event in events)
