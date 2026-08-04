"""Rollup persistence: rebuild from the ledger, read fast, never trust.

Unlike ``UsageEventRepository``, this one deliberately HAS delete paths.
A cache that cannot be dropped and regenerated is not a cache — and the
Rollup Invariant makes "drop and regenerate" the standard repair for any
disagreement with the ledger.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import UsageOrigin, UsageRollup
from intelliai_api.db.repositories.usage_events import UsageEventRepository


class UsageRollupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = UsageEventRepository(session)

    async def rebuild(
        self,
        organization_id: int,
        *,
        since: datetime,
        until: datetime,
        origins: Sequence[UsageOrigin] = (UsageOrigin.CUSTOMER,),
    ) -> dict[str, Decimal]:
        """Recompute one period from the ledger, replacing whatever was there.

        Delete-then-insert rather than upsert, on purpose: a unit that
        stopped appearing in the period (every event reversed, say) must
        vanish from the cache too. An upsert would leave a stale row
        behind that no ledger fact supports — precisely the disagreement
        this invariant exists to make impossible.
        """
        totals = await self._events.totals_for_organization(
            organization_id, since=since, until=until, billable_only=True, origins=origins
        )
        await self._session.execute(
            delete(UsageRollup).where(
                UsageRollup.organization_id == organization_id,
                UsageRollup.period_start == since,
                UsageRollup.period_end == until,
            )
        )
        for unit, amount in totals.items():
            self._session.add(
                UsageRollup(
                    organization_id=organization_id,
                    period_start=since,
                    period_end=until,
                    unit=unit,
                    amount=amount,
                )
            )
        await self._session.flush()
        return totals

    async def totals(
        self, organization_id: int, *, since: datetime, until: datetime
    ) -> dict[str, Decimal]:
        """Read the cache. Callers who need certainty read the ledger."""
        result = await self._session.execute(
            select(UsageRollup.unit, UsageRollup.amount).where(
                UsageRollup.organization_id == organization_id,
                UsageRollup.period_start == since,
                UsageRollup.period_end == until,
            )
        )
        return dict(result.all())  # type: ignore[arg-type]

    async def agrees_with_ledger(
        self,
        organization_id: int,
        *,
        since: datetime,
        until: datetime,
        origins: Sequence[UsageOrigin] = (UsageOrigin.CUSTOMER,),
    ) -> bool:
        """The auditor. A rollup nobody checks is a rollup that has drifted.

        Answers the Rollup Invariant's question directly, so the daily
        reconciliation has something to call rather than something to
        reimplement.
        """
        cached = await self.totals(organization_id, since=since, until=until)
        truth = await self._events.totals_for_organization(
            organization_id, since=since, until=until, billable_only=True, origins=origins
        )
        return cached == truth
