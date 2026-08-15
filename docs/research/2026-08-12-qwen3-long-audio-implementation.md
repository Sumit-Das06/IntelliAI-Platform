# Qwen3 Hybrid Long-Audio — Implementation Record (Milestone 19)

**Status:** COMPLETE — the full proof battery passed and the ceiling
was raised 120 → 600 in Phase 18. This document is the implementation
record for the approved Hybrid C strategy
([2026-08-12-qwen3-long-audio-strategy.md](2026-08-12-qwen3-long-audio-strategy.md)).
Research-plane record: the engine remains research-only; no production
route resolves to it, and production routing did not change in this
milestone.

**The law this milestone exists to enforce:** complete transcript OR
clean failure. NEVER a partial transcript with a 200. Every proof
below was run against that law; none broke it.

**Verdict:** Qwen long-audio is **READY for the 600-second product
limit** on this deployment shape (research/staging plane). Production
adoption remains gated on promotion (a founder ledger decision) plus
the §19 capacity decisions on VPS hardware.

---

## 1. What changed

| Surface | Change |
|---|---|
| `services/stt-runtime/.../engines/qwen3_asr.py` | `transcribe()` dispatches: ≤ direct limit → the proven single-pass path, byte-for-byte unchanged; above it → internal chunking (new). Single-inference call extracted to `_decode_once()` — the ONE decode call site both paths share. |
| `services/stt-runtime/.../config.py` | New deployment knobs: `qwen3_direct_audio_seconds` (120), `qwen3_chunk_window_seconds` (100), `qwen3_chunk_overlap_seconds` (5), `qwen3_chunk_snap_radius_seconds` (8). Ceiling `qwen3_max_audio_seconds` held at 120 through the proof battery, then raised to 600 in Phase 18 (§8). |
| `services/stt-runtime/.../slots.py` | Plumbs the new settings into the loader (plumbing is guard-tested). |
| `apps/api/.../core/config.py` | `RuntimeSettings.timeout_seconds` default 120 → 300 (configuration, not contract — §7). |
| `infra/compose/local-staging.yml` | Carried the 600 s override during the battery; the override is removed now that 600 is the committed default. |
| `services/stt-runtime/tests/test_qwen3_asr.py` | +23 deterministic tests: window planning, PCM slicing, boundary snap, overlap merge, chunked request laws, config plumbing, description keys. |

Nothing changed in: metering, collection, correction, public API shape,
Android client, production compose/routing, the evaluation ruler, the
Qwen context (4096), the pinned runtime build, the artifact pins.

## 2. Architecture

Chunking lives entirely inside `Qwen3AsrEngine.transcribe()`, below the
slot layer. Everything above the engine seam — gateway, metering,
collection, correction — sees exactly what it saw before: one request,
one `TranscriptionResult`, one usage event, one Speech Sample, one
correction lifecycle. That is not a discipline the upper layers
maintain; it is a property they cannot violate, because no chunk object
ever crosses the seam (the Milestone 15E seam law doing its job).

```
audio ≤ 120 s                     audio > 120 s (≤ ceiling)
     │                                 │
     ▼                                 ▼
 _decode_once(full audio)         plan_windows(duration, 100 s, 5 s)
     │                                 │ interior starts snapped toward the
     ▼                                 │ quietest nearby moment (±8 s, clamped)
 one full-span segment                 ▼
                                  per window, in order:
                                    slice_audio (PCM byte-slice)
                                    _decode_window_with_retry (max 1 retry)
                                    merge_chunk_text (normalized overlap dedup)
                                       │
                                       ▼
                                  ONE TranscriptionResult
                                  (text = join of contributions;
                                   one segment per contributing window)
```

No disk writes, no ffmpeg per chunk, no re-decode: windows are
frame-exact byte-slices of the already-decoded canonical PCM
(`slice_audio`), sharing the decode the pipeline already paid for.
Reassembly is exact: adjacent slices concatenate back to the original
bytes (tested).

## 3. Chunk configuration

All knobs are deployment configuration (env-tunable, described by
`describe()` so evidence records name the geometry that produced them):

