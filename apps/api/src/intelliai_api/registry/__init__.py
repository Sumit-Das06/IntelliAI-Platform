"""Registry V1 — the gateway's routing authority (ADR-0017).

Module charter:

1. **Why it exists** — one place answers "for this public model identifier,
   which capability, runtime service, and artifact handles the request?"
   Routing lives here so that swapping the model behind a public name is a
   one-record diff, invisible to clients and to endpoint code (ADR-0003).
2. **What it owns** — public model records, artifact records with
   per-artifact-version license verdicts, catalog validation (including the
   license gate: nothing routes without a verified commercial verdict), and
   `resolve()`.
3. **What it must never own** — engines, model files, builds/precision
   (ModelManager's business, ADR-0015), transport, lifecycle/lineage/
   promotion (Registry V2, M9), tenancy or auth (callers' business).
4. **Who may import it** — gateway routers and services; nothing below the
   gateway. Runtimes never import the registry: they are told what to do,
   they do not decide what exists.
5. **What it may import** — `intelliai_runtime_contract` (the capability
   vocabulary), `core.errors`, stdlib, pydantic. Never repositories or
   SQLAlchemy — V1 is code-declarative by decision, not by accident.
6. **How it grows** — M9 replaces the code catalog with Registry V2's
   database-backed record plane behind the same `resolve()` interface;
   records here are the seed schema. Until then, adding a model is a
   reviewed catalog diff.
"""

from intelliai_api.registry.catalog import default_registry
from intelliai_api.registry.records import (
    ArtifactRecord,
    LicenseVerdict,
    PublicModelRecord,
    Resolution,
)
from intelliai_api.registry.registry import ModelNotFoundError, Registry

__all__ = [
    "ArtifactRecord",
    "LicenseVerdict",
    "ModelNotFoundError",
    "PublicModelRecord",
    "Registry",
    "Resolution",
    "default_registry",
]
