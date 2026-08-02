# ADR-0017: Registry V1 — code-declarative, resolution-only, in the gateway

- **Status:** Accepted
- **Date:** 2026-08-02
- **Related:** ADR-0003, ADR-0005, ADR-0016; designs: REGISTRY_V2.md, MODEL_IDENTITY.md

## Context

ADR-0003 committed to routing inference through a model registry; ADR-0016
assigned "routing & model registry lookup" to the gateway. M1.5 designed
Registry V2 (REGISTRY_V2.md: record/resolution planes, 14 laws, lifecycle,
lineage) — a control plane scheduled for M9, deliberately after real serving
experience exists. M2 needs exactly one registry behavior: given the public
model identifier a customer sends, decide which capability, runtime service,
and artifact handles the request — and refuse to route anything without a
verified commercial license verdict (Constitution; ADR-0005; verdicts are
per artifact version, never per family).

## Problem

What is the smallest registry that satisfies M2 routing without prejudicing
Registry V2 — and where does it live?

## Decision

We will implement **Registry V1 as a code-declarative module inside the
gateway** (`intelliai_api/registry/`), containing:

1. **Records** — frozen, strictly-validated (`extra="forbid"`: a typo in a
   catalog is a startup failure, not a silent field) types:
   `ArtifactRecord` (id, version, capability, free-text provenance, and a
   mandatory per-version `LicenseVerdict`: SPDX license, commercial-use
   boolean, verification date, verification source) and
   `PublicModelRecord` (public id, capability, serving service, artifact
   reference). Capabilities are the frozen contract enum — never strings
   (ADR-0016). Records state *facts*; they may record any license verdict
   truthfully.
2. **The Registry** — composed from records at import time, validating the
   whole catalog eagerly: unique ids, every referenced artifact exists,
   artifact capability matches the public model's, and **the license gate:
   composing a registry that routes to an artifact without
   `commercial_use=True` raises immediately**. A misconfigured catalog
   cannot boot. `resolve(public_model_id)` returns a frozen `Resolution`
   (public id, capability, service, artifact record); unknown identifiers
   raise `ModelNotFoundError` (404 / `model_not_found` in the public
   envelope, ADR-0009).
3. **The catalog** — the declared data, reviewed like code because it is
   code. V1 ships one public model: `intelliai-stt` → capability
   `transcription` → service `stt-runtime` → artifact `whisper-small`
   (MIT, verified 2026-07-31 at the served distribution).

Deliberately absent (V2 concepts M2 does not need): lifecycle stages,
lineage graphs, deployment history, promotion workflows, ownership trees,
evaluation identities, adapters/builds as records, database persistence,
write APIs. Precision/hardware never appear in identity (ADR-0015):
quantization is a *build* concern owned by the runtime's ModelManager —
the artifact is `whisper-small`, never `whisper-small-int8`.

**Growth path to V2 (the reason this is not a redesign later):** V1 is
V2's resolution plane in miniature. Records become database rows in M9
with the same fields as a starting schema; `resolve()` keeps its signature
and callers; the license gate becomes a database constraint plus admission
check; free-text `provenance` is superseded by structured lineage; the
record-plane/resolution-plane distinction already exists here as
records-vs-Registry. Callers depend on `resolve()` and records — never on
how the catalog is stored — so storage can change under a stable interface.

## Alternatives considered

- **Implement Registry V2 now** — rejected: V2's concepts (lifecycle,
  lineage, promotion) encode assumptions that should be validated by real
  serving traffic first; building them before any model serves is
  speculation with a database. M9 exists precisely to build V2 from
  evidence.
- **Database-backed registry now** — rejected: there is no write path in
  M2 (no console, no promotion workflow), so a table adds migrations,
  seeds, and repository plumbing to serve what is today constant data. A
  code catalog is versioned, reviewed, and deployed exactly like the rest
  of the platform.
- **YAML/JSON catalog file** — rejected: loses the type checker, the
  frozen capability enum, IDE navigation, and import-time validation —
  configuration languages are where string drift breeds. The catalog IS
  configuration, but typed configuration in code, like `Settings`.
- **Routing hardcoded in endpoint handlers** — rejected: every model swap
  becomes a code change at N call sites; ADR-0003 exists to prevent
  exactly this. The endpoint asks the registry; nothing else knows the
  answer.
- **Registry inside the runtime services** — rejected: ADR-0016 ownership —
  runtimes execute models; they must not know product naming, routing, or
  licensing. A runtime that names its own models cannot be swapped.

## Trade-offs

- **Changing routing requires a deploy.** Accepted pre-customers; the M9
  review criterion below covers when this stops being acceptable.
- **No runtime mutation** (kill-switch, per-tenant overrides) — deliberate;
  those are V2 resolution-plane features, listed for review.
- One catalog per gateway build — no environment-specific model sets yet;
  acceptable while dev and prod serve identical models.

## Consequences

- The gateway gains its first import of `intelliai-runtime-contract` — the
  contract package now sits under both planes, as designed.
- `/v1/models` (step 6) becomes a projection of `Registry.list_models()`.
- Step 5's ModelManager receives the artifact identity to load from the
  resolution, keeping engine choice and build/precision selection inside
  the runtime.
- Adding a model (or swapping the artifact behind `intelliai-stt`) is a
  one-record diff reviewed under the same license-gate rules, invisible to
  clients.

## Future review criteria

- **M9 Registry V2** implements REGISTRY_V2.md over a database; this module
  becomes its resolution-plane client — if V2's design forces changes to
  `resolve()` callers beyond mechanical ones, V1 leaked assumptions and
  this ADR should record what they were.
- A need to change routing **without a deploy** (incident kill-switch,
  canary, per-tenant model access) triggers early V2 resolution-plane work.
- The first **external provider adapter** tests whether records describe
  non-self-hosted serving honestly.
- A catalog approaching ~10 models or needing environment divergence ends
  the single-code-catalog convenience.
