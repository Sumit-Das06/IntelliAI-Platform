# ADR-0011: MinIO (frozen final release) as dev-only S3 stand-in

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** IntelliAI core team

## Context

The platform stores audio artifacts in object storage behind the S3 API
(dev/prod parity requirement). MinIO was the default local S3-compatible
server for years, but the upstream open-source project was archived in
April 2026 — the official image is frozen at `RELEASE.2025-09-07T16-13-09Z`,
and MinIO is AGPLv3.

## Decision

We will use the final official MinIO image, pinned, **for local development
only**. Production uses a managed S3-compatible service. All application code
speaks the generic S3 API (endpoint URL + credentials via config) — no MinIO
SDK, no MinIO-specific features.

AGPL is acceptable here because we run an unmodified server as a local dev
tool and never distribute or modify it; nothing AGPL links into our codebase.

## Consequences

### Positive

- Battle-tested, stable dev experience; a frozen release cannot regress.
- Swap cost is one compose service definition + two env vars.

### Negative / accepted costs

- No upstream security fixes; acceptable only because it binds to 127.0.0.1
  in dev and never ships to production.

## Alternatives considered

- **Community forks (e.g. pgsty/minio)** — rejected for now: young forks,
  unclear maintenance trust; revisit if the frozen image bit-rots.
- **SeaweedFS (Apache-2.0) / RustFS (Apache-2.0)** — viable maintained
  replacements; not chosen today because the frozen MinIO image is the
  lower-friction dev tool. These are the designated successors if we
  ever need to move.
- **LocalStack S3** — heavier, emulation-focused; more than we need.

**Revisit when:** the pinned image fails on a new Docker/OS version, or any
need arises to expose object storage beyond localhost in development.
