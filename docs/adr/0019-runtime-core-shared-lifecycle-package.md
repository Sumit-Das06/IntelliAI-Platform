# ADR-0019: `packages/runtime-core` — shared runtime lifecycle package, extracted at the second consumer

- **Status:** Accepted
- **Date:** 2026-08-03
- **Related:** ADR-0001, ADR-0016, ADR-0018;
  [M3 design review](../milestones/3-tts-design.md)

## Context

M2 built the first inference runtime (stt-runtime) with its lifecycle
machinery — ModelManager (measured `ensure → load → warm-up → serve`),
ArtifactStore (SHA-256-verified volume cache), the bounded-admission
worker pool, and `RuntimeServiceError` — living inside the service.
That was deliberate: the platform rule is *extract at the second
consumer*, and there was only one. M3 introduces tts-runtime as the
second instantiation of the ADR-0018 template. The second consumer now
exists.

## Problem

Where does the lifecycle machinery every runtime shares permanently
live — copied into each runtime, or extracted once — and what is the
extracted package allowed to know?

## Decision

We will create `packages/runtime-core` as the permanent home for
everything shared by all runtimes: ModelManager (generic over the
runtime-local engine Protocol, warm-up supplied from outside as a
capability-defined deterministic probe), ArtifactStore, WorkerPool,
`RuntimeServiceError`, and future shared serving infrastructure.

Governing principle: **`runtime-core` owns lifecycle, never inference.**
It understands `ensure → load → warm → ready → execute → shutdown` and
nothing else — never Whisper, Kokoro, or any model-specific logic.
Inference always belongs to engines. A `runtime-core` change that
mentions a model family is a design error by definition.

The extraction is performed as a pure refactor against the M2-frozen,
production-validated stt-runtime, **before** any new contract members
land (refactor-before-feature): the acceptance criterion is that the
diff of ModelManager's logic between M2 and M3 is empty, proven by the
unmodified stt-runtime test suite and a baseline re-run.

## Alternatives considered

- **Copy the machinery into tts-runtime** — rejected: two divergent
  ModelManagers is how hash-verification discipline erodes in one of
  them silently; every future fix would need to land twice or won't.
- **Fold into `packages/runtime-contract`** — rejected: the contract is
  the *outward* language runtimes speak to the gateway; the core is the
  *inward* machinery runtimes are made of. Mixing them would give the
  gateway a dependency path into runtime internals, collapsing the
  plane boundary (ADR-0002).
- **Name it `serving-core`** — rejected: it names a function, and
  functions accrete — the package will hold model lifecycle and artifact
  integrity, which are not "serving" in any strict sense. `runtime-core`
  names an owner and completes an existing vocabulary: runtime plane,
  runtime contract, runtime core.
- **Extract at first consumer (during M2)** — rejected then, correctly:
  a shared package generalized from one example generalizes the wrong
  things. Waiting for the second consumer made the seams factual.

## Trade-offs

- Shared package, shared blast radius: a `runtime-core` bug ships to
  every runtime at once — accepted; the alternative (divergent copies)
  ships *unknown* bugs to unknown subsets.
- Refactoring a production-validated service purely for architecture —
  accepted, mitigated by the behavior-frozen proof (unchanged test
  suite, empty logic diff, baseline re-run).
- Genericity adds one level of indirection (engine type parameter,
  injected probe) to code that was previously concrete.

## Consequences

- tts-runtime (and every future runtime) starts from `runtime-core`
  instead of re-implementing lifecycle; runtime services contain only
  their capability: binding, pipeline, engines.
- Lifecycle fixes and hardening land once and reach every runtime.
- The workspace gains a fifth-plus package; the one-way dependency rule
  (ADR-0001) extends: runtimes depend on `runtime-core`; `runtime-core`
  depends on nothing IntelliAI-specific except (never) the gateway.

## Future review criteria

- A runtime whose lifecycle genuinely diverges (e.g. M8 streaming
  sessions needing incremental state) — extend `runtime-core`
  generically, or fork deliberately via a superseding ADR; never patch
  capability-awareness into the shared package.
- If `runtime-core` ever needs to import a contract capability schema or
  an engine library, the lifecycle/inference boundary was drawn wrong —
  reopen this ADR rather than eroding it.
