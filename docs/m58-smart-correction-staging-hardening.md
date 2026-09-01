# Milestone 58 — Smart Correction Staging Hardening + Founder Review

**Date:** 2026-09-02 · **Scope:** staging/local ONLY — production flag stays pinned OFF, Hostinger untouched, no production-readiness claims anywhere in this document.
**Hardware for every measured number:** RTX 5070 laptop (the M55 production-like reference), pinned correction server on :8802, staging stack via `local-prod.yml`.

The laws this milestone worked under, verbatim from the brief: raw transcript immutable; user edits highest priority; realtime STT outranks Smart Correction; no architecture redesign; no model replacement; no blind chunking; no partial correction; no validation bypass; no silent truncation.

---

## 1. Baseline reproduction (before any change)

M57's shipped state re-proven same-day before touching anything: 17 runtime unit tests + 5 gateway DB-integration tests green, live smoke through the authenticated gateway working, readiness `smart_correction: ready`.

## 2. Trust-gate hardening (unit-pinned, then hit live)

Three new mechanical rejections in `correction.py::_validate`, each with unit tests:

| Guard | Rejects | Why |
|---|---|---|
| `decimal_changed` | version 2.5 → 2.6 | decimals are entities, same as digit runs |
| `devanagari_digits_introduced` | एक → १ | the M56 entity-violation class; Devanagari digits already in the INPUT still pass through |
| `content_collapsed` | ≥20-word input answered with <30% of its words | the mirror of the runaway-length guard: a summarized/deduplicated transcript is DROPPED information, never served. Floor deliberately low so heavy filler/stutter removal (unit-pinned at ~46%) always passes |

The collapse gap was **discovered by our own measurement**: the first latency-ladder build repeated one seed sentence and the model deduplicated 500 words to ~36 — served with a 200. That can now never reach a user.

Gate refusals remain fail-open end to end: runtime logs `smart_correction_validation_failed` + reason → gateway friendly 503 → UI keeps the transcript untouched.

## 3. Concurrency cap (realtime outranks correction)

`smart_correction_max_concurrency` (default 1, `ge=1`), enforced with a non-blocking semaphore around the model call. The excess job gets a loud OVERLOADED refusal — "a correction is already running; try again in a moment" — never a queue that could starve realtime. Unit-pinned: refusal while the slot is held, normal service after release.

## 4. Hindi edge-case regression suite (new, deterministic, live)

`research/experiments/58-smart-correction-hardening/hi_regression.py` — 32 rows through the real authenticated gateway against the pinned temp-0 server. Eight categories: gender agreement, homographs, loanwords/Hinglish, names, numbers, email/URL, technical terms, already-correct keeps. Verdict law: `correct` rows must change AND keep every marker; `keep` rows must come back squash-identical; `guard` rows must keep every marker (meaning > grammar). The scorer normalizes nukta (फ़ == फ) so a legitimate spelling variant never scores as a failure.

**Prompt iteration ladder (each step rebuilt + rerun):**

| Version | Score | What changed |
|---|---|---|
| v1 (M57 prompt) | 25/32 | baseline: transliteration mangling of tech terms, der→डर, busy→बसी |
| v2 | 26/32 | tech-terms-stay-Latin + confusables rule — fixed those, but caused keep-row restyling (उसने→उन्होंने class) |
| v3 | 29/32 | exactly-unchanged/minimal-change/no-restyle promoted to rule 3 — all keeps recovered, nothing regressed |
| **v4 (frozen)** | **30/32** | बर्थडे/गिफ्ट added to the Roman-Hindi loanword examples — birthday→जन्मदिन translation fixed |

**Final 30/32.** The two remaining, honestly classified: `gA3` under-correction (model left बनाना unchanged — safe direction, a miss but never a corruption) and `fF1` the trust gate refusing a mangled email (safety working as designed — see §11). **Zero served meaning corruptions.**

## 5. English direction-of-action fix

The founder-matrix run caught the worst class live: "the file which i had sended you" came back as "the file that I **received from** you" — a semantic inversion no mechanical gate can see. One targeted EN prompt rule ("NEVER swap who did what to whom … it stays 'the file I sent you'") fixed the case; re-run confirmed, HI suite unaffected. This class is exactly why the feature is a *suggestion with the original preserved and a toggle* — the mitigation is structural, not just prompt-level.

## 6. Founder demo matrix (17 live cases)

`founder_demo_matrix.py` — 7 EN + 10 HI demo-facing cases, each recorded with input, AI suggestion, expectation, and mechanical verdict: **14/17 PASS** (`evidence/founder-demo-matrix.json`). All seven EN pass, including numbers/email/name preservation and already-correct-unchanged. The three non-passes, none a meaning corruption:
- `hi1` gender fix skipped on a Devanagari input (safe under-correction),
- `hi4` "cancel" rendered as रद्द — meaning identical, loanword policy says कैंसिल (style miss),
- `hi8` email inside Roman-Hindi → gate refusal, transcript kept (§11).

## 7. Latency ladder (live, varied non-repeating text)

| Words | EN | HI |
|---|---|---|
| 20 | 1.1 s | 1.3 s |
| 50 | 0.8 s | 2.4 s |
| 100 | 1.5 s | 4.8 s |
| 250 | 4.1 s | 11.6 s |
| 500 | 6.2 s | 17.8 s |

