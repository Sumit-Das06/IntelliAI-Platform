# Milestone 40 — Hindi TTS: Final Staging Validation + Production Promotion Readiness

| | |
|---|---|
| **Status** | COMPLETE — every staging/product gate re-proven on fresh replicate runs and live drills; the exact production promotion is prepared, reviewed, and reversible; production remains untouched |
| **Date** | 2026-08-24 |
| **Scope** | Validate the M39 implementation end to end on the production-shaped local stack (fresh replicate evidence, live drills), and prepare the EXACT future production promotion + rollback. Hostinger is unavailable — nothing deploys, production stays untouched. |
| **Evidence** | `research/experiments/40-hindi-tts-staging-validation/evidence/` |

    HINDI TTS STAGING: YES
    HINDI QUALITY GATE: PASS       (clean RT-WER 0.0620 / 0.0547 <= 0.08, replicated)
    LONG TEXT: PASS                (no truncation at any ladder length, both voices)
    STREAMING: PASS                (TTFA length-independent 0.77-1.5 s, 23.3x at 1897c)
    ENGLISH REGRESSION: PASS       (M35 battery 23/23; suites green)
    WEB E2E: PASS                  (both voices through the HTTPS edge)
    PRODUCTION PROMOTED: NO
    HOSTINGER DEPLOYED: NO

    FINAL CLASSIFICATION: A — READY FOR PRODUCTION PROMOTION

## 1. Final staging audit (Phase 1) — VERIFIED FROM CODE + LIVE RUNTIME

Every row checked against running containers and current source, never
documentation alone:

| Surface | Verdict | Evidence |
|---|---|---|
| Model artifact (kokoro-82m v2, 6 files SHA-pinned) | READY | boot re-hash; `/info` artifact identity; smoke §2 |
| Hindi voice packs (hf_alpha, hm_psi) | READY | artifact v2 spec pins; served voices list |
| Hindi G2P (espeak exec boundary, pin 1.5x) | READY | 12/12 parity fixtures; composition-time refusal tests |
| Hindi normalization v1 | READY | 22-test suite + live internals table (§5) |
| Danda chunking | READY | splitter pins + chunk-plan evidence + ladder audio (§4) |
| Streaming (M36 path) | READY | TTFA matrix (§7); byte-equality law CI-pinned |
| Playback (M37 session) | READY | zero-diff; structural pins green; protocol (§10) |
| Billing (characters-only) | READY | LIVE ledger drill (§9) |
| Auth / rate limiting | READY | unchanged M35 path; 401 row in EN battery |
| Error handling (customer-safe) | READY | live leak sweep (§11): engine token as voice → `voice_not_found` |
| Health / readiness | READY | gateway ready checks green; store refuses missing/corrupt files (readiness stays down) |
| Registry (staging proposal, prod refusal) | READY | 16-test proposal suite; live `/v1/audio/voices` per profile |
| Voices endpoint | READY | languages `["hi"]`/`["en"]` exact; zero engine tokens |
| Web UI (catalog-driven dropdown) | READY | page markers via HTTPS edge; console pins |
| Documentation | READY | M39/M40 docs; runbook gains the prepared promotion (§13) |
| Security (argv law, timeouts, no downloads) | READY | hostile-input pins; subprocess bounded; startup-only fetch |

No FAIL, no UNKNOWN rows remain.

## 2. What M40 adds beyond M39

M39 shipped and measured the implementation (same day, same stack).
M40's replicate battery re-proves every gate on fresh runs, and adds
what promotion readiness actually requires: a LIVE billing drill on
real ledger rows, a live leak sweep, the staging rollback drill, the
prepared production promotion + pinned rollback target, and the
deployment-readiness pass (seeding).

## 3. Hindi quality — REPLICATE, real gateway, E3 judge (Phase 2)

Frozen M38 set (61 cases), M38 methodology unchanged:

| Voice | clean slice (gate ≤ 0.08) | all-hi | M32-comparable | mixed CER | ladder |
|---|---|---|---|---|---|
| hindi-female (M40) | **0.0620 / 0.0225** | 0.2759 / 0.2272 | 0.1576 / 0.1121 | 0.6018 | 0.0458 / 0.0194 |
| hindi-male (M40) | **0.0547 / 0.0204** | 0.2616 / 0.2261 | 0.1382 / 0.1098 | 0.6211 | 0.0260 / 0.0120 |
| (M39, same stack) | 0.0707 · 0.0547 | 0.2817 · 0.2666 | 0.1686 · 0.1382 | 0.6018 · 0.6137 | 0.0482 · 0.0288 |

