# Qwen3 Long-Audio Strategy — Research & Architecture Recommendation

| | |
|---|---|
| **Status** | RESEARCH ONLY — nothing implemented; the 120 s guard remains in force; production untouched |
| **Date** | 2026-08-12 |
| **Question** | How should Hindi audio longer than 120 s be served by Qwen3-ASR 0.6B without silent truncation, memory spikes, concurrency damage, or any change to request-level metering/collection/correction semantics? |
| **Answer, measured** | **Hybrid: ≤120 s stays direct (unchanged); >120 s is chunked INSIDE the engine** — 100 s windows, 5 s overlap, normalized overlap-dedup merge. Chunking was the only strategy that transcribed 300 s AND 600 s completely, and at 600 s it was simultaneously the most accurate (CER 0.186 vs 0.252 for ctx 16384), 2.8× faster (177 s vs 498 s), and flattest on RSS — at the product's existing ctx 4096, with zero idle-memory increase. |

Labels: **[VERIFIED]** measured this date on the dev machine (single run per cell; ±20–40 % wall-clock variance observed elsewhere today) · **[ESTIMATED]** derived from measurements · **[UNKNOWN]** stated as such.

---

## 1. Current limitation

The engine refuses audio > 120 s with a clean 400 (`qwen3_max_audio_seconds`, set by the Milestone 17 finding). Verified through the real gateway (M18): 119 s → 200, 120 s → 200, 121 s → 400, unbilled, uncollected, surfaced usefully in Web and the keyboard. The guard is correct and **stays until the approved solution is proven.**

## 2. Root cause — three stacked mechanisms [VERIFIED]

**(a) Token budget arithmetic.** The mtmd encoder emits ~**12.5 audio-tokens/second** (measured: 20.97 s clip → 288 prompt tokens incl. ~25 template). Hindi output costs ~**12 text-tokens per speech-second**. Both live in ONE context window, so at ctx 4096: 300 s of audio ≈ 3,750 tokens leaves ~300 for output → the model emits ~5 % of the transcript and stops **with a 200** — the silent truncation. At 600 s, prefill alone exceeds the window → hard 400 at the server. Today's sweep reproduced both exactly (300 s: completeness 0.051; 600 s: HTTP 400).

**(b) Encoder memory scales with input length**, independent of ctx: RSS grew ~1.55 → 2.58 GiB across 120→600 s inputs at ctx 4096, and M17 measured 6.5 GiB on Linux. Long inputs are expensive to *hear*, not just to say back.

**(c) NEW: the model degrades on very long windows even when they fit.** At ctx 16384 (600 s fits arithmetically: 7,500 audio + ~3,600 output ≈ 11k < 16,384), output was still only **83.6 % complete at CER 0.2515** — the decoder loses the plot over very long single passes. Larger context alone can never fully deliver 600 s.

**Additional interacting limit:** the adapter's `max_tokens = 2048` independently caps output at ~170 speech-seconds; any long-audio design must raise it per-request or per-chunk.

## 3. Option A — larger context [VERIFIED, then rejected as the full solution]

Probe: hand-spawned pinned llama-server; concatenations of FROZEN-EVAL clips so references remain valid (concatenated references, scored with the plane's own `cer_unicode` ruler; sandbox-labeled, never ledger). Within-duration comparisons share identical audio+reference, so columns are directly comparable; absolute completeness carries a small constant construction bias (the `-t` cut of the final clip keeps its full reference — this, not truncation, is why even healthy 120 s rows read 0.92; M17's product-path probe confirmed ≤120 s output is complete).

| ctx | 120 s | 180 s | 300 s | 600 s | idle RSS |
|---|---|---|---|---|---|
| **4096** (product) | ✓ 0.92 / CER 0.163 / 49 s | ⚠ 0.83 / 0.239 / 87 s | ✗ **0.05** / 0.952 / 54 s | ✗ HTTP 400 | 1,334 MiB |
| **8192** | ✓ identical to 4096 | ✓ 0.99 / **0.093** / 105 s | ✓ 0.94 / 0.172 / 212 s | ✗ **0.05** / 0.952 / 160 s | 1,782 MiB |
| **16384** | — | — | ✓ identical to 8192 | ⚠ **0.84** / 0.252 / **498 s** | 2,678 MiB |

Readings: 8192 genuinely fixes 180–300 s (and 180 s truncation already begins at ctx 4096 — the 120 s guard was well placed). 8192 still silently truncates 600 s exactly as the arithmetic predicts. 16384 is incomplete AND slow at 600 s (RTF 0.83 — one request holds a pool slot for ~8 minutes) AND costs **+1.34 GiB idle KV on every replica forever**, paid even by 5-second dictations. **Reject as the complete answer; note 8192 as a viable partial step if only ≤300 s were ever needed.**

## 4. Option B — chunking [VERIFIED]

Design probed: fixed **100 s windows, 5 s overlap**, sequential inference at the product ctx 4096, merge by longest suffix/prefix match on **ruler-normalized words** (a "match" means what the evaluation plane means by it), per-chunk `max_tokens` 2048.

