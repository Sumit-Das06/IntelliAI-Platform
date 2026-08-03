# IntelliAI Platform — Architecture

> Current as of **v0.4 (Milestone 3 complete)**. Updated at every milestone
> close, alongside [PRD.md](PRD.md). Decisions behind this document live in
> [adr/](adr/) (0001–0020, all with review criteria); company law lives in
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

## What exists today (v0.4)

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
| Tests | 430 passing across 6 workspace packages (gateway over real HTTP+Postgres; both runtimes incl. isolation AST suites and license-boundary enforcement; contract goldens; runtime-core lifecycle + capability-independence proofs; eval determinism + CLI integration) |

## Request flow (as of v0.4)

The speech route mirrors transcription: SpeechService → registry + voice
catalog → `RuntimeClient.synthesize` → tts-runtime [text pipeline → voice
map → pool → engine] → WAV body + envelope header → raw audio to the
customer, envelope to accounting (`speech.completed`).

```
client ──► uvicorn ──► RequestContextMiddleware (request_id, timing, logs)
                          └─► router ──► [DI: CurrentAuth ── AuthService: bearer →
                                │         HMAC → lookup → revoke/expiry → AuthContext;
                                │         org_id + key_id bound into every log line]
                                │             └─► services ──► repositories ──► PG
                                │             └─► TranscriptionService ──► registry.resolve
                                │                  ──► RuntimeClient (HTTP; X-Request-ID
                                │                  propagated) ──► stt-runtime [pipeline →
                                │                  VAD → pool → engine] ──► envelope ──►
                                │                  translate + emit transcription.completed
                                └─► any failure ──► error handlers ──► one envelope
                                     {error: {type, code, message, param, request_id}}
```

## Deployment shape

Docker Compose (base file at repo root; overlays in `infra/compose/` for
gpu/prod). Every deployable is one process per container, non-root, logging
JSON to stdout, health-checked. The compose topology maps 1:1 to Kubernetes
(service→Deployment+Service, env→ConfigMap/Secret, volume→PVC, healthchecks→
probes) — post-1.0 concern by design.

## Where things will land (forward map)

~~M0.5 standards/CI~~ ✅ · ~~M1 orgs/users/keys~~ ✅ · ~~M1.5 AI strategy
layer~~ ✅ · ~~M2 STT + runtime contract + registry v1 + `/v1/models` +
evaluation seed with measured baselines~~ ✅
([review](milestones/2-stt-review.md)) · ~~M3 TTS + voices + runtime-core
+ speech evaluation wiring + GPL-free deployment~~ ✅
([review](milestones/3-tts-review.md); [design](milestones/3-tts-design.md)) ·
M4 metering/limits (Redis) · M5 batch jobs (PG `SKIP LOCKED`) · M6 console ·
M7 playground · M8 streaming (WebSocket, runtime-contract v2) · M9 registry
v2 (implements [REGISTRY_V2.md](REGISTRY_V2.md) + [MODEL_IDENTITY.md](MODEL_IDENTITY.md))
+ evaluation harness (formalizing the seed into the first-class evaluation
subsystem, with reserved evaluation identity) · M10 observability
(`/metrics`, OTel) · M11 docs/SDK (OpenAPI-driven) · M12 hardening/launch.
Parallel thread from M2 onward: customer discovery (PRD §6 operating
principles). Fine-tuning ladder stages (FINE_TUNING_STRATEGY.md) run as an
independent per-capability track gated on the evaluation seed's baselines.