**GATE PASS, replicated**: both voices land at or under their M39
numbers (replicate noise band ≤ 0.009 WER), zero synthesis failures on
all 122 gateway runs. The gate value is stable, not a lucky draw.

Category detail (numbers/dates/currency/phones): high edit-distance BY
CONSTRUCTION — correct verbalization punished against written forms;
per-row transcripts in the evidence carry the honest picture, and the
normalization table (§5) plus the Web E2E round-trip (§12) show the
speech itself is right. Mixed rows stay script-gap-dominated.

## 4. Long text (Phase 3) — HARD GATE

Chunk plans from the EXACT runtime splitter + measured audio through
the gateway (`m40-chunk-plan.json`, bench rows):

| chars | chunks (whole/stream) | audio F (M40) | audio M (M40) | RT-WER F/M |
|---|---|---|---|---|
| 118 | 1 / 2 | 11.0 s | 11.7 s | 0.042 / 0.000 |
| 298 | 1 / 2 | 23.1 s | 23.5 s | 0.068 / 0.051 |
| 683 | 3 / 4 | 55.7 s | 58.6 s | 0.022 / 0.014 |
| 1189 | 5 / 6 | 95.6 s | 100.2 s | 0.033 / 0.016 |
| 1897 | 8 / 8 | 149.6 s | 155.7 s | 0.067 / 0.056 |

No text lost at the plan level (byte-compare pinned), no silent
truncation at the audio level — duration scales linearly with text
(~12.7 chars/s) and every ladder row round-trips at ≤ 0.068 RT-WER,
so the CONTENT is complete, not merely long. Audio durations
reproduce M39's byte-for-byte (deterministic duration; waveform bytes
are not deterministic, the M33 fact). The 2000-char law refuses 2001
chars honestly (billing drill §9). Stream chunk plans complete with
no duplicates (the CI byte-equality law: concatenated stream ==
whole body).

## 5. Normalization battery (Phase 4) — original → internal → speech

`m40-normalization-internals.json` (the exact runtime function) +
round-trip through the judge:

| Original | Internal speech text | Round-trip proof |
|---|---|---|
| इसकी कीमत ₹12,500 है। | इसकी कीमत 12500 रुपये है। | E3 hears Hindi number words + रुपये (§12; M40 battery rows) |
| कृपया मुझे 25% छूट दें। | … 25 प्रतिशत … | प्रतिशत spoken |
| आपकी नियुक्ति 12/08/2026 को है। | … 12 अगस्त 2026 … | month name spoken |
| मेरा नंबर 9876543210 है। | … नौ आठ सात छह पाँच, चार तीन दो एक शून्य … | digit-by-digit |
| कक्षा में ४५ विद्यार्थी हैं। | … 45 … | Hindi forty-five |
| डिलीवरी 10:30 AM तक पहुँचेगी। | … सुबह 10 बजकर 30 मिनट … | daypart + time |
| मेरा policy number 12345 है। | (unchanged) | espeak's Hindi number reading |

All rows idempotent, zero English words (pinned), and the LIVE ledger
drill (§9) proves the ORIGINAL text is the billing fact — the internal
form never leaks to the API or the bill.

## 6. Hinglish battery (Phase 5)

The four spec lines re-judged in the M40 replicate: English tokens
preserved, Hindi tokens preserved, no unexpected transliteration —
exemplar: E3 heard *"इंटेली एआई का नया वर्शन आज रिलीज हुआ है।"*.
Romanized Hinglish remains UNSUPPORTED (documented limitation,
unchanged scope).

## 7. Streaming performance (Phase 6) — MEASURED LOCAL/STAGING

Best-of-3 by TTFA, M36 definitions, replicate run (machine under its
normal working load — slightly above the M39 pass, same shape):