| Setting | Default | Meaning |
|---|---|---|
| `qwen3_direct_audio_seconds` | 120 | at or below: the proven single-pass path |
| `qwen3_chunk_window_seconds` | 100 | window length (measured complete at ctx 4096) |
| `qwen3_chunk_overlap_seconds` | 5 | audio both adjacent windows hear |
| `qwen3_chunk_snap_radius_seconds` | 8 | seam search radius; 0 disables snapping |
| `qwen3_max_audio_seconds` | **600** (raised in Phase 18 after the battery; was 120) | request ceiling; the loud refusal beyond it is unchanged |

Window arithmetic (`plan_windows`) is deterministic and bounded: starts
advance by `window − overlap`; the last window ends exactly at the
duration; a tail bringing less new audio than the overlap is absorbed
into the last window instead of decoding a near-duplicate sliver.
600 s → exactly 7 windows. `max_tokens` per inference stays 2048 —
ample for 100 s of speech (~1200 output tokens worst measured) while
fitting ctx 4096 beside ~1250 audio tokens.

## 4. VAD / boundary behavior

Per the Phase 4 instruction, no new VAD was built. The pipeline's
`EnergyVad` answers a different question (does this clip contain speech
at all — threshold classifier over 30 ms RMS frames, upstream of the
engine); the seam question is "where is the quietest instant near
t = k·95 s". `quietest_moment()` answers it with the same family of
deterministic energy math: argmin of mean |int16| per 200 ms block
within ± the snap radius, ties broken toward the earliest block. A
window's start snaps there, clamped so the previous window still
overlaps every seam (coverage can never develop a gap) and so the seam
stays within the merge window's reach. Uniform audio (no quiet gap)
degrades to a stable deterministic pick; radius 0 disables snapping
entirely. Fixed-vs-snapped quality is compared on continuous speech in
§17.

## 5. Merge algorithm

`merge_chunk_text(previous_words, chunk_text)` returns the words the
new window ADDS: longest suffix(previous)/prefix(next) match on
normalized words, up to a 14-word overlap horizon. Normalization
(`normalize_for_merge`) is NFC + casefold + Unicode P*/C* stripping —
engine-local and used for MATCHING ONLY; output text keeps the model's
original words, and the runtime deliberately does not import the
evaluation ruler (layering law: the serving plane must not depend on
the evaluation plane). Pure-punctuation words can never anchor a match
(an all-empty normalized overlap is rejected), so unrelated texts
cannot glue together at a comma. No LLM, no second model, no
heuristics beyond exact normalized equality. Genuine repetition beyond
the overlap horizon survives (tested).

## 6. Retry / failure semantics

