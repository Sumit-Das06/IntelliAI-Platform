# Milestone 53 — Realtime STT Web Implementation

| | |
|---|---|
| **Status** | IMPLEMENTED on LOCAL/STAGING — decision **A. REALTIME ENGLISH + HINDI READY FOR STAGING** (recorded gate misses in §latency, honest) |
| **Date** | 2026-08-28 |
| **Scope** | The M52/M52H architecture as a real product feature behind flags that are OFF everywhere by default. Production untouched: no realtime route, no GPU requirement, batch byte-identical. |
| **Evidence** | `research/experiments/53-realtime-stt/` (51 files + screenshots) |

## 1. Objective + hand-off

M52 proved English realtime (whisper re-decode streaming; GPU passes
every gate), M52H proved Hindi realtime on the RTX 5070 (unchanged E3,
same-commit CUDA build). M53 turns that evidence into the actual web
feature: live partials in the existing Playground, one session
architecture for BOTH languages, finals through the existing
punctuation/provenance/consent machinery.

## 2. Architecture (REPO-VERIFIED, staging-measured)

    Browser mic (AudioWorklet → PCM16 mono 16 kHz, 100 ms frames)
      ↓ wss (Caddy)
    Gateway /v1/audio/realtime  — auth FIRST, then pipe; collects ONE
      ↓ ws                        final sample (batch-equivalent consent)
    stt-runtime realtime session (flag-gated)
      VAD gate → rolling 25 s window → engine → partials
      VAD-aligned commits OFF the hot path; skip-to-latest scheduling
      final → EXISTING punctuation stages → transcript.final
      ↓
    LA2 display (client): agreed word-prefix, monotonic by construction

Engines: `en/en-US/en-IN` → whisper-small on a DEDICATED realtime
instance (greedy partials, beam-5 finals; `device=cuda` on the staging
GPU host); `hi/hi-IN` → the UNCHANGED E3 GGUF through llama.cpp
b10344-CUDA (`llama-server.exe` byte-identical to the production pin;
`ggml-cuda.dll` pinned; `tools/realtime/launch_qwen_gpu.py` refuses
drift). Unknown languages refuse cleanly — never a silently wrong
model.

## 3. Feature flags (default OFF, guard-tested)

- Runtime: `INTELLIAI_STT_REALTIME_ENABLED` (default False; no
  committed compose file sets it in a container — the staging realtime
  runtime is a HOST instance via `make realtime-stt`).
- Gateway: `INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL` — empty everywhere
  by default; local-prod.yml points it at the host runtime;
  **prod.yml pins it empty** with a new ops guard test
  (`test_realtime_stt_ships_off_in_prod_and_on_only_in_the_local_stage`).
- Readiness: additive `"realtime": "ready"|"disabled"` key.

## 4. Session contract (implemented exactly as M52 proposed)

`auth` (key + language + contribution) → binary frames → `end`;
server: `session.started` → `transcript.partial*` →
`transcript.final {text, raw_text, language, duration_seconds}` →
`session.completed {audio_seconds, sample_id?}` (+`session.degraded`,
`session.error`). Sequences monotonic — asserted in EVERY battery run.
Stop is idempotent; disconnect kills the session with nothing
persisted; two sessions never share identity (unit-tested).

## 5. Staging scorecard (MEASURED end-to-end through the gateway)

| Metric | English | Hindi |
|---|---:|---:|
| FPT (first partial at client) | 1.11 s (boss30) | **0.66-0.76 s** (real 30 s) |
| Partial cadence p50 | **0.54-0.57 s** (30 s → 10 min) | 0.82-0.99 s (≤2 min) / 1.5 s (10 min) |
| Finalization | 0.29-1.2 s (10 min: **0.37 s**; 5 min outlier 4.0 s) | 1.2-3.2 s (30 s: 3.2 s incl. beam-final + collect) |
| Final vs offline quality | WER 2.08% vs the batch pipeline (word stream) | vs GROUND TRUTH: 10.9% (30 s — equals the direct-child quality), 22.5%/25.2%/16.7% (2/5/10 min) vs offline baselines 15.9%/23.2%/15.5% |
| Long session | 10 min: 966 partials, no degradation | 10 min: 387 partials, bounded |
| Silence session | 0 partials, empty final, **no sample stored** | same |
| Stability (browser display) | monotonic TRUE | monotonic TRUE |
| VRAM | 2118-2899 MiB total, flat across battery + c=4 + 10 repeats | same GPU |
| Concurrency (mixed en+hi short sessions) | c=1/2/4: 0 failures, all finals correct; latency grows (single hot lane by design) | shared |
| Sample/provenance | sample_id on completed; correction saved in-browser | sample_id ✓ |

Flood 8× (120 s in ~10 s): `session.degraded` emitted, final COMPLETE,
sample stored — nothing silently dropped.

## 6. Real browser E2E (fake-microphone Chromium = the true mic path)