| Text | whole TTFA (F / M) | **stream TTFA (F / M)** | speedup (F) |
|---|---|---|---|
| short question (25c) | 778 / 783 ms | 768 / 782 ms | 1.0× |
| 118 chars | 2 185 / 2 548 ms | **884 / 871 ms** | 2.5× |
| 298 chars | 5 137 / 5 440 ms | **1 002 / 1 010 ms** | 5.1× |
| 683 chars | 12 639 / 13 436 ms | **1 508 / 1 521 ms** | 8.4× |
| 1189 chars | 21 886 / 23 372 ms | **1 459 / 1 488 ms** | 15.0× |
| 1897 chars | 34 749 / 36 187 ms | **1 491 / 1 523 ms** | **23.3×** |

Stream TTFA stays length-independent (0.77-1.5 s across 25→1897
chars) on both voices; both replicate passes (M39: 0.48-1.6 s; M40:
0.77-1.5 s) band together as this machine's honest range. RTF per
bench median 0.25-0.26 under working load (0.18 solo in M39).
MEASURED LOCAL/STAGING — never an SLA.

## 8. Concurrency (Phase 7) — MEASURED LOCAL/STAGING

Streamed ladder c=1/2/4/8 (298-char text, hindi-female): all ok,
**zero errors**; TTFA p50 1.01 / 3.53 / 8.22 / 15.48 s; wall 5.98 /
9.5 / 16.9 / 33.85 s — honest queueing under the SAME 2+8 pool as
English (M39 replicate agreed: 0.68/3.87/8.74/18.93 s). No
Hindi-specific pool; container RSS measured **2.56 GiB** after the
full day's battery (the M32/M35 2.4-2.6 GiB band — one loaded model;
Hindi added ~1 MB of voice packs, no second engine); espeak
subprocesses are per-call and timeout-bounded — the container held
exactly ONE long-lived process (uvicorn) when checked after the
ladder, zero espeak orphans. Never VPS capacity claims.

## 9. Billing (Phase 8) — LIVE LEDGER DRILL

A fresh internal_qa drill org; real requests; real Postgres rows
(`m40-billing-drill.json`):

| Case | Ledger row |
|---|---|
| 57-char Hindi text: speed 0.75 / 1.0 / 1.25, both voices, whole-body AND full stream | **six rows, every one `characters=57`, billable, language=hi** |
| Mid-stream CLIENT ABORT after 65,573 delivered bytes (342-char text) | **billable, `characters=342`** — the F1 delivered-work law on the ORIGINAL text |
| Invalid voice / empty input / 2001 chars | **zero rows written** — refused before any plane crossing |

Speed, voice, and transport never change the bill; `audio_seconds`
rides lineage only. Exactly the M35/M36 semantics.

## 10. Playback / UX (Phase 9)

PlaybackSession is byte-unchanged since M37; every structural pin
(states, session identity, replay-only-on-COMPLETED, teardown-before-
src, observable, suspend/resume) is green in the api suite, for Hindi
exactly as for English — the session layer never knows the language.
The founder click-through protocol (Generate → Pause/Resume/Stop →
Generate twice fast → Replay → Download, watching
`__iaiPlayback.audibleSources ≤ 1`) stands as the human half; the M39
Web E2E plus §12 cover the scripted half.

## 11. Security / leak sweep (Phase 12) — LIVE

Live sweep over voices listing, models listing, error responses, and
health (`m40-leak-sweep`): **zero** occurrences of hf_alpha / hm_psi /
kokoro / espeak / misaki / model paths / hashes. Requesting the engine
token `hf_alpha` AS a voice answers a plain `voice_not_found` — engine
vocabulary is not addressable even in staging. Subprocess laws
re-pinned (constant argv, stdin transport, hostile-input tests,
timeout); artifacts hash-verified at boot; no request-time downloads.

## 12. Web E2E (Phase 15) — HTTPS edge, BOTH voices

Through Caddy (`https://localhost`, production-shaped stack):

- **hindi-female** (exclamation + IntelliAI + Hinglish + 10:30 AM):
  TTFB 1.25 s, total 2.78 s for 10.6 s of audio; E3 heard *"नमस्ते
  इंटेली ए आई में आपका स्वागत है। मुझे ऑफिस जाना है, प्लीज़ मुझे कल
  सुबह दस बज कर तीस मिनट पर कॉल करना।"* — every English token spoken,
  the AM/PM rule audible.
