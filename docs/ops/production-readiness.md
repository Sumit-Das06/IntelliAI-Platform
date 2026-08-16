# Production Readiness — Go/No-Go Checklist

> The single page an operator walks before the first real deployment,
> and again before every risky change. Boxes marked ✅ were verified at
> Milestone 20 (local dry run — no production server exists yet); empty
> boxes are exactly the items that wait on external inputs. Nothing on
> this page may be checked by intention — only by evidence.

## Code

- [x] CI green on the deployed commit (including the Deployment Config job)
- [x] Full test suites green (gateway / runtime / evaluation / contract / core)
- [x] Lint green (`make lint`)
- [x] mypy green (`make typecheck`)

## Docker

- [x] Production images build from a clean context (`make prod-build`; CI builds both on every infra change)
- [x] Qwen Linux runtime pinned: llama.cpp b10344 tarball checksummed at fetch, six binaries SHA-256-checked at build, re-verified at every load
- [x] Whisper artifact pinned (hash-verified by the ArtifactStore at boot; volume is a cache, never a source of truth)
- [x] Healthchecks on every service; readiness probes where readiness is the right question
- [x] `restart: unless-stopped` on every long-running service
- [x] Dependency ordering (api waits for healthy postgres/redis/minio)

## Security

- [x] Secrets external (`:?` required in compose — no defaults; `.env` never committed; examples placeholder-guarded by tests)
- [x] HTTPS: auto-certificates from `DOMAIN`, HTTP→HTTPS redirect, HSTS
- [x] Ports: every internal service loopback-bound; Caddy alone faces the internet (guard-tested AND smoke-checked at runtime)
- [x] Authentication enforced (smoke test proves 401 without a key)
- [x] Rate limiting + admission control (Redis-backed; fails open FAST and alarms)
- [x] 30 MB body ceiling at the edge, matching the gateway's transport limit
- [x] No server fingerprint, no internal model names in public surfaces (leak-scanned in every M18/M19 drill)
- [ ] Secrets generated ON the VPS and stored in the password manager *(needs the VPS)*

## Data

- [x] Postgres backup script (nightly cron line documented)
- [x] MinIO object-level backup (primary) + volume snapshot (secondary)
- [x] Restore process: two recorded drills + `make prod-restore-check` (mechanical, disposable-container)
- [ ] Off-box backup destination configured and one remote copy confirmed landed *(needs credentials from the boss)*
- [ ] Restore drill executed ON the production box *(needs the VPS)*

## STT

- [x] Hindi → Qwen validated end-to-end (staging profile; CER −60% vs incumbent; ledger `long_audio_ready_600s`)
- [x] English → Whisper validated (production route unchanged)
- [x] 600-second long-audio path validated locally (M19 proof battery: sandbox, staging, Web, kill drills, concurrency)
- [x] Android long-audio limitation documented (client call cap 150 s < long-audio walls; keyboard dictation unaffected — `apps/keyboard-android/RELEASE.md`)

## Deployment (all waiting on external inputs — see the runbook §0)

- [ ] VPS provisioned (8 vCPU / 16 GB class, Ubuntu 22.04+, ports 80/443)
- [ ] Domain chosen; DNS A record → VPS IP (before first start)
- [ ] Production secrets generated on the box
- [ ] Off-box backup destination
- [ ] Uptime monitor account (keyword matching on `"healthy"`)

## Promotion (Hindi → Qwen; deliberately PENDING)

- [ ] Qwen promotion proposal reviewed by the founder (`registry/proposals.py`, evidence in `MODEL_LEDGER.md`)
- [ ] Switch approved (the one-commit diff in `model-rollout.md`: compose slots + catalog route + guard updates)
- [ ] Rollback path re-read and approved (git revert; whisper stays pinned + cached)
- [ ] Canary shape approved (which tenants, what watch period, what abort criteria)
- [ ] VPS capacity re-measured for long audio (~4–5 concurrent 300 s per deployment, ~4 GiB steady-state slot RSS — Windows-measured; re-measure on VPS hardware)

## Alerts to configure on day one (Phase 12 catalogue)

The stack exposes `/health/live` and `/health/ready` on the gateway and
the runtime; readiness is slot-truthful (a dead optional specialist
degrades the report without killing the service; a dead default slot
503s the runtime). Configure, in the monitoring provider, alarms on:

1. **Readiness degraded** — keyword match on `"healthy"` at
   `https://$DOMAIN/health/ready` (NOT the status code: degraded
   deliberately returns 200 so the control plane stays serving).
2. **Repeated runtime restarts** — the supervisor logs
   `restart` events; more than N in an hour means a sick child, not a
   healed one.
3. **503/overload rate increase** — admission refusals are honest but a
   sustained rise means capacity, not noise.
4. **Latency increase** — p95 on short transcriptions against the
   measured baseline (~2–4 s at plateau).
5. **Disk/storage errors** — Postgres and MinIO volumes; the metering
   fallback file appearing (`usage-fallback.jsonl` non-empty) is a
   CRITICAL ledger signal, not housekeeping.
6. **Backup failures** — the nightly cron's exit status AND the
   off-box copy actually landing (a local-only backup is a warning
   state by design).

No observability stack ships in this milestone — these are provider
dashboard configurations, listed so day one is a checklist, not a
design session.
