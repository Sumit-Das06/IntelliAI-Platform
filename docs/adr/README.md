# Architecture Decision Records — Index

Template: [0000-adr-template.md](0000-adr-template.md). Write an ADR *before*
a significant decision lands; supersede rather than edit.

| # | Title | Status |
|---|---|---|
| [0001](0001-monorepo-with-enforced-boundaries.md) | Monorepo with enforced package boundaries | Accepted |
| 0002 | Control-plane / inference-plane separation | Reserved — writing in M0.5 |
| 0003 | Internal runtime contract for inference services | Reserved — writing in M0.5 |
| 0004 | CPU-first, GPU-ready: device as deployment config | Reserved — writing in M0.5 |
| 0005 | Commercial licensing policy for models | Reserved — writing in M0.5 |
| 0006 | Batch jobs via Postgres `SKIP LOCKED` | Reserved — writing in M0.5 |
| 0007 | uv workspaces for dependency management | Reserved — writing in M0.5 |
| 0008 | Structured logging standard | Reserved — writing in M0.5 |
| 0009 | API error envelope and response conventions | Reserved — writing in M0.5 |
| 0010 | Organizations-first tenancy model | Reserved — writing in M0.5 |
| [0011](0011-minio-as-dev-only-s3-standin.md) | MinIO (frozen final release) as dev-only S3 stand-in | Accepted |

Decisions 0002–0010 were *made* during Milestone 0 planning (recorded in
the [M0 review](../milestones/0-foundations-review.md) and project memory);
their formal ADR write-ups are an explicit M0.5 deliverable.
