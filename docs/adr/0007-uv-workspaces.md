# ADR-0007: uv workspaces with a single lockfile for the monorepo

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0001

## Context

The monorepo (ADR-0001) holds multiple Python packages with deliberately
different dependency sets (the gateway must never install torch; inference
services must stay minimal). All of them must resolve consistently, install
reproducibly on Windows/WSL2/CI/Docker, and share tooling.

## Problem

Which dependency manager gives per-package dependency isolation with
workspace-wide consistency and cross-platform reproducibility?

## Decision

We will use uv workspaces: a root `pyproject.toml` listing members
explicitly (adding a member is a reviewed act, not a glob match), one
cross-platform `uv.lock` at the root, `.python-version` pinning 3.12, and
`uv sync` as the only sanctioned way to build an environment.

## Alternatives considered

- **Poetry** — rejected: slow resolver, historically non-standard metadata,
  weak monorepo/workspace story.
- **pip + requirements.txt / pip-tools** — rejected: no workspace concept;
  freeze files are snapshots, not cross-platform resolutions.
- **Per-package independent envs, unmanaged** — rejected: guaranteed version
  drift between gateway and services sharing a contract package.

## Trade-offs

- uv is young and VC-backed (Astral); we accept vendor-health risk for
  order-of-magnitude speed and a genuinely universal lockfile.
- Single lockfile means occasional merge conflicts on busy branches.

## Consequences

- Identical environments locally, in CI, and in Docker builds — the
  clean-machine CI principle depends on this.
- Docker layer caching keys cleanly off manifests + lockfile.
- Workspace-wide dev tooling (ruff, mypy, pre-commit) installs once at root.

## Future review criteria

- uv abandoned, stalled, or relicensed → nearest exit is PEP-621-standard
  metadata, which we deliberately keep clean for that reason.
- A polyglot workspace need (Node console tooling) that uv cannot cover —
  acceptable; JS stays npm/pnpm-managed alongside.
