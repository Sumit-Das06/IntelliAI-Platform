"""GET /v1/usage/summary — API consumption, and only API consumption.

The subject of this endpoint is what the organization *asked the platform
to do*: requests, audio measured, outcomes, languages, public models. It
is deliberately NOT a dataset report — collected samples, corrections,
and storage are a different subject with their own page and their own
API (``/v1/speech-samples``). Mixing them would produce a page where
"12 requests" and "4 samples" invite a subtraction that means nothing.

Read-only over the existing append-only ledger: no new tables, no
rollups, no background jobs. Money-free by construction — the ledger
stores measurements, and pricing is a later, separate decision.

One thing this endpoint deliberately cannot report: which CLIENT made
the requests. Client identity (web, keyboard, api) is recorded on
collected samples, not on ledger events, and inferring API usage from
consented samples would be exactly the dataset/consumption confusion
this endpoint exists to avoid. Reporting it honestly needs a column on
``usage_events`` — a migration, and therefore a decision.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from intelliai_api.api.deps import CurrentAuth, SessionDep
from intelliai_api.core.time import utc_now
from intelliai_api.db.repositories import UsageEventRepository

router = APIRouter(prefix="/usage", tags=["usage"])

SECONDS_PER_MINUTE = 60


class UsagePeriod(BaseModel):
    start: datetime
    end: datetime
    days: int


class UsageTotals(BaseModel):
    #: Metered requests: work the platform accepted and performed. A
    #: request refused as invalid input never reaches the ledger (that
    #: refusal is an operational fact, not a commercial one), so it is
    #: absent here rather than counted as a failure.
    requests: int
    speech_minutes: float
    #: Mean measured audio per request that carried audio — a property of
    #: the audio, not of how long the platform took to serve it.
    average_request_seconds: float | None
    #: succeeded ÷ metered requests — platform reliability, from recorded
    #: outcomes rather than assumption. ``None`` when there are no
    #: requests: a rate over nothing is not 100%, it is undefined.
    success_rate: float | None
    #: The full distribution behind the rate, so it is always explicable.
    outcomes: dict[str, int]


class UsageDay(BaseModel):
    date: date
    requests: int
    speech_minutes: float


class UsageBreakdown(BaseModel):
    #: ``None`` for language means "none declared, none detected".
    key: str | None
    requests: int
    speech_minutes: float


class UsageSummaryResponse(BaseModel):
    period: UsagePeriod
    totals: UsageTotals
    daily: list[UsageDay]
    languages: list[UsageBreakdown]
    models: list[UsageBreakdown]


def _minutes(seconds: float) -> float:
    return round(seconds / SECONDS_PER_MINUTE, 2)


@router.get("/summary")
async def usage_summary(
    auth: CurrentAuth,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> UsageSummaryResponse:
    """Consumption for the last ``days`` UTC days, this day included.

    Every bucket in the window is returned, including empty ones: a
    trend with the quiet days omitted is a trend that lies about them.
    """
    repository = UsageEventRepository(session)
    end = utc_now()
    first_day = (end - timedelta(days=days - 1)).date()
    since = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)

    daily_rows = await repository.daily_activity_for_organization(
        auth.organization_id, since=since, until=end
    )
    outcomes = await repository.outcome_counts_for_organization(
        auth.organization_id, since=since, until=end
    )
    languages = await repository.language_activity_for_organization(
        auth.organization_id, since=since, until=end
    )
    models = await repository.model_activity_for_organization(
        auth.organization_id, since=since, until=end
    )

    by_day = {
        bucket: (requests, audio_requests, float(seconds))
        for bucket, requests, audio_requests, seconds in daily_rows
    }
    series: list[UsageDay] = []
    for offset in range(days):
        bucket = first_day + timedelta(days=offset)
        requests, _audio_requests, seconds = by_day.get(bucket, (0, 0, 0.0))
        series.append(UsageDay(date=bucket, requests=requests, speech_minutes=_minutes(seconds)))

    total_requests = sum(requests for _b, requests, _a, _s in daily_rows)
    total_audio_requests = sum(audio_requests for _b, _r, audio_requests, _s in daily_rows)
    total_seconds = float(sum(seconds for _b, _r, _a, seconds in daily_rows))
    succeeded = outcomes.get("succeeded", 0)

    return UsageSummaryResponse(
        period=UsagePeriod(start=since, end=end, days=days),
        totals=UsageTotals(
            requests=total_requests,
            speech_minutes=_minutes(total_seconds),
            average_request_seconds=(
                round(total_seconds / total_audio_requests, 2) if total_audio_requests else None
            ),
            success_rate=(round(succeeded / total_requests, 4) if total_requests else None),
            outcomes=outcomes,
        ),
        daily=series,
        languages=[
            UsageBreakdown(key=language, requests=requests, speech_minutes=_minutes(float(seconds)))
            for language, requests, _audio, seconds in languages
        ],
        models=[
            UsageBreakdown(key=model, requests=requests, speech_minutes=_minutes(float(seconds)))
            for model, requests, _audio, seconds in models
        ],
    )
