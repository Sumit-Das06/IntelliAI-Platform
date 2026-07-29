# ADR-0001: Monorepo with enforced package boundaries

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** IntelliAI core team

## Context

IntelliAI spans an API gateway, a web console, multiple inference services, shared
libraries, ML pipelines, research work, and SDKs. These components must evolve
together (a runtime-contract change touches gateway and services in one review) while
remaining independently buildable and deployable. Splitting them across repositories
imposes coordination overhead (versioned internal releases, cross-repo PRs) that a
small team cannot afford; putting them in one repository risks boundary erosion where
everything imports everything until nothing is independently deployable.

## Decision

We will use a single monorepo whose top-level directories are hard boundaries with an
explicit dependency direction:

| Component | May depend on |
|---|---|
| `apps/*` | `packages/*` only |
| `services/*` | `packages/runtime-contract` only |
| `packages/*` | nothing internal |
| `ml/*` | `packages/*`, public APIs of deployed services |
| `research/*` | anything |
| — nothing may depend on `research/*` — | |

Each Python component is a uv workspace member with its own `pyproject.toml` and
dependency set; a single root lockfile guarantees reproducible installs. Every
component is a separately buildable Docker image.

## Consequences

### Positive

- Atomic cross-component changes in a single PR (contract + gateway + service).
- One lockfile, one CI, one place to search; no internal package registry to run.
- Boundaries are reviewable facts (import direction), not tribal knowledge.

### Negative / accepted costs

- CI must path-filter to stay fast as the repo grows.
- Boundary discipline relies on review (later: an import-linter gate in CI).
- Repository clone grows over time; mitigated by keeping weights/datasets out of git.

## Alternatives considered

- **Polyrepo** — rejected: internal versioning and cross-repo coordination overhead
  is the dominant tax on small teams; every platform-wide change becomes N PRs.
- **Monolith (single package)** — rejected: inference services must deploy and scale
  independently of the control plane (ADR-0002); a single package makes that
  impossible and couples dependency sets (the gateway must never install torch).

## Future review criteria

- Clone size or CI wall-clock degrading developer experience despite path
  filtering and weights-out-of-git discipline → evaluate partial clones or
  splitting *release artifacts* (never the working tree) out.
- A component acquiring a genuinely independent release cadence and external
  consumers (e.g. the public SDK) → that component may graduate to its own
  repository; the platform core stays together.
