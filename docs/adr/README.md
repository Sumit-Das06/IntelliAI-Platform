# Architecture Decision Records — Index

ADRs are not documentation; they are permanent engineering decisions.
Template: [0000-adr-template.md](0000-adr-template.md) — Context, Problem,
Decision, Alternatives, Trade-offs, Consequences, Future review criteria.
Write the ADR *before* the decision lands; **supersede rather than edit**
(set the old ADR's status and this table's Superseded By column).

| # | Decision | Status | Date | Superseded By | Related |
|---|---|---|---|---|---|
| [0001](0001-monorepo-with-enforced-boundaries.md) | Monorepo with enforced package boundaries and one-way dependency direction | Accepted | 2026-07-29 | — | 0007 |
| [0002](0002-control-plane-inference-plane-separation.md) | Inference runs in dedicated services, never in the gateway process | Accepted | 2026-07-29 | — | 0003, 0004 |
| [0003](0003-internal-runtime-contract.md) | Capability-shaped internal runtime contract; providers are adapters | Accepted | 2026-07-29 | — | 0002, 0005 |
| [0004](0004-cpu-first-gpu-ready.md) | CPU-first serving; GPU adoption is deployment configuration only | Accepted | 2026-07-29 | — | 0002, 0003 |
| [0005](0005-permissive-model-licensing-policy.md) | Only commercially-clear model licenses; the registry enforces it | Accepted | 2026-07-29 | — | 0003, 0011 |
| [0006](0006-jobs-in-postgres-skip-locked.md) | Batch jobs via Postgres `SKIP LOCKED`, not a queue framework | Accepted | 2026-07-29 | — | 0002, 0010 |
| [0007](0007-uv-workspaces.md) | uv workspaces with a single lockfile for the monorepo | Accepted | 2026-07-29 | — | 0001 |
| [0008](0008-structured-event-logging.md) | Structured event logging with platform-wide correlation IDs | Accepted | 2026-07-29 | — | 0009 |
| [0009](0009-api-error-contract.md) | One OpenAI/Stripe-shaped error envelope for the entire API | Accepted | 2026-07-30 | — | 0008, 0003 |
| [0010](0010-organizations-first-tenancy.md) | Organizations-first tenancy from the first table | Accepted | 2026-07-29 | — | 0006, 0009 |
| [0011](0011-minio-as-dev-only-s3-standin.md) | MinIO (frozen final release) as dev-only S3 stand-in | Accepted | 2026-07-29 | — | 0005 |
