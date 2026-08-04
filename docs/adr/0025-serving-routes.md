# ADR-0025: Serving routes — registry-owned resolution with append-only selectors

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0003, ADR-0015, ADR-0016, ADR-0017, ADR-0026, ADR-0027

## Context

The Core Speech Language Policy makes English, Hindi, and Arabic
first-class product languages of `intelliai-stt` and `intelliai-tts`.
No single engine is expected to serve all three under the licensing and
quality gates, so one public model must eventually be served by several
artifacts — selected per request.

The seam already exists: every runtime request has carried a pinned
artifact id since M2, the gateway has always pinned it from registry
resolution, and the runtime has always refused a mismatch. What does not
exist is any way for resolution to give a *different* answer per
request, or any statement of who is allowed to decide that answer.

The three-planes law constrains the answer: the causal chain is one-way
(serving → evidence → promotion → registry state → routing), and the
registry is the platform's only resolution authority (ADR-0017).

## Problem

Who decides which artifact serves a request, on what inputs, recorded
where — such that promotion, rollback, evaluation attribution, and the
commercial invariants all keep working as engines multiply?

## Decision

**We will route by resolution: the registry maps (public model,
selector) → one artifact via declarative `ServingRoute` records, and no
other component decides.**

1. **The record.** A `ServingRoute` binds a `RouteSelector` to exactly
   one artifact (plus its deployment), carries the language's ladder
   status (ADR-0027), and reserves a binding `stage` field fixed at
   `production` until Registry V2 makes it variable. The public model's
   existing `artifact_id` remains the default route (empty selector);
   a model with only its default route behaves exactly as before.
2. **The selector.** `RouteSelector` is a typed record with append-only
   fields. Its only field in M5 is `language`, normalized to the base
   subtag for routing while the full tag is recorded as a ledger fact.
3. **The Selector Admission Test.** A selector dimension is admissible
   only if the customer could know its value from their own request or
   their own commercial agreement — declared intent (language, quality
   tier, latency class) or contracted policy (customer tier, region).
   Dimensions knowable only from our operations (hardware class, load,
   placement, cost) are inadmissible and live on deployment records.
4. **The Specificity Law.** Resolution selects the most specific
   matching selector; the default route matches everything; a tie
   between equally-specific selectors is a composition-time error, never
   a runtime coin-flip. Until Serving Strategies exist, exactly one
   binding may exist per selector.
5. **The Route/Strategy Boundary.** A ServingRoute binds one selector to
   one artifact. Coordination among multiple routes — fallbacks,
   cascades, A/B splits, shadow routing, canary routing, ensembles,
   chained routing, regional failover, or any future routing strategy —
   belongs to future **Serving Strategy** mechanisms and never changes
   the semantics of an individual ServingRoute. A Strategy, when
   designed (Registry V2), will be a named, versioned, evidence-gated
   object that references routes; it has no bindings of its own and can
   never launder an unevidenced artifact into traffic.
6. **Routing inputs are declared intent only.** STT routes on the
   request's declared language or falls to the default route; TTS routes
   on the voice, whose registry record binds it to its serving artifact.
   Detected language is a recorded fact, never a routing input.
7. **Validation at composition.** Every route's artifact must exist,
   match the capability, and carry a license verdict covering the
   language-specific serving path (voice packs, G2P, lexicons — the
   Hindi-GPL lesson made structural). A `supported` status without its
   evidence references is a composition error.
8. **Route changes are promotions.** In V1.5 a route change is a
   reviewed diff citing its evidence; the diff is the promotion record
   and git the audit trail. Rollback is a revert — possible because
   artifacts are immutable and retained.

## Alternatives considered

- **Runtime-side engine selection** (fallback chains, per-request
  heuristics) — rejected: the data plane making a control-plane
  decision; invisible to promotion, unattributable in evaluation, and —
  after this ADR — an unauthored Serving Strategy.
- **Gateway service code choosing** (if/else on language) — rejected:
  registry logic escaped its authority; untestable at composition time,
  invisible to the license gate.
- **Detect-then-route STT** — rejected for now: a two-pass architecture
  with its own latency and failure modes, bought before its evidence
  exists, and content-dependent routing makes the serving path
  non-deterministic from the request. Mismatch facts are recorded to
  justify it later, or prove it unnecessary.
- **A generic match-dict selector** — rejected: a stringly-typed policy
  engine no composition-time validation can defend; every typo a silent
  routing miss.
- **A per-dimension record family** (`LanguageRoute`, `RegionRoute`, …)
  — rejected: the migration the ServingRoute generalization exists to
  prevent.
- **`hardware_class` as a selector** — rejected by the admission test;
  placement is deployment metadata, never identity (ADR-0015).
- **Registry V2 now** (database-backed, promotion state machine) —
  rejected: designs the state machine before the first promotion has run
  through the simple version; V1.5's reviewed-diff promotions are the
  evidence V2 will be designed from.
- **Separate per-language public models** (`intelliai-stt-hi`) —
  rejected: breaks the Language Policy's promise (three languages, one
  product) and makes every customer integration language-aware.

## Trade-offs

- Declared-intent routing means undeclared-language traffic rides the
  default route even when a specialist exists; accepted, measured via
  observed-language facts, revisitable with evidence.
- One-binding-per-selector forecloses gradual rollout until Strategies
  exist; accepted — gradual rollout without the evidence machinery would
  be unattributable quality change.
- Code-declarative routes make every promotion a deploy; accepted
  deliberately while promotions are rare (the price-book reasoning,
  ADR-0023), with a measurable graduation trigger.
- A typed selector grows only by reviewed schema change, slower than a
  config edit; that friction is the point.

## Consequences

- Promotion and rollback become registry state changes with a uniform
  evidence bar; evaluation attribution is always exact because the
  serving artifact is a pure function of (request, registry state).
- The commercial plane is untouched by construction: routing changes
  which artifact serves; the Commercial Identity Invariant fingerprint
  is provably identical per route.
- Registry V2 inherits a working vocabulary — records, selectors,
  stages, the strategy boundary — and lifts it into its store rather
  than redesigning it. The measurable trigger: when route records
  outgrow reviewable diffs, the binding table (never the laws) moves.
- Adding a language or replacing an engine behind one is a reviewed
  diff plus its evidence, with zero changes to contract, runtime-core,
  or public APIs.

## Future review criteria

- A second selector dimension with a real customer need → extend
  `RouteSelector` append-only, under the admission test; precedence
  already defined by the Specificity Law.
- The first genuine need for coordinated routes (fallback, canary
  split) → design Serving Strategies in Registry V2; do not extend the
  route record.
- Sustained observed-vs-declared language mismatch on the default route
  → reconsider detection-based routing, with the two-pass costs
  measured.
- Route records outgrowing reviewable diffs → Registry V2's store.
