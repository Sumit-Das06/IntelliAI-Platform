"""Usage ledger persistence — append-only by construction.

This module has no update path and no delete path, and that absence is
tested (``test_usage_ledger.py`` parses this file and fails if a mutating
statement ever appears). The database enforces the same rule with
triggers, so the guarantee survives code that never goes through here:
two independent mechanisms, because a ledger is worth two.

Corrections are ``reverse()`` — a compensating event carrying negated
quantities. Netting a period is therefore ``SUM(amount)``, and the
original row is still there to explain what happened.

Every read is organization-scoped, without the ``get_by_hash`` style
exception that authentication needs: metering always knows its tenant.
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from intelliai_api.db.models import UsageEvent, UsageOrigin, UsageOutcome, UsageQuantity

#: The STT runtime's measured unit. Analytics reads name it explicitly
#: rather than summing every unit together: minutes of audio and (future)
#: pages of OCR are not addable quantities.
AUDIO_SECONDS = "audio_seconds"


class UsageEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        organization_id: int,
        capability: str,
        public_model_id: str,
        origin: UsageOrigin,
        outcome: UsageOutcome,
        billable: bool,
        occurred_at: datetime,
        quantities: Mapping[str, Decimal],
        request_id: str | None = None,
        api_key_id: int | None = None,
        idempotency_key: str | None = None,
        language: str | None = None,
        lineage: Mapping[str, Any] | None = None,
    ) -> UsageEvent:
        """Append one measured fact.

        ``quantities`` maps unit → amount exactly as the runtime reported
        it: no rounding, no unit conversion, no pricing. A billable event
        must carry at least one quantity — billing something we did not
        measure is the failure this ledger exists to prevent.
        """
        if billable and not quantities:
            raise ValueError("a billable event must carry at least one measured quantity")
        for unit, amount in quantities.items():
            if amount <= 0:
                raise ValueError(
                    f"measured amounts are positive; {unit}={amount} — "
                    "negative amounts belong to compensating events (reverse())"
                )

        event = UsageEvent(
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            capability=capability,
            public_model_id=public_model_id,
            language=language,
            origin=origin,
            outcome=outcome,
            billable=billable,
            occurred_at=occurred_at,
            lineage=dict(lineage or {}),
            quantities=[
                UsageQuantity(unit=unit, amount=amount) for unit, amount in quantities.items()
            ],
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def reverse(self, event: UsageEvent, *, reason: str, at: datetime) -> UsageEvent:
        """Correct a recorded fact without editing it.

        The compensating event copies the original's commercial identity
        (organization, capability, public model, origin, billability) and
        negates its quantities, so any ``SUM`` over the period nets to
        the corrected total while both rows survive for audit.

        ``at`` is the reversal's own timestamp, not the original's: a
        reversal belongs to the period in which it was **issued**. A
        correction must never reach backwards and silently restate a
        period that has already been reported.
        """
        if not reason.strip():
            raise ValueError("a reversal must state its reason — that is the whole point")

        reversal = UsageEvent(
            organization_id=event.organization_id,
            api_key_id=event.api_key_id,
            request_id=None,  # answers to no HTTP request
            idempotency_key=None,  # the original owns the key
            capability=event.capability,
            public_model_id=event.public_model_id,
            language=event.language,
            origin=event.origin,
            outcome=event.outcome,
            billable=event.billable,
            occurred_at=at,
            lineage=dict(event.lineage),
            reverses_usage_event_id=event.id,
            reversal_reason=reason,
            quantities=[
                UsageQuantity(unit=quantity.unit, amount=-quantity.amount)
                for quantity in event.quantities
            ],
        )
        self._session.add(reversal)
        await self._session.flush()
        return reversal

    async def get_for_organization(self, organization_id: int, public_id: str) -> UsageEvent | None:
        result = await self._session.execute(
            select(UsageEvent).where(
                UsageEvent.organization_id == organization_id,
                UsageEvent.public_id == public_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_request_id(self, organization_id: int, request_id: str) -> UsageEvent | None:
        """The support path: a customer quotes their ``X-Request-ID``."""
        result = await self._session.execute(
            select(UsageEvent).where(
                UsageEvent.organization_id == organization_id,
                UsageEvent.request_id == request_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: int,
        *,
        since: datetime,
        until: datetime,
    ) -> Sequence[UsageEvent]:
        """Events in ``[since, until)`` — half-open, so consecutive periods
        neither double-count nor drop the boundary instant."""
        result = await self._session.scalars(
            select(UsageEvent)
            .where(
                UsageEvent.organization_id == organization_id,
                UsageEvent.occurred_at >= since,
                UsageEvent.occurred_at < until,
            )
            .order_by(UsageEvent.occurred_at, UsageEvent.id)
        )
        return result.all()

    # ── Analytics reads ───────────────────────────────────────────
    # The console's Usage page reads API CONSUMPTION from this ledger:
    # requests, audio measured, outcomes, languages, public models. It
    # never reads the dataset tables — collected samples and corrections
    # are a different subject with a different page.
    #
    # Two counting rules, applied consistently everywhere below:
    #   * requests count only ORIGINAL events (a compensating event is a
    #     correction to a measurement, not a second request);
    #   * amounts SUM every row including compensating ones, because
    #     netting is what the negated quantities exist for.

    def _window(
        self, statement: Select[Any], organization_id: int, since: datetime, until: datetime
    ) -> Select[Any]:
        """Org scope + the half-open period every analytics read shares."""
        return statement.where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.occurred_at >= since,
            UsageEvent.occurred_at < until,
        )

    async def outcome_counts_for_organization(
        self, organization_id: int, *, since: datetime, until: datetime
    ) -> dict[str, int]:
        """Requests per outcome — the honest basis for a success rate.

        Failures reach the ledger out-of-band (``record_failure``), so
        this is a real distribution and not a tautological 100%.
        """
        statement = self._window(
            select(UsageEvent.outcome, func.count()).where(
                UsageEvent.reverses_usage_event_id.is_(None)
            ),
            organization_id,
            since,
            until,
        ).group_by(UsageEvent.outcome)
        result = await self._session.execute(statement)
        return {outcome.value: count for outcome, count in result.all()}

    def _activity_columns(self) -> tuple[Any, Any, Any]:
        """Requests, requests carrying audio, and netted audio seconds.

        ``LEFT JOIN`` on the audio unit: an event without a measured
        quantity (a failure) still counts as a request, and its absent
        amount contributes nothing.
        """
        return (
            func.count(distinct(UsageEvent.id)).filter(
                UsageEvent.reverses_usage_event_id.is_(None)
            ),
            func.count(distinct(UsageEvent.id)).filter(
                UsageEvent.reverses_usage_event_id.is_(None),
                UsageQuantity.amount.is_not(None),
            ),
            func.coalesce(func.sum(UsageQuantity.amount), 0),
        )

    def _activity_select(self, *group_by: Any) -> Select[Any]:
        requests, audio_requests, seconds = self._activity_columns()
        return (
            select(*group_by, requests, audio_requests, seconds)
            .select_from(UsageEvent)
            .join(
                UsageQuantity,
                (UsageQuantity.usage_event_id == UsageEvent.id)
                & (UsageQuantity.unit == AUDIO_SECONDS),
                isouter=True,
            )
        )

    async def bucketed_activity_for_organization(
        self,
        organization_id: int,
        *,
        since: datetime,
        until: datetime,
        unit: str,
    ) -> list[tuple[datetime, int, int, Decimal]]:
        """Per-bucket activity: (bucket start, requests, audio requests, seconds).

        ``unit`` is a ``date_trunc`` field — ``day``, ``hour``, or
        ``minute`` — chosen by the caller from a closed set, never
        interpolated from a customer's string.

        Bucketed in explicit UTC rather than the session's time zone, so
        the same request lands in the same bucket whatever the server is
        configured to think local time is. ``timezone('UTC', …)`` yields
        a naive timestamp, so the boundary is re-stamped as UTC on the
        way out and callers never handle an ambiguous datetime.
        """
        bucket = func.date_trunc(unit, func.timezone("UTC", UsageEvent.occurred_at)).label("bucket")
        statement = (
            self._window(self._activity_select(bucket), organization_id, since, until)
            .group_by(bucket)
            .order_by(bucket)
        )
        result = await self._session.execute(statement)
        return [
            (moment.replace(tzinfo=UTC), requests, audio_requests, seconds)
            for moment, requests, audio_requests, seconds in result.all()
        ]

    async def _grouped_activity(
        self,
        organization_id: int,
        column: InstrumentedAttribute[Any],
        *,
        since: datetime,
        until: datetime,
    ) -> list[tuple[Any, int, int, Decimal]]:
        statement = (
            self._window(self._activity_select(column), organization_id, since, until)
            .group_by(column)
            .order_by(func.count(distinct(UsageEvent.id)).desc(), column)
        )
        result = await self._session.execute(statement)
        return [tuple(row) for row in result.all()]

    async def language_activity_for_organization(
        self, organization_id: int, *, since: datetime, until: datetime
    ) -> list[tuple[str | None, int, int, Decimal]]:
        """Activity per observed language. ``None`` means the request did
        not declare one and the engine reported none — a real category,
        never silently folded into another language."""
        return await self._grouped_activity(
            organization_id, UsageEvent.language, since=since, until=until
        )

    async def model_activity_for_organization(
        self, organization_id: int, *, since: datetime, until: datetime
    ) -> list[tuple[str, int, int, Decimal]]:
        """Activity per PUBLIC model id (``intelliai-stt``). The artifact
        that served it lives in lineage and never leaves the database."""
        return await self._grouped_activity(
            organization_id, UsageEvent.public_model_id, since=since, until=until
        )

    async def totals_for_organization(
        self,
        organization_id: int,
        *,
        since: datetime,
        until: datetime,
        billable_only: bool = True,
        origins: Collection[UsageOrigin] | None = None,
    ) -> dict[str, Decimal]:
        """Netted consumption per unit for ``[since, until)``.

        Compensating events carry negated amounts, so a plain ``SUM``
        *is* the netting. ``origins`` exists so rating can select what it
        charges for without the ledger ever deciding: measurement is
        unconditional, billability is a filter applied here and above.
        """
        statement = (
            select(UsageQuantity.unit, func.sum(UsageQuantity.amount))
            .join(UsageEvent, UsageEvent.id == UsageQuantity.usage_event_id)
            .where(
                UsageEvent.organization_id == organization_id,
                UsageEvent.occurred_at >= since,
                UsageEvent.occurred_at < until,
            )
            .group_by(UsageQuantity.unit)
        )
        if billable_only:
            statement = statement.where(UsageEvent.billable.is_(True))
        if origins is not None:
            statement = statement.where(UsageEvent.origin.in_(list(origins)))

        result = await self._session.execute(statement)
        return {unit: total for unit, total in result.all() if total}