- **hindi-male** (question + ₹2,750 + 15/09/2026 + IntelliAI): TTFB
  2.70 s, total 3.56 s for 14.1 s of audio; currency and slash-date
  verbalized in Hindi, brand spoken (one judge slip on "order",
  recorded honestly — the battery's Hinglish rows measure token
  preservation cleanly).
- Page and voices endpoint via the edge: all M39/M40 markers, zero
  engine-token leaks. Evidence: `m40-web-e2e.json`. The founder
  click-through protocol (§10) remains the human half.

## 13. Production promotion — PREPARED, NOT ACTIVATED (Phase 16)

The E3/M26 shape, restated in `registry/proposals.py` and the runbook
(docs/ops/model-rollout.md "PREPARED promotion"): ONE reviewed commit —
catalog gains `HINDI_TTS_VOICES`, the hi refusal route becomes
`HINDI_TTS_ROUTE`, the `APPROVAL_PENDING` sentinel becomes the founder
decision reference, and the refusal guards flip to serving pins in the
same commit. No artifact re-admission, no image change, no client
change. **Two-knob law**: the catalog promotion is separate from the
TTS production-launch gate (prod.yml ships no TTS at all), so even a
landed promotion exposes nothing until the launch gate opens.

## 14. Rollback (Phase 17)

- **Future production rollback**: `git revert` of the promotion
  commit. `ROLLBACK_HINDI_TTS_ROUTE` restates today's live refusal
  verbatim and a test pins it EQUAL to the live route while the
  proposal is pending — the revert target cannot drift unreviewed.
- **Staging rollback — DRILLED LIVE** (`m40-rollback-drill.json`):
  one env line (`INTELLIAI_TTS_HINDI_G2P=off`) and a container
  recreate → the runtime serves ONLY the four English voices, the
  gateway answers a Hindi request with a clean customer-safe 400,
  English keeps serving; restore → six voices, Hindi 200 again.
  ~40 s per direction. Production rollback was NOT run — production
  was never touched.

## 15. Deployment readiness (Phase 18)

- `make seed-models` now also copies `models/kokoro-82m/v2/` into the
  model volume when present (the punctuation-artifact conditional
  pattern) — an offline box seeds the Hindi packs exactly like E3;
  boxes with egress keep the boot-download + re-hash path. The local
  seed source now carries v2 (both Hindi packs).
- prod.yml remains TTS-free; no staging value can leak (profile
  refused under `INTELLIAI_ENV=prod`, compose pins test-enforced; the
  base stack carries no `INTELLIAI_REGISTRY_PROFILE` — M18 law).
- Env examples: dev/staging TTS knobs live in the compose files
  themselves (reviewed configuration, not .env), so no example
  changes were required.
- Production smoke continues to exclude Hindi automatically: the
  smoke's Hindi section keys off the deployment's own declared
  posture, both directions.

## 16. Human voice gate (Phase 20)

Recorded per the M40 spec: **voice selection = accepted for product
staging** — hindi-female=hf_alpha, hindi-male=hm_psi (founder
decision, M39/M40 specs; selection not reopened). No formal MOS /
naturalness scores exist: the M38 audition pack remains available and
UNSCORED, and nothing here claims human scoring that never happened.

## 17. Tests (Phase 21)

api **671** · tts-runtime **170** (+1 skip) · evaluation **677** ·
runtime-core **46** · runtime-contract **46** — all green; ruff +
format clean; **mypy strict: 0 issues in 342 files**; `make
tts-smoke` green post-restore (floor 0.4.0, posture, six voices,
both-language gateway synthesis). No guard weakened; three tests
ADDED (promotion preparation pins).

## 18. Limitations / next step

- Romanized Hinglish unsupported (unchanged; own future milestone).
- Bare clock times (no AM/PM) pass through normalization v1.
- Naturalness = C-grade upstream ceiling until E-TTS-1; audition pack
  UNSCORED.
- VPS numbers remain UNKNOWN (M31 law) until Hostinger exists.
- **Next step**: the founder's production promotion decision (the
  prepared one-commit diff, §13) and, independently, the TTS
  production-launch gate (prod overlay + Hostinger + DNS) when VPS
  access arrives. E-TTS-1 stays the owned-voice ML milestone.
