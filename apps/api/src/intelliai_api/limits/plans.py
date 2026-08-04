"""Plans: where a tenant's limits come from.

Limits are never hardcoded per organization. An organization has a plan,
a plan carries limits, and an organization may later carry overrides —
built with exactly one plan today so that adding a tier is a
configuration change rather than a migration.

Code-declarative in V1, mirroring Registry V1 (ADR-0017) and the price
book (ADR-0023): a limit change is a commercial decision that deserves a
diff and a second look, and git supplies the audit trail without an
admin surface to build and secure.

**Launch numbers are deliberately generous (founder decision F4).** M4
validates the mechanism, not production numbers; a limit set too tight at
launch is indistinguishable from an outage to the customer who hits it.
The free tier ships from day one (F5) so that accrual, refusal, and
analytics all execute against real traffic instead of lying dormant.
"""

from dataclasses import dataclass

FREE = "free"


@dataclass(frozen=True)
class Plan:
    """One commercial tier's protection limits.

    Two dimensions, not one: **rate** protects against velocity, and
    **concurrency** protects against occupancy. For an inference platform
    the second matters more — a single long transcription occupies a
    worker for its whole duration regardless of request rate — and M3's
    measurements (TTS plateauing at 0.64 rps, the pool capping at 10)
    are why both exist.
    """

    id: str
    requests_per_minute: int
    burst: int  # tokens available instantaneously; absorbs legitimate spikes
    max_concurrent: int  # in-flight requests per organization
    capability_requests_per_minute: int  # per capability, per organization
    control_plane_requests_per_minute: int  # key/org management: enumeration guard

    @property
    def refill_per_second(self) -> float:
        return self.requests_per_minute / 60.0


PLANS: dict[str, Plan] = {
    FREE: Plan(
        id=FREE,
        requests_per_minute=600,
        burst=120,
        # Above the runtime worker pool's own ceiling (10 for TTS, M3), so
        # capacity backpressure still surfaces as an honest 503 rather
        # than being masked by a 429 the customer cannot act on.
        max_concurrent=25,
        capability_requests_per_minute=600,
        control_plane_requests_per_minute=120,
    ),
}

# Unauthenticated edge: the only pre-identity defence. Generous enough to
# never inconvenience a real client retrying with a bad key, tight enough
# that a credential-stuffing flood cannot make us hash and query forever.
UNAUTHENTICATED_REQUESTS_PER_MINUTE = 300
UNAUTHENTICATED_BURST = 60


def plan_for(plan_id: str) -> Plan:
    """Resolve a tenant's plan; unknown ids fall back to free.

    Falling back rather than raising is deliberate: an unrecognised plan
    id is an operations problem, and refusing to serve a paying customer
    because of our own catalog typo would be the wrong failure.
    """
    return PLANS.get(plan_id, PLANS[FREE])
