# Milestone 31 — Production Deployment Readiness + AI Services UI Readiness

| | |
|---|---|
| **Status** | COMPLETE — repository deployment-ready as far as possible without Hostinger; UI verified honest; clean-Linux rehearsal PASSED end to end |
| **Date** | 2026-08-20 |
| **Evidence** | `research/experiments/31-production-readiness/clean-linux-rehearsal.json` · guard tests in `apps/api/tests/test_ops_configuration.py` / `test_console.py` |

    PRODUCTION DEPLOYED: NO
    HOSTINGER REQUIRED: YES
    CODE/CONFIG READY: YES
    UI READY: YES
    CLEAN LINUX REHEARSAL: YES (full flow, real punctuated Hindi transcription through the HTTPS edge)

## 1. Deployment gap audit (verified from code, not docs)

A repository-wide audit produced a 20-item gap list; every item was
fixed, guard-tested, or explicitly classified HOSTINGER-ONLY. The living
operator view is the new
[production-readiness-checklist.md](../ops/production-readiness-checklist.md).
The four blocking findings, all fixed this milestone:

1. **`prod-up` had no seeding prerequisite** while production declares
   the undownloadable E3 slot — a fresh VPS would crash-loop. Fixed:
   `prod-up: seed-models` (same law local-prod always had), guard-tested.
2. **Seed target hardened**: pinned `alpine:3.20` (the repo's last
   unpinned image), punctuation copy made conditional, and — found live
   by the rehearsal — `chown -R 999:999` so a fresh volume is owned by
   the non-root runtime user instead of root.
3. **Deployment runbook** now carries the weight-transfer + seed step
   before preflight, installs `git make curl` on a fresh box, and no
   longer claims "production declares whisper only" (stale since M26).
4. **`.env.local-prod.example` was gitignored by accident** — now
   tracked; a fresh clone can run the staging battery without archaeology.

## 2-3. Docker + artifact readiness

- All base images tag-pinned, no `:latest` anywhere (guard-tested);
  `--no-dev` everywhere; non-root users; llama.cpp checksummed at build
  and re-verified at load; whisper + punctuation extras baked into the
  runtime image; `models/`, `*.gguf`, `backups/` excluded from build
  contexts (13 GB no longer ships to the daemon); api Dockerfile gained
  the `UV_HTTP_TIMEOUT=300` network posture (rehearsal finding).
- Artifacts, exact: `whisper-small@v1` (hash-pinned download),
  `qwen3-asr-0.6b-hi-ft-e3@v1` (seeded; onnx/mmproj shas in
  `engines/qwen3_asr.py`), `punct-cap-seg-47@v1` (seeded; shas in
  `engines/punctuation.py`). All hash-verified at every startup; a
  missing artifact refuses startup loudly; preflight catches it before
  Docker is touched. No mutable references exist — the `.invalid` seed
  URLs make silent revision drift structurally impossible.

## 4-5. Environment template + punctuation config

`.env.prod.example` now documents: the punctuation knobs (OFF, with the
promotion note), both backup-retention knobs (the `INTELLIAI_BACKUP_KEEP`
vs `INTELLIAI_OBJECT_BACKUP_KEEP` split fixed), the smoke key, the
storage bucket, and the four port overrides — with secrets still
empty-by-law (guard-tested). Punctuation separation is structural:
prod overlay pins `"false"`, local-prod pins `"true"`, base defaults
nothing, all three guard-tested.

## 6. Caddy / HTTPS

HSTS gained `includeSubDomains`; added `X-Frame-Options DENY` and a
Permissions-Policy; the no-edge-timeout law (the 450 s gateway deadline
rules) is now written in the Caddyfile and pinned by a guard; Caddy
gained a healthcheck (admin-endpoint probe) in both overlays. Domain
stays `{$DOMAIN:localhost}` — no DNS, no real certificates issued.

## 7. Backups

Mechanism verified end to end in M20 and re-audited: pg dump + volume
tar + object mirror with count verification; restore-check into a
disposable Postgres; nothing backup-shaped tracked in git. Off-box
destination remains a documented HOSTINGER-ONLY prerequisite — disaster
recovery is NOT claimed complete until a real remote exists.

## 8. Health / readiness / monitoring

Two blind spots closed:
- The gateway's runtime check now **fails on a "degraded" runtime** —
  a dead Hindi specialist slot turns `/health/ready` DEGRADED, so the
  keyword-matching uptime monitor alarms (previously everything stayed
  green while Hindi was down).
- Runtime `/health/ready` now reports the punctuation stage
  (`"punctuation": "ready"|"disabled"`), and `prod-smoke` asserts the
  reported posture matches the declared one (overlay-aware).
Monitoring itself stays provider-side (six documented day-one alarms);
no observability stack ships, by standing decision.

