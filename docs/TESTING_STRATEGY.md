# Testing Strategy

What we test, at which level, and the conventions that keep the suite
trustworthy. CI runs everything on clean machines; this document is about
writing tests worth running.

## Philosophy

- **Test promises, not plumbing.** A good test fails when a promise to a
  user breaks and survives any refactor that keeps the promise. Existing
  examples: the error envelope's exact key-set; secrets never appearing in
  `repr()`; readiness flipping 503 on critical failure.
- **Every guarantee we claim gets a test.** If it's worth stating in an ADR
  or the PRD, it's worth a red build when it regresses.
- **Coverage is a flashlight, not a target.** We look at it to find dark
  corners; we never write tests to move a number.

## The levels

| Level | Scope | Infrastructure |
|---|---|---|
| Unit | pure logic: config validation, taxonomy, aggregation rules | none |
| Integration | HTTP through the real app (in-process ASGI), DB through real Postgres | compose / CI service |
| Contract | inference services against the runtime contract, gateway against **fake engines** | none — never model weights in CI |
| Smoke | `make up`, health green, golden-path requests | full compose |

**Never SQLite as a Postgres stand-in.** Our correctness depends on
dialect behavior (timestamptz, JSONB, `SKIP LOCKED`). A suite green on
SQLite and red on Postgres is worse than no suite — it certifies a lie.

## Conventions

- **Hermetic by default:** tests never read the developer's `.env` or
  process env — settings are built explicitly (`conftest.settings`).
  Integration tests that genuinely need infra probe for it and
  `pytest.skip` with an actionable message ("requires make up").
- **Behavior-sentence names:** `test_noncritical_failure_reports_degraded_
  but_serves` — the suite's output reads as the spec.
- **Async tests** use the anyio marker; fixtures own resource lifecycle
  (create → yield → dispose).
- **Error paths are first-class:** every new endpoint tests its failure
  shapes (validation, not-found, auth) — the happy path is the easy third.
- **Tenancy tests are security tests:** when auth lands, every tenant-owned
  resource gets a "cannot read across orgs" test. These never get deleted
  to make a deadline.

## What we deliberately do not test

Framework behavior (FastAPI routing, Pydantic parsing mechanics),
third-party internals, and anything a type checker already proves. If mypy
guarantees it, a test restating it is noise.

## Future

M1 introduces per-test transaction rollback (savepoints) for fast isolated
DB tests; M9's evaluation harness is a *separate* concern — model quality
measurement, not software correctness — and never blocks CI.
