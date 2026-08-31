# Milestone 54 — Realtime STT Staging Hardening + Production Promotion Readiness

| | |
|---|---|
| **Status** | HARDENED on staging — decision **H. HINDI SERVICE ANOMALY BLOCKER** (a founder decision on the pre-existing BATCH anomaly + production-GPU verification stand between here and promotion; every realtime-specific gate passed or is honestly recorded) |
| **Date** | 2026-09-01 |
| **Scope** | Hardening the M53 staging feature + the evidence for a production promotion decision. **PRODUCTION ENABLED: NO. HOSTINGER: NO.** Flags stay OFF everywhere; batch semantics untouched. |
| **Evidence** | `research/experiments/54-realtime-stt-hardening/` |

## 1. M53 baseline — REPRODUCED, not remembered (MEASURED)

Same machine, same day, same clips, through the real gateway WS
(`baseline-*` evidence). The environment ran measurably slower than the
M53 recording — which is exactly why the spec forbade comparing against
memory:

| metric | EN (boss30 ×5 / long) | HI (real30s ×3 / long) |
|---|---|---|
| FPT | p50 1.24 s (1.20–2.08) | 0.75–1.06 s |
| partial p50 | 0.60–0.90 s | 0.80–1.51 s |
| partial p95 | 1.12–2.24 s | 1.35–2.82 s |
| finalization | p50 1.25 s, max 1.85 s (30 s); 1.7–2.7 s long | 3.3–4.0 s (30 s); 0.96–3.7 s long |
| stalls | one 16.8 s partial gap @10 min, DURING speech | none > 3.1 s |

## 2. Hardening objectives → what shipped (REPO-VERIFIED)

1. **Commit-landing at final** — `end` during an in-flight commit used
   to DISCARD it and re-decode the whole span (the measured EN ~4 s
   outlier class). The final now lands the commit, then decodes only
   the remainder.
2. **Finalization fast path** (`realtime_final_fast_path`, own
   rollback flag) — when only silence follows the last hot decode, that
   decode IS the final's raw text: zero re-decode. Measured: hello
   finalization 181 ms → **52–60 ms**; it fires whenever the user
   pauses before Stop (the common UX), and honestly does NOT fire when
   speech runs right up to the cut (clips in the battery).