## 9-10. Runbook + clean-Linux rehearsal — **PASSED**

Fresh WSL2 Ubuntu clone of the committed state, disposable secrets,
verbatim make-recipe commands: preflight → seed → build → up → migrate
→ health (both slots + punctuation ready) → org/key bootstrap → **real
Hindi transcription through the Caddy HTTPS edge, punctuated
("क्या क्या चीज़ें लेना है हाँ।")** → full 10-check smoke **SMOKE OK** →
teardown. Five findings recorded and fixed (evidence file) — the
biggest, the root-owned-volume crash-loop, would have burned the real
VPS deployment day. What could not be rehearsed is exactly the
HOSTINGER-ONLY list (real DNS/TLS, off-box backup, VPS ladder, canary).

## 11-16. AI Services UI audit

- **"Production" badge semantics (Phase 12)**: verified from source —
  it is a product-catalogue launch state (its only opposite is "Coming
  Soon"), deliberately NOT an infrastructure claim; the console card
  has said "Production" since before anything was deployed. The
  semantics are now DOCUMENTED at the data source (`console.js`) and
  test-pinned so they cannot be silently reinterpreted. Badge kept.
- **Language badges (Phase 13)**: `Hindi · Beta` / `Arabic · Beta`
  remain CORRECT — the registry ladder holds both at `available`
  ("served honestly, not promised"); M26 changed what serves Hindi,
  not the promise rung. Promoting Hindi's badge requires the
  `supported` rung decision (the evidence to support it now exists in
  the catalog — that call is the founder's, not this milestone's).
  What WAS false got fixed: four doc claims that Hindi quality is
  "unmeasured" (it measures CER 0.11612, −69% vs the incumbent).
- **Punctuation UI (Phase 14)**: no punctuation service card, no
  punctuation advertising anywhere — correct while production ships
  OFF; the copy change belongs to the future enable-promotion.
- **API documentation (Phase 15)**: `/docs` gained a bearer security
  scheme (Authorize button now works; documentation-only — enforcement
  unchanged), a platform description (auth, 25 MiB/600 s limits,
  languages, auto-detect), and real descriptions on `language`,
  `response_format`, and both `X-IntelliAI-*` headers; the route
  docstring documents the 600 s refusal and the sample-id header.
  `raw_text` stays internal (never emitted publicly — verified).
- **Playground (Phase 16)**: now states "Up to 10 minutes of audio per
  file (25 MB). Longer files are refused, never cut short." Language
  options unchanged and consistent with the card.
- Console leak guard extended (`qwen`/`llama`/`gguf` never on any
  console surface) and `/v1/models` FORBIDDEN_TERMS extended likewise.

## 17. Web / Android / iOS regression

- Web: full api suite (incl. console/playground/contract tests) green —
  **CONTRACT VERIFIED**; the M31 rehearsal's edge transcription used the
  same public endpoint — **LIVE VERIFIED (server side)**.
- Android: zero client changes; unit suites **NOT RUNNABLE HERE** (no
  JDK on this machine); contract shapes verified live in M30's battery
  and unchanged since — **CONTRACT VERIFIED**.
- iOS: zero client changes; **NOT RUNNABLE HERE** (no Mac);
  **CONTRACT VERIFIED** per M27/M30 evidence.

## 18. Security

No secrets committed (guards re-verified); no tunnel hostnames in
config; artifacts hash-verified; internal ports loopback-only with only
Caddy public (smoke-asserted); no model names in UI or API errors (leak
suites extended); `/docs`/`/openapi.json` are deliberately public (the
service card links there; nothing sensitive renders); no debug
endpoints (`/metrics` does not exist; `/info` is internal-port only).

## 19. Tests / CI

api 637 (+8 M31 guards) · runtime 205 (readiness pin updated) ·
evaluation 677 · datasets 81 · training 17 · contract 46 — green;
ruff + format clean; mypy strict clean. CI: green on the M31 commits.

## 20-22. Checklists, risks, and the future procedure

- READY-WITHOUT-HOSTINGER and HOSTINGER-ONLY checklists:
  [production-readiness-checklist.md](../ops/production-readiness-checklist.md).
- Remaining risks: VPS performance is UNKNOWN until the box exists
  (dev numbers are not SLAs); disaster recovery incomplete until an
  off-box destination exists; Arabic remains unmeasured on the
  incumbent; the AI-annotated punctuation eval rows still await native
  review before the punctuation enable-promotion.
- The exact future procedure is [deployment.md](../ops/deployment.md)
  §0-§16 — now including §1's `apt-get install git make curl` and
  §5b's weight transfer + `make seed-models`, every step of which
  (except DNS/TLS/off-box items) was executed verbatim in the
  rehearsal.