Each window: at most ONE retry, after a 12 s pause — long enough for
the supervisor's detect→restart cycle (~10 s measured in M17) to have
recovered a crashed child. A window failing twice fails the WHOLE
request with one clean error ("transcription of the full audio could
not be completed") that names neither chunks nor engines and carries no
fragment of partial text. The gateway then does what it always does
with a failed request: `outcome=failed`, `amount=0`, no sample, no
correction. There is no code path that returns fewer windows than were
planned — the loop either completes or raises.

## 7. Timeout changes

`INTELLIAI_RUNTIMES_TIMEOUT_SECONDS` default 120 → 450 — sized to
measurement, not to the research estimate. The strategy probe's single
600 s chunked run suggested ~180 s; the M19 engine-proof battery
measured **297–340 s** wall for 600 s decodes on the same hardware
(§9), so the earlier plan of 300 s would have timed out a healthy
request — exactly the situation the spec forbids (gateway deadline <
expected chunking runtime). Layer analysis for a 600 s chunked request:

| Layer | Deadline | Verdict |
|---|---|---|
| Caddy | none set | outlasts |
| gateway → runtime (httpx) | **450 (was 120)** | the binding deadline — worst measured 600 s wall (340 s) × ~1.3 margin |
| gateway admission lease | **540 (was 180)** | eviction insurance must outlast the deadline (its own documented invariant — 180 was already below the old plan) |
| runtime per-inference | 300 s per chunk | bounds each window (worst measured window ~75 s), not the request |
| Android okhttp | read 120 s / call 150 s | UNCHANGED — see §12: measured 300 s walls (150–155 s) already exceed the 150 s call cap; mobile long-audio needs a client decision, forbidden here |

Configuration, not contract: no public API shape moved.

## 8. The 120/600 limits

**Phase 18 EXECUTED** — after every required gate passed (§9, §10,
§11, §17, §18, §19a): the committed default ceiling is now **600 s**
(engine constant + `qwen3_max_audio_seconds`), the staging overlay's
temporary override is removed, and the final behavior is exactly the
approved shape:

- ≤ 120 s → the proven direct pass (unchanged since M15E)
- 120–600 s → chunked inside the engine
- \> 600 s → the same loud 400, now naming 600 s and nothing internal

The refusal tests moved with the ceiling (601 s refused, message says
"600 seconds"); the gateway pass-through test carries the new envelope
verbatim. The guard was held at 120 through the ENTIRE proof battery —
the raise landed only in this final phase, exactly as specified.

## 9. Sandbox proof (through the engine)

**VERIFIED.** `engine_proof.py`: the concatenated-clip probe inputs run
through `load_qwen3_asr` (pinned binary verified at load) +
`Qwen3AsrEngine.transcribe()` with the in-process ceiling override.
2–3 repeats per duration; scored with the evaluation ruler
(concatenated-clip probe — beside the frozen benchmark, never in it).
Raw record: `research/experiments/19-long-audio-strategy/engine-proof.json`.

| Duration | Walls (s) | CER (repeats) | Completeness | Segments | Contract |
|---|---|---|---|---|---|
| 120 (direct) | 48–55 | 0.1625 / 0.1632 | 0.92 | 1 | join==text ✓ |
| 180 (2 windows) | 96–98 | 0.1189 / 0.1189 | 1.02 | 2 | ✓ |
| 300 (4 windows) | 150–155 | 0.2084–0.2101 | 0.989–0.992 | 4 | ✓ |
| 600 (7 windows) | 297–340 | 0.1829–0.1846 | 1.005–1.006 | 7 | ✓ |

Reading, honestly:

- **No truncation, ever.** Every planned window decoded on every run
  (23/23 windows across the battery). Compare the direct decodes this
  replaces: 300 s direct at ctx 4096 kept 5.1% of the transcript;
  600 s at ctx 16384 kept 83.6%. Truncation has a signature and none
  of these rows has it.
- **Completeness gate met.** At 300 s the scorer's documented
  pessimism (the final clip is cut at exactly 300 s; its full
  reference stays) caps achievable completeness at ~0.983; measured
  0.989–0.992 sits ABOVE the audio-backed ceiling. At 600 s the
  pessimism is 0.1% and completeness is 1.005. The 120 s direct row
  (0.92) reproduces the pre-chunking baseline to the digit — the
  direct path is untouched.
- **CER beats the hand-rolled prototype** (300 s: 0.2084 vs 0.2092;
  600 s: 0.184 vs 0.1857) and far beats every direct alternative
  measured in the research (ctx 16384 600 s: 0.2515 incomplete).
- **Determinism, stated precisely:** window planning, snapping,
  slicing, and merging are deterministic (unit-proven). The BACKEND is
  not bit-deterministic run-to-run (llama.cpp CPU threading — the same
  property 15E documented as the 0.0011 replicate CER spread). Across
  repeats here: 180 s byte-identical; 300/600 s CER spread ≤ 0.0017,
  same class as the direct path's own band. Chunking adds no
  instability of its own. VERIFIED at this hardware; the band is
  INDICATIVE elsewhere.
- **Language resolution:** every chunked result resolved `hi` from the
  first window's emitted tag.
- **Two operational findings, promoted to actions:**
  1. *600 s walls (297–340 s) far exceed the research's single 176.7 s
     measurement* → the gateway deadline was sized to the measured
     worst, not the estimate (§7: 450 s, lease 540 s).
  2. *llama-server RSS grows across sequential window decodes*: peak
     1.55 GiB (120 s) → 2.4 (180) → 3.0 (300) → **3.98 GiB (600 s,
     run 3)** — the pinned build retains memory across multimodal
     requests instead of returning it. Not a per-request leak visible
     to customers, but a capacity fact: a busy long-audio slot trends
     toward ~4 GiB. Characterized further in §18; recycle policy is an
     ops decision recorded in §19.
- **Seam quality inspected** (600 s, 6 seams): no missing content, but
  near-duplicate phrases survive at seams where the two windows
  transcribed the shared 5 s DIFFERENTLY (decode variance defeats
  exact normalized matching, e.g. "पुरोहित" vs "पुराना"). This is the
  approved design's measured behavior (the research probe's 1.009–
  1.014 completeness was the same effect); cost ≈ +0.5% over-emission
  at 600 s, already included in every CER above. §17 quantifies it on
  harder speech; a variance-tolerant merge is deferred work (§21).

