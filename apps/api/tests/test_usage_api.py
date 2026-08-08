"""Usage summary: API consumption, org-scoped, honest about what it knows.

The laws pinned here: the endpoint reports CONSUMPTION and never dataset
statistics (no samples, corrections, or storage); it counts real requests
from the append-only ledger; the success rate is computed from recorded
outcomes rather than assumed; every bucket in the window is returned
including the empty ones; buckets are UTC whatever the server thinks
local time is; and one tenant's usage is invisible to another.
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
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _at(moment: datetime) -> str:
    """The instant as the API accepts it."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    assert set(body) == {
        "period",
        "granularity",
        "totals",
        "series",
        "daily",
        "languages",
        "models",
    }
    # The dataset vocabulary must not appear anywhere in the payload.
    serialized = str(body).lower()
    for dataset_word in ("sample", "correction", "storage", "bytes", "transcript"):
        assert dataset_word not in serialized
    # Nor may producer internals: public model ids only.
    assert [model["key"] for model in body["models"]] == ["intelliai-stt"]
    assert "whisper" not in serialized
    assert "lineage" not in serialized
    assert "artifact" not in serialized


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
    assert len(body["series"]) == 7
    assert all(bucket["requests"] == 0 for bucket in body["series"])


async def test_the_days_contract_is_unchanged(settings: Settings, db_engine: AsyncEngine) -> None:
    # Backwards compatibility: ?days= keeps meaning "the last N UTC days,
    # today included", and still fills the compatibility daily[] the
    # deployed console reads.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-days@example.com", consent=False)
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

        seven = await _summary(client, tenant.generated.secret, "?days=7")
        default = await _summary(client, tenant.generated.secret)

    assert seven["granularity"] == "daily"
    assert len(seven["series"]) == 7
    assert seven["totals"]["requests"] == 2
    assert len([b for b in seven["series"] if b["requests"]]) == 2
    # daily[] mirrors series and still carries plain dates.
    assert len(seven["daily"]) == 7
    assert seven["daily"][-1]["date"] == now.date().isoformat()
    assert seven["period"]["days"] == 7
    assert datetime.fromisoformat(seven["period"]["start"]) == datetime.combine(
        (now - timedelta(days=6)).date(), datetime.min.time(), tzinfo=UTC
    )
    # No parameters at all still means 30 daily buckets.
    assert default["granularity"] == "daily"
    assert len(default["series"]) == 30
    assert default["totals"]["requests"] == 3


async def test_daily_buckets_respect_utc_midnight(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The boundary case that a server time zone would silently move: one
    # second before midnight belongs to the day that is ending.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-utc-day@example.com", consent=False)
        yesterday = (utc_now() - timedelta(days=1)).date()
        last_moment = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(
            hours=23, minutes=59, seconds=59
        )
        first_moment = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC)
        await _record(
            factory, tenant.organization.id, occurred_at=last_moment, request_id="req_23_59_59"
        )
        await _record(
            factory, tenant.organization.id, occurred_at=first_moment, request_id="req_00_00_00"
        )

        body = await _summary(
            client,
            tenant.generated.secret,
            f"?start={yesterday.isoformat()}&end={yesterday.isoformat()}&granularity=daily",
        )

    assert len(body["series"]) == 1
    assert body["series"][0]["requests"] == 2
    assert body["series"][0]["timestamp"].startswith(yesterday.isoformat())
    assert body["totals"]["requests"] == 2


async def test_hourly_aggregation_buckets_by_utc_hour(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-hourly@example.com", consent=False)
        base = utc_now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=4)
        # Two in the first hour, one three hours later; the hours between
        # are silent and must still appear.
        await _record(factory, tenant.organization.id, occurred_at=base, request_id="req_h0_a")
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=base + timedelta(minutes=59, seconds=59),
            request_id="req_h0_b",
        )
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=base + timedelta(hours=3, minutes=30),
            request_id="req_h3",
        )

        body = await _summary(
            client,
            tenant.generated.secret,
            f"?start={_at(base)}&end={_at(base + timedelta(hours=4))}&granularity=hourly",
        )

    assert body["granularity"] == "hourly"
    assert body["daily"] == []  # the compatibility field is daily-only
    counts = [bucket["requests"] for bucket in body["series"]]
    assert counts == [2, 0, 0, 1]
    assert body["totals"]["requests"] == 3
    stamps = [bucket["timestamp"] for bucket in body["series"]]
    assert stamps == sorted(stamps)


async def test_minute_aggregation_buckets_by_utc_minute(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-minute@example.com", consent=False)
        base = utc_now().replace(second=0, microsecond=0) - timedelta(minutes=5)
        await _record(factory, tenant.organization.id, occurred_at=base, request_id="req_m0")
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=base + timedelta(seconds=59),
            request_id="req_m0_late",
        )
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=base + timedelta(minutes=2),
            request_id="req_m2",
        )

        body = await _summary(
            client,
            tenant.generated.secret,
            f"?start={_at(base)}&end={_at(base + timedelta(minutes=3))}&granularity=minute",
        )

    assert body["granularity"] == "minute"
    assert [bucket["requests"] for bucket in body["series"]] == [2, 0, 1]
    assert body["totals"]["requests"] == 3


