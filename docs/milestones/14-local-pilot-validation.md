# Local Pilot Validation — IntelliAI Platform

> Complete end-to-end validation of the product on the **local
> development environment**, run at commit `1dcb764` on 9 Aug 2026.
> Purpose: prove the PRODUCT works before asking for production
> deployment approval.
>
> **Nothing in this run touched production.** No Hostinger server, no
> production DNS, no production certificates, no production secrets, no
> Play Store upload. Every service, request, sample, and screenshot in
> this report came from `localhost`.
>
> Every claim below is labelled **VERIFIED**, **NOT VERIFIED**, or
> **BLOCKED**. Nothing is claimed that was not actually executed.

---

## 1. Environment under test

| Item | Value |
| --- | --- |
| Commit | `1dcb764` (clean tree, branch `main`) |
| Stack | `docker compose up -d` — api, stt-runtime, postgres, redis, minio (+adminer, tts profiles) |
| Migrations | `bfe7e9613396` (head) |
| API | `http://localhost:8000` |
| Android | Android 15 emulator → `http://10.0.2.2:8000` (the debug default) |
| Pilot tenants | `Pilot Demo Co` (consent ON), `Pilot Fail Co` (consent matrix + erasure), `Pilot Zero Co` (zero-usage) |

**Health — VERIFIED.** `/health/live` → 200 instantly.
`/health/ready` → `healthy` with all four checks:
`database`, `redis`, `storage`, `stt-runtime`.

---

## 2. Web / STT Studio — real browser, real STT

Driven with **Chromium (Playwright) against the actual console UI** —
uploading a real WAV, clicking the real buttons. No mocked STT, no
API-only shortcuts.

| Check | Result | Evidence |
| --- | --- | --- |
| Authenticate with local API key | **VERIFIED** | key connected via console, org badge "Pilot Demo Co" |
| Real transcription | **VERIFIED** | `"Hello intaly AI, this is a voice typing test."` |
| Auto language | **VERIFIED** | sample `smp_766c…`, `requested_language = (null)` |
| English | **VERIFIED** | sample `smp_c53f…`, `requested_language = en` |
| Hindi request handling | **VERIFIED** | sample `smp_d747…`, `requested_language = hi` |
| Arabic request handling | **VERIFIED** | sample `smp_5213…`, `requested_language = ar` |
| Contribution ON → sample | **VERIFIED** | 4 samples created |
| Contribution OFF → no sample | **VERIFIED** | 200 + transcript, dev panel: *"not stored (contribution off)"*, no row |
| Correction in browser | **VERIFIED** | Save correction → `corrected` event = 1 |
| Original transcript immutable | **VERIFIED** | `original_transcript` unchanged after correction |
| Current transcript changes | **VERIFIED** | `current_transcript = "Hello IntelliAI, corrected from the web studio."` |
| Usage event recorded | **VERIFIED** | 5 usage events for the web run |
| Usage page reflects requests | **VERIFIED** | screenshot `web-5-usage.png` |

> **Honest note on Hindi/Arabic:** the injected audio is English speech.
> What is verified is that the platform **routes and records the
> requested language correctly**. Native-speaker transcription quality
> is **NOT VERIFIED** and requires native audio.

---

## 3. Android Keyboard — emulator, local backend

