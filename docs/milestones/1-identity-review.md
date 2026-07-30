# Milestone 1 Review — Identity & API Keys (v0.2)

- **Closed:** 2026-07-31
- **Scope shipped:** identity schema (organizations, users, memberships,
  api_keys) · credential cryptography (`core/security.py`, ADR-0012) ·
  repositories + savepoint-rollback test infrastructure · identity service
  + bootstrap CLI · authentication dependency + `AuthContext` (ADR-0014) ·
  key management API (`/v1/api-keys`, ADR-0013) · 96 tests.
- **Verified live:** bootstrap ceremony, first authenticated request
  (user-performed), full rotation ceremony (create → revoke → old key
  rejected `api_key_revoked` → replacement works → idempotent re-revoke).

## What was built

The platform now has customers as a concept: tenants are born atomically
with an owner and a first key; keys authenticate every `/v1` request into
an immutable `AuthContext`; organizations self-manage their credentials
(create/list/revoke) over the public API; every request and event is
attributed (`organization_id`, `key_id`) in the logs.

## Assumptions validated

- **Org-first tenancy (ADR-0010) carried real weight**: every service
  method, repository signature, and test flowed naturally from it; no
  design friction anywhere.
- **The layering paid rent immediately**: bootstrap logic written once in
  the service is consumed unchanged by CLI and HTTP; the error contract
  absorbed six new codes with zero shape changes; DI made every layer
  testable in isolation.
- **Fast-hash key verification** is ~µs + one indexed query — auth adds
  single-digit ms (measured: 92 ms first request including pool warm-up,
  single-digit thereafter).
- **Savepoint-rollback fixtures** ran 40+ DB tests against the dev
  database with zero residue — pattern proven for all future milestones.

## Assumptions still unvalidated (M2 will test them)

- The entire **inference plane** remains on paper: runtime contract,
  plane separation, CPU latency envelope, request_id propagation across
  services.
- **Auth under concurrency/load** — correctness proven, contention not
  (touch_last_used is designed race-safe; unmeasured).
- **Multi-member organizations** — schema supports them; nothing exercises
  a second member until M6.

## Technical debt register (M1 additions)

| Debt | Intentional? | Trigger to resolve |
|---|---|---|
| Any org key can manage keys (no scopes/roles) | ✅ ADR-0013 | first restricted-key need or M4 |
| Key lookup hits PG every request (no cache) | ✅ ADR-0012 | auth latency in M4 metrics |
| Single unversioned pepper | ✅ ADR-0012 | enterprise compliance ask |
| Log-based domain events (false positive on rollback) | ✅ documented | M4 billing → outbox rows |
| No pagination on key listing | ✅ | console (M6) or >50-key orgs |
| Bootstrap CLI key extraction is fragile in scripts (grep matched prefix+key) | ⚠ cosmetic | add `--json` output flag when console/tooling needs it |
| `_client_with_db` helper duplicated in test_auth (helpers.py exists) | ⚠ cosmetic | consolidate on next test touch |

Carried from M0.5: TestClient/httpx2 deprecation watch; Dependabot and
dev-environment rule amendment — **still not done, now two milestones old;
they go first in M2 step 0, no excuses.**

## Risks entering M2 (Runtime Services)

1. **The runtime contract must be designed against BOTH engines**
   (whisper + piper) or it silently becomes whisper-shaped — flagged in
   the M0.5 review, now imminent.
2. First heavy native dependencies (ffmpeg, ctranslate2) — the untested
   WSL2-vs-Windows question becomes real.
3. First multi-service deployment: two more containers, service discovery
   via compose DNS, request_id propagation — all first-times.
4. Model weights: download/cache strategy must keep them out of git and
   out of images (large-file guard helps; image bloat is the new risk).

## If we rebuilt M1 today, what would we change?

Honestly: **the architecture, nothing** — every ADR held. Three process
lessons: (1) demo/CLI output should have had a machine-readable mode from
the start (the grep incident); (2) the `api_key_id`-vs-redaction collision
says: when a naming convention (log fields) meets a filter convention
(redaction markers), write the compatibility test the same day; (3) the
BaseHTTPMiddleware contextvar boundary cost a debugging cycle that
reading Starlette's docs first would have avoided — "read the known
limitations of a component before building on it" is cheaper than
rediscovering them.

## Readiness report for M2

| Status | Item |
|---|---|
| ✅ Ready | Auth pipeline end-to-end; every future endpoint inherits `CurrentAuth` |
| ✅ Ready | Attribution in logs (org/key on every request) — metering's foundation |
| ✅ Ready | Test patterns for HTTP+DB; error contract absorbing new codes |
| ✅ Ready | Container image rebuilt with full M1 surface |
| ⚠ Attention | M2 step 0: Dependabot + dev-env rule amendment (2 milestones overdue) |
| ⚠ Attention | Runtime contract: design against both STT and TTS shapes simultaneously |
| ⚠ Attention | User should rotate the chat-exposed dev key via the new endpoints |
| ❌ Blocking | — none — |

**M1 complete pending review sign-off. Next: Milestone 2 — STT Service &
Runtime Contract (v0.3): the platform transcribes its first audio.**
