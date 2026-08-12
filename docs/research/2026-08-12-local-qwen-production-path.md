# Milestone 18 — Local Qwen Production-Path Integration: Close-Out

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — the candidate served real requests through the REAL customer pipeline, locally: gateway auth → registry routing → multi-slot runtime → transcript → usage ledger → consent-gated collection → correction |
| **Date** | 2026-08-12 (all verification this date, on the dev machine) |
| **The question this milestone had to answer** | *"Can Web and Android now use Qwen for Hindi through the SAME real IntelliAI backend pipeline locally?"* |
| **The answer, from verified evidence** | **Web: YES — verified in a real browser driving the real Studio against the real gateway** (screenshots committed). **Android: YES at the contract level — every branch of the shipped keyboard client's request/parse contract was exercised byte-faithfully against the live gateway and passed; no device/emulator exists on this machine, so no device run is claimed.** Production remains Hindi → Whisper, guard-tested. |

Labels: **[EVIDENCE]** committed drill/DB/screenshot record · **[FACT]** verified/recorded ·
**[TEST]** deterministic suite · **[LIMIT]** an honest boundary of what was verified.

---

## 1. Architecture before integration

Two disconnected worlds: the product path (clients → `/v1/audio/transcriptions` → `default_registry()` → hi→whisper-small) and the research path (eval harness → research manifest → qwen3 slot). The gateway had never resolved to the candidate; auth, metering, ledger, collection, and clients had never seen a Qwen request.

## 2. Integration points changed (the whole diff)

1. **`registry_profile` setting** (`production` default | `staging`): `staging` composes the live catalog PLUS the prepared proposal — `staging_registry()` in [proposals.py](../../apps/api/src/intelliai_api/registry/proposals.py). Refused outright under `INTELLIAI_ENV=prod` by a settings validator. One `if` in `main.py`, logged loudly.
2. Nothing else. No engine duplication, no second pipeline, no client changes, no contract changes. The runtime already hosted both slots (M16); the deployment declaration is configuration.

## 3. Local staging configuration [FACT]

Dev compose stack untouched and running throughout (api :8000 with the production-shaped catalog, runtime :8001 whisper-only). Beside it, natively: multi-slot runtime :8011 (`SLOTS=whisper,qwen3-asr`, pinned binaries verified at load) + staging gateway :8010 (`INTELLIAI_REGISTRY_PROFILE=staging`), sharing the same Postgres/Redis/MinIO. Tenant: `org_7a32e8fc0593806184421b62` ("M18 Staging Verification", **usage-origin `internal_qa`**, consent granted with a named reference). No secrets in any committed file.

## 4. Production-route protection [TEST]

- Default profile is `production` (pinned test).
- `staging` + `prod` env = startup refusal (pinned test).
- `INTELLIAI_REGISTRY_PROFILE` appears in no committed compose (pinned test).
- Live catalog still resolves hi→whisper-small; the candidate artifact is absent from it; the PENDING-approval sentinel can never appear live (pinned tests, from M17).

## 5–6. Web and Android verification

**Web [EVIDENCE — real Chromium, real Studio, real gateway]:** seeded the console's stored key, drove `/console/playground`: Hindi upload → **Devanagari transcript rendered in the Studio**, Developer Details showing request id `req_059a2188…` + sample id; correction saved through the Studio's own button ("Your correction helps improve IntelliAI STT."); contribution toggle off → dev pane reads **"not stored (contribution off)"**; 121 s upload → the Studio surfaces *"audio longer than 120 seconds is not supported by the requested model"*. **Zero internal names in the raw response pane and in the entire rendered page.** Screenshots: `evidence/web-01…04.png` + `web-summary.json`.

**Android [EVIDENCE at contract level; LIMIT: not a device run]:** no SDK/emulator/device exists on this machine, and no device run is claimed. Instead: byte-faithful replays of the shipped client's requests ([IntelliAIApiClient.kt](../../apps/keyboard-android/app/src/main/java/com/intelliai/keyboard/api/IntelliAIApiClient.kt) — same multipart fields and filename, same headers incl. `X-IntelliAI-Client: keyboard/1.0` and the contribution opt-out, same correction payload+media type) with responses checked against the client's exact `interpret()` contract. Results: Hindi dictation → SUCCESS with the Devanagari text the keyboard would insert + sample id from the header; contribution off → SUCCESS with no sample; auto mode → default route (visibly whisper: it mis-hears "मैप…हार्ड" as "मैद…हाद" — organic proof the two routes serve different models); missing/bad key → the exact `authentication_error` branch; 121 s → `invalid_request_error` whose message the keyboard surfaces verbatim; correction → 200. First replay attempt earned a 400 by omitting the JSON content-type the real client sets — the gateway correctly enforced it; recorded, fixed, re-run. Record: `android-contract-replay.json`. **A physical-device pass remains recommended before any customer-facing rollout.**

## 7. Authentication [EVIDENCE]

Missing key → 401; invalid key → 401; both with request ids, standard envelopes, zero leaks; valid key → 200s throughout. (Revoked/expired states are covered by the existing auth suite; the staging profile changes nothing in the auth plane — [TEST] `test_auth_is_unchanged_on_the_staging_profile`.)

## 8–9. Metering and usage ledger [EVIDENCE — direct DB inspection]

