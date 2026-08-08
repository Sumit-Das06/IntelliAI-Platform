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

Two ways to ask for a window, never both at once:

* ``?days=N`` — the last N UTC days, this day included (the original
  contract, unchanged);
* ``?start=…&end=…`` — an explicit period, at ``daily``, ``hourly``, or
  ``minute`` granularity.

Sending both is refused rather than silently resolved: a caller who
disagrees with themselves deserves an error, not a guess.

One thing this endpoint deliberately cannot report: which CLIENT made
the requests. Client identity (web, keyboard, api) is recorded on
collected samples, not on ledger events, and inferring API usage from
consented samples would be exactly the dataset/consumption confusion
this endpoint exists to avoid. Reporting it honestly needs a column on
``usage_events`` — a migration, and therefore a decision.
"""

import math
import re
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from intelliai_api.api.deps import CurrentAuth, SessionDep
from intelliai_api.core.errors import InvalidRequestError
from intelliai_api.core.time import utc_now
from intelliai_api.db.repositories import UsageEventRepository

router = APIRouter(prefix="/usage", tags=["usage"])

SECONDS_PER_MINUTE = 60
DEFAULT_DAYS = 30

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Granularity(StrEnum):
    DAILY = "daily"
    HOURLY = "hourly"
    MINUTE = "minute"


class _Bucketing:
    """How one granularity buckets, steps, and how far it may reach.

    The ceilings exist so a minute-level question can never become a
    million-bucket answer: they bound the work, the payload, and the
    chart in one place, and they are the reason this endpoint needs no
    rollup table.
    """

    def __init__(self, unit: str, step: timedelta, limit: timedelta, limit_text: str) -> None:
        self.unit = unit
        self.step = step
        self.limit = limit
        self.limit_text = limit_text


BUCKETING = {
    Granularity.DAILY: _Bucketing("day", timedelta(days=1), timedelta(days=90), "90 days"),
    Granularity.HOURLY: _Bucketing("hour", timedelta(hours=1), timedelta(days=30), "30 days"),
    Granularity.MINUTE: _Bucketing("minute", timedelta(minutes=1), timedelta(hours=48), "48 hours"),
}


class UsagePeriod(BaseModel):
    start: datetime
    end: datetime
    #: Window length in whole days, rounded up. Retained from the
    #: original contract; ``start``/``end`` are the precise answer.
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


class UsageBucket(BaseModel):
    #: Start of the bucket, in UTC. Every bucket in the window is
    #: present, including the empty ones.
    timestamp: datetime
    requests: int
    speech_minutes: float


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
    granularity: Granularity
    totals: UsageTotals
    series: list[UsageBucket]
    #: Compatibility with the pre-granularity contract: the same daily
    #: buckets as ``series``, and empty at finer granularities. ``series``
    #: is the field to build on.
    daily: list[UsageDay]
    languages: list[UsageBreakdown]
    models: list[UsageBreakdown]


def _minutes(seconds: float) -> float:
    return round(seconds / SECONDS_PER_MINUTE, 2)


def _parse_moment(raw: str, *, param: str, exclusive_end: bool = False) -> datetime:
    """An ISO date or datetime, always resolved to an instant in UTC.

    A bare date names a whole day, which is how a date-range picker
    reads: ``end=2026-08-08`` means *through the end of the 8th*, so it
    resolves to the exclusive boundary at the start of the 9th.
    """
    text = raw.strip()
    try:
        if _DATE_ONLY.match(text):
            day = date.fromisoformat(text)
            moment = datetime.combine(day, time.min, tzinfo=UTC)
            return moment + timedelta(days=1) if exclusive_end else moment
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidRequestError(
            f"'{param}' must be an ISO date (2026-08-06) or datetime "
            f"(2026-08-06T14:00:00Z); got {raw!r}.",
            code="invalid_period",
            param=param,
        ) from exc
    # A datetime without an offset is read as UTC, never as server-local:
    # the ledger's buckets are UTC and the answer must not depend on
    # where the process happens to run.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _floor(moment: datetime, granularity: Granularity) -> datetime:
    """The start of the bucket containing ``moment``."""
    if granularity is Granularity.DAILY:
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity is Granularity.HOURLY:
        return moment.replace(minute=0, second=0, microsecond=0)
    return moment.replace(second=0, microsecond=0)


def _resolve_window(
    *,
    days: int | None,
    start: str | None,
    end: str | None,
    granularity: Granularity,
    now: datetime,
) -> tuple[datetime, datetime, int]:
    """The half-open window ``[since, until)`` this request is asking for.

    Returns the window and the day count kept in ``period.days``.
    """
    if days is not None and (start is not None or end is not None):
        raise InvalidRequestError(
            "Ask for a window with 'days' or with 'start' and 'end', not both.",
            code="period_conflict",
            param="days",
        )

    if start is None and end is None:
        window_days = days if days is not None else DEFAULT_DAYS
        first_day = (now - timedelta(days=window_days - 1)).date()
        return datetime.combine(first_day, time.min, tzinfo=UTC), now, window_days

    if start is None or end is None:
        raise InvalidRequestError(
            "'start' and 'end' are given together — one without the other does not name a period.",
            code="invalid_period",
            param="start" if start is None else "end",
        )

    since = _parse_moment(start, param="start")
    # Never report the future: the platform cannot know usage that has
    # not happened, so a window reaching past now simply stops at now.
    until = min(_parse_moment(end, param="end", exclusive_end=True), now)

    if since >= until:
        raise InvalidRequestError(
            "'start' must fall before 'end', and the period cannot lie entirely in the future.",
            code="invalid_period",
            param="start",
        )

    bucketing = BUCKETING[granularity]
    if until - since > bucketing.limit:
        raise InvalidRequestError(
            f"'{granularity.value}' granularity covers at most {bucketing.limit_text}; "
            "ask for a shorter period or a coarser granularity.",
            code="period_too_long",
            param="granularity",
        )

    return since, until, max(1, math.ceil((until - since) / timedelta(days=1)))


@router.get("/summary")
async def usage_summary(
    auth: CurrentAuth,
    session: SessionDep,
    days: Annotated[int | None, Query(ge=1, le=90)] = None,
    start: Annotated[str | None, Query()] = None,
    end: Annotated[str | None, Query()] = None,
    granularity: Annotated[Granularity, Query()] = Granularity.DAILY,
) -> UsageSummaryResponse:
    """Consumption for a window, bucketed in UTC.

    Every bucket in the window is returned, including empty ones: a
    trend with the quiet buckets omitted is a trend that lies about
    them. Nothing between buckets is interpolated — an absent bucket is
    zero, not a guess.
    """
    now = utc_now()
    since, until, window_days = _resolve_window(
        days=days, start=start, end=end, granularity=granularity, now=now
    )
    bucketing = BUCKETING[granularity]

    repository = UsageEventRepository(session)
    rows = await repository.bucketed_activity_for_organization(
        auth.organization_id, since=since, until=until, unit=bucketing.unit
    )
    outcomes = await repository.outcome_counts_for_organization(
        auth.organization_id, since=since, until=until
    )
    languages = await repository.language_activity_for_organization(
        auth.organization_id, since=since, until=until
    )
    models = await repository.model_activity_for_organization(
        auth.organization_id, since=since, until=until
    )

    measured = {
        bucket: (requests, audio_requests, float(seconds))
        for bucket, requests, audio_requests, seconds in rows
    }
    series: list[UsageBucket] = []
    cursor = _floor(since, granularity)
    while cursor < until:
        requests, _audio, seconds = measured.get(cursor, (0, 0, 0.0))
        series.append(
            UsageBucket(timestamp=cursor, requests=requests, speech_minutes=_minutes(seconds))
        )
        cursor += bucketing.step

    total_requests = sum(requests for _b, requests, _a, _s in rows)
    total_audio_requests = sum(audio_requests for _b, _r, audio_requests, _s in rows)
    total_seconds = float(sum(seconds for _b, _r, _a, seconds in rows))
    succeeded = outcomes.get("succeeded", 0)

    return UsageSummaryResponse(
        period=UsagePeriod(start=since, end=until, days=window_days),
        granularity=granularity,
        totals=UsageTotals(
            requests=total_requests,
            speech_minutes=_minutes(total_seconds),
            average_request_seconds=(
                round(total_seconds / total_audio_requests, 2) if total_audio_requests else None
            ),
            success_rate=(round(succeeded / total_requests, 4) if total_requests else None),
            outcomes=outcomes,
        ),
        series=series,
        daily=[
            UsageDay(
                date=bucket.timestamp.date(),
                requests=bucket.requests,
                speech_minutes=bucket.speech_minutes,
            )
            for bucket in series
        ]
        if granularity is Granularity.DAILY
        else [],
        languages=[
            UsageBreakdown(key=language, requests=requests, speech_minutes=_minutes(float(seconds)))
            for language, requests, _audio, seconds in languages
        ],
        models=[
            UsageBreakdown(key=model, requests=requests, speech_minutes=_minutes(float(seconds)))
            for model, requests, _audio, seconds in models
        ],
    )
