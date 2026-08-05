"""Analytics: watching the commercial plane rather than trusting it.

Three read-only concerns, all queries over the ledger, because at this
scale the usage tables ARE the analytics warehouse (§12.5):

- **reconciliation** — is the chain gateway → ledger → rollups → rating
  coherent? The auditor that turns "we believe we bill correctly" into a
  measured fact.
- **anomalies** — is anything happening a human should look at? Every
  threshold is relative to the tenant's own history.
- **language** — what the Core Speech Language Policy needs in order to
  be a roadmap input rather than an intention.

Nothing here writes, and nothing here can influence a ledger fact, a
quota, a price, or a rated amount (Operational Measurement Independence,
§10.1c). Analysis informs what we choose to charge; the only route from
an observation to a charge is a published price book version.
"""

from intelliai_api.analytics.anomalies import (
    FailureRate,
    UsageSpike,
    failure_rates,
    reversal_activity,
    stale_rollups,
    usage_spikes,
)
from intelliai_api.analytics.language import (
    POLICY_LANGUAGES,
    LadderCoverage,
    LanguageReport,
    LanguageUsage,
    language_report,
)
from intelliai_api.analytics.reconciliation import (
    Finding,
    Reconciler,
    ReconciliationReport,
    reconcile,
)

__all__ = [
    "POLICY_LANGUAGES",
    "FailureRate",
    "Finding",
    "LadderCoverage",
    "LanguageReport",
    "LanguageUsage",
    "Reconciler",
    "ReconciliationReport",
    "UsageSpike",
    "failure_rates",
    "language_report",
    "reconcile",
    "reversal_activity",
    "stale_rollups",
    "usage_spikes",
]
