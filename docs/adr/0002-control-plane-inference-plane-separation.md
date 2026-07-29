# ADR-0002: Inference runs in dedicated services, never in the gateway

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0003, ADR-0004

## Context

The platform serves two fundamentally different workloads: control-plane
work (auth, metering, routing — millisecond, memory-light, I/O-bound) and
model inference (seconds-to-minutes, gigabytes of weights, CPU/GPU-bound,
heavy native dependencies). These workloads scale differently, fail
differently, deploy at different cadences, and require different hardware.

## Problem

Does model inference run inside the API application process, or in separate
deployable services?

## Decision

We will keep inference out of the gateway process permanently. Each model
family runs in its own service (`services/<name>`), communicating with the
gateway over HTTP on a private network. The gateway never imports ML
libraries; inference services never know about accounts, keys, or billing.

## Alternatives considered

- **In-process inference** — one deployable, no network hop. Rejected: couples
  scaling (10 auth requests/s ≠ 10 transcriptions/s), turns the API image
  into a multi-GB torch installation, lets one model OOM kill the control
  plane, and forces GPU hardware onto the entire tier.
- **Serverless per-request inference** — rejected: cold starts include model
  loading (tens of seconds); economics only work for sparse traffic.
- **Queue-only communication (no sync path)** — rejected for the sync API:
  adds broker latency and infrastructure to every request; remains the right
  shape for batch jobs (ADR-0006).

## Trade-offs

- A network hop (~1-5 ms) on every inference call.
- More deployables to build, monitor, and version.
- An internal contract (ADR-0003) that must be maintained with discipline.

## Consequences

- Gateway image stays small (299 MB today) and restarts in seconds.
- Each service scales, fails, and deploys independently; per-service
  hardware choice becomes deployment configuration (ADR-0004).
- Registry-based routing and provider adapters become possible.
- Local development needs docker compose, not just one process.

## Future review criteria

- If p95 gateway→service overhead exceeds ~10% of end-to-end latency for the
  smallest served models, consider co-locating that specific hot path.
- If operating N services exceeds team capacity before revenue supports it,
  consider consolidating *services*, never re-merging into the gateway.
