# Milestone 42 — IntelliAI TTS Production Promotion

| | |
|---|---|
| **Status** | COMPLETE — speech synthesis is an APPROVED production service in the repository: English and Hindi, one artifact, one reviewed and reversible commit. Nothing is deployed. |
| **Date** | 2026-08-24 |
| **Founder decision** | **F-M42** — approve TTS production promotion (English + Hindi; hindi-female=hf_alpha, hindi-male=hm_psi), on the M38 selection, M39 implementation, M40 validation, and M41 status alignment |
| **Evidence** | this document · `docs/ops/model-rollout.md` (ACTIVE promotion + deploy procedure) · M40 evidence, unchanged and re-cited |

    TTS PRODUCTION PROMOTED: YES
    ENGLISH TTS PROMOTED: YES
    HINDI TTS PROMOTED: YES
    HOSTINGER DEPLOYED: NO
    REAL CUSTOMER TRAFFIC: NO
    DNS CHANGED: NO
    PRODUCTION SERVER TOUCHED: NO

    FINAL CLASSIFICATION: A — TTS PRODUCTION PROMOTED, DEPLOYMENT PENDING

## 1. What "promoted" means here (and what it does not)

Promotion is a **repository state**: the catalog and the production
configuration now declare speech synthesis an approved production
service, reviewed like any other code change and revertible by one
`git revert`. It is NOT a deployment. No host was contacted, no DNS
record exists, no production secret was generated, no production
server was started, and no customer traffic was served. The three
steps stay deliberately separate, and the runbook now says so in those
words: **promotion** (this commit) → **deployment** (a host runs the
prod-check → prod-up → prod-migrate → prod-smoke sequence) →
**launch** (customer traffic).

## 2. Pre-promotion posture (what M42 found)

| Surface | Before |
|---|---|
| Catalog: `intelliai-tts × en` | SUPPORTED on kokoro-82m (since M3 / F-M5-2) |
| Catalog: `intelliai-tts × hi` | **UNAVAILABLE** — the honest refusal |
| Catalog voices | 4, all English (2 launch + 2 permanent legacy aliases) |
| Staging proposal | `HINDI_TTS_ROUTE` + 2 voice records, carrying `APPROVAL_PENDING`; a test refused the sentinel in any live registry |
| `infra/compose/prod.yml` | **no TTS service at all** |
| `make prod-*` | no `--profile tts`, so the service could not start |
| Gateway readiness roster | TTS deliberately absent |
| `prod-preflight.sh` | no TTS artifact requirement |
| `prod-smoke.sh` | six services; no synthesis check |

## 3. The promotion diff — one reviewed, reversible commit

The E3/M26 shape, applied to synthesis. Four things move together:

1. **Catalog** (`registry/catalog.py`): the two Hindi voice records
   join `_VOICES`; the hi refusal route becomes
   `AVAILABLE → kokoro-82m` with a Hindi serving-path license verdict
   (Apache weights + espeak-ng **binary at an exec boundary**) and the
   evidence chain — corpus `m38-hindi-tts-probe-texts@v1`,
   `quality_baseline 2026-08-22-hindi-tts-model-selection`,
   `production_benchmark 2026-08-24-kokoro-hindi-staging-validation-m40`,
   `approval F-M42`. The kokoro-82m artifact provenance now names what
   it actually serves (4 packs, both languages, the espeak posture).
2. **Production configuration** (`infra/compose/prod.yml`,
   `Makefile`): a `tts-runtime` block pinning
   `SLOTS: kokoro · NORMALIZE_TEXT: "true" · OOV_FALLBACK: espeak ·
   HINDI_G2P: espeak`, `INTELLIAI_RUNTIMES_TTS_ENABLED: "true"` on the
   gateway, and `PROD := docker compose --profile tts …` so every
   production target composes the service it approved.
3. **Guards** (`core/health.py`, `prod-preflight.sh`,
   `prod-smoke.sh`): readiness answers for synthesis where the
   deployment serves it; the preflight refuses a prod start whose
   `models/kokoro-82m/v2/` files are missing; the smoke covers seven
   services, the TTS posture, all four voices, and one real synthesis
   per promoted language.
4. **Proposals + tests** (`registry/proposals.py`, six test modules):
   the proposal is ACTIVATED (its text moves to git history like E3's
   did), `ROLLBACK_TTS_PRODUCTION_ROUTE` becomes the reviewed revert
   target, and every production-refusal pin becomes a
   production-serving pin in the same commit.

**No artifact re-admission, no image change, no API change, no client
change.** The registry manifest was regenerated (`make manifest`) and
its diff is exactly the promoted route + two voices.

## 4. English TTS promotion (Phase 2)

