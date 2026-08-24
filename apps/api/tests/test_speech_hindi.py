"""M39 — Hindi TTS through the gateway product plane (staging profile).

The voice is the routing key: `hindi-female` / `hindi-male` exist only
in the staging registry, resolve to the incumbent artifact, ride the
SAME endpoint, and bill by the SAME characters-only law as English.
The production profile keeps refusing them before any plane crossing.
"""

from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent
from intelliai_api.registry.proposals import staging_registry
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db
from tests.test_speech_api import PEPPER, FakeSynthesisClient, make_envelope

pytestmark = pytest.mark.anyio

HINDI_TEXT = "नमस्ते, आपका नाम क्या है? " * 10


def install_staging(fake: FakeSynthesisClient) -> Callable[[FastAPI], None]:
    """The staging-profile app shape: same fake runtime, the registry
    the staging profile composes (main.py does exactly this swap)."""

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}
        app.state.registry = staging_registry()

    return configure


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="Hindi TTS Co", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


async def _tts_events(
    factory: async_sessionmaker[AsyncSession], tenant: BootstrapResult
) -> list[UsageEvent]:
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


async def test_hindi_voice_serves_and_bills_characters_exactly(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    text = ("न" * 999) + "।"  # exactly 1000 characters, Devanagari
    fake = FakeSynthesisClient(envelope=make_envelope(voice="hindi-female", characters=1000))
    async with client_with_db(settings, db_engine, install_staging(fake)) as (client, factory):
        tenant = await _tenant(factory, "hindi-bill@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": text, "voice": "hindi-female"},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 200
        # The runtime saw the PUBLIC voice id — engine pack tokens never
        # cross the contract in either direction.
        assert fake.calls[0].voice == "hindi-female"
        assert fake.calls[0].text == text

        (event,) = await _tts_events(factory, tenant)
        assert event.billable is True
        assert {q.unit: q.amount for q in event.quantities} == {"characters": Decimal(1000)}
        # The voice's declared language is the recorded language fact.
        assert event.language == "hi"


async def test_hindi_male_resolves_too(settings: Settings, db_engine: AsyncEngine) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope(voice="hindi-male", characters=21))
    async with client_with_db(settings, db_engine, install_staging(fake)) as (client, factory):
        tenant = await _tenant(factory, "hindi-male@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": "मेरा नाम सुमित है।", "voice": "hindi-male"},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 200
        assert fake.calls[0].voice == "hindi-male"


async def test_the_default_production_profile_now_serves_the_hindi_voices(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # M42: the promotion landed in the LIVE catalog, so the default
    # (production) profile serves the Hindi voices exactly as staging
    # does — the two profiles agree because no proposal is pending.
    from tests.test_speech_api import install  # the default-profile shape

    fake = FakeSynthesisClient(envelope=make_envelope(voice="hindi-female", characters=7))
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "hindi-prod-serves@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": "नमस्ते।", "voice": "hindi-female"},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 200
        assert fake.calls[0].voice == "hindi-female"


async def test_engine_voice_tokens_are_still_refused_before_any_plane_crossing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The promotion promoted PRODUCT names, never engine assets: asking
    # for the pack behind the voice is still a plain voice_not_found,
    # refused by the registry before the runtime is ever called.
    from tests.test_speech_api import install

    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "hindi-engine-token@example.com")
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "intelliai-tts", "input": "नमस्ते।", "voice": "hf_alpha"},
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "voice_not_found"
        assert fake.calls == []


async def test_voices_endpoint_reflects_the_profile(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_envelope())
    async with client_with_db(settings, db_engine, install_staging(fake)) as (client, factory):
        tenant = await _tenant(factory, "hindi-voices@example.com")
        listing = await client.get(
            "/v1/audio/voices",
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
        )
        assert listing.status_code == 200
        by_id = {voice["id"]: voice for voice in listing.json()["data"]}
        assert by_id["hindi-female"]["languages"] == ["hi"]
        assert by_id["hindi-male"]["languages"] == ["hi"]
        # English voices stay exactly English.
        assert by_id["english-female"]["languages"] == ["en"]
        assert by_id["english-male"]["languages"] == ["en"]
        # No engine token leaks into the public listing.
        surface = str(listing.json()).lower()
        for banned in ("hf_alpha", "hm_psi", "kokoro", "espeak"):
            assert banned not in surface