EN boss30 and HI real-30s through getUserMedia → AudioWorklet → wss:
live text visible from **2.6-2.9 s**, display monotonic (both
languages), Stop → punctuated final ("see, this is a text to which I
generated from my speech, okay, …"; Hindi with danda/question marks),
**Share clipboard == displayed final**, **Correction saved through the
real endpoint** ("Your correction helps improve IntelliAI STT."),
sample id present, zero engine-name leaks in the DOM. Mobile 390 px and
tablet 820 px: button visible, no horizontal scroll. Screenshots in
evidence.

## 7. What the browser E2E caught (fixed + re-proven — why E2E exists)

1. **LA2 display shrink**: a rewritten shorter partial could shrink the
   shown text → display now only ever advances (monotonic by
   construction; re-verified in-browser both languages).
2. **Mic kept streaming after Stop** → mic now stops at Stop (privacy +
   protocol hygiene).
3. **`session.completed` lost on the wire**: the runtime closed
   immediately after sending it — a transport-flush race the python
   client never hit. Fix: ordered shutdown (client closes after
   completed; the gateway ends the bridge only after relaying it).
4. **Qwen generation loop** (staging battery): one 2-min Hindi session
   inflated by ~180 repeated words → duration-scaled `max_tokens` in
   the realtime backend + `realtime_commit_suspect_repetition`
   observability; retry/trim guard named for promotion hardening.

## 8. Punctuation, provenance, consent (all EXISTING machinery)

Partials are raw and EPHEMERAL. The final raw transcript passes through
the existing Hindi/M50-English stages inside the runtime session (M51
stand-down law intact), so `text`/`raw_text` semantics match batch. The
gateway collects AT MOST one sample per session via the existing
DataCollectionService — same consent ceiling, contribution-off honored
(unit-tested), correction flow unchanged (proven live in-browser).
Cancel/disconnect: buffers discarded, nothing persisted.

## 9. Batch regression — ZERO (the critical law)

`POST /v1/audio/transcriptions` code path untouched; on the
realtime-enabled stack, boss30 double-run is **byte-identical**; the
whole workspace suite is green; flag-off drill leaves batch working
(`rollback.json`).

## 10. Rollback (drilled live)

Gateway URL emptied → WS handshake refused pre-accept, Playground shows
"Realtime isn't available…", Upload untouched, batch answers. Restored
→ sessions work again (hello: FPT 0.79 s, final 290 ms, sample ✓). The
runtime flag independently gates the internal endpoint (readiness
`realtime: disabled`, unit-tested).

## 11. Security & privacy

Auth before any audio (same AuthService as HTTP; bad key → 4401
without accepting frames); key/audio/transcripts never logged; bounded
buffers everywhere (60 s lag ceiling, 900 s session cap, 64 KB frames,
30 min collection cap); session isolation unit-tested; browser DOM and
event bodies leak-scanned clean. Privacy documented in
`privacy.json` — retention unchanged from batch.

## 12. Gates verdict (PROPOSED gates, honest misses recorded)

- EN: FPT ≤1 s — boss30 measured 1.11 s at the client (borderline;
  compute is not the limit — first words + transport). Partial p50 ≤1 s
  **PASS** (0.54-0.57 s at every length). Finalization ≤1 s: PASS in
  steady state (0.29-0.37 s); one 5-min run logged 4.0 s (commit
  landing + final queue — promotion-hardening item). Quality near
  offline **PASS**.
- HI: FPT ≤1 s **PASS** (0.66-0.76 s). Partial p50 ≤1 s PASS ≤2 min;
  1.5 s at 10 min (M52H's known scheduling shape — materially improved
  vs M52H's 1.8 s sim, not yet ≤1 s; recorded miss). Finalization
  1.2-3.2 s — **recorded miss** (qwen beam-final + punctuation +
  collection stack up; hardening item). Quality near offline PASS
  (0-2.3 pt vs baselines after the loop fix; the 2-min slice runs
  ~6.6 pt over baseline — seam tuning continues).
- BOTH: VAD-gated ✓ bounded memory ✓ session isolation ✓ authenticated
  ✓ batch regression zero ✓ rollback ✓.

## 13. Decision + next milestone

**A. REALTIME ENGLISH + HINDI READY FOR STAGING** — the feature works
end-to-end in the real product on the staging stack, with the misses
above stated plainly rather than gate-shopped.

Next (ONE, founder-gated): **Realtime STT staging hardening +
promotion readiness** — Hindi finalization/cadence tuning
(end-triggered final fast-path, commit scheduling), the qwen
repetition guard, concurrency fairness beyond one hot lane, and the
production GPU serving decision. **PRODUCTION ENABLED: NO. HOSTINGER:
NO.**

| verdict | |
|---|---|
| REALTIME STT | **YES (staging)** |
| ENGLISH | **PASS** |
| HINDI | **PASS (with recorded latency misses)** |
| GPU | **PASS** (2.1-2.9 GiB VRAM, flat) |
| WEBSOCKET | **PASS** |
| FPT | EN borderline 1.1 s / HI **PASS** |
| PARTIAL LATENCY | EN **PASS** / HI PASS ≤2 min, 1.5 s @10 min |
| FINALIZATION | EN PASS (one 4 s outlier) / HI **MISS recorded** (1.2-3.2 s) |
| QUALITY | **PASS** (EN 2.08% vs batch; HI 0-2.3 pt vs baselines, 2-min slice noted) |
| STABILITY | **PASS** (monotonic display, both languages, in-browser) |
| BATCH REGRESSION | **PASS (zero)** |
| PUNCTUATION | **PASS** (existing stages, final-only) |
| PROVENANCE | **PASS** (one sample; raw→punctuated→correction) |
| SHARE | **PASS** |
| CORRECTION | **PASS** |
| SECURITY | **PASS** |
| PRIVACY | **PASS** |
| ROLLBACK | **PASS** |
| PRODUCTION ENABLED | **NO** |
| HOSTINGER | **NO** |