English was already the catalog's `supported` route with its own
evidence (F-M5-2); what it lacked was a production deployment posture.
It now has one: `english-female` / `english-male` are approved
production voices, served by the pinned artifact, with the stale-image
guard (`make tts-smoke`, version floor 0.4.0), SHA-256 verification at
load, and the M35 hardening posture pinned in the overlay. The engine
voice packs behind those names never cross the product plane — the
leak sweep and the "engine token is not addressable" test both hold.

## 5. Hindi TTS promotion (Phase 3)

`hindi-female → hf_alpha`, `hindi-male → hm_psi` — the founder's M39
selection, unchanged. The same production laws E3's promotion used:
explicit artifact identity (kokoro-82m, revision `f3ff3571…`),
provenance recorded, SHA-256 pins per file, guard tests, and a stated
rollback target. **No other Hindi voice was promoted**: the research
packs (hf_beta, hm_omega) and the rejected candidates (Supertonic,
F5-Hindi) are absent from the catalog, pinned by a test that asserts
the served voice set exactly.

## 6. API, billing, streaming (Phases 4-6) — unchanged, by construction

- **API**: same `POST /v1/audio/speech`, same `GET /v1/audio/voices`,
  same fields (`stream`, `voice`, `speed`, `response_format`), same
  auth, request ids, and error envelopes. No new endpoint; the OpenAPI
  schema is untouched.
- **Billing**: not one line of billing logic changed. Characters are
  the billable unit; `audio_seconds` stays telemetry. The M40 live
  ledger drill remains the evidence (speed / voice / transport
  invariance at `characters=57`; the F1 client-abort law at
  `characters=342`; zero rows for refusals), and the M35/M36/M39
  billing tests all pass unchanged.
- **Streaming**: chunking, backpressure, cancellation and the M37
  PlaybackSession are byte-identical. Promotion changed what the
  catalog declares, never how synthesis runs.

## 7. Production guards (Phase 7) — every one intact, three strengthened

| Guard | State after promotion |
|---|---|
| Staging profile refused under `INTELLIAI_ENV=prod` | intact (settings validator + preflight + test) |
| Staging registry cannot leak into production | intact — and now moot for TTS: with no pending proposal, staging composes exactly the live catalog (test-pinned) |
| No unseeded artifact | **strengthened**: the preflight now refuses a prod start whose TTS artifact set is incomplete |
| No mutable `latest` | intact — pinned revision + per-file SHA-256 |
| No request-time downloads | intact — the store verifies at load; seeding covers a box without egress |
| No internal names in public API/UI | intact — live sweep: zero engine tokens across voices, models, status, errors, console pages, console.js |
| No secrets in the repository | intact — `.env`, `.env.prod.example`, Caddyfile untouched |
| Readiness truthfulness | **strengthened**: the gateway probes `tts-runtime` wherever the deployment serves it — no false green, no permanent meaningless DEGRADED |
| Production smoke requirements | **strengthened**: seven services, TTS posture, four voices, one real synthesis per language |

## 8. Artifact requirements (Phase 8)

Production requires `kokoro-82m` v2 — base weights, config, and four
voice packs (`af_heart`, `am_michael`, `hf_alpha`, `hm_psi`) — each
SHA-256-pinned at revision `f3ff3571…`. `make seed-models` copies
`models/kokoro-82m/v2/` into the model volume; the store hash-verifies
the placed files at every load; the runtime reports ready only after
that verification, and readiness failure keeps the gateway honest. The
espeak-ng binary (Hindi G2P + English OOV) ships in the runtime image;
the GPL python chain remains build-fatally banned.

## 9. UI semantics after promotion (Phase 9)

The M41 mechanism, extended to three states — read from the registry
AND this deployment's env, never hardcoded:

| Deployment | `/console/status` | Badge |
|---|---|---|
| local / staging (`env != prod`) | `preview`, `["en","hi"]` | **Preview** |
| production (`INTELLIAI_ENV=prod`) | `production`, `["en","hi"]` | **Production** |
| after a rollback (catalog refuses hi) | `soon`, `["en"]` | **Coming Soon** |

So an undeployed local tree never claims the customer's production
service is live, and a production box never under-claims a service it
serves. All three states are test-pinned, including the rolled-back
posture composed from `ROLLBACK_TTS_PRODUCTION_ROUTE`.

## 10. Rollback (Phase 11) — tested at repository level

- **Target**: `ROLLBACK_TTS_PRODUCTION_ROUTE` in `proposals.py`
  restates the pre-promotion refusal verbatim; a test pins its shape,
  and a second test pins that rollback is **whole-language, never
  half-promoted** — the voices and the route live in the same reviewed
  commit, so reverting removes both and `hindi-female` answers
  `voice_not_found` before any plane crossing.
