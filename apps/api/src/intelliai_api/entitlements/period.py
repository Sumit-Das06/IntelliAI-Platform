"""Billing periods: calendar month, UTC (founder decision F6).

"Month" is ambiguous and the ambiguity is expensive after the first
invoice, so the rule is fixed here once and imported everywhere:

- a period is the half-open interval ``[start, end)`` — consecutive
  periods neither double-count the boundary instant nor drop it;
- ``start`` is midnight UTC on the first of the month;
- an event belongs to the period containing its ``occurred_at``, which
  is its **completion** time (§15 R6).

Half-open is not a detail. With closed intervals the instant
``2026-09-01T00:00:00Z`` belongs to two months, and every aggregate over
both is wrong by exactly the traffic in that microsecond — a bug that
appears once a month, in production, in money.
"""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BillingPeriod:
    start: datetime  # inclusive
    end: datetime  # exclusive

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    @property
    def label(self) -> str:
        return self.start.strftime("%Y-%m")


def period_for(moment: datetime) -> BillingPeriod:
    """The calendar month, in UTC, containing ``moment``.

    Any aware timestamp is accepted and converted; a naive one is
    rejected rather than assumed, because assuming a timezone is how a
    server's local time silently becomes a billing boundary.
    """
    if moment.tzinfo is None:
        raise ValueError("billing periods are computed from timezone-aware instants only")
    moment = moment.astimezone(UTC)
    start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
    end = (
        datetime(moment.year + 1, 1, 1, tzinfo=UTC)
        if moment.month == 12
        else datetime(moment.year, moment.month + 1, 1, tzinfo=UTC)
    )
    return BillingPeriod(start=start, end=end)
