# Production Readiness Checklist (M31)

| | |
|---|---|
| **Status** | LIVING CHECKLIST — the single page an operator reads before and during the Hostinger deployment |
| **Companion** | [deployment.md](deployment.md) (the step-by-step runbook) · [production-readiness.md](production-readiness.md) (the detailed audit) |

Every "ready" line below is verified by code, guard tests, or a recorded
drill — never by intention. The Hostinger column is honest: those items
CANNOT be done without the box, the domain, or the credentials.

## READY WITHOUT HOSTINGER (verified on this repository)

- [x] **Repository** — single `git clone` carries everything except
      weights and secrets; `.env` and `models/` are gitignored by law;
      clean-clone rehearsal recorded in the M31 report.
- [x] **Dockerfiles** — pinned bases, `--no-dev`, non-root users,
      checksummed llama.cpp layer, whisper + punctuation extras baked
      in; `models/`, `*.gguf`, and `backups/` excluded from every build
      context.
- [x] **Compose** — no `:latest` anywhere (seeding container pinned
      `alpine:3.20`); healthchecks on every long-running service
      including Caddy (admin-endpoint probe); only Caddy publishes
      beyond loopback in prod; tools/tts behind profiles.
- [x] **Caddy config** — auto-HTTPS with `{$DOMAIN:localhost}`, HSTS
      (`includeSubDomains`), nosniff, frame-deny, Permissions-Policy,
      no Server header, 30 MB edge body cap, no response timeout (the
      450 s gateway deadline rules; pinned by guard tests), validated
      by preflight in a throwaway container.
- [x] **Model artifacts** — `whisper-small` (downloadable, hash-pinned),
      `qwen3-asr-0.6b-hi-ft-e3@v1` and `punct-cap-seg-47@v1` (seeded,
      non-downloadable by design, hash-verified at every startup);
      `make seed-models` is a `prod-up` prerequisite and copies
      punctuation only when present.
- [x] **Punctuation posture** — capability implemented + staged (M30);
      prod overlay pins the flag OFF; preflight refuses ENABLED without
      the seed; smoke asserts posture; readiness reports the stage.
- [x] **Healthchecks** — `/health/live` (no I/O), `/health/ready`
      (db critical; redis/minio/stt-runtime non-critical); a degraded
      runtime slot now FAILS the runtime check, so a dead Hindi
      specialist alarms the keyword-matching monitor.
- [x] **Backups** — `make prod-backup` (pg dump + volume tar + object
      mirror with count verification); retention knobs documented
      (`INTELLIAI_BACKUP_KEEP` for dumps/tars,
      `INTELLIAI_OBJECT_BACKUP_KEEP` for object snapshots); nothing
      backup-shaped is tracked in git.
- [x] **Restore-check** — `make prod-restore-check` proves the newest
      dump restores into a disposable Postgres (alembic stamp + table
      count) without touching live data.
- [x] **Smoke tests** — `make prod-smoke`: containers/health, migration
      currency, 401 law, edge headers + redirect, publisher audit,
      punctuation posture, optional end-to-end transcription.
- [x] **UI** — AI Services badges match the registry ladder ("Beta" =
      `available`, served-not-promised; semantics documented at the
      source and test-pinned); playground documents the 10-minute/25 MB
      ceiling; `/docs` shows bearer auth, language semantics, limits,
      and response shapes without leaking internals.
- [x] **Documentation** — deployment runbook carries the seed step;
      stale pre-M26 claims corrected across ops + product docs.
- [x] **Deployment scripts** — `prod-check`, `prod-build`, `prod-up`
      (seeds first), `prod-migrate` (backup-gated), `prod-health`,
      `prod-smoke`, `prod-backup`, `prod-restore-check`, `prod-down`.

## HOSTINGER-ONLY (blocked on the box / domain / credentials)

- [ ] VPS credentials + base hardening (SSH keys, firewall, fail2ban).
- [ ] Domain + DNS A record → real Let's Encrypt issuance (until then:
      `DOMAIN=localhost` internal CA only).
- [ ] Production secrets generated ON THE BOX (`.env`, mode 600; the
      examples ship empty by guard-tested law).
- [ ] Weight transfer (`models/qwen3-asr-0.6b*`, `punct-cap-seg-47`) —
      rsync then `make seed-models`; preflight enforces presence.
- [ ] Off-box backup destination (`INTELLIAI_BACKUP_S3_*`) + cron +
      first real restore drill from the remote copy.
- [ ] Uptime monitoring keyword-matched on `"healthy"` (never the
      status code) + the six day-one alarms in production-readiness.md.
- [ ] VPS performance re-ladder (Linux, real cores) for E3 AND the
      punctuation stage; dev-box numbers are not SLAs.
- [ ] Real customer canary per the M24 playbook (90/10 → 25/75 →
      50/50), THEN the separate punctuation-enable promotion.