- **English is untouched** by that revert: it was the supported route
  before M42 and the promotion never changed it.
- **UI proof**: the console-status test composes the exact registry the
  revert produces and asserts the console goes back to Coming Soon.
- **Deployment-tier rollback** (drop Hindi, keep English) remains one
  env line, drilled live at M40 (~40 s per direction).
- Production rollback was NOT run: production was never touched.

## 11. Validation (Phase 12) — labelled honestly

| Proof | What ran | Result |
|---|---|---|
| **Repository proof** | `docker compose --profile tts -f docker-compose.yml -f infra/compose/prod.yml config` with a real DOMAIN | composes cleanly; `tts-runtime` present with the promoted posture; `INTELLIAI_ENV: prod` + `INTELLIAI_RUNTIMES_TTS_ENABLED: "true"` on the gateway |
| **Repository proof** | `prod-preflight.sh` against a scratch `INTELLIAI_ENV=prod` env file (removed afterwards; the real `.env` untouched) | **PREFLIGHT OK** — including the new "promoted TTS artifact present for seeding (base + 4 voice packs)" check and the tts-profile compose validation |
| **Repository proof** | `make manifest` | regenerated; diff is exactly the promoted route + two voices |
| **Local production-shaped proof** | the running local stack (`env=dev`, staging profile, Caddy on 127.0.0.1) after rebuilding the gateway image | `/v1/audio/voices` lists six voices with `hindi-*` → `["hi"]`; `/console/status` → `preview` + `["en","hi"]`; `/health/ready` → **healthy with `tts-runtime` in the roster**; engine token as a voice → `voice_not_found` |
| **Actual production deployment** | **NOT RUN — no host exists** | — |

## 12. Security / leak sweep (Phase 17)

Live sweep over the voices listing, models listing, console status, an
error response, the services page and console.js: **zero** occurrences
of `hf_alpha`, `hm_psi`, `kokoro`, `espeak`, `misaki`, model paths, or
artifact hashes. Requesting `hm_psi` as a voice returns a plain
`voice_not_found`. The manifest that crosses into the evaluation
package keeps its own no-engine-names test, still green.

## 13. Tests (Phase 16) — all green, none weakened

api **681** · tts-runtime **170** (+1 skip) · stt-runtime **205**
(+1 skip) · evaluation **677** · datasets **79** (+2 skips) ·
training **17** · runtime-contract **46** · runtime-core **46** ·
mypy strict **0 issues in 342 files** · ruff + format clean ·
`make tts-smoke` green.

Five suites changed because the world changed, each updated to assert
the NEW truth rather than to pass: the TTS ladder (hi is now
`available`, ar still refused), the voice catalog (six voices, Hindi
declaring `hi`), ladder coverage (Arabic synthesis is now the refused
example), the evaluation manifest resolution (hi resolves; ar still
raises), and the console status (three states). Four **new** pins were
added: the prod overlay posture, the preflight artifact requirement,
the production smoke coverage, and the readiness roster when a
deployment serves TTS.

## 14. Production safety assertion (Phase 18)

- `git status` shows only repository files: catalog, proposals,
  gateway config/health, console assets, compose overlays, ops
  scripts, docs, manifest, tests.
- `infra/Caddyfile`, `.env`, `.env.prod.example`: **unchanged**
  (verified by diff) — no DNS, no certificates, no secrets.
- The only running containers are the LOCAL production-shaped stack
  (`INTELLIAI_ENV=dev`, staging profile, Caddy bound to 127.0.0.1)
  that predates this milestone. **No production server exists, none
  was started, and zero customer requests were served.**
- The scratch prod-env file used for the preflight dry run was deleted
  in the same command that created it.

## 15. Limitations / next milestone

- Hostinger/VPS access still does not exist: the deployment milestone
  owns provisioning, DNS, certificates, production secrets, the first
  live smoke, backup/restore rehearsal, and the VPS capacity
  re-measurement (M31 law: dev numbers are not SLAs).
- Hindi enters the ladder at `available`, not `supported` — the
  promise-level promotion is a separate, later decision with its own
  evidence bar (a production baseline it cannot have before serving).
- Naturalness remains the C-grade upstream ceiling; the M38 audition
  pack is still UNSCORED, and E-TTS-1 remains the owned-voice ML
  milestone.
- Romanized Hinglish is still unsupported (documented since M39).
- **Next**: the deployment/launch milestone — `prod-check` →
  `prod-build` → `prod-up` → `prod-migrate` → `prod-health` →
  `prod-smoke` on a real host, then the launch decision that opens
  customer traffic.
