# IntelliAI Platform — Architecture

> Current as of **v0.15 (Milestone 0.5 complete)**. Updated at every milestone
> close, alongside [PRD.md](PRD.md). Decisions behind this document live in
> [adr/](adr/) (0001–0011, all with review criteria); working rules live in
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
│                    (services/stt-whisper M2, services/tts-piper  │
│                    M3, external-provider adapters later)         │
└──────────────────────────────────────────────────────────────────┘
```

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
5. **CPU-first, GPU-ready:** device is deployment configuration
   (env vars + compose overlay + CUDA base image), never application code.
6. **Commercial licensing gate:** no model ships without a recorded license
   and commercial-use verdict in the registry.
7. **Multi-tenancy from the first table:** organizations own everything;
   API keys belong to organizations; every tenant query is org-scoped.

## What exists today (v0.15)

| Component | State |
|---|---|
| Monorepo + boundaries | `apps/ services/ packages/ ml/ research/ infra/ docs/ tools/` (ADR-0001) |
| Dev environment | one command: `make up` → api + Postgres 16 + Redis 7 + MinIO (+ Adminer via `make db-ui`) |
| API gateway skeleton | FastAPI app factory · typed fail-fast Settings (SecretStr, frozen) · structlog JSON/console · `X-Request-ID` correlation middleware · modular health (`/health/live`, `/health/ready`, healthy/degraded/unhealthy) |
| Error contract | nine-type taxonomy (`core/errors.py`) · one envelope `{error:{type,code,message,param,request_id}}` rendered by four handlers (`api/errors.py`) · `Retry-After` on retryables · 400-not-422 · opaque 500s (ADR-0009) |
| Persistence | async SQLAlchemy engine (pooled, pre-ping) · session-per-request · naming conventions + TimestampMixin fixed pre-first-table · repositories contract · Alembic (async, settings-driven) |
| Containerization | multi-stage uv build · non-root · ~300MB · health-ordered compose startup |
| Quality gate | pre-commit (ruff, gitleaks, large-file guard, conventional commits) · `make check` (lint+types+tests) · CI on clean machines (path-filtered lint/typecheck/test-with-real-PG behind `CI OK`) |
| Standards | ADRs 0001–0011 with future review criteria · CONTRIBUTING + five handbooks (principles, patterns, security, testing, documentation) |
| Tests | 26 passing: config, logging, health (fakes), error contract, DB integration on real Postgres (auto-skip w/o infra) |

## Request flow (as of v0.15)

```
client ──► uvicorn ──► RequestContextMiddleware (request_id, timing, logs)
                          └─► router ──► [DI: SettingsDep · SessionDep · HealthDep]
                                │             └─► (M1+: service ──► repositories ──► PG)
                                │             └─► (M2+: registry ──► inference service
                                │                  via runtime contract, request_id propagated)
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

~~M0.5 standards/CI~~ ✅ · M1 orgs/users/keys · M2 STT + runtime contract +
registry v1 · M3 TTS + voices · M4 metering/limits (Redis) · M5 batch jobs
(PG `SKIP LOCKED`) · M6 console · M7 playground · M8 streaming (WebSocket)
· M9 registry v2 + evaluation harness · M10 observability (`/metrics`,
OTel) · M11 docs/SDK (OpenAPI-driven) · M12 hardening/launch.
