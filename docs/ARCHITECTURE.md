# IntelliAI Platform — Architecture

> Current as of **v0.6 (Milestone 5 complete)**. Updated at every milestone
> close, alongside [PRD.md](PRD.md). Decisions behind this document live in
> [adr/](adr/) (0001–0027, all with review criteria); company law lives in
> [CONSTITUTION.md](CONSTITUTION.md) with the strategy stack indexed at
> [STRATEGY.md](STRATEGY.md); working rules live in
> [/CONTRIBUTING.md](../CONTRIBUTING.md) and the `docs/` handbooks.

## The three planes

```
┌──────────────────────────────────────────────────────────────────┐
│ EXPERIENCE PLANE   console (M6) · playground (M7) · docs · SDKs  │
├──────────────────────────────────────────────────────────────────┤
│ CONTROL PLANE      apps/api: auth · keys · rate limits · usage   │
│                    metering · model registry · jobs              │
├──────────────────────────────────────────────────────────────────┤
│ DATA PLANE         /v1/* inference APIs → inference services     │
│                    (services/stt-runtime M2, services/tts-runtime│
│                    M3, external-provider adapters later) —       │
│                    services are named for capabilities, engines  │
│                    swap; shared lifecycle in packages/runtime-core│
└──────────────────────────────────────────────────────────────────┘
```

Orthogonal to the deployment planes above, the platform recognizes three
*permanent* planes (M3 design review §7): **inference** serves customer
requests, **evaluation** produces immutable evidence about model
behavior, **control** decides what serves customers. Evaluation never
participates in inference and never makes deployment decisions directly;
the causal chain is one-way — serving creates evidence → evidence informs
promotion → promotion changes registry state → registry changes routing.

## Invariants (the rules that don't move)

1. **Inference never runs inside the gateway.** Every model — ours or an
   external provider's — is an independent service behind the internal
   runtime contract (`packages/runtime-contract`), routed via the model
   registry. Providers are adapters; the API layer never names one.
2. **The platform layer is domain-generic.** Speech/vision/LLM specifics
   exist only inside inference services and `api/v1/<domain>/` routers.
3. **`/v1` contracts are append-only once stable**; breaking changes get a
   new version package that coexists with the old.
4. **Nothing above the repository layer imports SQLAlchemy**
   (router → service → repository → SQLAlchemy → PostgreSQL).
