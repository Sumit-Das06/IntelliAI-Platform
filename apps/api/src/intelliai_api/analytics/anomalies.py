"""Anomaly detection: commercial consistency, watched rather than assumed.

Reconciliation answers *is the chain coherent right now*. These answer
the quieter question: *is anything happening that a human should look
at?* They are deliberately queries over the ledger rather than a
monitoring stack — at this scale the usage tables ARE the analytics
warehouse (§12.5), and a dashboard built before there is traffic teaches
nothing and then rots.

Every threshold here is **relative to the tenant's own history**, never
global. A global threshold is either useless for a small customer or
noisy for a large one, and both failures train people to ignore alerts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Numeric, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageQuantity, UsageRollup


@dataclass(frozen=True)
class UsageSpike:
    """A tenant consuming far more than it usually does."""

    organization_id: int
    unit: str
    recent: Decimal
    baseline: Decimal

    @property
    def multiple(self) -> Decimal:
        return self.recent / self.baseline if self.baseline else Decimal(0)


@dataclass(frozen=True)
class FailureRate:
    """How much capacity a tenant is burning on work nobody can bill."""

    organization_id: int
    succeeded: int
    failed: int

    @property
    def failure_share(self) -> float:
        total = self.succeeded + self.failed
        return self.failed / total if total else 0.0


async def usage_spikes(
    session: AsyncSession,
    *,
    now: datetime,
    window: timedelta = timedelta(days=1),
    baseline_windows: int = 7,
    multiple: Decimal = Decimal(5),
    organization_ids: Sequence[int] | None = None,
) -> list[UsageSpike]:
    """Tenants whose recent consumption dwarfs their own trailing average.

    Not fraud detection — a signal. A legitimate launch and a leaked key
    look identical here, and that is fine: the query's job is to put a
    human in front of the difference.
    """
    recent_start = now - window
    baseline_start = now - window * (baseline_windows + 1)
    scope = (
        (UsageEvent.organization_id.in_(list(organization_ids)),)
        if organization_ids is not None
        else ()
    )

    recent = (
        select(
            UsageEvent.organization_id.label("organization_id"),
            UsageQuantity.unit.label("unit"),
            func.sum(UsageQuantity.amount).label("amount"),
        )
        .join(UsageQuantity, UsageQuantity.usage_event_id == UsageEvent.id)
        .where(
            UsageEvent.occurred_at >= recent_start,
            UsageEvent.occurred_at < now,
            UsageEvent.billable.is_(True),
            UsageEvent.origin == UsageOrigin.CUSTOMER,
            *scope,
        )
        .group_by(UsageEvent.organization_id, UsageQuantity.unit)
        .subquery()
    )
    baseline = (
        select(
            UsageEvent.organization_id.label("organization_id"),
            UsageQuantity.unit.label("unit"),
            (func.sum(UsageQuantity.amount) / Decimal(baseline_windows)).label("amount"),
        )
        .join(UsageQuantity, UsageQuantity.usage_event_id == UsageEvent.id)
        .where(
            UsageEvent.occurred_at >= baseline_start,
            UsageEvent.occurred_at < recent_start,
            UsageEvent.billable.is_(True),
            UsageEvent.origin == UsageOrigin.CUSTOMER,
            *scope,
        )
        .group_by(UsageEvent.organization_id, UsageQuantity.unit)
        .subquery()
    )

    result = await session.execute(
        select(recent.c.organization_id, recent.c.unit, recent.c.amount, baseline.c.amount)
        .join(
            baseline,
            (baseline.c.organization_id == recent.c.organization_id)
            & (baseline.c.unit == recent.c.unit),
        )
        .where(
            baseline.c.amount > 0,
            recent.c.amount > baseline.c.amount * literal(multiple, Numeric(20, 6)),
        )
    )
    return [
        UsageSpike(
            organization_id=organization_id,
            unit=unit,
            recent=recent_amount,
            baseline=baseline_amount,
        )
        for organization_id, unit, recent_amount, baseline_amount in result.all()
    ]


async def failure_rates(
    session: AsyncSession, *, since: datetime, until: datetime, threshold: float = 0.1
) -> list[FailureRate]:
    """Tenants burning capacity on work that will never be billed.

    Non-billable events exist precisely so this is answerable: a runtime
    that times out after two minutes held a worker for two minutes, and
    counting only successes systematically understates what serving
    costs.
    """
    result = await session.execute(
        select(
            UsageEvent.organization_id,
            func.count().filter(UsageEvent.billable.is_(True)).label("succeeded"),
            func.count().filter(UsageEvent.billable.is_(False)).label("failed"),
        )
        .where(UsageEvent.occurred_at >= since, UsageEvent.occurred_at < until)
        .group_by(UsageEvent.organization_id)
    )
    rates = [
        FailureRate(organization_id=organization_id, succeeded=succeeded, failed=failed)
        for organization_id, succeeded, failed in result.all()
    ]
    return [rate for rate in rates if rate.failure_share > threshold]


async def stale_rollups(
    session: AsyncSession, *, older_than: datetime
) -> list[tuple[int, str, datetime]]:
    """Caches nobody has refreshed.

    A stale rollup is not wrong — the ledger has not changed under it
    necessarily — but an old ``computed_at`` is the first thing to look
    at when a total looks surprising.
    """
    result = await session.execute(
        select(UsageRollup.organization_id, UsageRollup.unit, UsageRollup.computed_at)
        .where(UsageRollup.computed_at < older_than)
        .order_by(UsageRollup.computed_at)
    )
    return [(organization_id, unit, computed) for organization_id, unit, computed in result.all()]


async def reversal_activity(session: AsyncSession, *, since: datetime, until: datetime) -> int:
    """How often we are correcting ourselves.

    Reversals are healthy — they are how a ledger stays honest — but a
    rising count is a signal that something upstream is producing charges
    that need undoing.
    """
    return (
        await session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                UsageEvent.occurred_at >= since,
                UsageEvent.occurred_at < until,
                UsageEvent.reverses_usage_event_id.is_not(None),
            )
        )
        or 0
    )
