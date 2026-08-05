"""Language analytics for the Core Speech Language Policy.

The policy makes English, Hindi, and Arabic first-class **product**
languages. A policy without measurement is an intention, so this answers
the questions that turn it into a roadmap input:

- what are customers actually asking for, per capability, over time?
- which of the three policy languages is genuinely being adopted, and by
  how many distinct organizations — not just how many requests?
- what are we serving *outside* the policy, which is where the next
  language candidate comes from?

**Language is a fact, never a price.** It is recorded on the ledger
because it is an observed property of the request (§7.6), and it informs
which engines to research and adopt. It is not a pricing dimension and
not an admission dimension (§10.1a, §10.1c): a Hindi request and an
English request of the same size consume the same quota and cost the
same, and the day that stops being true it will be because a published
price book says so.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageQuantity

# The Core Speech Language Policy's first-class product languages.
POLICY_LANGUAGES = ("en", "hi", "ar")


@dataclass(frozen=True)
class LanguageUsage:
    language: str | None  # None = the request did not state or observe one
    capability: str
    requests: int
    organizations: int
    quantities: dict[str, Decimal]

    @property
    def in_policy(self) -> bool:
        return (self.language or "").split("-")[0].lower() in POLICY_LANGUAGES


@dataclass(frozen=True)
class LadderCoverage:
    """One (capability, language): what we promise, and what we served."""

    capability: str
    language: str
    status: str  # the ladder rung, as the registry states it
    requests: int
    organizations: int

    @property
    def is_contradiction(self) -> bool:
        """Traffic on a language we say we do not serve.

        Never expected — the gateway refuses `unavailable` languages
        before crossing a plane — and therefore worth a loud check rather
        than a comment claiming it cannot happen.
        """
        return self.status == "unavailable" and self.requests > 0

    @property
    def is_unexercised_promise(self) -> bool:
        """A promise nobody has used yet: a product signal, not a defect."""
        return self.status == "supported" and self.requests == 0


@dataclass(frozen=True)
class LanguageReport:
    since: datetime
    until: datetime
    rows: tuple[LanguageUsage, ...]

    @property
    def policy_rows(self) -> tuple[LanguageUsage, ...]:
        return tuple(row for row in self.rows if row.in_policy)

    @property
    def outside_policy_rows(self) -> tuple[LanguageUsage, ...]:
        return tuple(row for row in self.rows if row.language and not row.in_policy)

    def adoption(self) -> dict[str, int]:
        """Distinct organizations per policy language.

        Organizations, not requests: one enthusiastic customer looks like
        adoption in a request count and does not in this one, and the
        roadmap question is how many customers need a language.
        """
        counts = dict.fromkeys(POLICY_LANGUAGES, 0)
        for row in self.policy_rows:
            key = (row.language or "").split("-")[0].lower()
            counts[key] = counts.get(key, 0) + row.organizations
        return counts

    def unserved_demand(self) -> tuple[str, ...]:
        """Languages customers asked for that the policy does not name.

        The evidence that should drive engine research, rather than
        intuition about which language matters next.
        """
        return tuple(sorted({row.language for row in self.outside_policy_rows if row.language}))

    def against_ladder(self, ladder: Mapping[tuple[str, str], str]) -> tuple[LadderCoverage, ...]:
        """What we *promise* per (capability, language) beside what we *served*.

        Two different silences look identical in a usage report and mean
        opposite things: a `supported` language with no traffic is a
        product problem, and an `unavailable` language with traffic is a
        serving defect. Reading adoption without the rung beside it
        cannot tell them apart, which is why this join exists rather
        than a second query.
        """
        served: dict[tuple[str, str], tuple[int, int]] = {}
        for row in self.rows:
            base = (row.language or "").split("-")[0].lower()
            key = (row.capability, base)
            requests, organizations = served.get(key, (0, 0))
            served[key] = (requests + row.requests, organizations + row.organizations)
        return tuple(
            LadderCoverage(
                capability=capability,
                language=language,
                status=status,
                requests=served.get((capability, language), (0, 0))[0],
                organizations=served.get((capability, language), (0, 0))[1],
            )
            for (capability, language), status in sorted(ladder.items())
        )


async def language_report(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime,
    origins: Sequence[UsageOrigin] = (UsageOrigin.CUSTOMER,),
    organization_ids: Sequence[int] | None = None,
) -> LanguageReport:
    """Per-language, per-capability consumption over a window.

    ``organization_ids`` scopes the report to named tenants — the same
    query serves the platform roadmap and a single customer's own usage
    view in the console (M7).
    """
    scope = (
        (UsageEvent.organization_id.in_(list(organization_ids)),)
        if organization_ids is not None
        else ()
    )
    counts = await session.execute(
        select(
            UsageEvent.language,
            UsageEvent.capability,
            func.count().label("requests"),
            func.count(func.distinct(UsageEvent.organization_id)).label("organizations"),
        )
        .where(
            UsageEvent.occurred_at >= since,
            UsageEvent.occurred_at < until,
            UsageEvent.billable.is_(True),
            UsageEvent.origin.in_(list(origins)),
            *scope,
        )
        .group_by(UsageEvent.language, UsageEvent.capability)
        .order_by(func.count().desc())
    )

    amounts = await session.execute(
        select(
            UsageEvent.language,
            UsageEvent.capability,
            UsageQuantity.unit,
            func.sum(UsageQuantity.amount),
        )
        .join(UsageQuantity, UsageQuantity.usage_event_id == UsageEvent.id)
        .where(
            UsageEvent.occurred_at >= since,
            UsageEvent.occurred_at < until,
            UsageEvent.billable.is_(True),
            UsageEvent.origin.in_(list(origins)),
            *scope,
        )
        .group_by(UsageEvent.language, UsageEvent.capability, UsageQuantity.unit)
    )
    by_key: dict[tuple[str | None, str], dict[str, Decimal]] = {}
    for language, capability, unit, amount in amounts.all():
        by_key.setdefault((language, capability), {})[unit] = amount

    rows = tuple(
        LanguageUsage(
            language=language,
            capability=capability,
            requests=requests,
            organizations=organizations,
            quantities=by_key.get((language, capability), {}),
        )
        for language, capability, requests, organizations in counts.all()
    )
    return LanguageReport(since=since, until=until, rows=rows)