5. **Hardware-agnostic architecture, CPU-first deployment** (ADR-0015,
   superseding ADR-0004's framing): contracts, identity, and APIs never
   assume a device; hardware/precision/placement live in builds and
   deployments; CPU remains the stated deployment default while
   measurements support it.
6. **Commercial licensing gate:** no model ships without a recorded license
   and commercial-use verdict in the registry — verified **per artifact
   version**, never assumed at family level.
7. **Multi-tenancy from the first table:** organizations own everything;
   API keys belong to organizations; every tenant query is org-scoped.
8. **Product capabilities are permanent; individual engines are
   temporary.** The platform evolves by replacing engines beneath stable
   products (public model and voice identities never change when their
   mechanics do). Corollary — the **Core Speech Language Policy v1**
   (PRD §6): English, Hindi, and Arabic are first-class product
   languages; if no single engine serves all three under the licensing
   and quality gates, multiple engines serve one stable API.
9. **Customers buy capabilities, not foundation models** (the *Commercial
   Identity Invariant*, M4). Usage, pricing, quotas, invoices,
   subscriptions, and analytics attach permanently to public capabilities
   (`intelliai-stt`, `intelliai-tts`). Artifacts, routing decisions,
   quantization, fine-tunes, adapters, merges, and engine replacements are
   implementation details that may never alter commercial identity — the
   commercial twin of invariant 8, proven by an eight-reality continuity
   test with a pricing-policy negative control.
10. **Commercial evidence is immutable; commercial interpretation
    evolves.** The platform keeps two permanent append-only ledgers —
    evaluation evidence (what models did) and customer usage (what
    customers consumed). Neither is ever edited; corrections are
    compensating entries. Plans, discounts, and prices are *lenses*
    applied at read time and recorded by version. **New commercial
    features add interpretation, never columns to the ledger.**
11. **Operational measurement never becomes commercial measurement.**
    Latency, memory, GPU, queue depth, topology, and routing decisions may
    not influence ledger facts, quotas, pricing, rating, or invoices —
    no surge pricing by load, no cost-recovery pricing by placement, no
    quota consumption by latency. The only route from an observation to a
    charge is a published price book version.
12. **Rollups are caches; the ledger is authoritative.** Every derived
    aggregate must be exactly reproducible from the ledger, and any
    disagreement is repaired by rebuilding the cache — never by adjusting
    the facts.
13. **The platform speaks two vocabularies** (M5). The *permanent*
    vocabulary names promises and identities — capabilities, public model
    and voice ids, languages and their ladder statuses, units, dataset and
    corpus versions, the ledgers, price-book and rating-algorithm
    versions, request ids, the laws themselves. The *temporary* vocabulary
    names implementations — engines, artifacts in service, builds,
    deployments, slots, route bindings, topology. The admission test for
    any new noun: **if we replaced or renamed this, who breaks?** If
    customers, history, or reproducibility break, it is permanent:
    append-only, never renamed, never removed. Customer surfaces,
    deployment names, and ledger *facts* draw only from the permanent
    column; the temporary column appears in ledgers only inside lineage —
    stored, never projected. Invariants 6, 8 and 9 are instances of this
    one test.
14. **Every (public model, language) pair has an explicit status from a
    three-rung ladder** (ADR-0027): `supported` — a product promise;
    `available` — served best-effort and honestly labelled, promising
    nothing; `unavailable` — refused with a clear error naming what *is*
    served, and the refusal recorded as demand evidence. The rungs are
    exhaustive by construction: toward a customer exactly three stances
    exist. The ladder is a **lifecycle**, not three labels — a language
    enters at `available` and reaches `supported` only through evidence
    that `available` service makes possible, which no state machine
    enforces because a production baseline is unobtainable without having
    served. **No language passes `available` without a versioned
    evaluation corpus the platform owns or has formally adopted,
    containing material in that language**: evidence quality is bounded
    by dataset quality.
15. **Routing is resolution.** The registry is the only component that
    maps a customer's request to an artifact, and it does so from
    declarative, evidence-gated state (ADR-0025). Runtimes serve what
    they are told; gateways ask; nothing else decides. Two rules bound
    what may ever influence that map:
    - **The Selector Admission Test.** A routing dimension is admissible
      only if the customer could know its value from their own request or
      their own commercial agreement — declared intent or contracted
      policy. A dimension knowable only from our operations (hardware
      class, load, placement, cost) is inadmissible and lives on
      deployment records. *What serves a customer may depend on what they
      asked for and what they bought — never on what our infrastructure
      was doing.*
    - **The Specificity Law.** Resolution selects the most specific
      matching selector; the default route matches everything; a tie
      between equally specific selectors is a composition-time error,
      never a runtime coin-flip.
16. **Binding, never coordination — the Route/Strategy Boundary.** A
    serving route binds one selector to one artifact. Coordination among
    routes — fallbacks, cascades, A/B splits, shadow and canary routing,
    ensembles, chained routing, regional failover — belongs to future
    *Serving Strategy* mechanisms and never changes the semantics of an
    individual route. A route record that accretes coordination fields is
    a resolution function that has stopped being pure. **There is no
    automatic cross-artifact fallback**: an automatic quality
    substitution is a promotion nobody approved.
17. **Three identities, never interchangeable** (ADR-0026). An
    **artifact** is a set of trained weights — an identity, permanent as
    a record. A **deployment** is a named place that hosts one or more
    artifacts — configuration. A **runtime process** realizes a
    deployment — ephemeral. *A deployment hosts an artifact; a runtime
    process realizes a deployment.* An artifact can be hosted by several
    deployments, so it is never a place; a deployment can be realized by
    several processes, so a restart is never a change of what is hosted;
    and a process holds no identity at all — nothing may name one, route
    to one, or record one as the thing that served. A slot's artifact
    binding is fixed for the life of its process: replacing it is a
    deployment operation, never a mutation.
18. **Three languages in one request, and only one of them routes.** The
    **requested** language is an input the customer declared, normalized
    to its base subtag for routing and recorded in full as a request
    fact; the **resolved route** is the registry's answer, a pure
    function of (request, registry state), decided before any inference
    runs; the **observed** language is what the engine reported. *Observed
    language is an output fact produced by serving; it is never routing
    input.* The arrow only points down: an evaluation cannot cause its
    own adoption, and serving state cannot alter the record of what was
    measured. Engines are told what routing decided, never what the
    customer typed.
19. **The Evidential Chain, and the promotion chain it feeds.** No route
    above `unavailable` without its evidence; no evidence without a
    versioned corpus; no trained artifact without cited dataset versions.
    Every binding is therefore explainable years later from immutable
    records alone — the evaluation-plane sibling of Historical
    Explainability. Evidence becomes serving only along one path:
    *evaluation → switching test → promotion verdict → **human review** →
    registry diff → serving changes*. The switching test never performs a
    promotion; it ends at a verdict, and every step after it is a human
    act or a consequence of one. **Rollback is a revert, not a
    promotion** — it restores a state that was already justified, on
    evidence that never expired.
20. **Language never touches admission or price.** A Hindi request and an
    English request of the same size consume the same quota and cost the
    same; routing changes which artifact serves and nothing commercial —
    proven per route by the continuity fingerprint. Capacity differences
    between languages surface as the runtime's honest 503, never as a
    429, and the only route from an observation to a charge remains a
    published price book version (invariant 11).

## What exists today (v0.6)

| Component | State |
|---|---|
| Monorepo + boundaries | `apps/ services/ packages/ ml/ research/ infra/ docs/ tools/` (ADR-0001) |
| Dev environment | one command: `make up` → api + Postgres 16 + Redis 7 + MinIO (+ Adminer via `make db-ui`) |
| API gateway skeleton | FastAPI app factory · typed fail-fast Settings (SecretStr, frozen) · structlog JSON/console · `X-Request-ID` correlation middleware · modular health (`/health/live`, `/health/ready`, healthy/degraded/unhealthy) |
| Error contract | nine-type taxonomy (`core/errors.py`) · one envelope `{error:{type,code,message,param,request_id}}` rendered by four handlers (`api/errors.py`) · `Retry-After` on retryables · 400-not-422 · opaque 500s (ADR-0009) |
| Persistence | async SQLAlchemy engine (pooled, pre-ping) · session-per-request · naming conventions + TimestampMixin fixed pre-first-table · repositories contract · Alembic (async, settings-driven) |
| Containerization | multi-stage uv build · non-root · ~300MB · health-ordered compose startup |
| Quality gate | pre-commit (ruff, gitleaks, large-file guard, conventional commits) · `make check` (lint+types+tests) · CI on clean machines (path-filtered lint/typecheck/test-with-real-PG behind `CI OK`) |
| Standards | ADRs 0001–0015 with future review criteria · CONTRIBUTING + five handbooks (principles, patterns, security, testing, documentation) |
| Strategy layer (M1.5) | [CONSTITUTION.md](CONSTITUTION.md) (20 principles) over four domain constitutions · nine-document strategy stack indexed at [STRATEGY.md](STRATEGY.md): AI strategy & data constitution, capability map (11 primitives, 3 serving classes), verified foundation-model selections, model identity (two-axis hierarchy, artifacts/builds/deployments), Registry V2 control-plane design, fine-tuning ladder, consolidated research report, founding review |
| Identity & auth | organizations/users/memberships/api_keys schema · HMAC-peppered shown-once keys (`core/security.py`) · repositories with org-scoped signatures · `IdentityService` (bootstrap CLI, key lifecycle) · `AuthService` → immutable `AuthContext` · `/v1/organization`, `/v1/api-keys` (create/list/revoke, tenant-isolated 404s) |
| Runtime contract | `packages/runtime-contract` v1 — the permanent transport-free language (frozen `Capability` enum, envelopes, error taxonomy, operational-only metadata; ADR-0016); HTTP binding cross-pinned by CI test |
| Runtime core | `packages/runtime-core` (ADR-0019, extracted at the second consumer, behavior-frozen): ArtifactStore (SHA-256-verified cache) · generic ModelManager (capability-supplied warm-up probe) · bounded WorkerPool · `RuntimeServiceError` · shared logging — *owns lifecycle, never inference* (boundary CI-enforced) |
| Model registry v1 | code-declarative resolution + composition-time license gate (per-artifact-version verdicts); public models `intelliai-stt` → `stt-runtime`/`whisper-small`, `intelliai-tts` → `tts-runtime`/`kokoro-82m` (Apache-2.0 verified 2026-08-03); public voice records beside the model catalog (Registry V2 will own voice resolution) (ADR-0017) |
| STT runtime | `services/stt-runtime` (ADR-0018): HTTP binding · media pipeline (magic-byte whitelist → sandboxed ffmpeg → 16 kHz mono → energy VAD, per-stage timing, silence short-circuit) · engines behind Protocol (ReferenceEngine in CI; faster-whisper via optional extra, AST-enforced isolation) |
| TTS runtime | `services/tts-runtime` (ADR-0018 template #2 + ADR-0020 binary binding): JSON in → WAV body + bounded operational-only `X-Runtime-Envelope` (errors always JSON) · text pipeline (validate → normalize seam → voice resolution) · VoiceMap (same public voice ids per engine — the rebinding law) · engines behind Protocol (ReferenceSynthesisEngine in CI; Kokoro-82M via optional extra, **espeak-free by license firewall**; English-only per verdict, Hindi gated) · GPL-free deployment image (build fails if the espeak chain is importable) |
| Public AI API | `/v1/audio/transcriptions` (OpenAI-compatible: json/text/verbose_json) · `/v1/audio/speech` (raw WAV out, zero internal headers) · `/v1/audio/voices` + `/v1/models` product catalogs (leak-guard-tested) · transport-agnostic RuntimeClient (transcribe + synthesize) · total runtime→public error translation (shared) · `transcription.completed`/`speech.completed` accounting events |
| Evaluation | `ml/evaluation`: versioned immutable datasets/corpora (audio never in git), stdlib metrics + registry with declared directions, live-runtime eval runners (`run`, `speech-eval` — reproducibility metadata from live /info), deterministic benchmark harnesses (`bench`, `bench-tts`) · committed baselines: STT WER 0.000; TTS EN round-trip WER 0.072 (+ live reproduction); [STT](../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md) & [TTS](../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md) production baselines (gateway overhead 0.86 %/2.0 % of inference — ADR-0002 validated both shapes) |
| Usage ledger (M4) | `usage_events` + `usage_quantities` — append-only by database trigger (UPDATE/DELETE/TRUNCATE refused) *and* by an AST test forbidding a mutating statement in the repository; money-free; capability-agnostic `(unit, amount)` rows; usage **origin** taxonomy (customer/benchmark/evaluation/research/fine_tuning/demo/internal_qa); internal **lineage** stored and never projected; corrections are compensating events (ADR-0021) |
| Admission control (M4) | `limits/` — Redis token buckets and concurrency leases, each a single atomic Lua script clocked by `redis TIME`; guard attached to the **/v1 router** so no endpoint can forget it; hierarchy IP(pre-auth) → org → key(surface-namespaced) → capability → control-plane; plan-derived limits; fails open **loudly and cheaply** via a circuit breaker (ADR-0022) |
| Entitlements (M4) | `entitlements/` — quota computed from the **ledger** (never a counter), spend limits from rated usage, calendar-month UTC half-open periods, free tier live from day one; overshoot bounded by input limits; reserve/settle seam named and unbuilt |
| Pricing (M4) | `pricing/` — versioned immutable price books selected **per event** by `occurred_at` (a price cut never re-prices the past), pure rating carrying `price_book_versions` + `rating_algorithm_version`, discounts as read-time agreements, rounding once at the line; `usage_rollups` as a rebuildable cache the ledger always outranks (ADR-0023) |
| Idempotency (M4) | optional `Idempotency-Key`; at-most-once **billing** (not compute) enforced by database uniqueness — held even with Redis stopped, in production (ADR-0024) |
| Commercial analytics (M4) | `analytics/` — reconciliation across gateway → ledger → rollups → rating (8 checks), anomaly queries against each tenant's own baseline, language adoption for the Core Speech Language Policy; `intelliai commercial-report` exits non-zero on disagreement; [commercial baseline](benchmarks/2026-08-04-commercial-plane-baseline.md) (+18 ms p50, 2.1 % of a served request) |
| Model registry v1.5 (M5) | `ServingRoute` records binding a typed, append-only `RouteSelector` (one dimension: language) to one artifact and deployment, carrying the ladder rung, its serving-path licence verdict, and its evidence citations; `resolve(model, language)` and `resolve_voice(model, voice)`; composition refuses an empty selector, a tie, an unevidenced promise, an unversioned corpus citation, a non-commercial serving path, or a binding stage below `production` (reserved for V2) (ADR-0025, ADR-0027) |
| Multi-artifact runtimes (M5) | Deployments declare the artifacts they host (`INTELLIAI_{STT,TTS}_SLOTS`); `ModelManager`'s multi-slot shape needed no change, so `runtime-core` gained zero code; slot selection by the request's pinned artifact (unhosted → `INVALID_INPUT`); per-slot voice catalogs keyed by the loaded engine, so a voice cannot be resolved before a slot is selected; engine-named deployments refused at startup (ADR-0026) |
| Language routing (M5) | Gateway resolves per declared language (STT) and per voice (TTS); runtime clients keyed by **deployment**; `language_not_supported` (400) names what *is* served and is recorded as demand evidence with no billable event; TTS ledger language derived from the rendering voice — M4's gap closed with **no public language field** (F-M5-7) |
| Evaluation identity (M5) | Every record names public model, language, artifact, artifact version, build, deployment, dataset version, benchmark, judge, timestamp — plus a slice-coverage block that stops a record overstating itself (`is_quality_claim`); the registry exports a **resolution manifest** (CI drift-guarded) so evaluation measures what the registry selected and never an operator's claim; datasets located by `name@vN`, never by filename |
| Promotion (M5) | Three classes with distinct bars — language enablement (absolute), route replacement (relative), voice rebinding (relative + listening); `switching_test` reports *comparability* separately from outcome, and a wash-with-movement is a `TRADE` for a human to accept in writing; the Evidential Chain checked on both sides (shape at composition, resolution in CI); [procedure](../ml/evaluation/PROMOTION.md) |
| Language policy state (M5) | STT: `en` supported, `hi`/`ar` available. TTS: `en` supported, `hi`/`ar` unavailable. Ladder coverage joins usage to the rungs in `commercial-report`; no Hindi or Arabic **speech corpus** exists, so neither can pass `available` (F-M5-8, F-M5-6) |
| Tests | 823 passing across 6 workspace packages (gateway over real HTTP+Postgres+Redis; both runtimes incl. isolation AST suites, multi-slot coexistence and license-boundary enforcement; contract goldens; runtime-core lifecycle + capability-independence proofs; eval determinism, identity, promotion bars and the Evidential Chain; commercial continuity proof with pricing negative control, now per route) |

## Request flow (as of v0.6)

Transcription resolves on the customer's **declared language**; synthesis
resolves on the **voice**, because a voice's sound is an artifact-specific
asset. Both ask the registry and accept its answer; neither contains a
branch on language. Resolution names an artifact *and* a deployment, and
the runtime client is keyed by the deployment.

```
client ──► uvicorn ──► RequestContextMiddleware (request_id, timing, logs)
                          └─► router ──► [DI: CurrentAuth ── AuthService: bearer →
                                │         HMAC → lookup → revoke/expiry → AuthContext;
                                │         org_id + key_id bound into every log line]
                                │             └─► services ──► repositories ──► PG
                                │             └─► TranscriptionService ──► capability check
                                │                  ──► registry.resolve(model, language)
                                │                       [route → artifact + deployment,
                                │                        or language_not_supported 400]
                                │                  ──► RuntimeClient[deployment] (HTTP;
                                │                  X-Request-ID propagated) ──► stt-runtime
                                │                  [pipeline → VAD → pool → SLOT SELECTED BY
                                │                  PINNED ARTIFACT → engine] ──► envelope ──►
                                │                  translate + emit transcription.completed
                                └─► any failure ──► error handlers ──► one envelope
                                     {error: {type, code, message, param, request_id}}
```

## Deployment shape

Docker Compose (base file at repo root; overlays in `infra/compose/` for
multilingual/gpu/prod). Every deployable is one process per container,
non-root, logging JSON to stdout, health-checked. The compose topology
maps 1:1 to Kubernetes (service→Deployment+Service, env→ConfigMap/Secret,
volume→PVC, healthchecks→probes) — post-1.0 concern by design.

A capability service is a **set of deployments**; today's topology is the
degenerate case of one deployment per capability, carrying the service's
own name, and the gateway holds a deployment → URL map. Deployment names
draw only from permanent vocabulary — capabilities and languages, never
engines — and an engine-named deployment is refused at startup. **On CPU
the default is one artifact per deployment** (F-M5-5): the measured
~54 MiB interpreter overhead buys simpler operations, independent
scaling, and a cleaner blast radius, rollback, and promotion. Packing
remains supported by the architecture and is not the default posture.

## Where things will land (forward map)

~~M0.5 standards/CI~~ ✅ · ~~M1 orgs/users/keys~~ ✅ · ~~M1.5 AI strategy
layer~~ ✅ · ~~M2 STT + runtime contract + registry v1 + `/v1/models` +
evaluation seed with measured baselines~~ ✅
([review](milestones/2-stt-review.md)) · ~~M3 TTS + voices + runtime-core
+ speech evaluation wiring + GPL-free deployment~~ ✅
([review](milestones/3-tts-review.md); [design](milestones/3-tts-design.md)) ·
~~M4 metering, admission control, entitlements, pricing + commercial
production baseline~~ ✅ ([review](milestones/4-metering-review.md);
[design](milestones/4-metering-design.md)) ·
~~M5 multilingual foundation — serving routes, multi-artifact runtimes,
language routing, evaluation identity, promotion workflow, deployment
topology~~ ✅ ([review](milestones/5-multilingual-review.md);
[design](milestones/5-multilingual-design.md)). *The socket, not the
bulb: adopting a language engine is now an artifact record, a deployment,
a route binding and its evidence — no contract, runtime-core, gateway, or
commercial change.* · M5.5 batch jobs
(PG `SKIP LOCKED`, and the trigger for reserve/settle quota) · M6 console ·
M7 playground · M8 streaming (WebSocket, runtime-contract v2) · M9 registry
v2 (implements [REGISTRY_V2.md](REGISTRY_V2.md) + [MODEL_IDENTITY.md](MODEL_IDENTITY.md))
+ evaluation harness (formalizing the seed into the first-class evaluation
subsystem, with reserved evaluation identity) · M10 observability
(`/metrics`, OTel) · M11 docs/SDK (OpenAPI-driven) · M12 hardening/launch.
Parallel thread from M2 onward: customer discovery (PRD §6 operating
principles). Fine-tuning ladder stages (FINE_TUNING_STRATEGY.md) run as an
independent per-capability track gated on the evaluation seed's baselines.
