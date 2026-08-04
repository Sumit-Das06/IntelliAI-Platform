"""Internal lineage: what actually served a request, for our eyes only.

The Commercial Identity Invariant says a customer buys a capability, not
a foundation model. Lineage is where the model goes — recorded so that
cost-to-serve can be attributed per artifact and so the usage ledger can
be joined to the evaluation evidence ledger, and never projected to a
customer, never an input to rating (ADR-0021, ADR-0023).

Deliberately a plain mapping rather than a schema: what identifies "the
thing that served this" differs by capability and will keep changing —
artifact today, adapter and merge and quantization tomorrow — and none of
that may ever force a migration.
"""

from typing import Any

from intelliai_api.registry import Resolution


def runtime_lineage(
    resolution: Resolution, *, served_artifact: str, service_version: str
) -> dict[str, Any]:
    """Lineage for one runtime-served request.

    ``served_artifact`` is what the runtime reported it actually loaded,
    which is not assumed to equal what the registry routed to: a
    disagreement is exactly the kind of thing this record exists to make
    visible after the fact.
    """
    return {
        "artifact": served_artifact,
        "routed_artifact": resolution.artifact.id,
        "artifact_version": resolution.artifact.version,
        "provenance": resolution.artifact.provenance,
        "service": resolution.service,
        # Which deployment of that service answered. Capacity and residency
        # are deployment properties (ADR-0026), so cost-to-serve cannot be
        # attributed without it once a capability has more than one.
        "deployment": resolution.deployment,
        "service_version": service_version,
    }