## 10. Product-path staging proof

**VERIFIED.** The M18 staging shape (native multi-slot runtime :8011
`whisper,qwen3-asr` with the 600 s overlay ceiling + native gateway
:8010 on the staging registry profile, sharing the dev stack's
Postgres/Redis/MinIO; the `internal_qa` staging tenant). Every request
through the REAL `POST /v1/audio/transcriptions`. Records:
`research/experiments/19-long-audio-strategy/staging-drills.json` +
`kill-drills.json`.

| Drill | Result |
|---|---|
| 300 s Hindi, contribution ON, verbose_json | 200 in **79.6 s**; `duration: 300.0`; `language: hi`; 4 segments at the real snapped offsets; segment texts join to exactly `text`; sample header present; usage **+1 request / +300.0 s / 0 failed**; zero leaks |
| Correction on the 300 s sample | 200, `collection.corrected` event, zero leaks |
| 600 s Hindi, contribution OFF | 200 in **180.8 s**; 7,717 chars; NO sample; usage **+1 / +600.0 s / 0 failed**; zero leaks |
| Post-drill 300 s | 200 in 79.3 s — the deployment healed |

Fresh-process walls (80 s / 181 s) are far inside the 450 s deadline;
the deadline stays sized to the contended sandbox worst (340 s), since
production will not be idle.

**The kill-mid-window drill found a real engine defect** — which is
what drills are for. Killing the child mid-window returned in 0.9 s
with a raw `internal_error`: a child dying MID-RESPONSE raises
`ConnectionResetError`/`IncompleteRead` from `response.read()`, which
urllib does NOT wrap in `URLError`, so the exception escaped
`_decode_once`'s mapping clause and bypassed the one-retry contract.
Customer-visible behavior was still safe (500, no partial text,
amount 0, no sample) — but by the outer layer's accident, not the
engine's design. Fixed: the transport clause now catches
`(OSError, http.client.HTTPException)` (supersets of every mid-stream
death shape); two new deterministic tests pin it (`@truncate` stub:
retry-after-truncation succeeds on the chunked path; clean INTERNAL on
the direct path). The drill was re-run with honest timing against the
fixed engine (`kill-drills.json`):

| Kill timing | Outcome |
|---|---|
| 35 s into a 600 s request (early window) | **200, complete 7,718-char transcript** — retry engaged, supervisor restarted the child inside the 12 s retry delay, remaining windows decoded on the NEW child; +600.0 s billed once, sample present; ~30 s recovery overhead; zero leaks |
| 100 s into a 600 s request (middle window) | **200, complete transcript**, same recovery shape |
| (first pass, pre-fix code) kill mid-window | clean failure: 500, no partial text, amount 0.0, no sample — safe even before the fix, then made contract-true by it |

A mid-request child crash is now invisible to the customer when the
supervisor wins the race, and a clean whole-request failure when it
does not. No scenario returns partial text.

## 11. Web verification

**VERIFIED [EVIDENCE — real Chromium, real Studio, real gateway].**
`web_verification.py` drove `/console/playground` exactly as a user
would (stored key, Upload file, Transcribe). Record:
`web-verification.json` + `evidence/web-*.png`.