async def test_start_and_end_filter_the_window(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-window@example.com", consent=False)
        now = utc_now()
        inside = (now - timedelta(days=3)).date()
        outside = (now - timedelta(days=10)).date()
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=datetime.combine(inside, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=9),
            request_id="req_inside",
        )
        await _record(
            factory,
            tenant.organization.id,
            occurred_at=datetime.combine(outside, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=9),
            request_id="req_outside",
        )

        body = await _summary(
            client,
            tenant.generated.secret,
            f"?start={(now - timedelta(days=4)).date().isoformat()}"
            f"&end={(now - timedelta(days=2)).date().isoformat()}",
        )

    # A bare end date means THROUGH that day: three days, one request.
    assert len(body["series"]) == 3
    assert body["totals"]["requests"] == 1
    assert body["period"]["days"] == 3


async def test_a_future_end_is_clamped_to_now(settings: Settings, db_engine: AsyncEngine) -> None:
    # The platform cannot know usage that has not happened, so a window
    # reaching into the future simply stops at now.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-future@example.com", consent=False)
        now = utc_now()

        body = await _summary(
            client,
            tenant.generated.secret,
            f"?start={now.date().isoformat()}&end={(now + timedelta(days=5)).date().isoformat()}",
        )

    assert datetime.fromisoformat(body["period"]["end"]) <= utc_now()
    assert len(body["series"]) == 1  # today only


async def test_minute_granularity_is_capped_at_two_days(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-minute-cap@example.com", consent=False)
        now = utc_now()

        refused = await client.get(
            f"/v1/usage/summary?start={_at(now - timedelta(hours=49))}"
            f"&end={_at(now)}&granularity=minute",
            headers=_bearer(tenant.generated.secret),
        )
        allowed = await client.get(
            f"/v1/usage/summary?start={_at(now - timedelta(hours=47))}"
            f"&end={_at(now)}&granularity=minute",
            headers=_bearer(tenant.generated.secret),
        )

    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "period_too_long"
    assert "48 hours" in refused.json()["error"]["message"]
    assert allowed.status_code == 200


async def test_hourly_granularity_is_capped_at_thirty_days(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-hourly-cap@example.com", consent=False)
        now = utc_now()

        refused = await client.get(
            f"/v1/usage/summary?start={_at(now - timedelta(days=31))}"
            f"&end={_at(now)}&granularity=hourly",
            headers=_bearer(tenant.generated.secret),
        )
        allowed = await client.get(
            f"/v1/usage/summary?start={_at(now - timedelta(days=29))}"
            f"&end={_at(now)}&granularity=hourly",
            headers=_bearer(tenant.generated.secret),
        )

    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "period_too_long"
    assert "30 days" in refused.json()["error"]["message"]
    assert allowed.status_code == 200


async def test_daily_granularity_is_capped_at_ninety_days(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-daily-cap@example.com", consent=False)
        now = utc_now()

        refused = await client.get(
            f"/v1/usage/summary?start={_at(now - timedelta(days=91))}&end={_at(now)}",
            headers=_bearer(tenant.generated.secret),
        )
        over_days = await client.get(
            "/v1/usage/summary?days=91", headers=_bearer(tenant.generated.secret)
        )

    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "period_too_long"
    assert "90 days" in refused.json()["error"]["message"]
    # The original guard still answers for the days form.
    assert over_days.status_code == 400


async def test_a_window_is_asked_for_one_way_or_the_other(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A caller who disagrees with themselves gets an error, not a guess.
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "usage-conflict@example.com", consent=False)
        today = utc_now().date().isoformat()

        conflict = await client.get(
            f"/v1/usage/summary?days=7&start={today}&end={today}",
            headers=_bearer(tenant.generated.secret),
        )
        half = await client.get(
            f"/v1/usage/summary?start={today}", headers=_bearer(tenant.generated.secret)
        )
        backwards = await client.get(
            f"/v1/usage/summary?start={today}&end=2020-01-01",
            headers=_bearer(tenant.generated.secret),
        )
        nonsense = await client.get(
            f"/v1/usage/summary?start=not-a-date&end={today}",
            headers=_bearer(tenant.generated.secret),
        )
        unknown_granularity = await client.get(
            "/v1/usage/summary?days=7&granularity=yearly",
            headers=_bearer(tenant.generated.secret),
        )

    assert conflict.status_code == 400
    assert conflict.json()["error"]["code"] == "period_conflict"
    assert half.status_code == 400
    assert half.json()["error"]["code"] == "invalid_period"
    assert backwards.status_code == 400
    assert nonsense.status_code == 400
    assert nonsense.json()["error"]["code"] == "invalid_period"
    # Platform envelope: validation errors are 400, never 422.
    assert unknown_granularity.status_code == 400


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
        now = utc_now()
        window = f"?start={_at(now - timedelta(hours=2))}&end={_at(now)}&granularity=hourly"

        mine = await _summary(client, owner.generated.secret)
        theirs = await _summary(client, stranger.generated.secret)
        their_hourly = await _summary(client, stranger.generated.secret, window)

    assert mine["totals"]["requests"] == 1
    assert theirs["totals"]["requests"] == 0
    assert theirs["models"] == []
    # Isolation holds at every granularity, not just the default.
    assert their_hourly["totals"]["requests"] == 0
    assert all(bucket["requests"] == 0 for bucket in their_hourly["series"])


async def test_the_endpoint_requires_authentication(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/v1/usage/summary")

    assert response.status_code == 401
