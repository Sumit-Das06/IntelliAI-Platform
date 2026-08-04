"""EntitlementService — has this customer used more than they bought?

The *entitlement* half of admission control, and deliberately a separate
package from the *protection* half (``limits/``), because ADR-0022's
whole argument is that they are different systems:

| | Rate limit (``limits/``) | Quota / spend (here) |
|---|---|---|
| question | too fast right now? | too much this period? |
| measured in | requests | usage, and money |
| store | Redis, ephemeral | Postgres, derived from the ledger |
| on loss | brief over-admission | entitlement error |
| retry | later succeeds | never helps |

**Quota is computed from the ledger, not from a counter.** The usage
events are already the exact, durable record of what was consumed
(ADR-0021); a parallel counter would be a second source of truth that
can drift from the first, and the first is the one invoices are built
from. Reading the ledger costs a grouped SUM over one indexed range; the
graduation path when that stops being cheap is a rollup that is *derived
from* the ledger, never a replacement for it.

**Only ``origin = customer`` counts** (founder decision F7). Benchmark,
evaluation, research, and demo traffic is metered exactly like a
customer's and excluded here — measurement is unconditional, billability
is a filter.

**Overshoot is bounded, not eliminated.** A request's cost is unknown
until after inference, so the last admitted request may cross the line.
The bound is the concurrency limit times the maximum single-request
cost, and that maximum is already bounded by the input limits that exist
for safety. Nobody may raise an input limit without also raising this
bound. Reserve/settle is the mechanism that would remove the overshoot
entirely; it is deliberately unbuilt until M5's long batch jobs make a
single request a meaningful fraction of a period (ADR-0022).
"""

from datetime import datetime
from decimal import Decimal

import structlog

from intelliai_api.core.errors import QuotaExceededError
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import UsageOrigin
from intelliai_api.db.repositories import UsageEventRepository
from intelliai_api.entitlements.period import BillingPeriod, period_for
from intelliai_api.entitlements.pricing import CURRENT, PriceBook, rate
from intelliai_api.limits.plans import Plan, plan_for

logger = structlog.get_logger(__name__)


class EntitlementService:
    def __init__(
        self,
        usage: UsageEventRepository,
        *,
        price_book: PriceBook = CURRENT,
    ) -> None:
        self._usage = usage
        self._price_book = price_book

    async def check(
        self,
        *,
        organization_id: int,
        organization_public_id: str,
        plan_id: str,
        spend_limit: Decimal | None,
        now: datetime | None = None,
    ) -> None:
        """Refuse if this tenant is over quota or over their money ceiling.

        Raises ``QuotaExceededError`` (429, ``quota_exceeded_error``) and
        deliberately carries **no ``Retry-After``**: retrying a quota
        never helps, and saying otherwise builds clients that hammer a
        wall until the month turns over.

        Never raises for its own failures. If entitlement cannot be
        determined, the request is served, an alarm fires, and nothing is
        published about quota — the Operational Honesty Principle's third
        state. A fabricated allowance would be worse than silence.
        """
        period = period_for(now or utc_now())
        plan = plan_for(plan_id)

        try:
            totals = await self._usage.totals_for_organization(
                organization_id,
                since=period.start,
                until=period.end,
                billable_only=True,
                origins=[UsageOrigin.CUSTOMER],
            )
        except Exception:
            logger.error(
                "entitlement.unavailable",
                organization_id=organization_public_id,
                period=period.label,
                exc_info=True,
            )
            return

        self._enforce_quota(plan, totals, period, organization_public_id)
        self._enforce_spend(plan, totals, period, organization_public_id, spend_limit)

    def _enforce_quota(
        self,
        plan: Plan,
        totals: dict[str, Decimal],
        period: BillingPeriod,
        organization_public_id: str,
    ) -> None:
        for unit, allowance in plan.monthly_quota.items():
            consumed = totals.get(unit, Decimal(0))
            if consumed < allowance:
                continue
            logger.info(
                "entitlement.quota_exceeded",
                organization_id=organization_public_id,
                unit=unit,
                consumed=str(consumed),
                allowance=str(allowance),
                period=period.label,
            )
            raise QuotaExceededError(
                f"Your plan's monthly allowance for {unit} is exhausted "
                f"({consumed} of {allowance} used). It resets on "
                f"{period.end.date().isoformat()} 00:00 UTC.",
                code="quota_exceeded",
            )

    def _enforce_spend(
        self,
        plan: Plan,
        totals: dict[str, Decimal],
        period: BillingPeriod,
        organization_public_id: str,
        spend_limit: Decimal | None,
    ) -> None:
        # The stricter of what the plan permits and what the customer
        # authorised: both parties get to protect themselves.
        ceilings = [value for value in (plan.monthly_spend_cap, spend_limit) if value is not None]
        if not ceilings:
            return
        ceiling = min(ceilings)

        spent = rate(totals, self._price_book)
        if spent < ceiling:
            return

        logger.info(
            "entitlement.spend_limit_exceeded",
            organization_id=organization_public_id,
            spent=str(spent),
            ceiling=str(ceiling),
            price_book=self._price_book.version,
            period=period.label,
        )
        raise QuotaExceededError(
            "The spend limit for this billing period has been reached. "
            f"It resets on {period.end.date().isoformat()} 00:00 UTC, or "
            "raise the limit to continue.",
            code="spend_limit_exceeded",
        )
