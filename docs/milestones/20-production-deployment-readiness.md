# Milestone 20 — Production Deployment Readiness

> **DEPLOYMENT READY: YES** (pending the external inputs only) ·
> **PRODUCTION DEPLOYED: NO.** No server was touched, no DNS changed,
> no certificate issued, no production secret created, no customer
> exists. This milestone ends at *deployment-ready*, exactly as
> specified.

## 1. Current deployment state

Everything a deployment needs that can exist without a server now
exists, is validated, and is guard-tested. What remains is exactly the
external-input list (§17). The repository deploys from a pinned commit
onto a clean Ubuntu box with `git clone` + `cp .env.prod.example .env`
(fill values) + five make targets.

## 2. Architecture (unchanged — validated, not redesigned)

```
Internet
   ↓
 Caddy :80/:443          ← the ONLY internet-facing service
   ↓
  API :8000              ← host-loopback bind (smoke checks use it)
   ↓
STT Runtime :8001        ← whisper (serving) + pinned qwen layer (dormant)
   ↓
Postgres / Redis / MinIO ← loopback + internal network only
```

The M14B base compose was already production-shaped (loopback-only
ports, `:?`-required secrets, healthchecks, restart policies,
dependency ordering); the prod overlay adds Caddy and pins
`INTELLIAI_ENV=prod` + explicit whisper slots. **No parallel compose
architecture was created** — 19 ops guard tests pin this posture.

## 3. Docker changes

None to the stack shape. Added: the `Deployment Config` CI job (§14)
and the operational scripts (§below). The images were already correct.

## 4. Qwen runtime packaging (was already done — now CI-verified)

`infra/docker/stt-runtime.Dockerfile` vendors llama.cpp **b10344**
(ubuntu-x64): BuildKit refuses the tarball unless it matches
`sha256:01b90b07…`; six load-bearing binaries are individually
SHA-256-checked at build; the engine re-hashes them at every load
(platform pin table) and refuses to serve through an unpinned build.
GGUF weights are pinned in code (`bca25981…` / `41a342b5…` at a pinned
HF revision) and hash-verified by the ArtifactStore at boot. No
implicit downloads, no `latest`, no remote code, deterministic build —
and since M20, CI rebuilds the image and re-asserts the llama-server
hash on every infra change.

Carrying the layer activates nothing: engines load only for declared
artifacts, and every committed deployment declares `whisper` only
(guard-tested).

## 5. Whisper runtime packaging

Unchanged and already pinned: the `whisper` extra installs
faster-whisper into the image; artifact bytes are hash-verified into
the model volume at first boot (the volume is a cache, never a source
of truth). Runtime readiness *is* the artifact check — a slot is ready
only after verification.

## 6. Environment / configuration

