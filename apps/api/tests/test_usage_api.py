"""Usage summary: API consumption, org-scoped, honest about what it knows.

The laws pinned here: the endpoint reports CONSUMPTION and never dataset
statistics (no samples, corrections, or storage); it counts real requests
from the append-only ledger; the success rate is computed from recorded
outcomes rather than assumed; the daily series covers every day in the
window including the quiet ones; and one tenant's usage is invisible to
another.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import UsageOrigin, UsageOutcome
from intelliai_api.db.repositories import UsageEventRepository
from tests.helpers import client_with_db
from tests.test_collection import _bearer, _post_kwargs, _tenant, install
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio


async def _record(
    factory: async_sessionmaker[AsyncSession],
    organization_id: int,
    *,
    outcome: UsageOutcome = UsageOutcome.SUCCEEDED,
    audio_seconds: float | None = 11.0,
    language: str | None = "en",
    occurred_at: datetime | None = None,
    request_id: str,
) -> None:
    """Append one ledger event directly — the analytics reads are about
    what the ledger holds, whatever produced it."""
    async with factory() as session:
        quantities = {} if audio_seconds is None else {"audio_seconds": Decimal(str(audio_seconds))}
        await UsageEventRepository(session).record(
            organization_id=organization_id,
            api_key_id=None,
            request_id=request_id,
            capability="transcription",
            public_model_id="intelliai-stt",
            language=language,
            origin=UsageOrigin.CUSTOMER,
            outcome=outcome,
            billable=outcome is UsageOutcome.SUCCEEDED,
            occurred_at=occurred_at or utc_now(),
            quantities=quantities,
        )
        await session.commit()


async def _summary(client: Any, secret: str, query: str = "") -> dict[str, Any]:
    response = await client.get(f"/v1/usage/summary{query}", headers=_bearer(secret))
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def test_it_reports_consumption_never_dataset_statistics(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A real transcription writes BOTH a usage event and (with consent) a
    # speech sample. Usage must speak only about the first: samples,
    # corrections, and storage belong to Speech Samples.
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "usage-scope@example.com", consent=True)
        transcribed = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="en"),
        )
        assert transcribed.status_code == 200
        assert "X-IntelliAI-Sample" in transcribed.headers  # a sample WAS collected

        body = await _summary(client, tenant.generated.secret)

    assert body["totals"]["requests"] == 1
    assert body["totals"]["speech_minutes"] == pytest.approx(11.0 / 60, abs=0.01)
    assert set(body) == {"period", "totals", "daily", "languages", "models"}
    # The dataset vocabulary must not appear anywhere in the payload.
    serialized = str(body).lower()
    for dataset_word in ("sample", "correction", "storage", "bytes", "transcript"):
        assert dataset_word not in serialized
    # Nor may producer internals: public model ids only.
    assert [model["key"] for model in body["models"]] == ["intelliai-stt"]
    assert "whisper" not in serialized


async def test_the_success_rate_reflects_recorded_outcomes(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Failures reach the ledger out-of-band, so the rate is a real
    # measurement — never a tautological 100%.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-outcomes@example.com", consent=False)
        organization_id = tenant.organization.id
        await _record(factory, organization_id, request_id="req_ok_1")
        await _record(factory, organization_id, request_id="req_ok_2")
        await _record(
            factory,
            organization_id,
            outcome=UsageOutcome.FAILED,
            audio_seconds=None,
            request_id="req_fail_1",
        )

        body = await _summary(client, tenant.generated.secret)

    totals = body["totals"]
    assert totals["requests"] == 3
    assert totals["outcomes"] == {"succeeded": 2, "failed": 1}
    assert totals["success_rate"] == pytest.approx(2 / 3, abs=0.001)
    # A failed request measured no audio, so the average is over the two
    # requests that actually carried some.
    assert totals["average_request_seconds"] == pytest.approx(11.0, abs=0.01)


async def test_an_empty_period_is_undefined_not_perfect(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A success rate over zero requests is not 100% — it is unknown.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-empty@example.com", consent=False)

        body = await _summary(client, tenant.generated.secret, "?days=7")

    assert body["totals"]["requests"] == 0
    assert body["totals"]["success_rate"] is None
    assert body["totals"]["average_request_seconds"] is None
    assert body["totals"]["speech_minutes"] == 0.0
    assert len(body["daily"]) == 7
    assert all(day["requests"] == 0 for day in body["daily"])


async def test_the_series_covers_every_day_in_the_window(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Quiet days are part of the trend: omitting them would draw a line
    # that lies about the shape of usage.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-series@example.com", consent=False)
        now = utc_now()
        await _record(factory, tenant.organization.id, request_id="req_today")
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=now - timedelta(days=2),
            request_id="req_two_days_ago",
        )
        # Outside the window entirely — must not be counted.
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=now - timedelta(days=20),
            request_id="req_long_ago",
        )

        body = await _summary(client, tenant.generated.secret, "?days=7")

    assert len(body["daily"]) == 7
    assert body["totals"]["requests"] == 2
    busy = [day for day in body["daily"] if day["requests"]]
    assert len(busy) == 2
    assert body["daily"][-1]["date"] == now.date().isoformat()
    assert datetime.fromisoformat(body["period"]["start"]).tzinfo is not None
    assert datetime.fromisoformat(body["period"]["start"]) == datetime.combine(
        (now - timedelta(days=6)).date(), datetime.min.time(), tzinfo=UTC
    )


async def test_languages_and_models_are_ranked_and_honest(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-breakdown@example.com", consent=False)
        organization_id = tenant.organization.id
        for index in range(3):
            await _record(factory, organization_id, language="en", request_id=f"req_en_{index}")
        await _record(factory, organization_id, language="hi", request_id="req_hi")
        # No language declared and none detected — a real category.
        await _record(factory, organization_id, language=None, request_id="req_none")

        body = await _summary(client, tenant.generated.secret)

    languages = body["languages"]
    assert languages[0]["key"] == "en"  # busiest first
    assert languages[0]["requests"] == 3
    assert {entry["key"] for entry in languages} == {"en", "hi", None}
    assert body["models"] == [
        {
            "key": "intelliai-stt",
            "requests": 5,
            "speech_minutes": pytest.approx(55.0 / 60, abs=0.01),
        }
    ]


async def test_usage_is_organization_scoped(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        owner = await _tenant(factory, "usage-owner@example.com", consent=False)
        stranger = await _tenant(factory, "usage-stranger@example.com", consent=False)
        await _record(factory, owner.organization.id, request_id="req_owner")

        mine = await _summary(client, owner.generated.secret)
        theirs = await _summary(client, stranger.generated.secret)

    assert mine["totals"]["requests"] == 1
    assert theirs["totals"]["requests"] == 0
    assert theirs["models"] == []


async def test_the_endpoint_requires_auth_and_validates_the_window(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-validation@example.com", consent=False)

        unauthenticated = await client.get("/v1/usage/summary")
        too_long = await client.get(
            "/v1/usage/summary?days=91", headers=_bearer(tenant.generated.secret)
        )
        too_short = await client.get(
            "/v1/usage/summary?days=0", headers=_bearer(tenant.generated.secret)
        )

    assert unauthenticated.status_code == 401
    # Platform envelope: validation errors are 400, never 422.
    assert too_long.status_code == 400
    assert too_short.status_code == 400