| Step | Result |
|---|---|
| 300 s Hindi, contribute ON | Done in 87.5 s; Devanagari transcript (3,447 chars); request id `req_db89a4de…` and sample id `smp_6b70fa91…` in Developer Details; the Studio's own verbose_json shows **4 segments whose texts join to exactly the transcript**; duration 300 |
| UI responsiveness DURING decode | the tab strip still switches while the request is in flight (checked mid-decode on both runs) |
| Correction via the Studio's button | "Your correction helps improve IntelliAI STT." |
| 600 s Hindi, contribute OFF | Done in 190.0 s; 7,714 chars; dev pane reads "not stored (contribution off)"; **7 segments**, join==text; duration 600 |
| Leak scan | zero internal names in both raw response panes AND the entire rendered page, both runs |

## 12. Android verification

**Contract analysis; NO Android change (none is permitted, and none is
needed for correctness).** The shipped client parses only the final
`text` — chunking is invisible to it by construction. But its okhttp
budget (read 120 s, call 150 s — sized when the gateway's deadline was
120 s) cannot survive real long-audio walls: 300 s requests measured
80–155 s (marginal, machine-dependent), 600 s measured 180–340 s
(impossible). Long audio on mobile therefore stays FORMALLY
UNSUPPORTED until a deliberate client release re-times those budgets —
a product decision deferred (§21), not a bug. Short dictation, the
keyboard's actual use case, is unaffected (§18 ladder). The M18
contract replays remain the Android evidence of record; a
physical-device pass stays recommended before any customer rollout.

## 13. Usage/metering verification

**VERIFIED (no metering code changed — inspection confirmed none was
needed).** The gateway meters `output.duration_seconds` from the ONE
`TranscriptionResult`, and chunking never crosses the seam, so
request-level metering holds by construction — and was still verified
against the live ledger: 300 s request → exactly +1 request /
+300.0 s; 600 s → +1 / +600.0 s; killed request → +1 / **0.0 s** /
outcome `failed`. No duplicates anywhere in the summary deltas.

## 14. Speech Sample verification

**VERIFIED.** One sample per successful contributed request (300 s:
sample id issued in the response header, and the correction landing on
that id proves the stored sample is real); contribution OFF →
transcript delivered, NO sample; failed request → NO sample. No chunk
metadata exists anywhere in the sample surface — the collection layer
receives the same single result it always has.

## 15. Correction verification

**VERIFIED.** The 300 s sample accepted one correction through the
public correction endpoint (200, `collection.corrected`,
`correction_source=user`); original transcript immutability is the
already-pinned M18 behavior, unchanged by this milestone. One sample →
one correction lifecycle, exactly as for short audio.

## 16. verbose_json behavior

Chunked responses carry one segment per CONTRIBUTING window: `start` is
the window's real (possibly snapped) start offset, `end` the next
window's start (last: the duration), `text` the window's post-merge
contribution. Concatenated segment texts equal the final `text` by
construction — the result text IS the join of the segments, never a
separate string to reconcile. No word timestamps are invented (this
lineage emits none); a window whose contribution is empty (silence)
produces no segment. Short audio keeps today's single full-span
segment, unchanged.

## 17. Continuous-speech seam results

**VERIFIED (completeness) / INDICATIVE (A/B margin — one run per
cell).** `seam_probe.py`: a deliberately harder input than the
strategy probe's — IndicVoices **Extempore/Conversation clips only**
(no Read speech), so the ~95 s window boundaries land mid-speech —
through `Qwen3AsrEngine.transcribe()`, once with the default snap
radius (8 s) and once with snapping disabled. Duplicate detector:
normalized trigrams straddling a seam that the merge failed to dedup.
Record: `research/experiments/19-long-audio-strategy/seam-probe.json`.

| Input | Snapped (r=8) | Fixed (r=0) |
|---|---|---|
| 300 s CER / completeness | **0.2100 / 0.991** | 0.2195 / 0.979 |
| 300 s duplicate trigrams | **10** | 13 |
| 600 s CER / completeness | **0.1811 / 1.001** | 0.1890 / 1.004 |
| 600 s duplicate trigrams | **16** | 26 |