Same shared API (`http://10.0.2.2:8000` = the host's `localhost:8000`),
real microphone path, audio injected over the emulator gRPC.

| Check | Result | Evidence |
| --- | --- | --- |
| Installs / enables / selects | **VERIFIED** | IME enabled + selected, screenshot `android-1-setup.png` |
| API key configured securely | **VERIFIED** | only the `ik_live_…` hint displayed after save |
| Microphone permission | **VERIFIED** | dictation captured audio |
| Real audio reaches local STT | **VERIFIED** | transcripts returned from the local runtime |
| Transcript inserted into another app | **VERIFIED** | Contacts field: `"Hello intaly AI, this is a voice typing test."` |
| Auto | **VERIFIED** | `requested_language = (null)` |
| English | **VERIFIED** | `requested_language = en` |
| Hindi request handling | **VERIFIED** | `requested_language = hi` (Devanagari output: `अलो इंटली आई…`) |
| Arabic request handling | **VERIFIED** | `requested_language = ar` |
| Contribution ON | **VERIFIED** | +1 sample per dictation |
| Contribution OFF | **VERIFIED** | samples 8 → 8, transcript still inserted |
| Correction | **VERIFIED** | `smp_2c2c…`: original preserved, current = `"Corrected via the IntelliAI keyboard pilot."`, 1 `corrected` event |
| Client source recorded | **VERIFIED** | `client_source = keyboard`, `client_version = 1.0` |
| No audio on device disk | **VERIFIED** | `find /data/data/...` → none |
| No API key in logs | **VERIFIED** | `logcat` clean |

---

## 4. Shared-backend proof — the central claim

One organization, both clients, one query:

```
 client_source | client_version | samples | distinct_models |     model     | runtime_service |   artifact
---------------+----------------+---------+-----------------+---------------+-----------------+---------------
 web           |                |       4 |               1 | whisper-small | stt-runtime     | whisper-small
 keyboard      | 1.0            |       5 |               1 | whisper-small | stt-runtime     | whisper-small
```

Usage ledger for the same org:

```
 public_model_id | capability    | outcome   | billable | events | distinct_artifacts
-----------------+---------------+-----------+----------+--------+--------------------
 intelliai-stt   | transcription | succeeded | t        |     11 |                  1
```

**VERIFIED.** Both clients produced samples through **one API, one
runtime service, one artifact**, differing only by
`X-IntelliAI-Client` (`web` vs `keyboard/1.0`). There is no
Android-specific transcription path. `WebKeyboardContractTest` fails the
build if anyone forks it.

---

## 5. Data governance — consent is the ceiling

Executed live against the API on `Pilot Fail Co`:

| Case | Org consent | Contribution | Result | Verdict |
| --- | --- | --- | --- | --- |
| C | OFF | ON | 200, no sample header, 0 rows | **VERIFIED** |
| B | ON | OFF | 200, no sample header, 0 rows | **VERIFIED** |
| A | ON | ON | 200, sample created, 1 row | **VERIFIED** |

The organization's consent is checked **before** the per-request
preference, so a client can never opt in beyond what the tenant granted.

---

## 6. Dataset → training artifact pipeline

Run through the real API on the pilot org's own collected samples.

| Check | Result | Evidence |
| --- | --- | --- |
| Dataset creation | **VERIFIED** | `ds_8b32…` |
| Preview = freeze truth | **VERIFIED** | eligible 4/4, corrected 1, 17.636 s |
| Version freeze (immutable membership) | **VERIFIED** | `dsv_df13…`, 4 samples |
| Preparation | **VERIFIED** | `prep_d7ed…` `status=ready`, valid 4/4 |
| Manifest + checksum | **VERIFIED** | 887 bytes, `sha256:6a82b5f1…`, storage bytes re-hashed = match |
| Manifest line shape | **VERIFIED** | `audio, duration_seconds, id, language, text` |
| Reproducibility | **VERIFIED** | second POST → same preparation id, same checksum |
| **Correction after freeze does NOT change v1** | **VERIFIED** | pinned text still `"Hello into lee AI…"`, checksum unchanged, status still `ready` |
| New version picks up the new pin | **VERIFIED** | `dsv_2a82…` v3 pinned `"Corrected AFTER v1 was frozen"`, different checksum, `ready` |
| Honest FAILED path | **VERIFIED** | member erased → prepare → `status=failed`, reason `membership_count_mismatch`, valid 0/1 |

This is the flywheel proven end to end: **speech → sample → correction →
dataset → immutable version → pinned transcript → deterministic JSONL
artifact**, with reproducibility that survives the world moving on.

---

## 7. Usage analytics

| Check | Result |
| --- | --- |
| Totals (requests, speech minutes, avg duration, success rate) | **VERIFIED** — 11 requests, 1.04 min, 5.67 s avg, 100% |
| Daily granularity | **VERIFIED** |
| Hourly granularity | **VERIFIED** (17 points) |
| Minute granularity | **VERIFIED** (42 735 points) |
| Custom range (`start`/`end`) | **VERIFIED** |
| Zero usage | **VERIFIED** — fresh org: 0 requests, empty models/languages |
| Languages breakdown | **VERIFIED** — en 7, hi/ar/auto split |
| Models exposed publicly | **VERIFIED** — `intelliai-stt` only |
| **No internal engine names in public API** | **VERIFIED** — 0 "whisper" mentions across `/v1/usage/summary`, `/v1/speech-samples`, `/v1/models`, `/v1/datasets` |

---

## 8. Failure behaviour

All returned the existing platform error envelope; no new formats.

| Failure | Response | Verdict |
| --- | --- | --- |
| Invalid API key | 401 `authentication_error` / `invalid_api_key` | **VERIFIED** |
| Missing API key | 401 `authentication_error` / `missing_api_key` | **VERIFIED** |
| Unsupported language | 400 `invalid_request_error`, `param=language` | **VERIFIED** |
| Invalid audio (text file) | 400 `invalid_request_error`, `param=file`, lists supported containers | **VERIFIED** |
| Empty audio | 400 `invalid_request_error` "audio file is empty" | **VERIFIED** |
| Unknown model | 404 `resource_not_found_error` / `model_not_found` | **VERIFIED** |
| **STT runtime down** | 503 `service_unavailable_error` / `runtime_unavailable`; readiness → `degraded` (HTTP 200, control plane serves) | **VERIFIED** |
| **MinIO down** | **200 + transcript, no sample header** — collection failed open, exactly as designed | **VERIFIED** |
| Cross-org sample read | 404 `sample_not_found` (never 403 — no existence disclosure) | **VERIFIED** |
| Cross-org correction | 404 `sample_not_found` | **VERIFIED** |
| Contribution OFF / consent OFF | see §5 | **VERIFIED** |
| PostgreSQL down | **NOT VERIFIED** — deliberately skipped: killing the live dev database risks the pilot data this report rests on. Covered by unit tests (critical check → `unhealthy`/503). |

---

## 9. Backup & restore drill (this run)

| Step | Result |
| --- | --- |
| `infra/backup.sh` | **VERIFIED** — `pg-20260809-161730.sql.gz` + volume tar |
| `infra/backup-objects.sh` | **VERIFIED** — 52/52 objects mirrored (loud local-only warning, correct: no off-box remote configured) |
| Object restore into disposable MinIO | **VERIFIED** — 52/52 present |
| Postgres restore into disposable container | **VERIFIED** — 0 errors |
| DB parity live vs restored | **VERIFIED** — `103\|47\|39666\|6\|bfe7e9613396` identical |
| Dataset manifest checksum | **VERIFIED** — 891 B, matches DB record |
| Keyboard audio object | **VERIFIED** — 213 036 B restored |
| Web audio object | **VERIFIED** — 194 478 B restored |
| Live stack impact | **VERIFIED** — untouched; drill containers/volumes removed |

---

## 10. Android release configuration

| Check | Result |
| --- | --- |
| Debug allows local backend | **VERIFIED** — `http://10.0.2.2:8000` used for the entire Android run |
| Release requires HTTPS | **VERIFIED** — `ServerAddressTest` (6 tests) + `ReleaseConfigGuardsTest` (7 tests), run against the **release variant** |
| Release refuses localhost / 10.0.2.2 / 127.0.0.1 | **VERIFIED** — including over HTTPS |
| Debug APK builds | **VERIFIED** — 7.12 MB |
| Release APK builds | **VERIFIED** — 5.68 MB, **unsigned** |
| No production signing key created or committed | **VERIFIED** — none exists |
| APK published | **NOT DONE** (deliberately out of scope) |

---

## 11. Quality gates

| Gate | Result |
| --- | --- |
| Backend test suite | see final report line — full suite, no skips of substance |
| Android unit tests (debug + release) | **VERIFIED** — BUILD SUCCESSFUL |
| Android lint | **VERIFIED** |
| ruff / ruff format | **VERIFIED** |
| mypy strict | **VERIFIED** — 284 source files, no issues |
| Debug + release APK builds | **VERIFIED** |
| Migration head check | **VERIFIED** — applied head == latest revision |
| Hooks | **VERIFIED** — never bypassed |

---

## 12. Screenshots (real local data)

`data/reports/screenshots-pilot/` — 16 images, all captured during this
run from the live local stack:

**Web:** home · studio-transcribed · correction-saved · contribution-off
· usage · samples · datasets-ready · dataset-failed
**Android:** setup · keyboard · recording · transcript-inserted ·
language-picker · contribution · correction-offer · correction-dialog

---

## 13. Known limitations (stated plainly)

1. **Physical Android device: NOT VERIFIED.** Emulator only. The manual
   checklist is `apps/keyboard-android/RELEASE.md`.
2. **Native Hindi/Arabic quality: NOT VERIFIED.** Only request routing
   is proven; the test audio is English.
3. **PostgreSQL-down failure: NOT VERIFIED live** (see §8 reasoning).
4. **Off-box backup: NOT CONFIGURED.** Local snapshots only, and the
   script says so loudly. A destination is a production input.
5. **Web console stores its API key in browser `localStorage`** —
   assessed and accepted for the pilot (`SECURITY_GUIDELINES.md`),
   re-decide before any consumer launch.
6. **Consumer identity does not exist.** The pilot model is one API key
   per person; a public consumer launch needs user accounts + tokens.
7. **Load/soak testing: NOT PERFORMED.** Single-user validation only.

---

## 14. Production blockers (what the CTO decision unblocks)

None of these are code problems — all are external inputs:

1. Server (existing Hostinger server to be inspected) — **BLOCKED on approval**
2. Domain + DNS A-record — **BLOCKED**
3. Three generated production secrets (pepper, Postgres, MinIO) — **BLOCKED**
4. Off-box backup destination — **BLOCKED**
5. Uptime-monitor account (keyword match on `"healthy"`) — **BLOCKED**
6. Privacy policy URL (needs counsel; source material drafted) — **BLOCKED**
7. Android signing keystore (only if publishing) — **BLOCKED**

Everything the repository can control is done: deployment runbook,
backup/restore, health checks, error contract, governance.

---

## 15. Pilot fixtures created by this run (local dev database only)

| Organization | Public id | Consent | Samples | Purpose |
| --- | --- | --- | --- | --- |
| Pilot Demo Co | `org_a7b5c3472b231cf8bafa6395` | ON | 9 | web + Android golden path, dataset pipeline |
| Pilot Fail Co | `org_af029fbe14cffc67f358949e` | ON (granted mid-test) | 0 | consent matrix; erasure → FAILED preparation |
| Pilot Zero Co | `org_e24db3685965d5ba87c5067e` | OFF | 0 | zero-usage analytics case |

These exist only in the local development database. Their API keys were
generated locally, are not production credentials, and are not recorded
in this repository. They can be removed with
`make erase-org org=…` when the demo is finished.

## 16. Verdict

**The product works locally, end to end, proven rather than asserted:**
two clients on one backend, a complete data flywheel through to a
checksummed training artifact, honest consent enforcement, honest
failures, and a restore that has now been drilled three times.

**Recommended next step:** present this report → CTO approval → inspect
the existing Hostinger server → plan production deployment (14C).

**Not started and not to be started without approval:** production
deployment, DNS, certificates, Play Store publishing, fine-tuning, GPU
training.
