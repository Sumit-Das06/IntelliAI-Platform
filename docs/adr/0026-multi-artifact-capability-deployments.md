# ADR-0026: Multi-artifact capability deployments and the naming law

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0002, ADR-0015, ADR-0018, ADR-0019, ADR-0025

## Context

Serving routes (ADR-0025) let one public model resolve to several
artifacts. Something has to host them. Today each capability runs as one
service with one deployment holding one engine — but the lifecycle
machinery was built ahead of this moment: `ModelManager` has supported
multiple named slots since M2 (`SlotSpec`, `DEFAULT_SLOT`), the runtimes
simply configure one, and every request already pins the artifact it
wants, which the runtime validates and refuses on mismatch.

The constraints: services are named by capability, never by engine (the
M3 rename exists because of this); CPU-first deployment makes memory the
binding constraint (each resident speech engine is GiB-scale, measured
in M2/M3); and capacity backpressure belongs to the runtime's own
bounded admission (ADR-0018).

## Problem

What is the deployment topology for many artifacts behind one
capability, and what may its pieces be called?

## Decision

**We will keep one capability service per capability and make it plural
in deployments: each deployment hosts one-or-more artifacts as
ModelManager slots, the registry routes to (service, deployment), and
deployment names draw only from permanent vocabulary.**

1. **Topology.** A capability service (`stt-runtime`, `tts-runtime`) is
   a set of named deployments. Each deployment declares the artifacts it
   hosts; each hosted artifact is a slot with its own warm-up probe.
   `/health/ready` reflects all slots; `/info` lists every hosted
   artifact.
2. **Slot selection.** The request's existing pinned artifact id selects
   the slot. An artifact the deployment does not host remains
   `INVALID_INPUT` — the M3 refusal, unchanged in meaning: registry and
   topology disagreeing must be loud.
3. **The naming law.** Deployment names may reference capabilities and
   languages — permanent vocabulary — and may never reference engines.
   `tts-runtime-indic` is lawful; anything engine-derived is not.
   Language-named deployments are safe because languages are promises
   kept regardless of what serves them.
4. **Packing is a per-adoption deployment decision.** One artifact per
   deployment is the default posture on CPU; artifacts share a process
   only with measured residency headroom. Artifacts sharing a deployment
   share its worker pool — capacity is a deployment property.
5. **Gateway.** Runtime clients become keyed by deployment name;
   `Resolution` carries the deployment, defaulting to the service name.
   Today's topology is the degenerate case: one deployment per
   capability.

## Alternatives considered

- **One fat process hosting every engine** — rejected by arithmetic:
  GiB-scale residency per engine on CPU-first hardware, and a shared
  blast radius where one engine's crash-loop takes down healthy
  languages.
- **One service per engine** — rejected on the naming law; engine-named
  services leak engine identity into topology, ops vocabulary, and
  support conversations, and break exactly when the engine changes.
- **New lifecycle machinery for multi-engine hosting** — rejected as
  unnecessary: multi-slot `ModelManager` has existed since M2;
  "lifecycle, never inference" (ADR-0019) needs zero changes.
- **Per-artifact worker pools inside one deployment** — rejected:
  premature partitioning of measured-scarce CPU; the pool is the
  deployment's admission boundary (ADR-0018).
- **Per-language rate limits to manage per-language capacity** —
  rejected: capacity differences surface as the runtime's honest 503,
  never as 429 (the M4 independence laws).

## Trade-offs

- More deployments mean more processes to operate, more health surfaces,
  and per-slot cold-start cost; accepted as the price of memory
  isolation and independent scaling per language group.
- Shared pools within a packed deployment mean one artifact's load can
  starve its neighbor; accepted where packing was justified by
  measurement, and solved by unpacking, not by new machinery.
- The gateway must maintain a deployment→URL map instead of two static
  URLs; a configuration surface, not a design cost.

## Consequences

- Adding a language's engine is: an artifact record, a deployment
  hosting it, a route binding — no service renames, no contract changes,
  no gateway logic.
- Deployment isolation makes partial multilingual availability honest:
  a down deployment 503s its routes while others serve.
- The M4 R2 lesson carries forward cleanly: more deployments add HTTP
  clients, not database connections.
- Kubernetes mapping stays 1:1 (deployment → Deployment); compose
  overlays express the same topology in dev.

## Amendments

**Amendment 2 — three identities, and the CPU packing posture
(2026-08-05, founder decision F-M5-5).** Names what Decision 4 assumed
and rules the default it left open.

> A deployment hosts an artifact. A runtime process realizes a
> deployment. These identities are related but never interchangeable.

Each relation is many-to-one downward and one-to-many upward. An artifact
can be hosted by several deployments, so it is never a place. A
deployment can be realized by several processes — that is scaling out —
so it is never a process, and a restart is never a change of what is
hosted. A process holds no identity at all: nothing may name one, route
to one, or record one as the thing that served, because it will not exist
tomorrow.

**On CPU, one artifact per deployment is the default.** The measured
~54 MiB interpreter overhead (Step 6) is accepted in exchange for simpler
operations, independent scaling, a cleaner blast radius, cleaner
rollback, and cleaner promotion. Packing remains supported by the
architecture and is no longer a posture anyone has to argue against.

**Amendment 1 — a slot hosts exactly one artifact at a point in time
(2026-08-05, founder clarification at M5 step 2 review).** Clarifies
Decision 1; nothing in the decision is reversed.

> A slot's artifact binding is fixed for the life of the process: slots
> are created at startup, loaded once, and released once. **Replacing
> the artifact behind a slot is a deployment operation — a new process
> with a new declaration — never a mutation of a running slot.** Nothing
> in the runtime may rebind, hot-swap, or reload a slot in place.

The reason is attribution, not simplicity. For the whole life of a
process, `(slot → artifact)` is constant, so every evaluation record,
ledger lineage entry, and benchmark names what actually served it
without needing a timestamp. An in-place swap would make artifact
identity a function of *when* you asked, and both the evaluation and
commercial planes assume it is not.

## Future review criteria

- Measured residency headroom on target hardware → revisit the
  one-artifact-per-deployment default (F-M5-5).
- A deployment count that makes the static URL map an operational burden
  → service discovery, without touching the naming law.
- GPU deployments arriving (ADR-0015) → hardware class lands on
  deployment records, never in names or selectors.