`.env.prod.example` documents every required value (DOMAIN, pepper,
Postgres, MinIO, backup destination) plus, since M20: the explicit
warning never to set `INTELLIAI_REGISTRY_PROFILE`, and the M19
long-audio numbers for the record (direct 120 s / window 100 s /
overlap 5 s / ceiling 600 s / deadline 450 s / lease 540 s — all code
defaults; nothing to configure). Guards pin that examples carry no
minted-looking secrets and that production secrets ship empty
(generation is the operator's act). The lease>deadline invariant is
now a test (`test_the_admission_lease_outlasts_the_runtime_deadline`).

## 7. HTTPS / Caddy

Unchanged config, newly validated three ways: `caddy validate` in the
preflight, in CI, and exercised live in the dry run. `DOMAIN` is pure
configuration (no invented domain anywhere); with a real domain Caddy
issues Let's Encrypt automatically; HTTP answers only with redirects;
HSTS, nosniff, referrer-policy ride every response; no Server header;
30 MB body ceiling matches the gateway's transport limit; **no proxy
timeout** — deliberately, so the 450 s long-audio deadline is owned by
the gateway, not the edge.

## 8. Health / readiness

Gateway `/health/live` + `/health/ready` (database, redis, storage,
stt-runtime; degraded deliberately returns 200 so the control plane
stays serving — the monitor must keyword-match `"healthy"`). Runtime
readiness is slot-truthful (M17): a dead optional specialist degrades
the body; only a dead default slot 503s. The day-one alert catalogue
is written down in `docs/ops/production-readiness.md`.

## 9. Database migration flow

Single Alembic head (`bfe7e961`), 11 revisions, applied to a pristine
database on every CI run. `make prod-migrate` now **mechanically
refuses** to run without a <24 h Postgres backup (`force=1` documented
for the first deploy of an empty database). Startup never auto-runs
migrations; failures stop the deployment.

## 10. Backup / restore

M14B scripts unchanged (guard-tested: no embedded credentials, never
delete source data). Added `make prod-restore-check`: restores the
newest pg dump into a disposable container and verifies the migration
stamp and table count — the mechanical half of the recorded drills.
Off-box destination stays a placeholder until credentials exist; the
scripts warn loudly while local-only. Disaster recovery is **not**
claimed until the off-box copy lands (checklist item, unchecked).

## 11. Web readiness

Inspected, nothing to fix: the console uses relative URLs exclusively
(zero `localhost`, hardcoded ports, staging labels, or environment
references in any static asset); code examples derive from
`window.location.origin`; limit messages come from the server verbatim
(so the 600 s ceiling text flows through automatically); M18/M19
real-browser runs already proved the Studio behind a gateway origin
with zero internal names in the rendered page.

## 12. Android readiness

Release builds ship an **empty** default server URL by design (a
production domain is a deliberate config — guard-tested), HTTPS-only
(no cleartext merged in release — guard-tested), one reserved line in
`build.gradle.kts` for the future domain. `RELEASE.md` now documents
the production-endpoint procedure AND the long-audio client
limitation: okhttp call cap 150 s vs measured server walls (300 s
audio: ~80–155 s — marginal; 600 s audio: ~180–340 s — impossible).
Keyboard dictation is unaffected. **No timeout was silently raised**;
the change a long-audio client would need is documented and deferred
to a dedicated Android milestone.

## 13. Security review

- Secrets: none in git (gitleaks hook on every commit; example files
  placeholder-guarded), none in images (weights + secrets arrive at
  runtime), none defaulted in compose (`:?` required, guard-tested).
- Ports: loopback-only everything except Caddy — guard-tested
  statically AND swept at runtime by the smoke script.
- Redis runs unauthenticated **by accepted posture** on the isolated
  compose network (never published beyond loopback); stated here so it
  is a decision, not an accident.
- Auth enforced (smoke proves 401), rate limiting + admission control
  Redis-backed, 30 MB body ceiling at edge and gateway.
- No internal model names / paths / chunk details in public surfaces
  (leak-scanned across every M18/M19 drill; engine messages
  guard-tested); no MinIO credentials touch API responses; dev tools
  (adminer) and TTS stay behind explicit compose profiles.
- The staging registry profile: refused under prod by validator,
  refused by preflight before startup, absent from every committed
  compose (guard-tested thrice over).

## 14. CI/CD readiness

New `Deployment Config` job (path-filtered to infra changes): resolves
the prod compose config with dummy secrets, validates the local-staging
overlay, validates the Caddyfile, **builds both production images**,
and re-asserts the pinned llama-server hash inside the built image —
so a base-image bump (e.g. Dependabot) can never merge unbuilt again.
CI still deploys nothing; there is nothing to deploy to.

## 15. Local deployment dry-run (EXECUTED, 2026-08-16)

The production configuration, exercised end to end on local Docker
with `DOMAIN=localhost`, generated throwaway secrets (never production
ones, deleted after), a scratch compose project
(`intelliai-dryrun` — same knobs `backup.sh` always had), and the
developer stack stopped for the duration and restored after:

| Step | Result |
|---|---|
| `prod-preflight` | **PREFLIGHT OK** — with exactly the two expected dry-run warnings (localhost domain; env-file mode) |
| `prod-build` (both images) | built; one transient wheel-download failure on first attempt succeeded on retry |
| `prod-up` | six services up; postgres/redis/minio healthy before api started (dependency ordering observed) |
| migrations | `upgrade head` → `bfe7e9613396 (head)` verified |
| runtime first boot | whisper downloaded + hash-verified into a FRESH volume; healthy in ~30 s |
| `prod-smoke` | **SMOKE OK, 9/9**: services, healthchecks, gateway live+ready(healthy), runtime ready, migrations-at-head, 401 without a key, HTTPS 200 through Caddy with HSTS+nosniff and no Server header, HTTP→HTTPS 308, loopback-only port sweep — and **one real transcription through the TLS edge (200)** with a bootstrapped throwaway key |
| `backup.sh` + `restore-check` | pg dump + volume tar produced; dump restored into a disposable container with `ON_ERROR_STOP=1` — **14 tables, migration stamp `bfe7e9613396`** |
| teardown | `down -v`, throwaway env/key/backups deleted, dev stack restored healthy, zero dry-run volumes remain |

The dry run also FOUND and fixed three Windows-host-only portability
faults in the new scripts (curl's `/dev/null` target, the Python Store
shim, mktemp's virtual `/tmp`) — none of which exist on the Ubuntu
VPS, all of which now degrade gracefully anyway. That is what dry runs
are for.

## 16. Deployment runbook

`docs/ops/deployment.md` updated: preflight-first sequence
(`prod-check → prod-build → prod-up → prod-backup → prod-migrate →
prod-health → prod-smoke`), the qwen-layer and long-audio notes, the
mechanical backup gate, restore-check, and the link to the readiness
checklist. The PREPARED-NOW vs REQUIRES-BOSS split lives in §0 of the
runbook and §17 below.

## 17. Required inputs from the boss later

| Input | Goes where |
| --- | --- |
| VPS access (8 vCPU / 16 GB class, Ubuntu 22.04+, ports 80/443) | SSH |
| Domain/subdomain + DNS A record → VPS IP (before first start) | `.env` `DOMAIN` |
| Approval to generate production secrets ON the box | `.env` (pepper, Postgres, MinIO) |
| Off-box backup destination (S3-compatible endpoint + write-only key + bucket) | `.env` `INTELLIAI_BACKUP_S3_*` |
| Uptime-monitor account (keyword matching) | provider dashboard |

## 18. Production promotion remains disabled

Hindi (and everything else) still routes to whisper-small. The
validated hi→qwen proposal stays PENDING in `registry/proposals.py`,
reachable only through the staging profile that production refuses.
The promotion is one reviewed commit (slots + route + guard updates),
written out concretely in `docs/ops/model-rollout.md`, with rollback
and the measured capacity facts to price in first.

## 19. Known limitations

1. Long-audio walls, concurrency ceiling (~4–5 × 300 s in flight per
   deployment), and slot RSS (~4 GiB steady-state) are
   Windows-measured; re-measure on VPS hardware before enabling long
   audio for customers.
2. Android long audio formally unsupported (client budgets — §12).
3. Off-box backup and on-box restore drill wait on credentials/VPS.
4. A physical-device Android pass remains recommended before customer
   rollout (M18's contract replays are the evidence of record).
5. The runtime healthcheck's 600 s start period covers whisper's first
   boot; the qwen promotion diff should re-check it for ~1 GB more on
   the VPS link.

## 20. Exact next step once Hostinger credentials arrive

```
ssh <vps>                                    # 1. verify machine class, ports 80/443
curl -fsSL https://get.docker.com | sh       # 2. prerequisites
git clone <repo> /opt/intelliai && cd /opt/intelliai
git checkout <the pinned, CI-green commit>
cp .env.prod.example .env && chmod 600 .env  # 3. fill: DOMAIN + generated secrets
make prod-check                              # 4. preflight must print PREFLIGHT OK
make prod-build && make prod-up              # 5. Caddy obtains certificates
make prod-migrate force=1                    # 6. first deploy of an empty database
make prod-health && make prod-smoke          # 7. must print SMOKE OK
make bootstrap-org …                         # 8. first tenant + key; re-run smoke with it
make prod-backup && make prod-restore-check  # 9. then configure the backup cron + monitor
```

Then: staging verification on the box if desired, and the canary
decision — which is the founder's, not this document's.