| Input | completeness | CER | wall | peak RSS | chunks |
|---|---|---|---|---|---|
| 300 s | **1.01** | 0.209 | **81 s** (RTF 0.27) | 2,334 MiB | 4 |
| 600 s | **1.01** | **0.186** | **177 s** (RTF 0.29) | 3,267 MiB | 7 |

Against the best direct alternative per duration: at 300 s chunking pays a measurable seam cost (CER 0.209 vs 0.172 direct-8192) but runs **2.6× faster**; at 600 s chunking **wins on accuracy outright** (0.186 vs 0.252) and runs 2.8× faster. Seam inspection: the dedup merge produced coherent joins on all 9 seams (recorded in the probe JSON); the completeness slightly >1.0 is residual seam duplication of a few words — the failure mode is a couple of repeated words, never lost content, and it is bounded by the overlap window.

Design notes carried into the recommendation: chunks are **pure PCM byte-slices** of the already-decoded canonical audio (no re-decode, no ffmpeg in product code — the probe used ffmpeg only because it worked from files); max chunk count at the 600 s product ceiling is **7**; silence-aware boundary snapping is a cheap refinement because `EnergyVad` already computes speech regions internally (currently discarded — exposing them is additive); per-chunk retry is natural (each chunk is an independent, idempotent inference).

## 5. Option C — hybrid [RECOMMENDED]

`audio ≤ 120 s` → today's direct path, byte-for-byte unchanged (every proven benchmark stays valid). `audio > 120 s` → the chunked path of §4. One code path decides by duration **inside `Qwen3AsrEngine.transcribe()`**, which is the load-bearing architectural choice: the engine already holds canonical PCM, and everything above the engine seam — worker-pool admission (one slot), response envelope (one), metering (one), collection (one), correction (one) — remains single-request **by construction**, not by discipline. No gateway change, no route change, no public API change.

## 6. Option D — background job [REJECTED for now]

Inspection finding: the platform has **no background-job infrastructure whatsoever** — no queue, no workers, no `BackgroundTasks`, nothing. Option D means building a job subsystem AND a public way to fetch results later (status endpoint or webhook) — a real public-API surface change. Sync chunked 600 s completes in ~177 s [VERIFIED], which users of a 10-minute upload can reasonably wait for. **Trigger to revisit:** product demand for >10-minute audio (meetings, call recordings), where waiting becomes unreasonable and a job API earns its complexity.

## 7. Option E — different long-audio model [REJECTED]

The only resident candidate is whisper-small, whose Hindi failure is the reason for the switch (same-voice A/B today: Korean/Cyrillic fragments, 25 s, unusable). Routing long Hindi to it would ship worse output on longer — likely more valuable — recordings. No third model earns two-model operational complexity while chunking meets the need at ctx 4096.

## 8. Metering [by construction]

The gateway meters `output.duration_seconds` of the ONE envelope the runtime returns — the full audio duration, once. N internal chunk inferences are invisible to it. **Zero metering code changes; semantics untouched.** (Failure path unchanged too: a failed request records `outcome=failed` at amount 0 — verified live in M18.)

## 9. Speech Samples [by construction]

Collection runs in the gateway after success, on the original upload + the single returned transcript → **one sample**, original audio, merged transcript, exactly as short requests behave today.

## 10. Correction [by construction]

One sample → one correction lifecycle; `original_transcript` immutable, `current_transcript` evolves. Nothing chunk-shaped exists at this layer.

## 11. verbose_json / segments — what can be guaranteed

Today long-Hindi would have returned one full-span segment; under chunking the honest shape is **one segment per chunk window**: `start`/`end` are the REAL window offsets we cut (chunk 1 ≈ 0–100 s, chunk 2 ≈ 95–195 s post-merge attribution, …), `text` is that chunk's post-merge contribution. **Guaranteed:** segment boundaries are true audio-window boundaries; concatenated segment text equals `text`. **Not guaranteed, and not fabricated:** word-level timing, or that a segment boundary falls between words the model heard as separate. This is *more* granular than the current single span and needs one sentence added to the prepared product disclosure.

## 12. Failure / retry

Recommended, matching existing API semantics (the product never silently returns partials): each failed chunk gets **one retry** (the supervisor may be mid-restart; M17 measured ~10 s recovery, and chunks are idempotent) → if it still fails, **the whole request fails** with the standard envelope; no partial transcript; usage records `failed` at 0; the keyboard's existing one-bounded-retry on 503 composes correctly on top. Partial-transcript delivery is rejected: it would be the API's first silent-quality lie, and the 300 s truncation bug taught exactly why. Bounded worst case: 7 chunks × 2 attempts.

## 13. Call-center implications