All under the 60 s stage timeout with full-length output (HI 500 came back at 73% length — condensation at max size, above the collapse floor, recorded honestly). A 650-word request is refused in **30 ms** with the actionable message "transcript too long for correction; try a shorter selection" — the refusal reaches the browser (400-message surfacing shipped in M58) and the UI appends "Your transcript is unchanged." No silent truncation anywhere.

## 8. Long-Hindi UX (real browser)

250-word Hindi transcript: **11.7 s** in Chromium through the ✨ Improve button — page stays responsive throughout (verified mid-flight), button shows "Improving…", success note lands, output 248 words. Matches the ladder within 0.1 s.

## 9. Realtime non-regression (the realistic case)

M57 proved the continuous-hammer worst case; M58 measured what a real user actually causes — exactly ONE correction fired mid-way through a live session, same-day idle references:

| Metric | EN idle | EN +1 correction | HI idle | HI +1 correction |
|---|---|---|---|---|
| partial gap p50 | 0.56 s | 0.58 s | 0.87 s | 0.95 s |
| partial gap p95 | 0.92 s | 1.00 s | 1.96 s | 2.50 s |
| finalization | 1.08 s | 0.96 s | 3.05 s | 3.38 s |

Cadence p50 stays under the 1 s target in every cell; the only visible cost is ~0.5 s of HI p95 during the correction's own 5 s window. The correction served normally (200, 4.2–5.0 s) alongside the live session. Realtime priority holds.

## 10. Browser E2E (EN + HI, real Chromium, fake mic)

Full flow green both languages: record → final → Improve → AI text differs → Original/AI toggle both directions → mid-flight user edit WINS (suggestion discarded with the explanatory note) → zero engine-name leaks in the page. New M58 drills:
- **Duplicate click:** two clicks in one event-loop turn fire exactly **1** network request (the first E2E draft measured 2 — a test artifact: Playwright waits for the disabled button to re-enable, i.e. a legitimate second correction; the synchronous double-dispatch proves the real guard).
- **Long-HI async** (§8).

## 11. The email-in-Hindi limitation (honest, by design)

Emails inside HINDI correction inputs get mangled by the model during transliteration; the trust gate catches it (`entity_dropped`), refuses, and the user keeps their transcript — observed at `fF1` and `hi8`. This is the safety design absorbing a capability miss: **no wrong email can ever be served**, but AI-improve effectively declines Hindi sentences containing emails. Recorded as a known limitation for the founder review, not hidden inside a pass rate.

## 12. Flag-off / fail-open / recovery drills (re-verified live)

- **Flag off** (staging overlay): readiness reports `disabled`; gateway answers the friendly 503 ("AI correction is not available right now. Your transcript is unaffected.") with zero model traffic and no engine names in the body; flag restored → `ready`.
- **Backend killed live:** correction server process killed → readiness flips to `degraded` within the 15 s probe window → relaunch via the pinned launcher → `ready`, live correction serves again.

## 13. Observability + alerts

`tools/ops/realtime_alerts.py` extended with three smart-correction signatures, thresholds chosen so the fail-open design working normally never pages anyone:
- `correction_gate` — ≥3 validation refusals in the window (a burst means drift, one is the gate doing its job),
- `correction_load` — ≥3 overload refusals in the window,
- `correction_down` — readiness reports `smart_correction=degraded` (`disabled` is configuration, never an alert).

All three **fire-proven**: forced-log drill (exit 1) and the `correction_down` alert fired LIVE during the §12 kill drill, went silent after recovery.

## 14. Security / privacy posture (unchanged, re-verified)

Auth-first at the gateway; transcripts never logged and never leave the machine (all inference local against the pinned :8802 server); no engine names on any public surface (E2E leak scan clean, error envelopes clean); keys live only outside the repo; production compose pins the flag `false` + empty URL inside the existing stt-runtime block (ops-guard tested); raw transcript immutable — `ai_correction_suggested` is its own append-only event and `current_transcript` moves only on a human save.

## 15. Verification roll-up + decision

- Runtime correction unit tests: **23** (17 M57 + 6 M58) green; gateway integration 5 green; full workspace suite green; ruff + mypy clean.
- Evidence in `research/experiments/58-smart-correction-hardening/evidence/`: `hi-regression-final.json` (30/32), `founder-demo-matrix.json` (14/17), `latency-ladder.json` (11/11), `realtime-single-correction.json`, `m58-browser-en.json` / `m58-browser-hi.json` (+ screenshot), `flag-off-reverify.json`, `alerts-drill.json`.
- Every failure across every suite is one of: safe under-correction, a style-policy miss with meaning intact, or the trust gate refusing to serve — **no meaning corruption was served in any M58 run**.

### Decision: **A — READY FOR FOUNDER REVIEW**

This is a staging-readiness statement only. It is **not** a production-readiness claim: production flags remain pinned off, no Hostinger/DNS change was made, and promotion remains a separate founder-gated decision that also depends on the standing M55 production-GPU-box condition.

**Open items for the founder review:** the email-in-Hindi limitation (§11), the loanword-vs-translation style policy (§6, hi4), and the Devanagari-input gender under-correction class (§4/§6) — all safe-direction, all documented.