- **Snapping wins every cell**: lower CER at both durations, −38%
  seam duplicates at 600 s. The Phase 4 question ("does the boundary
  refinement improve quality materially?") is answered by measurement:
  yes — it stays.
- **Continuous speech does not break the design**: CER on mid-speech
  seams (0.18–0.21) sits in the same class as the strategy probe's
  near-silence seams. No missing-content signature at either duration.
- **The residual seam artifact** is duplication, not loss: a few
  short near-duplicate phrases per request where the two windows
  transcribed the shared 5 s differently. Bounded (completeness ~1.0),
  visible in the raw seam texts, already included in every CER here.

## 18. Concurrency regression

**Short audio — VERIFIED, no material regression.** Same clip bytes
(wav sha `ea63be5b`), levels, repetitions, and pool (2+8) as the M16
Windows ladder, against the staging runtime carrying the chunked
dispatch (`short-ladder-m19.json`):

| c | M16: ok / p50 / rps | M19: ok / p50 / rps |
|---|---|---|
| 1 | 5/5 / 705 ms / 1.42 | 5/5 / 735 ms / 1.36 |
| 5 | 25/25 / 2068 ms / 2.23 | 25/25 / 2128 ms / 2.13 |
| 10 | 50/50 / 4251 ms / 2.34 | 50/50 / 4463 ms / 2.14 |
| 20 | 50+50×503 / 4323 ms / 2.28 | 50+50×503 / 4816 ms / 2.06 |

The admission contract is IDENTICAL (exactly half refused at c=20 with
clean 503s, zero other errors), RTF class unchanged (0.12 vs 0.115),
plateau within 8% of baseline — measured with the dev compose stack
running beside the ladder, a busier host than a clean bench. The direct
path's code delta is a single duration comparison; nothing structural
moved.

**Long audio — capacity characterization, NOT a guarantee**
(`long-concurrent.json`; every request through the real gateway; all
succeeded, zero leaks):

| Batch | Walls (s) | Peak llama RSS |
|---|---|---|
| 2 × 300 s | 76.6, 164.8 | 3,382 MiB |
| 5 × 300 s | 83.6 / 173.2 / 255.3 / 336.5 / **422.3** | 3,382 MiB |
| 2 × 600 s | 181.5, 374.1 | 3,407 MiB |

Two facts worth pricing into capacity planning:

1. **Long requests serialize behind the single decode slot** (the qwen
   child decodes one inference at a time), so walls grow linearly with
   queue depth. The 5th concurrent 300 s request finished at 422 s —
   just inside the 450 s gateway deadline. **~4–5 in-flight 300 s
   requests is this deployment shape's honest concurrent ceiling**;
   beyond that the gateway times out truthfully rather than hanging.
   More long-audio capacity means replicas, not patience.
2. **The RSS retention PLATEAUS.** After serving the entire day's load
   (drills, Web runs, a 100-request ladder, and 9 concurrent long
   requests), the child sat at ~3.4 GiB peak — it did not continue
   toward the unbounded growth the §9 trend alone could not rule out.
   Plan ~4 GiB steady-state per busy long-audio slot on this build.

## 19a. Failure-safety matrix (Phase 19)

Every spec case, with its evidence. No scenario returns a successful
partial transcript — the chunked loop either completes every window or
raises, and the raise carries no fragment of text.

| # | Case | Evidence | Outcome |
|---|---|---|---|
| 1 | windows 1..n all succeed | deterministic 3-window test; staging 300 s | one merged result, segments join == text |
| 2 | a window fails once, retry succeeds | `@fail`-then-ok test; **live kill at 35 s** | complete transcript; one 12 s retry pause |
| 3 | a window fails twice | fail-twice test (message carries no text, no "chunk"/engine words) | whole request fails; usage `failed`/0; no sample |
| 4 | child dead before window 1 | slot-readiness refusal test (M15E) + M18 outage drill | immediate NOT_READY, never queued |
| 5 | child dies during a window | `@truncate` tests (drill-found fix) + **live kills at 35 s / 100 s** | recovery (complete transcript) or clean whole failure |
| 6 | child dies during the FINAL window | final-window fail-twice test | whole failure; earlier windows' text does not escape |
| 7 | request timeout | per-window timeout mapped to clean INTERNAL (M15E test); gateway 450 s deadline sized above worst measured wall (§7) | bounded, honest |
| 8 | malformed window response | malformed-body test → INTERNAL, retried like any window failure | clean |
| 9 | empty window response (silence) | silent-window test | valid result; no empty segment |
| 10 | all windows complete (600 s / 7) | sandbox ×3, staging, Web | complete, billed once |

## 19. Risks

- **Concurrent long-audio ceiling:** ~4–5 in-flight 300 s requests per
  deployment before the 450 s deadline starts refusing tails honestly
  (§18, measured). Production long-audio adoption needs either queue
  admission tuned for long requests or replicas — an ops decision to
  make BEFORE promotion, with VPS-hardware numbers.
- **Memory steady-state:** ~3.4–4 GiB per busy long-audio slot (the
  pinned build retains buffers; plateau measured, §18). The supervisor
  makes a periodic recycle a one-line policy if VPS numbers differ.
- **Seam duplication under decode variance** (bounded, measured ≈+0.5%
  over-emission; §17) — the failure mode is a repeated phrase, never
  lost audio.
- **Merge horizon:** overlap dedup looks 14 words back; pathological
  ultra-fast speech could exceed it across a 5 s overlap. Same failure
  mode as above.
- **The admission lease (now 540 s)** was found BELOW the deadline
  during this milestone (180 < 300) — the invariant is restored and
  documented at the setting itself; regression here would reopen
  silent over-admission.

## 20a. Security / leak checks (Phase 20)

| Check | Result |
|---|---|
| Internal names in public responses | ZERO across every drill: the marker set (`qwen, llama, gguf, ggml, whisper, ctranslate, faster` — plus `chunk, window` for the drills) scanned every staging/kill/Web response body and the entire rendered Studio page. The engine's error messages name nothing internal by construction (tested). |
| Chunk details in public errors | the whole-request failure message ("transcription of the full audio could not be completed") carries no window count, index, or fragment of text (tested). |
| Private audio files for chunks | none exist: windows are in-memory PCM byte-slices; the engine writes nothing to disk (no temp files, no ffmpeg per chunk — code-level fact, exercised by every proof). |
| Secrets in logs/evidence | gateway logs carry `key_id`, never keys; the staging key lives only in the operator's environment; no committed file or evidence JSON contains it (gitleaks hook on every commit). |
| Duplicate metering / samples | usage deltas were EXACT on every drill (+1/+300.0, +1/+600.0, +1/0.0-failed); one sample per contributed success, none on failure or opt-out. |
| Description surface | `describe()` reports the chunk geometry as plain numbers; the no-path-leak test covers the new keys. |

## 20. Remaining limitations

1. **Android long audio is formally unsupported** — the shipped
   client's okhttp budgets (read 120 s / call 150 s) predate long
   audio; 300 s is marginal and 600 s impossible until a deliberate
   client release (§12). Short dictation unaffected.
2. **Seam duplication under decode variance** — a few short
   near-duplicate phrases per long request where adjacent windows
   transcribed the shared overlap differently; bounded (≈+0.5%
   over-emission), measured, included in every CER reported here.
3. **No word-level timestamps** in chunked segments — attribution is
   window-level (real offsets); this lineage emits no alignments.
4. **llama-server memory retention** — the pinned build retains RSS
   across sequential window decodes (1.5 → ~4 GiB over a sustained
   battery). A capacity fact, not a request-visible defect; the
   supervisor makes a recycle policy a one-line ops decision if VPS
   measurements demand one.
5. **Exact-text nondeterminism of the backend** (llama.cpp CPU
   threading; CER band ≤0.0017 across repeats) — pre-existing, 15E-
   documented; chunking adds none of its own.
6. **Long-audio walls measured on Windows only.** The Linux runtime is
   pin-identical and quality-identical (M17), but 300/600 s walls were
   not re-measured on Linux/VPS hardware in this milestone.

## 21. What is deferred

- Android long-audio UX (client timeout redesign) — forbidden here.
- Production promotion of hi→qwen3 — a founder ledger decision.
- Word-level alignment (separate aligner model in this lineage).
- Streaming/background transcription jobs — explicitly out of scope.
- A variance-tolerant overlap merge (would shrink seam duplication
  further; the exact-match merge is the approved, measured design).
- VPS-hardware long-audio characterization (with the M17 Linux
  scripts) before any production promotion.
