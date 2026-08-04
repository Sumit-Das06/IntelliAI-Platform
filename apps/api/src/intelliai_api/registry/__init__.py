"""Registry V1.5 — the gateway's routing authority (ADR-0017, ADR-0025).

Module charter:

1. **Why it exists** — one place answers "for this public model identifier
   *and what the customer declared*, which capability, runtime service,
   deployment, and artifact handles the request?" Routing lives here so
   that swapping the model behind a public name is a one-record diff,
   invisible to clients and to endpoint code (ADR-0003).
2. **What it owns** — public model records, artifact records with
   per-artifact-version license verdicts, serving routes and their ladder
   statuses, catalog validation (including the license gate: nothing
   routes without a verified commercial verdict, and no route without one
   covering its whole language-specific serving path), and `resolve()`.
3. **What it must never own** — engines, model files, builds/precision
   (ModelManager's business, ADR-0015), transport, lifecycle/lineage/
   promotion (Registry V2, M9), tenancy or auth (callers' business), and
   **coordination among routes** — fallbacks, cascades, splits, canaries
   and ensembles are Serving Strategies, reserved for V2 (ADR-0025).
4. **Who may import it** — gateway routers and services; nothing below the
   gateway. Runtimes never import the registry: they are told what to do,
   they do not decide what exists.
5. **What it may import** — `intelliai_runtime_contract` (the capability
   vocabulary), `core.errors`, stdlib, pydantic. Never repositories or
   SQLAlchemy — V1 is code-declarative by decision, not by accident.
6. **How it grows** — M9 replaces the code catalog with Registry V2's
   database-backed record plane behind the same `resolve()` interface;
   records here are the seed schema, and V1.5 is deliberately V2's
   vocabulary in miniature (routes are records, resolution is a pure
   function of records, promotion is a record change, stages have a
   reserved home). Until then, adding a model — or promoting a
   language — is a reviewed catalog diff, and that diff *is* the
   promotion record.
"""

from intelliai_api.registry.catalog import default_registry
from intelliai_api.registry.records import (
    ADMITTED_SELECTOR_DIMENSIONS,
    ArtifactRecord,
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    PublicModelRecord,
    PublicVoiceRecord,
    Resolution,
    RouteSelector,
    RouteStage,
    ServingRoute,
    normalize_language,
)
from intelliai_api.registry.registry import (
    LanguageNotSupportedError,
    ModelNotFoundError,
    Registry,
    VoiceNotFoundError,
)

__all__ = [
    "ADMITTED_SELECTOR_DIMENSIONS",
    "ArtifactRecord",
    "LanguageEvidence",
    "LanguageNotSupportedError",
    "LanguageStatus",
    "LicenseVerdict",
    "ModelNotFoundError",
    "PublicModelRecord",
    "PublicVoiceRecord",
    "Registry",
    "Resolution",
    "RouteSelector",
    "RouteStage",
    "ServingRoute",
    "VoiceNotFoundError",
    "default_registry",
    "normalize_language",
]