3. **Repetition guard** — n-gram run detection (1–4-gram, run ≥6, or
   ≥4 when output is denser than 6 words/s) → retry once (the service
   path CAN be nondeterministic — §8) → trim the run to TWO occurrences
   → seam-collapse so trimmed spans can never re-assemble a loop across
   commits. Legitimate repetition ("हाँ हाँ, बिल्कुल", "नहीं नहीं, मैं
   नहीं गया") is unit-pinned untouchable; nothing is ever removed
   silently (`realtime_repetition_detected/_trimmed`, counters in the
   session summary). A deliberately loopy engine in tests produces
   partials AND finals with runs ≤ 2, never an empty text.
4. **Hindi first-partial fast start** — the first decode may run on a
   0.3 s window (`realtime_first_step_seconds`). MEASURED law: the
   Hindi backend yields words from 300 ms (client FPT 0.75–1.06 →
   **0.33–0.41 s**); whisper-small returns EMPTY on windows that short
   and English FPT WORSENED (+0.3–2.5 s) — so the early first step is
   Hindi-only, with the negative English result recorded.
5. **Observability** — per-session summary: hot queue-wait and decode
   p50/p95/max, commit count, repetition counters, fast-path flag,
   punctuation latency (§18/§29).
6. **Readiness `degraded`** — a configured Hindi backend that stops
   answering now reports `realtime: degraded` instead of a false ready
   (cached probe; unit-pinned).

## 3. Hindi finalization (Phase 2) — MEASURED

real30s (31.8 s, multi-speaker): 3.3–4.0 s baseline → **0.67–0.90 s**
hardened (n=3, commit-landing + remainder-only final decode). 2 min:
3.7 s → 0.64 s. 5 min: 1.4 s. 10 min: 6.5 s — decomposed by the new
telemetry: ~3.0 s of that is the HINDI PUNCTUATION stage on a
1,800-word transcript (§18) plus a full-window final decode when the
fast path misses. Proposed p95 ≤ 1 s: **met at ≤2 min, missed at 5–10
min — recorded, not relaxed silently.** One cold-server rerun measured
3.55 s (first decode after ~30 min idle) — warm-path numbers above are
the steady state.

## 4. Hindi long-session scheduling (Phase 5) — MEASURED

Queue-wait is NOT the bottleneck: hot-lane queue p95 ≤ 0.7 ms in every
session (skip-to-latest + one-in-flight-per-session works). Decode time
IS the cadence: partial p50 0.60–0.86 s across 30 s–10 min (baseline
0.80–1.51), p95 1.2–1.5 s (baseline 1.35–2.82). Proposed ≤1 s p50:
**met at every length on this battery**; p95 materially reduced.

**Window counterfactual (12 s window / 3 s margin), MEASURED and
rejected**: cadence unchanged (qwen's fixed per-call overhead
dominates small windows), Hindi finalization WORSE (1.7–2.9 s vs
0.67–0.90 s — more in-flight commits at Stop). The M53 defaults
(25 s / 5 s) stand on evidence.

## 5. Repetition guard in the wild (Phase 3/4)

Battery + drills: `repetition_detected: 0` across every session — the
M53 event did not recur under duration-scaled max_tokens; the guard is
the seatbelt, proven by unit law rather than by waiting for the crash.
Telemetry names are internal-only; no event or UI surface leaks them.

## 6. English finalization + FPT (Phases 7–8) — MEASURED

The outlier CLASS (commit-discard at final) is fixed by design;
finalization across 5 hardened boss30 runs: 1.13–1.33 s, no 4 s
outlier; long EN sessions 0.25–0.29 s (fast path). The remaining
~1.2 s at 30 s is the beam-5 remainder decode + punctuation — a known,
bounded cost. FPT breakdown: boss30 opens with ~0.07 s speech onset, so
onset is NOT the driver; the floor is min-step audio (0.5 s) + first
decode + wire. FPT p50 1.22 s (1.15–1.27) — the ≤1 s target stays
NARROWLY missed; whisper's occasional 2–12 s slow decode (§7 stalls)
is the tail driver, not scheduling.

**EN stalls**: the baseline 16.8 s partial gap reproduced smaller
(7.6–12.1 s max) — telemetry attributes them to INDIVIDUAL slow whisper
decodes (hot_decode max 2.2–12.0 s) on a laptop GPU shared with the
Hindi server, not to queueing. Alert §17 watches them; a production
GPU decision (§10) sizes them away.

## 7. Concurrency + fairness (Phases 9–10) — MEASURED

Policy (documented, by construction): ONE in-flight decode per session
through a FIFO single hot lane = round-robin; commits on their own
lane; 60 s lag → degraded event; 900 s cap → explicit error.

Mixed EN+HI short sessions: c=1 p50 0.55 s → c=2 p50 1.5–1.65 s →
c=4 p50 2.0–2.4 s (finals 8.6–14.7 s). **Loud-neighbor probe** (4
shorts + one EN 10-minute session): every short completed with a
correct final, zero degraded, zero errors, p50 within 0.2 s of each
other — one loud session starves nobody. The fairness law holds; the
ABSOLUTE latency at c≥4 is a capacity fact of one laptop GPU (§10),
not a fairness defect. c=8 was deliberately not run: c=4 already
exceeds target UX on this GPU and a laptop capacity number would be a
false production claim (the spec's own rule).

## 8. The Hindi batch service anomaly (Phases 15–16) — ANSWERED

Matrix (`service-anomaly.json`), 31.8 s + 60 s multi-speaker + short
single-speaker, n=5 per cell:

| path | real30s words | real60s words | short words |
|---|---|---|---|
| CPU batch service | **94/61/46/2/82 — UNSTABLE** | **61/92/180/196/159 — UNSTABLE** | 9×5 stable |
| CPU service, contended ×2 | 68/79 | 96/207 | 9/9 |
| **GPU direct (same model)** | **117/117/117 byte-stable** | **225/225/225 byte-stable** | 9/9/9 |

Answers: still reproducible **YES** (and now shown at 60 s too);
worsens under contention (latency 79–128 s) — consistent with the M52H
CPU-contention hypothesis; **GPU eliminates it**; the realtime path
does NOT share the affected path (different process, GPU backend —
realtime real30s words 107±1 across every run). Impact: this is an
EXISTING BATCH defect on CPU-contended boxes, predating realtime; the
promotion checklist carries it as an explicit founder decision — the
measured fix direction is GPU batch serving (or a dedicated
investigation milestone if CPU batch must stay).

## 9. Quality regression (Phases 6/17) — MEASURED, no material change

Frozen rulers (`unicode_generic@v2`, frozen `wer.py`), finals vs
GROUND TRUTH (HI) / the batch pipeline's own text (EN):

| clip | baseline WER | hardened WER | delta |
|---|---:|---:|---:|
| HI real30s | 16.81% | 16.81% | 0.0 |
| HI 2 min | 21.80% | 23.22% | +1.4 pt |
| HI 5 min | 27.85% | 26.05% | −1.8 pt |
| HI 10 min | 18.26% | 18.15% | −0.1 pt |
| EN boss30 ×5 | 2.08% each | 2.08% ×4, **0.0% ×1** | ≤0 |

CER moves the same way (10.6/14.0/15.1/8.9% hardened). VAD-aligned
commit seams (Phase 6) stay the law — word counts within 1 of
baseline everywhere; the ±1.4/−1.8 pt long-clip movement is seam
noise in both directions, not a trend. The 12 s-window counterfactual
(§4) also confirms the seam design: more seams bought nothing.

## 10. GPU production decision (Phases 11–13) — ANSWER: A, with a verification condition

**What GPU does production need for realtime EN+HI?** — **RTX
5070-class (8 GB) minimum, hosting BOTH engines on one card.**
MEASURED on the staging 5070 Laptop: whisper CT2 float16 + E3
llama-server resident together at **2.9–3.2 GiB VRAM, flat** across
the whole milestone (≈4.9 GiB headroom), util ≤78% under c=4 + loud
neighbor, zero OOM. VRAM is not the constraint; SERIAL DECODE
THROUGHPUT is: target UX holds to ~2 concurrent sessions per GPU;
capacity beyond that is horizontal (more runtime+GPU instances), never
VRAM oversubscription. The 2–12 s whisper decode stalls observed here
are laptop-thermal-class behavior; a server/desktop card of the same
generation is EXPECTED (not measured) to remove that tail — the
promotion milestone must re-run the c-ladder and stall check on the
actual production GPU before enablement. No cloud/VPS vendor is being
recommended here and no Hostinger GPU is assumed.

Startup (MEASURED): cold start → ready **12.4 s** (CT2 CUDA load +
ADR-0019 warm-up decode + backend probe + both punctuation stages);
warm restart 6.8 s; artifacts SHA-verified at start; request-time
downloads structurally impossible.

## 11. Batch regression (Phase 14) — ZERO (MEASURED)

`POST /v1/audio/transcriptions` double-runs on the hardened stack:
EN boss30 (punctuation_en path), HI short (Hindi stage), EN 2 min
(long-audio chunking) — **byte-identical sha256 on every pair**. The
long multi-speaker HI instability is the pre-existing §8 finding, not
a regression, and is scored there.

## 12. Punctuation (Phase 18) — MEASURED

Final-only, EXISTING stages, no realtime punctuation model. Latency by
telemetry: 15–95 ms typical, 170 ms @5 min, **3.0 s on a 1,800-word
10-minute Hindi transcript** — a newly measured superlinear cost that
dominates long-session finalization; named a hardening item for the
punctuation stage, NOT patched here. Partials stay raw; finals stay
punctuated (unit + browser pinned).

## 13. Provenance (Phase 19) — RE-VERIFIED

Partials ephemeral (repo-verified); raw → punctuated → corrected chain
live in-browser; AT MOST one consented sample per session
(sample_id on every contribution-on battery session, exactly one);
silence sessions store NOTHING (sample_id_present false, both
languages); abrupt disconnect persists nothing.

## 14. Lifecycle: stop/cancel/disconnect (Phase 20) — DRILLED

Start→Stop→Start again: distinct session ids, clean event sequences.
Abrupt transport abort mid-stream (no `end`, no close handshake): no
events leak, no sample stored, and the NEXT session works normally
(final + sample id) — the stack survives rude clients.

## 15. Backpressure, silence, short speech (Phases 21–23) — DRILLED

* **Flood 8×** (2 min in ~15 s), both languages: `session.degraded`
  emitted LOUDLY, final COMPLETE (239/321 words), sample stored,
  zero errors — nothing silently dropped; finalization 10–12.6 s while
  the backlog drains (bounded, honest).
* **Silence 5 s**: 0 partials, 0 decodes, empty final in 42–48 ms,
  **no sample stored** — the M52 silence law, still absolute.
* **Shorts** (hello/yes/no/okay/stop; हाँ/नहीं/ठीक है/रुको/हाँ सर):
  EN final median **41 ms**, HI **109 ms** (fast path); EN FPT median
  0.65 s; HI shorts FPT ~1.0–1.1 s on these clips (clip-dependent
  openings; real-speech HI clips measured 0.33–0.41 s).

## 16. Real browser E2E + mobile (Phases 24–25) — PASS

Fake-microphone Chromium (the true getUserMedia → AudioWorklet → wss
path) on the hardened stack: live text from 2.4–2.5 s, display
monotonic BOTH languages, Stop → punctuated final, **Share clipboard ==
final**, **correction saved through the real endpoint**, zero
engine-name leaks in the DOM. 390 px / 820 px / desktop: button
visible, no horizontal scroll (screenshots in evidence).

## 17. Observability + alerts (Phases 29–30)

Internal metrics (logs; never public API): sessions started/completed/
degraded, first-partial/finalization (client-measured in batteries;
server session summaries), hot queue-wait + decode p50/p95/max, commit
count, `realtime_qwen_repetition_detected`/retries/trimmed words, GPU
VRAM/util (sampled), session duration/audio seconds.

Alert thresholds (PROPOSED, staging-calibrated): >5% sessions degraded
per hour; FPT p95 > 3 s sustained; finalization p95 > 5 s sustained;
any `repetition_trimmed`; hot_decode max > 15 s (the stall signature);
GPU OOM or runtime crash (readiness flips non-ready); readiness
`degraded` (Hindi backend down) > 1 min; session > 890 s (cap
approach). Normal user cancellation (disconnect) alerts NOTHING.

## 18. Rollback (Phase 31) — DRILLED LIVE, three legs

ON→works (the whole milestone). **Flag off** (gateway URL emptied, api
restarted): WS handshake refused PRE-ACCEPT (HTTP 403 rejection; unit
tests pin close 4404), batch answered normally, compose file restored
byte-identical. **GPU runtime down** (process killed): session refused
cleanly, batch unaffected. **Restore**: runtime relaunched → smoke
session FPT 0.87 s, final 53 ms, sample stored. The runtime flag
independently reports `disabled`, and a dead Hindi backend reports
`degraded` (M54, unit-pinned).

## 19. Production config (Phases 26–27) — PREPARED, NOT ENABLED

`infra/compose/prod-realtime.yml` is the reviewed ON-switch overlay —
referenced by NO deploy command; a new ops guard pins that it stays
un-wired, that prod.yml pins the URL empty, and that no committed
compose enables the runtime flag. Readiness now answers
`disabled/ready/degraded` without model names, hashes, or paths.

## 20. Promotion checklist (Phase 32)

Thirteen items in `promotion-checklist.json`: 1–3, 5, 7–9, 11–13
**PASS/DONE**; open before promotion: **(4)** re-run the c-ladder on
the production GPU, **(6)** wire the §17 thresholds into the ops alarm
channel, **(10)** the founder decision on the Hindi batch anomaly —
plus the product call on the recorded latency misses (EN FPT ~1.2 s;
HI 5–10 min finalization).

## 21. Scorecard (Phase 33)

| Metric | English | Hindi |
|---|---:|---:|
| FPT | p50 1.22 s (1.15–1.27) | 0.33–0.41 s (real speech) |
| Partial p50 | 0.51–0.59 s | 0.60–0.86 s |
| Partial p95 | 0.55–1.62 s (stall tail §6) | 1.23–1.46 s |
| Finalization p50 | 1.23 s (30 s) / 0.25–0.29 s (long) | 0.89 s (30 s) / 0.64–1.4 s (2–5 min) |
| Finalization worst | 1.33 s | 6.5 s (10 min; 3.0 s punctuation) |
| WER | 2.08% vs batch (one run 0.0%) | 16.8/23.2/26.1/18.2% vs truth |
| CER | — (word ruler) | 10.6/14.0/15.1/8.9% |
| Long-session WER delta | 0.0 | +0.0/+1.4/−1.8/−0.1 pt |
| Repetition | n/a | 0 events; guard unit-proven |
| Stability | monotonic ✓ | monotonic ✓, words 107±1 |
| VRAM | 2.9–3.2 GiB (both engines, flat) | shared |
| RAM | runtime RSS ~1.29 GiB | shared |
| c=1 / c=2 / c=4 | p50 0.55 / 1.6 / 2.2 s | shared lane |

Batch regression **ZERO** · browser E2E **PASS** (+mobile) ·
punctuation final-only **PASS** · provenance **PASS** · Share **PASS**
· Correction **PASS** · rollback **PASS** · security **PASS** ·
privacy **PASS**.

## 22. Decision (Phase 34)

**H. HINDI SERVICE ANOMALY BLOCKER** — chosen honestly over A: every
realtime-specific requirement passed, is bounded, or is recorded
plainly, but promotion cannot proceed until the founder disposes of
the pre-existing Hindi BATCH instability (fix via GPU serving / accept
+ document / dedicated investigation) — promoting a GPU realtime
Hindi while batch Hindi is unstable on the same production box is a
product-coherence decision only the founder can make. NOT chosen: D
(latency) because the p50 targets are met and the misses are recorded
with causes and owners; E/F (capacity/fairness) because fairness holds
and capacity is documented with an explicit production-GPU
verification step.

## 23. Next milestone (Phase 35)

Exactly ONE blocking milestone proposed: **M55 — Production GPU
serving readiness**: provision/verify the production GPU box; re-run
the realtime c-ladder + stall check there; serve HINDI BATCH through
the same GPU path (the measured fix for §8 — one decision resolves
checklist items 4, 6 via alarm wiring, and 10); then the separate
founder-gated **realtime production promotion** milestone flips the
prepared overlay. **PRODUCTION ENABLED: NO. HOSTINGER: NO.**
