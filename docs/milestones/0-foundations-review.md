# Milestone 0 — Foundations (v0.1) — Completion Review

- **Closed:** 2026-07-29
- **Commits:** `d7d0d18` … Step 8 (8 implementation steps, all on `main`)
- **Verdict:** ✅ Complete, with two items consciously deferred to M0.5 (listed below)

## Definition of Done — verification

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Fresh clone + documented commands → full stack, all healthchecks green | ✅ | `cp .env.example .env && make up && make migrate`; `docker compose ps` all `(healthy)` incl. api |
| 2 | `/health/live` 200; `/health/ready` 200 with per-dependency status; Postgres down → ready 503 while live stays 200 | ✅ | Demonstrated live (Step 6): healthy → degraded (redis) → 503 (postgres) → recovered |
| 3 | `alembic upgrade head` clean from empty DB | ✅ | Initial migration `cd09df1257af` applied; stamp verified in DB and by test |
| 4 | Test suite green | ✅ | 20/20 (config, logging, health, DB integration on real Postgres) |
| 5 | `ruff check` / `mypy` clean | ⏭ **Deferred to M0.5** | Tooling deliberately moved into the Engineering Standards milestone (user-approved scope change) |
| 6 | JSON logs in prod mode, pretty in dev; request ID on every request line | ✅ | Both renderings demonstrated; `X-Request-ID` echoed & logged |
| 7 | No secrets in git; api container non-root | ✅ | `.env` gitignored + dockerignored; `whoami` in container → `app`; image 299MB |
| 8 | ADRs merged; placeholder READMEs everywhere | ◐ | 0001 & 0011 merged; 0002–0010 decisions made, formal write-ups are an M0.5 deliverable (see ADR index); READMEs ✅ |

## What M0 delivered beyond the original plan

Adminer DB browser behind a compose profile (`make db-ui`); `make psql`;
platform-standard health response format with healthy/degraded/unhealthy
semantics; naming conventions + TimestampMixin landed *before* first table;
repositories-layer contract; `.gitattributes` LF enforcement; PRD.

## Technical debt register (small, known, scheduled)

| Item | Impact | Scheduled |
|---|---|---|
| No lint/type/CI gates yet | Style/type drift possible until M0.5 | M0.5 |
| Error envelope not implemented (`core/errors.py` absent; FastAPI default 422 shape still exposed) | Non-standard error responses until then | M0.5 (ADR-0009 + implementation) |
| Health checkers create Redis/HTTP clients per probe | Event-loop contention inflates measured latencies (~190ms artifact vs 3-4ms real) | M10 (or first time it annoys us) |
| Starlette TestClient deprecation warning (httpx2 transition upstream) | Noise only, may break on a future upgrade | Watch; act when it becomes an error |
| `BaseHTTPMiddleware` for request context | Fine now; revisit for WebSocket streaming | M8 |
| Single uvicorn worker; no multi-worker/process manager config | Fine for dev; prod sizing needed | M12 deployment guide |
| Migrations run manually (`make migrate`), not on container start | Correct by design (migrations ≠ app startup), but deploy runbook must say so | M12 |

## Improvement suggestions carried forward

1. M0.5: import-linter (or ruff rules) to *mechanically* enforce the
   layering/boundary rules that are currently review-enforced.
2. M1: adopt the savepoint-per-test fixture pattern for fast DB tests.
3. M2: reuse health-checker clients; propagate `X-Request-ID` on outbound
   inference calls (designed in, needs implementation).

## Milestone 1 readiness checklist (Auth: orgs, users, API keys — v0.2)

- [ ] M0.5 completed first (standards, CI, error envelope) — per approved roadmap
- [ ] Schema design review: `organizations`, `users`, `memberships`, `api_keys`
      (org-owned keys; prefixed public IDs; hashed key storage, shown once)
- [ ] Password hashing + key hashing choices (argon2 vs bcrypt; SHA-256+pepper for keys)
- [ ] `CurrentOrg` / `CurrentUser` dependencies; auth middleware vs dependency decision
- [ ] Repository implementations + first real migrations
- [ ] Tenancy scoping tests (cross-org isolation as a test, not a hope)
- [ ] PRD §6 and ARCHITECTURE.md updated at close
