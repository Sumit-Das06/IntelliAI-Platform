"""AdmissionController — may this caller act right now?

The single place the platform decides whether to admit a request, and
the single place the fail-open posture lives:

> **Redis-backed protection fails open, loudly.**

A limiter outage becoming a platform outage is a worse failure than a few
minutes of unbounded traffic (ADR-0022). Failing open must also fail
*fast*: a limiter that hangs has taken the platform down more effectively
than one that refuses, which is why the client is built with a short
socket timeout and why every path here is bounded.

429 is *your allowance*; 503 is *our capacity*. This module only ever
produces the first — capacity backpressure stays in the runtime worker
pool where ADR-0018 put it, so a customer can always tell "slow down"
from "they are broken".
"""

import time
from collections.abc import Sequence

import structlog

from intelliai_api.core.errors import RateLimitError
from intelliai_api.limits.backend import RedisLimiterBackend
from intelliai_api.limits.rules import ALLOWED_UNMEASURED, LimitDecision, LimitRule, LimitScope

logger = structlog.get_logger(__name__)

_SCOPE_MESSAGE = {
    LimitScope.IP: "Too many requests. Slow down and retry shortly.",
    LimitScope.ORGANIZATION: (
        "Your organization is sending requests too quickly. Retry after the "
        "interval in Retry-After."
    ),
    LimitScope.API_KEY: (
        "This API key is sending requests too quickly. Retry after the interval "
        "in Retry-After, or spread load across keys."
    ),
    LimitScope.CAPABILITY: (
        "Too many requests for this capability. Retry after the interval in Retry-After."
    ),
    LimitScope.CONTROL_PLANE: (
        "Too many management requests. Retry after the interval in Retry-After."
    ),
}


class AdmissionController:
    """
    **Failing open is not enough on its own — it must also stay cheap.**
    Measured at step 3: with Redis unreachable, every request paid the
    full socket budget on each of its five limiter calls, adding ~1.2 s.
    That is a limiter outage becoming a platform degradation by another
    route, which is precisely the outcome the fail-open posture exists to
    prevent. A circuit breaker closes it: after a few consecutive
    failures the limiter stops calling Redis at all for a cooldown, and
    requests pay nothing.
    """

    def __init__(
        self,
        backend: RedisLimiterBackend | None,
        *,
        namespace: str = "",
        failure_threshold: int = 3,
        cooldown_seconds: float = 5.0,
    ) -> None:
        # None = limiting disabled by configuration (a deployment choice,
        # not a failure): every decision is an unmeasured allow.
        self._backend = backend
        self._prefix = f"{namespace}:" if namespace else ""
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._open_until = 0.0

    @property
    def enabled(self) -> bool:
        return self._backend is not None

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _tripped(self) -> bool:
        """True while the breaker is open — skip Redis entirely."""
        return time.monotonic() < self._open_until

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold and not self._tripped():
            self._open_until = time.monotonic() + self._cooldown_seconds
            # Logged once per trip, not once per request: an outage should
            # produce an alarm, not a log flood that buries it.
            logger.error(
                "ratelimit.circuit_opened",
                cooldown_seconds=self._cooldown_seconds,
                consecutive_failures=self._consecutive_failures,
            )

    def _record_success(self) -> None:
        if self._consecutive_failures:
            logger.info("ratelimit.circuit_closed")
        self._consecutive_failures = 0
        self._open_until = 0.0

    async def check(self, rules: Sequence[LimitRule]) -> LimitDecision:
        """Evaluate rules in order; the first refusal wins.

        Ordering is the cost gradient of §2 — broadest and cheapest
        first — so a caller over their organization ceiling is refused
        before we spend anything on narrower questions.
        """
        if self._backend is None or self._tripped():
            return ALLOWED_UNMEASURED

        tightest: LimitDecision | None = None
        for rule in rules:
            try:
                allowed, remaining, retry_after, reset = await self._backend.consume(
                    self._key(rule.key),
                    capacity=rule.burst,
                    refill_per_second=rule.refill_per_second,
                )
            except Exception:
                # Fail open, loudly. The alarm matters as much as the
                # decision: unlimited traffic nobody knows about is the
                # failure this posture is meant to make survivable, not
                # invisible.
                logger.error("ratelimit.unavailable", scope=rule.scope.value, exc_info=True)
                self._record_failure()
                return ALLOWED_UNMEASURED
            self._record_success()

            decision = LimitDecision(
                allowed=allowed,
                limit=rule.requests_per_minute,
                remaining=remaining,
                reset_seconds=reset,
                scope=rule.scope,
                retry_after=max(1, retry_after) if not allowed else None,
            )
            if not allowed:
                return decision
            # Headers advertise the SCARCEST allowance the caller has, not
            # the last one checked — otherwise a client tuning against the
            # headers would tune against the wrong ceiling.
            if tightest is None or decision.remaining < tightest.remaining:
                tightest = decision

        return tightest or ALLOWED_UNMEASURED

    async def acquire(self, key: str, *, limit: int, lease_id: str, ttl_ms: int) -> bool:
        """Claim one in-flight slot; True if the caller may proceed."""
        if self._backend is None or self._tripped():
            return True
        try:
            acquired, _held = await self._backend.acquire_slot(
                self._key(key), limit=limit, lease_id=lease_id, ttl_ms=ttl_ms
            )
        except Exception:
            logger.error("ratelimit.concurrency_unavailable", exc_info=True)
            self._record_failure()
            return True  # fail open, loudly
        self._record_success()
        return acquired

    async def release(self, key: str, *, lease_id: str) -> None:
        if self._backend is None or self._tripped():
            return
        try:
            await self._backend.release_slot(self._key(key), lease_id=lease_id)
        except Exception:
            # A leaked lease expires on its own — self-healing by design,
            # which is why this is a warning and not an incident.
            logger.warning("ratelimit.release_failed", exc_info=True)


def refuse(decision: LimitDecision) -> RateLimitError:
    """Render a refusal into the platform error contract (ADR-0009).

    ``rate_limit_exceeded`` always carries ``Retry-After``, because
    retrying a rate limit genuinely succeeds. Quotas (Step 4) will use a
    different code and deliberately omit it: retrying a quota never
    helps, and telling a client otherwise builds clients that hammer.
    """
    scope = decision.scope or LimitScope.ORGANIZATION
    return RateLimitError(
        _SCOPE_MESSAGE[scope],
        code="rate_limit_exceeded",
        retry_after=decision.retry_after or 1,
    )
