# Deployment Guide — IntelliAI STT v1 (Controlled Pilot)

> **STATUS: PREPARED, NOT DEPLOYED.** Everything below is implemented,
> validated locally (prod compose config + Caddyfile syntax checked, two
> restore drills recorded in [backup.md](backup.md)), and waiting on the
> external inputs in section 0. No production server exists yet; nothing
> in this repository claims otherwise. When the first real deployment
> happens, record it under "Deployment log" at the bottom.

One VPS, Docker Compose, HTTPS via Caddy. Same stack as development —
the prod overlay adds exactly one internet-facing thing (Caddy on
80/443) and pins the production posture. ~30 minutes from blank machine
to serving.

## 0. External inputs needed before starting

| Input | Why | Where it goes | Secret? |
| --- | --- | --- | --- |
| VPS (8 vCPU / 16 GB class, Ubuntu 22.04+, ports 80+443) | the host | — | no |
| Domain/subdomain, A record → VPS IP, **before first start** | Caddy needs live DNS to obtain Let's Encrypt | `.env` `DOMAIN` | no |
| `INTELLIAI_AUTH_KEY_PEPPER` — `openssl rand -hex 32` | API-key hashing; rotation invalidates every issued key | `.env` | **yes** |
| `POSTGRES_PASSWORD` — `openssl rand -hex 16` | database | `.env` | **yes** |
| `MINIO_ROOT_PASSWORD` — `openssl rand -hex 16` | object store | `.env` | **yes** |
| Off-box backup destination (S3-compatible endpoint + write-only key + bucket, or an rclone remote) | disaster recovery | `.env` `INTELLIAI_BACKUP_S3_*` or rclone config | **yes** |
| Uptime-monitor account (any provider with **keyword matching**) | alerting | provider dashboard | no |

Generate secrets ON the VPS, store them in the password manager, never
paste them into chat, tickets, or this repository.

## 1–3. Provision VPS, install runtime, configure DNS

```bash
# on the VPS
curl -fsSL https://get.docker.com | sh          # Docker Engine + compose plugin
git clone <repo> /opt/intelliai && cd /opt/intelliai
```

Create the DNS A record now — certificate issuance at step 6 needs it
already resolving. **Pick the region deliberately**: data residency is a
product fact (India-first cohort → an Indian region).

## 4–5. Configure environment and secrets

```bash
cp .env.prod.example .env    # fill EVERY value; compose refuses to start
chmod 600 .env               # with any required secret missing (:?)
```

`.env` lives only on the VPS and in the password manager. The example
files carry placeholders only — `test_ops_configuration.py` refuses
minted-looking values in them.

## 6–7. HTTPS and first start

```bash
make prod-up      # base + prod overlay; Caddy obtains Let's Encrypt
                  # automatically; HTTP answers only with redirects;
                  # HSTS + nosniff headers ride every response
```

First start downloads the hash-verified STT model (~480 MB); the
runtime healthcheck allows up to 10 minutes.

## 8. Database migrations (safe order, always)

```bash
make backup          # BEFORE any migration — even on first deploy
make prod-migrate    # alembic upgrade head, one-shot container
docker compose -f docker-compose.yml -f infra/compose/prod.yml \
  run --rm --no-deps api alembic -c apps/api/alembic.ini current   # verify head
```

Never auto-run migrations on container start; never downgrade against
production data without the pre-migration dump proven restorable.

## 9–11. Verify health, storage, STT

```bash
curl -s https://$DOMAIN/health/ready | python3 -m json.tool
```

`status` must be `"healthy"`, with checks for `database`, `redis`,
`storage`, **and `stt-runtime`**. `"degraded"` still serves the control
plane but is an alarm state. Then one real transcription per served
language (English at minimum) using the step-12 key.

## 12. Verify Web STT Studio (real, never mocked)

1. `make bootstrap-org …` → org + first key (shown once).
2. `make grant-consent org=… ref="<signed consent doc>"` only if the
   tenant contributes data (opt-in by law; the product works without).
3. `https://$DOMAIN/console/playground` on a phone browser: paste key →
   Record → Transcribe → transcript; edit → Save correction; untick the
   contribution checkbox → response carries no `X-IntelliAI-Sample`.
4. Envelope spot-checks: wrong key → 401 `authentication_error`; burst
   past plan RPM → 429 with `Retry-After`; quota exhaustion (if staged)
   → `quota_exceeded_error`, distinct from rate limiting.

## 13. Verify Android Keyboard (real, never mocked)

1. When the domain exists, bake the release default (one line reserved
   for 14D): `DEFAULT_BASE_URL = "https://$DOMAIN"` in the release block
   of `apps/keyboard-android/app/build.gradle.kts`.
2. Immediate check without a release build: in the app's settings set
   API Server to `https://$DOMAIN`, paste a pilot key, and dictate into
   a real app. Verify: Auto/EN/HI/AR send the right `language` field;
   contribution off → no sample header; correction round-trips; invalid
   key and airplane mode produce their honest messages.
3. Emulator first; then the physical-device checklist in
   `apps/keyboard-android/RELEASE.md`. **Report the two separately** —
   emulator verification never counts as physical verification.

## 14–15. Verify backups and restore

```bash
make backup && ls -la backups/ && tail -5 backups/backup.log
```

All three artifacts must appear (`pg-*.sql.gz`, `minio-*.tar.gz`,
`objects-*/`), the object line must report equal counts, and once
`INTELLIAI_BACKUP_S3_*` is configured the local-only warning must be
GONE. Within the first week: run the full restore drill from
[backup.md](backup.md) against disposable containers on the VPS and
record it. The repository's drills #1–#2 prove the **method**; only a
drill on the production box proves the **deployment**.

## 16. Rollback

- **Code:** `git revert <commit> && make prod-up`, then `/health/ready`
  + one transcription.
- **Model/catalog:** [model-rollout.md](model-rollout.md) — revert the
  catalog commit; usage-ledger lineage marks the boundary.
- **Database:** restore the step-8 dump into a parallel container,
  verify, swap. Never downgrade in place.
- **Full box loss:** new VPS → steps 1–7 → restore from the off-box
  copies per [backup.md](backup.md) → re-point DNS.

## After deploy (same day, not optional)

1. **Uptime monitor** on `https://$DOMAIN/health/ready` with a
   **keyword match on `"healthy"`** — never the status code alone: a
   degraded report (e.g. STT runtime down) deliberately returns HTTP 200
   so the control plane stays in rotation, and the monitor must alarm
   on it.
2. **Backup cron** — all three lines from [backup.md](backup.md), one
   manual run, and confirm the off-box copy actually landed remotely.
3. **Restore drill** on the VPS (steps 14–15).
4. Secrets in the password manager; `.env` never leaves the box.

## Updating

```bash
cd /opt/intelliai && git pull && make backup && make prod-up && make prod-migrate
```

Compose rebuilds only what changed. TTS stays off (profile) until its
version arrives.

## Deployment log

*(empty — no production deployment has happened yet)*
