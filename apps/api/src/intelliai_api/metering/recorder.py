"""UsageRecorder — the one place a served request becomes a ledger fact.

Every capability service calls this and nothing else. The recorder owns
four guarantees that are easy to state and easy to lose:

**1. It never raises on the serving path.** A bookkeeping failure is a
revenue incident and a paging event; it is never a customer-visible
error. *Never charge the customer for our bookkeeping; never let our
bookkeeping charge the customer.*

**2. A successful request's event shares the request's transaction.**
The write happens before the response is serialized, on the connection
the request already holds, so the event and the response either both
happen or neither does. The write is wrapped in a SAVEPOINT: if the
ledger rejects the row, the savepoint rolls back and the surrounding
transaction — the one that will return the customer's answer — is still
usable. Without the savepoint a refused ledger write would poison the
session and turn a bookkeeping problem into a 500, which is exactly the
outcome the first guarantee forbids.

**3. A failed request's event does NOT share the request's transaction.**
The asymmetry is deliberate: a failing request's transaction is about to
be discarded, and the fact that we burned capacity is precisely what must
survive that discard. Failure events are therefore written and committed
on their own short-lived session.

**4. Duplicates are absorbed, not raised.** A retry that reaches the
ledger with a request id or idempotency key already present is a
duplicate the database refuses; that refusal is the at-most-once billing
guarantee working, not an error to propagate (ADR-0024).

Ordering — the response is written *after* the ledger, never before.
Founder decision F1 makes that not merely safer but correct: successful
generation, not socket completion, defines billability. Work that was
generated and then failed to reach the customer is billable, so recording
first cannot over-record; recording last could lose revenue for work
demonstrably delivered.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelliai_api.core.time import utc_now
from intelliai_api.db.models import UsageOutcome
from intelliai_api.db.repositories import UsageEventRepository
from intelliai_api.metering.fallback import NullUsageFallback, UsageFallback
from intelliai_api.services.auth import AuthContext
from intelliai_runtime_contract import RuntimeErrorType

logger = structlog.get_logger(__name__)


class UsageRecorder:
    def __init__(
        self,
        session: AsyncSession,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        fallback: UsageFallback | None = None,
    ) -> None:
        self._session = session
        self._session_factory = session_factory
        self._fallback = fallback or NullUsageFallback()

    async def record_success(
        self,
        *,
        auth: AuthContext,
        capability: str,
        public_model_id: str,
        quantities: Mapping[str, Decimal],
        outcome: UsageOutcome = UsageOutcome.SUCCEEDED,
        language: str | None = None,
        lineage: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        """Record delivered work, inside the request's own transaction."""
        await self._write(
            auth=auth,
            capability=capability,
            public_model_id=public_model_id,
            outcome=outcome,
            billable=True,
            quantities=quantities,
            language=language,
            lineage=lineage,
            idempotency_key=idempotency_key,
        )

    async def record_runtime_failure(
        self,
        *,
        auth: AuthContext,
        capability: str,
        public_model_id: str,
        error_type: RuntimeErrorType | None,
        language: str | None = None,
        lineage: Mapping[str, Any] | None = None,
    ) -> None:
        """Record a failure — but only the failures that cost us capacity.

        The policy lives here rather than in each capability service, so
        two capabilities can never drift on what "a recordable failure"
        means:

        - ``INVALID_INPUT`` — the caller's request could not be served.
          We refused it; we did not spend inference on it. **No ledger
          row**: the ledger is the record of work performed, and a
          refusal is an operational fact belonging to the request-event
          family, not a commercial one.
        - ``NOT_READY``, ``OVERLOADED``, ``INTERNAL``, and an unreachable
          runtime — our side failed after accepting the work. **A
          non-billable row**, because a runtime that times out after two
          minutes held a worker for two minutes, and cost-to-serve
          analysis that counts only successes systematically understates
          what serving costs.
        """
        if error_type is RuntimeErrorType.INVALID_INPUT:
            return
        await self._record_failure(
            auth=auth,
            capability=capability,
            public_model_id=public_model_id,
            language=language,
            lineage=lineage,
        )

    async def _record_failure(
        self,
        *,
        auth: AuthContext,
        capability: str,
        public_model_id: str,
        language: str | None = None,
        lineage: Mapping[str, Any] | None = None,
    ) -> None:
        """Record capacity we spent on work that never reached the customer.

        Never billable — nothing was delivered and nothing was measured.
        It exists because a runtime that times out after two minutes cost
        us a worker for two minutes, and cost-to-serve analysis that only
        counts successes systematically understates what serving costs.

        Written out-of-band: the request is about to raise, and its
        transaction with it.
        """
        if self._session_factory is None:
            # No independent session available (unit-test wiring): the
            # operational fact still leaves a trace, it just does not
            # reach the ledger.
            logger.warning(
                "usage.failure_not_recorded",
                reason="no out-of-band session",
                capability=capability,
            )
            return

        async with self._session_factory() as session:
            recorder = UsageRecorder(session, fallback=self._fallback)
            await recorder._write(
                auth=auth,
                capability=capability,
                public_model_id=public_model_id,
                outcome=UsageOutcome.FAILED,
                billable=False,
                quantities={},
                language=language,
                lineage=lineage,
                idempotency_key=None,
                savepoint=False,
            )
            await session.commit()

    async def _write(
        self,
        *,
        auth: AuthContext,
        capability: str,
        public_model_id: str,
        outcome: UsageOutcome,
        billable: bool,
        quantities: Mapping[str, Decimal],
        language: str | None,
        lineage: Mapping[str, Any] | None,
        idempotency_key: str | None,
        savepoint: bool = True,
    ) -> None:
        async def write() -> None:
            await UsageEventRepository(self._session).record(
                organization_id=auth.organization_id,
                api_key_id=auth.api_key.id,
                request_id=auth.request_id,
                idempotency_key=idempotency_key,
                capability=capability,
                public_model_id=public_model_id,
                language=language,
                origin=auth.usage_origin,
                outcome=outcome,
                billable=billable,
                occurred_at=utc_now(),
                quantities=quantities,
                lineage=lineage,
            )

        try:
            if savepoint:
                async with self._session.begin_nested():
                    await write()
            else:
                await write()
        except IntegrityError:
            # The at-most-once billing guarantee doing its job: a retry
            # reached the ledger with an identity already recorded. The
            # customer is served; they are billed exactly once.
            logger.info(
                "usage.duplicate_suppressed",
                organization_id=auth.organization_public_id,
                capability=capability,
                idempotency_key=idempotency_key,
            )
        except Exception:
            # Revenue-affecting, never customer-affecting. Two sinks and
            # an alarm; the daily reconciliation invariant is what
            # guarantees somebody notices.
            self._fallback.capture(
                {
                    "organization_id": auth.organization_public_id,
                    "api_key_id": auth.key_public_id,
                    "request_id": auth.request_id,
                    "idempotency_key": idempotency_key,
                    "capability": capability,
                    "public_model_id": public_model_id,
                    "language": language,
                    "origin": auth.usage_origin.value,
                    "outcome": outcome.value,
                    "billable": billable,
                    "occurred_at": utc_now().isoformat(),
                    "quantities": {unit: str(amount) for unit, amount in quantities.items()},
                    "lineage": dict(lineage or {}),
                }
            )
            logger.critical(
                "usage.write_failed",
                organization_id=auth.organization_public_id,
                request_id=auth.request_id,
                capability=capability,
                public_model_id=public_model_id,
                quantities={unit: str(amount) for unit, amount in quantities.items()},
                exc_info=True,
            )
