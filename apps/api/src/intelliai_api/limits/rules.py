"""Limit rules and decisions — the vocabulary admission control speaks.

A rule is deliberately generic: a scope, an identity within that scope,
and a rate. Nothing here knows what a capability is, which capabilities
exist, or that speech is the platform's business. Adding OCR, vision, or
chat produces new *rules*, never new *code* — the same property the
ledger has, for the same reason.
"""

from dataclasses import dataclass
from enum import StrEnum


class LimitScope(StrEnum):
    """The hierarchy of §10.2, as a vocabulary.

    Order matters and is a cost gradient: the cheapest, most protective
    check runs first, so expensive work is never done for a request that
    will be refused.
    """

    IP = "ip"  # pre-authentication only; meaningless afterwards
    ORGANIZATION = "organization"  # the commercial ceiling
    API_KEY = "api_key"  # a subdivision, never an addition
    CAPABILITY = "capability"  # protects measured, capability-specific capacity
    CONTROL_PLANE = "control_plane"  # key/org management: enumeration guard


@dataclass(frozen=True)
class LimitRule:
    """One thing to check before admitting a request."""

    scope: LimitScope
    identity: str  # the subject within the scope (org public id, ip, …)
    requests_per_minute: int
    burst: int

    @property
    def key(self) -> str:
        return f"ratelimit:{self.scope.value}:{self.identity}"

    @property
    def refill_per_second(self) -> float:
        return self.requests_per_minute / 60.0


@dataclass(frozen=True)
class LimitDecision:
    """The answer, plus everything the response headers need.

    ``allowed=False`` carries the scope that refused, which is what makes
    a 429 diagnosable: a customer who cannot tell *which* limit they hit
    cannot fix their integration.
    """

    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    scope: LimitScope | None = None
    retry_after: int | None = None
    degraded: bool = False  # the limiter was unavailable and failed open

    @property
    def headers(self) -> dict[str, str]:
        """OpenAI/Stripe-shaped, matching the API our surface already imitates."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset_seconds),
        }


ALLOWED_UNMEASURED = LimitDecision(
    allowed=True, limit=0, remaining=0, reset_seconds=0, degraded=True
)
