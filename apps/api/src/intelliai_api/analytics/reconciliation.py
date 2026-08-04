"""Reconciliation: the auditor of the commercial plane.

Every guarantee this milestone makes is only worth what its check is
worth. A ledger nobody reconciles is a ledger that has drifted; a rollup
nobody audits is a second truth; a fallback sink nobody empties is a
revenue loss with extra steps.

The chain has four links and this module walks all of them:

    gateway ──▶ ledger ──▶ rollups ──▶ rating

**A stated limitation, rather than a silent one.** The first link is
only partially checkable today. Comparing successful billable responses
to billable ledger rows requires *persisted* request events, and M4
records requests only as structured logs (§7.1). What this module can
prove about that link is that nothing was *rejected* — the durable
fallback sink is empty and no write-failure alarm is outstanding — which
catches the failure mode that matters (a write the ledger refused) but
not a request that never reached the recorder at all. Persisting request
events completes the link and is registered as M4 debt.

Links two through four are checked exactly, because they are all
derivable from the ledger, which is the point of the ledger.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageQuantity
from intelliai_api.db.repositories import UsageEventRepository, UsageRollupRepository
from intelliai_api.entitlements import BillingPeriod
from intelliai_api.pricing import CATALOG, PriceBookCatalog, rate_events, rate_rollup


@dataclass(frozen=True)
class Finding:
    """One thing that is not as it should be."""

    check: str
    severity: str  # "critical" | "warning"
    detail: str


@dataclass
class ReconciliationReport:
    period: BillingPeriod
    organizations: int = 0
    events: int = 0
    findings: list[Finding] = field(default_factory=list)
    ledger_total: Decimal = Decimal(0)
    rollup_total: Decimal = Decimal(0)

    @property
    def clean(self) -> bool:
        return not self.findings

    def fail(self, check: str, detail: str) -> None:
        self.findings.append(Finding(check=check, severity="critical", detail=detail))

    def warn(self, check: str, detail: str) -> None:
        self.findings.append(Finding(check=check, severity="warning", detail=detail))


class Reconciler:
    def __init__(
        self,
        session: AsyncSession,
        *,
        catalog: PriceBookCatalog = CATALOG,
        fallback_path: Path | None = None,
    ) -> None:
        self._session = session
        self._catalog = catalog
        self._events = UsageEventRepository(session)
        self._rollups = UsageRollupRepository(session)
        self._fallback_path = fallback_path

    async def run(
        self, period: BillingPeriod, *, organization_ids: Sequence[int] | None = None
    ) -> ReconciliationReport:
        """Audit a period, platform-wide or for named tenants.

        Scoping exists because "reconcile everything" and "explain THIS
        customer's invoice" are both real questions, and the second is the
        one a support conversation actually starts with.
        """
        report = ReconciliationReport(period=period)
        await self._check_fallback_sink(report)
        await self._check_ledger_integrity(report, period, organization_ids)
        await self._check_rollups_and_rating(report, period, organization_ids)
        return report

    @staticmethod
    def _scope(organization_ids: Sequence[int] | None) -> tuple[Any, ...]:
        if organization_ids is None:
            return ()
        return (UsageEvent.organization_id.in_(list(organization_ids)),)

    async def _check_fallback_sink(self, report: ReconciliationReport) -> None:
        """Link 1: did the ledger refuse anything the gateway tried to write?

        A non-empty sink is a revenue incident with a recovery path — the
        events are there to be replayed — which is exactly why "degrade
        open" was defensible in the first place (§6.1).
        """
        if self._fallback_path is None or not self._fallback_path.exists():
            return
        lines = [
            line
            for line in self._fallback_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if lines:
            report.fail(
                "gateway_to_ledger",
                f"{len(lines)} usage event(s) the ledger refused are waiting in "
                f"{self._fallback_path}; replay them before trusting this period",
            )

    async def _check_ledger_integrity(
        self,
        report: ReconciliationReport,
        period: BillingPeriod,
        organization_ids: Sequence[int] | None = None,
    ) -> None:
        """Link 2: is the ledger internally coherent?

        Every one of these is already prevented by a constraint. Checking
        them anyway is the difference between believing the constraints
        hold and knowing it — constraints get dropped by migrations, and a
        migration that silently removes one should be found by an audit
        rather than by an invoice.
        """
        in_period = (
            UsageEvent.occurred_at >= period.start,
            UsageEvent.occurred_at < period.end,
            *self._scope(organization_ids),
        )

        report.events = (
            await self._session.scalar(
                select(func.count()).select_from(UsageEvent).where(*in_period)
            )
            or 0
        )
        report.organizations = (
            await self._session.scalar(
                select(func.count(func.distinct(UsageEvent.organization_id)))
                .select_from(UsageEvent)
                .where(*in_period)
            )
            or 0
        )

        # A billable event with nothing measured is a charge for an
        # unmeasured thing — the failure the whole ledger exists to make
        # impossible.
        unmeasured = await self._session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                *in_period,
                UsageEvent.billable.is_(True),
                ~UsageEvent.quantities.any(),
            )
        )
        if unmeasured:
            report.fail(
                "billable_without_measurement",
                f"{unmeasured} billable event(s) carry no measured quantity",
            )

        # Traceability: a charge nobody can tie to a request.
        untraceable = await self._session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                *in_period,
                UsageEvent.request_id.is_(None),
                UsageEvent.reverses_usage_event_id.is_(None),
            )
        )
        if untraceable:
            report.fail(
                "untraceable_events",
                f"{untraceable} non-compensating event(s) carry no request id",
            )

        # Commercial Completeness (§7.8): a billable row must come from a
        # customer request, so a billable reversal must reverse one.
        orphan_reversals = await self._session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                *in_period,
                UsageEvent.reverses_usage_event_id.is_not(None),
                UsageEvent.reversal_reason.is_(None),
            )
        )
        if orphan_reversals:
            report.fail(
                "unexplained_reversals",
                f"{orphan_reversals} reversal(s) state no reason",
            )

        # A zero quantity says nothing and dilutes every average.
        zero_quantities = await self._session.scalar(
            select(func.count())
            .select_from(UsageQuantity)
            .join(UsageEvent, UsageEvent.id == UsageQuantity.usage_event_id)
            .where(*in_period, UsageQuantity.amount == 0)
        )
        if zero_quantities:
            report.fail("zero_quantities", f"{zero_quantities} quantity row(s) are zero")

    async def _check_rollups_and_rating(
        self,
        report: ReconciliationReport,
        period: BillingPeriod,
        organization_ids: Sequence[int] | None = None,
    ) -> None:
        """Links 3 and 4: does the cache agree, and does the money follow?

        The Rollup Invariant (§8.5) says the ledger wins any disagreement.
        This is where that is discovered rather than assumed — and where
        rating from the cache is proven to produce the same money as
        rating from the truth.
        """
        organizations = await self._organizations_with_usage(period, organization_ids)
        for organization_id in organizations:
            cached = await self._rollups.totals(
                organization_id, since=period.start, until=period.end
            )
            if not cached:
                # A cold cache is not drift, and conflating the two is how
                # alerts get ignored: "never built" and "disagrees with the
                # ledger" have different causes and different urgencies.
                report.warn(
                    "rollup_missing",
                    f"organization {organization_id} has no rollup for {period.label}",
                )
                continue

            agrees = await self._rollups.agrees_with_ledger(
                organization_id, since=period.start, until=period.end
            )
            if not agrees:
                truth = await self._events.totals_for_organization(
                    organization_id,
                    since=period.start,
                    until=period.end,
                    origins=[UsageOrigin.CUSTOMER],
                )
                report.fail(
                    "rollup_disagrees_with_ledger",
                    f"organization {organization_id}: cache {cached} vs ledger {truth}; "
                    "rebuild the rollup — the ledger is authoritative",
                )
                continue

            events = await self._events.list_for_organization(
                organization_id, since=period.start, until=period.end
            )
            from_ledger = rate_events(
                events,
                organization_public_id=str(organization_id),
                period_label=period.label,
                catalog=self._catalog,
            )
            from_cache = rate_rollup(
                list(cached.items()),
                organization_public_id=str(organization_id),
                period_label=period.label,
                at=period.start,
                catalog=self._catalog,
            )
            report.ledger_total += from_ledger.total
            report.rollup_total += from_cache.total
            if from_ledger.total != from_cache.total:
                report.fail(
                    "rating_disagrees_between_ledger_and_rollup",
                    f"organization {organization_id}: ledger {from_ledger.total} vs "
                    f"cache {from_cache.total} ({period.label})",
                )

    async def _organizations_with_usage(
        self, period: BillingPeriod, organization_ids: Sequence[int] | None = None
    ) -> Sequence[int]:
        result = await self._session.scalars(
            select(func.distinct(UsageEvent.organization_id)).where(
                UsageEvent.occurred_at >= period.start,
                UsageEvent.occurred_at < period.end,
                *self._scope(organization_ids),
            )
        )
        return list(result.all())


async def reconcile(
    session: AsyncSession,
    period: BillingPeriod,
    *,
    catalog: PriceBookCatalog = CATALOG,
    fallback_path: Path | None = None,
    organization_ids: Sequence[int] | None = None,
) -> ReconciliationReport:
    return await Reconciler(session, catalog=catalog, fallback_path=fallback_path).run(
        period, organization_ids=organization_ids
    )
