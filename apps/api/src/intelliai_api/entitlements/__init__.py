"""Entitlements: what the customer bought, and what they have left.

The durable half of admission control. ``limits/`` protects the platform
and is allowed to be approximate, ephemeral, and lost; this is exact,
derived from the ledger, and shares fate with authentication (ADR-0022).

A separate package rather than a module inside ``limits/`` because the
two must not become one system by convenience — and because this one
imports the database and the ledger, which ``limits/`` deliberately never
may (Protection Independence Invariant, design §10.1a).
"""

from intelliai_api.entitlements.period import BillingPeriod, period_for
from intelliai_api.entitlements.pricing import CURRENT, INTERNAL_V1, PriceBook, rate
from intelliai_api.entitlements.service import EntitlementService

__all__ = [
    "CURRENT",
    "INTERNAL_V1",
    "BillingPeriod",
    "EntitlementService",
    "PriceBook",
    "period_for",
    "rate",
]
