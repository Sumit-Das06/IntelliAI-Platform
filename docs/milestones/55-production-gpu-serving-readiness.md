# Milestone 55 — Production GPU Serving Readiness

| | |
|---|---|
| **Status** | Decision **A. PRODUCTION GPU READY** — classification **PRODUCTION-LIKE-GPU-VERIFIED** (no designated production GPU box exists yet; every gate ran on the closest production-shaped GPU per this milestone's own fallback rule, and the checklist carries the production-box re-run as the enablement condition) |
| **Date** | 2026-09-01 |
| **Scope** | GPU serving validation + deployment readiness ONLY. **PRODUCTION REALTIME: OFF. PRODUCTION GPU TRAFFIC: OFF. HOSTINGER: untouched.** |
| **Evidence** | `research/experiments/55-production-gpu-readiness/` (84 files) |

## 1-2. Objective + hardware (MEASURED)

RTX 5070 Laptop 8 GB, driver 591.91 / CUDA 13.1, i7-14650HX, 31.6 GB
RAM, Windows 11, Docker 29.3.1 (`hardware.json`). CUDA proven by
INFERENCE, not installation: llama b10344-CUDA ×2 instances + CT2
fp16 resident, warm-up decodes through every path, VRAM/util sampled
throughout (`cuda.json`).

## 3-4. Artifacts + runtime pins (REPO-VERIFIED, live-hashed)

E3 GGUF+mmproj sha-verified at every startup; `llama-server.exe`
b2ace4b8… and `ggml-cuda.dll` 5ea989dc… match the code pins; the
launcher refuses drift; whisper-small via ArtifactStore; runtimes from
the locked workspace. Mutable downloads structurally impossible.

## 5-6. Startup + coexistence (MEASURED)

Realtime runtime cold→ready 12.4 s (warm 6.8 s); GPU llama launch
~10-25 s; batch container in external mode: engine "load" 12.6 ms +
**a real 281 ms GPU warm-up decode** before ready. All three resident:
2899 MiB (EN+HI realtime) → 4888-5304 MiB with the batch instance —
~2.8 GiB headroom, flat over ~50 sessions, zero OOM.

## 7-8. English realtime + stall check (MEASURED)

20 consecutive boss30 sessions: FPT p50 **1.10 s** (p95 1.15, max
1.39), finalization p50 **203 ms** (max 358 — the fast path landing
consistently on the warm GPU), cadence p50 0.53 s, **max partial gap
1.74 s — ZERO stalls in 20 runs**. The M54 7.6-16.8 s stalls did not
reproduce: they are INTERMITTENT, thermal/clock-state behavior of this
laptop — not claimed fixed; the >15 s hot-decode alert stays armed and
the production-GPU re-check is the checklist condition. c-ladder:
c=1 p50 0.53 s → c=2 0.67 s → c=4 ~1.05 s → c=8 ~2.1 s (stable, zero
errors, zero degraded at every c).

## 9-11. Hindi realtime (MEASURED)

FPT 0.33-0.42 s; cadence p50 0.62-0.79 s at 30 s/2/5/10 min; p95
1.2-1.4 s; **finalization 0.77-1.04 s (30 s) and 1.23-1.43 s at every
long length — the M54 10-minute 6.5 s event (3.0 s punctuation on a
cold/loaded box) did not reproduce (10-min final 1.31 s, punctuation
sub-second)**. Quality vs frozen ground truth: 2 min −3.6 pt BETTER
than M54, 5 min −1.3 pt, 10 min +0.8 pt, 30 s +0.9…+3.4 pt across 3
runs — inside the established seam-variance band, no directional
regression (`hi-quality.json`).

## 12-13. Hindi BATCH through GPU — the anomaly DISPOSITIONED (MEASURED)

The batch engine gained an additive, flag-gated **external-server
mode** (`INTELLIAI_STT_QWEN3_SERVER_URL`, default empty = today's CPU
child; slot stays truthful via a new external health monitor). Through
the REAL public gateway route on its own GPU llama instance (:8798):

| clip | old CPU service (M54, historical) | GPU service now (n=5) |
|---|---|---|
| real30s multi | 2-94 words, UNSTABLE | **117 ×5, byte-deterministic**, WER 10.92%, 2.4 s |
| real60s multi | 61-196, UNSTABLE | 224-225 stable, 3.5 s |
| 2 min multi | (unstable class) | 441-443 stable, WER 21.09%, 8.2 s |
| short single | 9 stable | 9 ×5 deterministic, 0.25 s |

**Phase 34 decision: A — GPU batch becomes production-required for
Hindi.** The CPU path keeps its documented long-multi-speaker
limitation as a degraded fallback only.

## 14-16. Mixed workload, fairness, capacity (MEASURED)

Batch on its own instance under a CONTINUOUS hammer (13 calls, all 117
words) alongside live EN+HI sessions: realtime completed cleanly but
cadence roughly doubled (p50 2.1-2.2 s) — separate instances isolate
VRAM and queues, not GPU compute. Production policy: cap batch
concurrency on a realtime GPU (batch already serializes) or separate
cards at scale. Fairness: equal degradation at every c, no starvation,
degraded stays the explicit signal. **RECOMMENDED SAFE CAPACITY: 2
concurrent realtime sessions per 5070-class GPU (target UX with
margin); 4 = acceptable-degraded burst; scaling is horizontal — never
VRAM oversubscription.**

## 17-19. GPU memory, CPU/RAM, network (MEASURED)

VRAM states and growth: `gpu-memory.json` (flat, no fragmentation
symptoms). Host: llama 4.1 GiB RSS total + runtime 430 MiB, CPU ~3%
idle, 7.2 GB RAM free — the GPU did not move the bottleneck to CPU.
Network: loopback RTT 10-28 ms; the decomposition separates UI/LA2 lag
(browser first-visible 2.4-3.8 s) from client FPT from decode — and
every number here is loopback: the production edge adds real RTT.

## 20-24. Browser E2E, mobile, batch E2E, punctuation, provenance

EN+HI fake-mic Chromium: monotonic display, Share==final, correction
saved, zero leaks; 390/820/desktop clean. Batch E2E: GPU path
deterministic (above); CPU rollback path serves. Punctuation
final-only, sub-second everywhere this milestone (alert armed at 5 s).
Provenance unchanged: one consented sample max, partials ephemeral.

## 25-29. Security, privacy, readiness, observability, ALERTS (drilled)

Posture unchanged and re-verified (`security.json`, `privacy.json`).
Readiness truth on BOTH services drilled live: realtime
`ready/degraded/disabled`; batch slot flips `restarting`/`degraded` on
external-backend death and SELF-RECOVERS. Alerts are now a runnable
checker (`tools/ops/realtime_alerts.py`) with the M54 thresholds:
**all five forced conditions fire (exit 1), clean logs and user
cancellation stay silent (exit 0), and two conditions fired LIVE in
the failure drills.** Production schedules it on the GPU host.

## 30-33. Capacity decision, scaling, failure, rollback

Capacity/scaling: §14-16. Failure drills (LIVE): batch instance killed
→ honest 503 + degraded readiness + alert + self-recovery; realtime
backend killed → `realtime: degraded` + alert + explicit session
error, relaunch → recovered smoke (fpt 0.98 s, final 132 ms).
Rollback: M54's flag-off drill stands; batch-GPU-off returns to the
committed CPU mode and serves. Final stack state: committed compose,
nothing uncommitted enabled.

## 34-36. Batch decision, production config, checklist

Batch: **A** (§12-13). `prod-realtime.yml` now carries BOTH prepared
switches — the gateway realtime URL and the batch GPU URL — still
wired into NOTHING (ops guard re-verified green). Checklist:
`promotion-checklist.json` — every item PASS, three open enablement
conditions: provision the production GPU box + re-run
c-ladder/stalls/edge-latency there; the founder's product call on
recorded latencies; schedule the alert checker.

## 37. Product latency decision (PROPOSED to the founder)

On warm-GPU evidence: EN FPT p50 1.10 s (target 1 s narrowly missed;
first words visible fast, finals 0.2 s), HI FPT 0.35 s, finals ≤1.4 s
at every length. **Recommendation: acceptable as-is for a v1 realtime
launch** — no further latency-hardening milestone before promotion;
the remaining gap is hardware-tier, not architecture. Founder ratifies
at the promotion gate.

## 38. Scorecard

| Metric | EN Realtime | HI Realtime | HI Batch (GPU) |
|---|---:|---:|---:|
| FPT | p50 1.10 s (20 runs) | 0.33-0.42 s | n/a |
| Partial p50 | 0.53 s | 0.62-0.79 s | n/a |
| Partial p95 | 0.58-1.2 s | 1.2-1.4 s | n/a |
| Finalization p50 | 203 ms | 0.92 s (30 s) / ≤1.43 s long | latency p50 0.25-8.2 s by length |
| Finalization max | 358 ms | 1.43 s | — |
| WER | 2.08% vs batch (M54 law holds) | 17.7-20.2% (30 s) vs truth | 10.92% (30 s) vs truth |
| CER | — | 9.0-14.2% | 5.12% (30 s) |
| Long audio | 10 min clean | 10 min: p50 0.79 s, final 1.31 s | 2 min stable 441-443 |
| VRAM | shared 2.9-5.3 GiB flat | shared | +2.1 GiB own instance |
| RAM | runtime 430 MiB | shared | llama 1.0 GiB |
| GPU util | ≤73% c1 | ≤91% c2+ | hammer → ~2× realtime cadence |
| c=1 / c=2 / c=4 / c=8 | 0.53 / 0.67 / 1.05 / 2.1 s p50 | mixed cells same lane | serialized |
| Error rate | 0 across ~50 sessions | 0 | 0 |
| Stall max | 1.74 s (20 runs; M54 events intermittent) | 1.6 s | — |
| Determinism | stable | words ±1 | **byte-deterministic (30 s ×5)** |

## 39-40. Decision + next milestone

**A. PRODUCTION GPU READY (PRODUCTION-LIKE-GPU-VERIFIED).** All
realtime and batch gates pass on the production-shaped GPU; the
anomaly is dispositioned by measurement; capacity, alerts, failure,
and rollback are drilled. What A does NOT claim: validation of a box
that does not exist yet — the three checklist conditions gate
enablement. **Next (founder-gated): REALTIME STT PRODUCTION
PROMOTION** — provision the production GPU host, re-run the ladder/
stall/edge checks there, wire the alert schedule, make the latency
product call, then flip the prepared overlay. **PRODUCTION: OFF.**