Session totals for the staging org: **22 `succeeded` events carrying 389.0 audio-seconds; 1 `failed` event carrying 0** (the outage request: audited, not billed). Per-drill checks: 10 events for exactly the 10 successful requests of the main drill (401s and the 121 s 400 recorded nothing); runtime logs attribute **7 requests to `qwen3-asr-0.6b` and 3 to `whisper-small`** — matching the request plan one-for-one. `/v1/usage/summary` reflects the requests and names only public models; no duplicates anywhere; no metering semantics changed.

## 10–12. Samples, contribution, correction [EVIDENCE]

17 samples collected under consent (Hindi via Qwen and English via whisper), `X-IntelliAI-Sample` returned, sample fetch clean of internal names. Contribution OFF: transcript returned, header absent, **no row created**, usage still metered. Correction (both via API and via the Studio): 200, `original_transcript` immutable, `current_transcript` corrected — verified in DB by the integration tests and live via the sample API. No Qwen-specific collection path exists.

## 13. verbose_json [EVIDENCE]

Hindi (Qwen): valid response, `text` present, **exactly one segment `{id,start,end,text}` spanning `[0, duration]`**, no fake word timestamps. English (whisper): same shape, 2 segments. The prepared product disclosure stands unchanged. Web Developer Details renders the raw JSON safely; the keyboard reads only `text` and is structurally indifferent.

## 14. 120-second behavior through the gateway [EVIDENCE]

119 s → 200 (1,144 chars); 120 s → 200 (1,158 chars); 121 s → **400, `param=file`, message names the limit and nothing internal**; not billed, not collected; Web shows the message in the Studio; the keyboard's parser surfaces it verbatim. Limit unchanged this milestone.

## 15. Failure/restart through the gateway [EVIDENCE]

llama-server child killed under live traffic: Hindi → **503 `service_unavailable_error` in 0.16 s** (bounded, no leak — and the keyboard's single bounded 503-retry policy matches this envelope); English kept serving from the same process; **no automatic Qwen→Whisper fallback fired** (integration test additionally pins: one runtime call, zero re-routes); supervisor recovered (~3 s on this box — fast enough that the readiness poll caught post-recovery state; the M17 drills hold the mid-outage readiness evidence: truth in 0.76 s); Hindi 200 after recovery; the failed request audited at amount 0; teardown left **0 orphans**.

## 16. The local end-to-end flow — verification matrix

| Test | Web | Android | Gateway | Qwen | Usage | Sample | Result |
|---|---|---|---|---|---|---|---|
| Hindi explicit | ✅ real browser | ✅ contract replay | ✅ | ✅ served | ✅ 1 event | ✅ created | **PASS** |
| Hindi hi-IN | — | — | ✅ | ✅ | ✅ | ✅ | **PASS** |
| Hindi Auto (undeclared) | — | ✅ replay | ✅ default route | — (whisper, by design) | ✅ | ✅ | **PASS** (declaration-first law) |
| English | — | — | ✅ | — (whisper) | ✅ | ✅ | **PASS** |
| Valid auth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| Missing/invalid auth | — | ✅ both branches | ✅ 401 ×2 | — | ✅ nothing billed | — | **PASS** |
| verbose_json | ✅ dev pane | n/a (text-only client) | ✅ | ✅ 1 segment | ✅ | ✅ | **PASS** |
| Contribution ON | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **PASS** |
| Contribution OFF | ✅ "not stored" | ✅ no sample | ✅ | ✅ | ✅ still billed | ✅ none | **PASS** |
| Correction | ✅ Studio save | ✅ 200 | ✅ | ✅ | — | ✅ original immutable | **PASS** |
| 119 s / 120 s | — | — | ✅ 200/200 | ✅ | ✅ billed | ✅ | **PASS** |
| >120 s | ✅ useful error | ✅ surfaced message | ✅ 400 | ✅ refused | ✅ not billed | ✅ none | **PASS** |
| Qwen unavailable | — | envelope matches retry policy | ✅ 503 in 0.16 s | ✅ isolated | ✅ failed@0 | — | **PASS** |
| Restart recovery | — | — | ✅ 200 after | ✅ | ✅ once | — | **PASS** |

Android column = byte-faithful client-contract replay, not a device run [LIMIT].

## 17. Evidence index

`research/experiments/18-local-product-path/`: `gateway-drills.json` · `gateway-failure-drill.json` · `android-contract-replay.json` · `evidence/web-01-hindi-qwen.png` · `web-02-correction-saved.png` · `web-03-contribution-off.png` · `web-04-121s-rejected.png` · `web-summary.json` · staging runtime/gateway logs. Drill scripts committed beside them.

## 18–19. Tests and CI

New [TEST]: 12 full-stack staging-path tests (routing ×4, verbose_json shape+leak, usage event+summary, sample, contribution off, correction immutability, 120 s pass-through with no billing/collection, unavailable-with-no-fallback, auth) + 3 profile guards + the compose guard. All suites green locally; CI green on the milestone commits.

## 20. Remaining blockers before Hostinger (unchanged from M17, plus one)

1. Vendored Linux runtime layer in the stt-runtime image (hash contract already enforced in code).
2. VPS re-validation with the committed scripts (all Linux numbers are WSL2).
3. **A real Android device/emulator pass** (this milestone's one verification gap).
4. Founder decisions: the switch, the segment disclosure, the promotion commit (replace the PENDING sentinel).

---

*Production untouched throughout: the dev stack kept serving hi→whisper beside the staging pair; the live catalog never changed; no customer traffic, no customer audio, no public API change. The staging profile is the promotion diff running under a flag production refuses — which is exactly what a local canary should be.*
