"""Admission control: may this caller act right now?

The protection half of the commercial plane. It answers a different
question from every neighbour, over a different truth class, with a
different failure consequence (ADR-0022):

- **rate limiting** — too fast right now? Redis, approximate, ephemeral,
  self-healing, fails open. This package.
- **quota** — too much this period? Postgres, exact, durable, derived
  from the ledger. Step 4.
- **capacity** — do we have room at all? The runtime worker pool's own
  503. Not here, and never conflated with a 429.

Nothing in this package knows what a capability is or which ones exist:
a rule is a scope, an identity, and a rate. Adding OCR or vision produces
new rules, never new code.
"""

from intelliai_api.limits.backend import RedisLimiterBackend
from intelliai_api.limits.capability import CapabilityAdmission
from intelliai_api.limits.controller import AdmissionController, refuse
from intelliai_api.limits.plans import (
    FREE,
    PLANS,
    UNAUTHENTICATED_BURST,
    UNAUTHENTICATED_REQUESTS_PER_MINUTE,
    Plan,
    plan_for,
)
from intelliai_api.limits.rules import LimitDecision, LimitRule, LimitScope

__all__ = [
    "FREE",
    "PLANS",
    "UNAUTHENTICATED_BURST",
    "UNAUTHENTICATED_REQUESTS_PER_MINUTE",
    "AdmissionController",
    "CapabilityAdmission",
    "LimitDecision",
    "LimitRule",
    "LimitScope",
    "Plan",
    "RedisLimiterBackend",
    "plan_for",
    "refuse",
]