Chunking **protects** the small-model concurrency story: short calls are untouched (no idle-KV tax — unlike Option A's +0.45–1.34 GiB per replica), and RSS stays in the ~1.5–3.3 GiB band rather than 6.5 GiB spikes. Long requests occupy one pool slot for RTF×duration (~0.3×) [VERIFIED]: a 600 s recording holds a slot ~177 s. With today's pool (2 exec + 8 queue) [ESTIMATED from the M16/M17 ladders]: ~12 concurrent live *calls* per box for short-utterance traffic, unchanged; a mix containing long recordings consumes slots proportionally (one 600 s job ≈ ~25 short dictations of capacity) — a scheduling/pricing fact to carry into VPS sizing, not a blocker. 10/20 concurrent short calls: as measured in M16 (stable at 10; clean 503 shedding at 20). 20 concurrent 600 s uploads on one box is not a real-time workload and belongs to Option D's future.

## 14. Resource / capacity summary

| Strategy | 300 s | 600 s | Peak RSS | Idle cost | Wall @600 s | Complexity |
|---|---|---|---|---|---|---|
| Direct ctx 4096 (today) | ✗ silent 5 % | ✗ 400 | 2.6 GiB | — | — | none (guarded) |
| Direct ctx 8192 | ✓ 0.172 | ✗ silent 5 % | 3.8 GiB | **+450 MiB always** | — | trivial but insufficient |
| Direct ctx 16384 | ✓ 0.172 | ⚠ 84 %, 0.252 | 3.8 GiB | **+1.34 GiB always** | 498 s | trivial but wrong |
| **Chunked ctx 4096** | **✓ 0.209** | **✓ 0.186** | **3.3 GiB** | **zero** | **177 s** | moderate, engine-contained |

Timeout chain note [VERIFIED by inspection]: the binding sync limit is the **gateway's 120 s runtime-call deadline** (`INTELLIAI_RUNTIMES_TIMEOUT_SECONDS`; Caddy adds none). Chunked 600 s needs ~180–220 s runtime time → the implementation must raise that config to ~300 s (configuration, not contract) or cap sync support near 350 s. Recommendation: raise to 300 s alongside the feature.

## 15. Recommended architecture

**Option C.** Chunking lives entirely inside `Qwen3AsrEngine.transcribe()`: duration ≤ `qwen3_max_audio_seconds_direct` (120) → current path; else PCM byte-slice windows (100 s, 5 s overlap, optionally VAD-snapped), sequential child inferences (per-chunk timeout + one retry), ruler-normalized overlap-dedup merge, per-window segments, one `TranscriptionResult`. The product guard becomes two-tier: direct-limit 120 s (internal), request-limit raised 120 → 600 s **only after the implementation passes its proof battery**. Gateway timeout config 120 → 300 s. Everything else in the platform: untouched.

## 16. Implementation phases (next milestone, on approval)

1. Engine: window slicer + merge + per-chunk retry + segments; settings (`direct` limit, window, overlap); `max_tokens` per chunk. Deterministic tests against the stub server (merge, seams, retry, failure, segment offsets, refusals above the still-600 s ceiling).
2. Sandbox proof: re-run today's probe THROUGH the engine (not hand-rolled) — completeness ≥ 0.99 at 300/600 s, CER parity with today's numbers, RSS bound, seams inspected.
3. Product-path proof (staging stack): 300/600 s through the real gateway — one usage event, one sample, correction, verbose_json shape, failure drill mid-chunk (kill child at chunk k → retry-after-recovery or clean whole-request failure, never partial).
4. Raise the guard 120 → 600 and the gateway timeout 120 → 300; keep both as config; ladder re-check for concurrency regressions on short audio (must be zero — the direct path is untouched).
5. Docs + disclosure sentence + ledger.

## 17. Risks

- **Seam errors on continuous speech.** The probe's seams sit near clip boundaries (silence-adjacent) — real mid-sentence cuts are harder. Mitigation: VAD-snapped boundaries (regions already computed internally) + the 5 s overlap; measure on continuous long recordings in phase 2. [UNKNOWN magnitude]
- **Single-run cells.** Every number above is one run; wall-clock ±20–40 % variance was observed elsewhere today. Rankings are robust (the gaps are ×2–5 or complete-vs-truncated); exact values are indicative.
- **Sequential chunks stretch tail latency** for the longest uploads (~3 min for 600 s). Parallel chunking across the pool is possible later but spends call-center concurrency; explicitly deferred.
- **Construction bias** of concatenated audio (documented in §3) — absolute CERs here are not benchmark numbers and are labeled accordingly.

## 18. Open questions

Window size 100 s vs 60/80 s (quality-vs-seam-count curve); VAD-snap gain; punctuation continuity across seams (chunk outputs are independently punctuated — merge currently keeps both sides' punctuation as-is); behavior policy for >600 s uploads (stays a clean 400 until Option D exists); whether ctx 8192 + chunking combined ever pays (larger windows, fewer seams — measure only if seam quality disappoints).

## 19. Decision required

Approve **Option C (hybrid, engine-internal chunking)** as the architecture for the next milestone — including the gateway-timeout config raise (120→300 s) and the two-tier guard (direct 120 s / request 600 s, raised only after the phase-2/3 proofs pass). Until approval and proof, the 120-second guard stands and nothing changes.

---

*Probe evidence: `research/experiments/19-long-audio-strategy/ctx-vs-chunking.json` (per-cell metrics, seam texts) + `idle-rss.txt` + the committed probe script. The staging stack was paused during measurement and restored; no production, guard, context, API, metering, sample, or model change was made.*
