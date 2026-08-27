# Realtime STT Streaming — Research + Feasibility (Milestone 52)

| | |
|---|---|
| **Status** | COMPLETE — decision **B. REALTIME STT FEASIBLE WITH ARCHITECTURAL CHANGES** (§32) |
| **Date** | 2026-08-27 |
| **Scope** | Research/feasibility only. No production change; the prototype lives in `research/experiments/52-realtime-stt/prototype/` behind its own auth, its own port, its own process. |
| **Evidence** | `research/experiments/52-realtime-stt/` (hardware.json + 30 evidence files) |
| **Labels** | Every claim tagged MEASURED / REPO-VERIFIED / WEB-RESEARCHED / USER-PROVIDED / EXPERIMENTAL / ESTIMATED / UNKNOWN / PROPOSED |

## 1. Objective

Can the CURRENT IntelliAI STT stack support a reliable realtime
transcription experience (partials while speaking, final on stop), and
what is the right architecture? Sarvam's realtime playground is the
qualitative UX reference (USER-PROVIDED screenshot only — no Sarvam
credentials exist; nothing Sarvam-quantitative appears anywhere here).

## 2. Current architecture (REPO-VERIFIED)

Browser mic → `MediaRecorder` (webm/opus) → ONE complete blob →
`POST /v1/audio/transcriptions` (gateway, Bearer auth) → stt-runtime
`POST /v1/transcribe` (multipart WAV + params) → pipeline
`validate → detect → decode(ffmpeg) → normalize → vad → engine` →
(>120 s: in-engine windowing + seam merge, M19) → punctuation stage(s)
→ ONE response (`text` + `raw_text`). Text first exists only after the
complete clip is ingested. There is **no WebSocket/SSE/streaming
abstraction anywhere** in gateway or runtimes today.

## 3-4. Model streaming capability — Qwen3-ASR 0.6B E3 (REPO-VERIFIED + MEASURED)

- Serving: pinned llama.cpp `llama-server` child + mtmd audio projector;
  the engine sends ONE WAV per completion request. **No incremental
  audio API, no partial output, no reusable audio/KV state between
  requests** (REPO-VERIFIED: `engines/qwen3_asr.py`; llama.cpp mtmd has
  no streaming-audio entry point in the pinned build). A realtime
  update therefore costs a FULL re-inference of the window.
- MEASURED cost ladder (real Hindi prefixes, staging container, CPU;
  `evidence/qwen-ladder.json`): 1 s audio → **1307 ms**; 2 s → 1614 ms;
  5 s → 2086 ms; 8 s → 2716 ms; 16 s → 4579 ms; 19.9 s → 7546 ms
  (one 3 s-prefix outlier at 14.5 s — server variance, recorded).
- Cadence crossings (MEASURED): windows decodable within a 500 ms
  budget: **none**. Within 1000 ms: **none**. Within 2000 ms: only 2 s.
- Verdict: **E3-on-CPU cannot produce realtime partials.** Even 1 s
  updates arrive slower than the audio they describe (RTF > 1 at short
  windows; llama.cpp fixed per-request overhead dominates).

## 5. Whisper-small capability (REPO-VERIFIED + MEASURED)

- faster-whisper/CT2: also **no incremental state API** — but a full
  window re-decode is CHEAP: Linux CPU (production-parity WSL2, same
  1.2.1 pin) decodes 0.5 s in ~0.9 s, 30 s in ~2.6 s (RTF p50
  0.09-0.12). A fixed encoder pass (whisper pads every input to a 30 s
  mel window) sets the ~0.85-1.0 s per-update floor on CPU.
- Windows-native CT2 is ~3× slower (30 s → 7.6 s) — all CPU numbers
  here are Linux (MEASURED; `hardware.json`).
- **Whisper is the realtime-capable current engine; E3 is not.** The
  goal is not replacing Qwen — Hindi final quality stays E3's; §15.

## 6. Audio chunk design (MEASURED; boss30 clip, growing window, beam 5)

| chunk | FPT ms | update p50 ms | cadence s | stability |
|---|---|---|---|---|
| 50 ms | 2000 | 1213 | 1.26 | 0.74 |
| 100 ms | 2100 | 1320 | 1.26 | 0.65 |
| 200 ms | 2020 | 1601 | 1.50 | 0.62 |
| 300 ms | 1340 | 1589 | 1.54 | 0.61 |
| 500 ms | 3160 | 1790 | 1.56 | 0.45 |
| 1000 ms | 2160 | 1994 | 1.55 | 0.59 |

Chunk size barely matters on CPU — **the decode time (~1-1.3 s) is the
cadence**, not the chunk. Policy (PROPOSED): transport frames 100 ms
PCM16 (3.2 KB ≈ 32 kbps — trivial bandwidth), decode step ≥ 500 ms of
new audio. Streamed final text was byte-equal to the offline decode in
EVERY ladder run (WER vs offline 0.0).

## 7-9. FPT, partial cadence, finalization (MEASURED)

- **FPT** (first useful text): CPU 1.3-3.7 s (content-bound too — the
  first words must exist; boss speech onset 0.36 s). Proposed ≤1000 ms:
  **CPU misses**; GPU: text appeared 92.6 ms after 1.0 s of audio
  existed (content-bound, compute negligible) — **GPU passes**.
- **Partial update latency**: CPU p50 1.2-2.0 s; GPU p50 446 ms.
- **Finalization** (stop → final): WS prototype with rolling commits:
  **286 ms** (boss30, CPU, real transport). Growing-window worst case
  3.4-4.0 s (full 30 s beam-5 re-decode) — the rolling/commit policy is
  what keeps finals under the proposed 1 s. GPU final: 974 ms full
  30 s window. PROPOSED gate ≤1 s: passes with the rolling policy.

## 10. Transcript stability (MEASURED)

Raw partials churn: consecutive-partial stable-token ratio mean
0.45-0.74 (beam 5) and 0.19 (greedy) — whisper re-hears the tail as
context grows. **Display fix measured**: LocalAgreement-2 (show only
the word-prefix where the last two decodes agree, never shrink):
**monotonic in every run** (zero flicker), mean lag 6.2-6.5 words,
71-75% of the final text visible live (`la2-metrics-*.json`). Greedy
partials + LA2 display ≈ beam-5 partials + LA2 — so partials can run
greedy (cheaper) with no user-visible cost.

## 11. Duplication / loss (MEASURED)

Rolling-window commits (25 s window, 5 s margin): zero adjacent 3-gram
repeats in every run; long-session word counts scale linearly (48 / 241
/ 622 / 1223 words for 30 s / 2 / 5 / 10 min). Final-vs-offline WER on
long sessions: 4.2% / 3.4% / 2.4% — commit-seam divergence, the same
class M19 solved for batch with quiet-moment snapping. **Fix identified
(PROPOSED, not built): align commits to VAD-silent regions.** boss30
single-window runs: 0.0 divergence.

## 12. Short speech (MEASURED)

"hello / yes / no / okay / call me / stop" (1.1-1.4 s): every final
correct, **zero hallucination** through the sim. FPT ~2 s, final
~2.5-2.8 s on CPU (decode-queue bound; the prototype's end-triggered
final is faster). M48's 1 s-ambiguous-audio "Thank you." class: not
reproduced on these clear clips; the VAD gate below is the guard.

## 13. Silence (MEASURED)

Model alone DOES hallucinate on silence ("You" on digital silence AND
on pink noise — `silence5.json`/`noise5.json`). The production
`EnergyVad` correctly reports has_speech=False on both (MEASURED
directly), and the prototype refuses to decode a speechless window →
**zero inference, ~zero CPU during silence**. Law for any realtime
implementation: every window decode is VAD-gated (the M52 prototype
already does this).

## 14. Long continuous speech (MEASURED, rolling window)

| session | cadence s | stability | WER vs offline | repeats | RSS MiB |
|---|---|---|---|---|---|
| 2 min | 1.66 | 0.81 | 0.042 | none | 864 |
| 5 min | 1.73 | 0.90 | 0.034 | none | 1255 |
| 10 min | 1.82 | 0.94 | 0.024 | none | 886 |

No unbounded memory growth (10 min ended BELOW 5 min's transient
peak), no transcript-growth bug, no drops, no session degradation.

## 15. English / Hindi / mixed (MEASURED, mix rows n=1 EXPERIMENTAL)

- English: everything above.
- Hindi realtime via E3: **blocked on CPU** (§3). Hindi realtime via
  whisper-small-hi partials + E3 final is architecturally possible but
  whisper-hi quality was already judged below E3 (that is WHY E3 owns
  the route) — quality-gated, not measured here.
- Mixed (TTS-built Hinglish clip, qualitative ROUTE behavior only):
  hi-route dropped the English half and looped the Hindi sentence;
  en-route dropped the Hindi half; English-only audio on the hi-route
  transliterated to Devanagari at RTF 8.3 (pathological, M48-known).
  **No Hinglish support is claimed. None exists.**

## 16. Punctuation interaction (design, MEASURED costs)

Final-only punctuation is correct: partials display raw (unpunctuated,
LA2-stable), the FINAL raw transcript passes through the existing M50
stage exactly as today (45-200 ms, M50/M51 MEASURED; the M51
engine-already-punctuated stand-down law applies unchanged). No
punctuation-streaming system is needed or proposed for v1.

## 17. Provenance (design)

Partials are EPHEMERAL display events — never persisted, never part of
provenance. The session's final raw transcript enters the EXISTING
chain unchanged: raw → punctuated → human correction; the collection/
consent path sees exactly one final sample, same as an upload.

## 18. Session model (MEASURED via prototype)

`session.started {session_id}` → binary PCM frames in /
`transcript.partial {session_id, text, sequence, is_final:false}` out →
`{"event":"end"}` → `transcript.final` → `session.completed`. Session
id minted per connection, stamped on every event; sessions share
nothing. Start→stop→start-again: second session has a new id, first
never finalizes, **no stale text leaked** (`ws-restart.json`).

## 19. Disconnect / reconnect (MEASURED behavior, policy PROPOSED)

Mid-stream disconnect kills the session cleanly (nothing finalized,
nothing leaked). **No seamless resume is promised — none exists.**
PROPOSED product policy: on reconnect the client starts a NEW session;
a client that kept its local audio can fall back to the existing HTTP
upload for a complete final. Tab-sleep / mic-permission loss = the
same disconnect path (browser-side; UNKNOWN exact browser timings —
implementation-phase testing).

## 20. Backpressure (MEASURED)

Flood at 8× realtime (120 s of audio in ~10 s): the prototype emitted
**`session.degraded`** (loud, at the 60 s unprocessed ceiling), kept
every frame, and the final covered the COMPLETE audio 9.5 s later —
lagged, never silently dropped. Policy (PROPOSED): bounded buffer +
degraded event + complete-but-lagged final; a hard cap beyond that
closes the session with an explicit error, never a quiet truncation.
(The first prototype build mislabeled a mid-stream partial as final
under flood — caught by this very probe and fixed; the event contract
must capture finality at decode-start, a real implementation lesson.)

## 21-22. Current Qwen performance / CPU vs GPU (MEASURED)

- Qwen E3 CPU: compute time > audio duration at every realtime window
  size (§3) — continuous realtime impossible without state reuse or
  acceleration. GPU E3: **UNMEASURED** (no CUDA llama.cpp build pinned;
  a rented-GPU/M53 measurement item).
- Whisper-small GPU (RTX 5070 Laptop, WSL CUDA, fp16 — MEASURED):
  0.5 s window 71 ms (greedy) / 118 ms (beam 5); 30 s window 514/659 ms.
  Streaming sim: update p50 446 ms, FPT compute-cost 93 ms
  (content-bound ~1.1 s), final 974 ms. **Every proposed gate passes on
  GPU.** CPU remains viable for a ~1.5 s-cadence English experience.

## 23-24. Prototype + event contract (MEASURED)

Isolated WS prototype (FastAPI, shared-secret before accept, VAD-gated
greedy partials, rolling commits, bounded buffer) + mic-paced client:
realtime boss30 through REAL transport: 20 partials, cadence 1.53-1.59 s,
final 286 ms after end. The §18 contract is PROPOSED for the product;
the current gateway has no WS layer — a new session endpoint/adapter
service is the architectural addition (Caddy proxies WebSocket fine).

## 25-26. Security & privacy (design + MEASURED probes)

Auth before audio (wrong/no token refused at handshake — MEASURED);
session-scoped state only; events carry no model name/path/exception;
buffer bounded. Privacy: frames processed in memory only; partials
never persisted; final sample follows the EXISTING consent/contribution
semantics unchanged; disconnect/cancel discards the buffer. Realtime
must NOT silently widen persistence — pinned as a design law for M53.

## 27. Cost model (ESTIMATED from single-session measurements, one laptop)

- CPU EN session: ~1.1 s decode per ~1.6 s cadence ≈ 0.7 duty × ~4 CT2
  threads ≈ **~3 thread-equivalents/session** → order 6-8 concurrent
  realtime sessions on a 24-thread box before lag (ESTIMATED; no
  multi-session run was performed).
- GPU EN session: 71-450 ms compute per 1 s cadence → order 10-20
  sessions per RTX-5070-class GPU with a serialized queue (ESTIMATED).
- Bandwidth: 32 kbps/session up, KB-scale events down (computed).
- RAM: model shared; per-session buffers MB-scale (MEASURED RSS §14).

## 28. Sarvam reference (USER-PROVIDED QUALITATIVE)

The supplied screenshot shows: WebSocket type, `saaras:v3-realtime`,
16 kHz query param, ~100 ms base64 PCM chunks via a persistent
connection, `transcript.partial` / `transcript.final` events, a
latency-vs-accuracy "stream type" knob. This matches the architecture
family M52 measured. **No Sarvam latency/WER/capacity is reported —
credentials do not exist.**

## 29. Proposed gates — measured verdicts

| gate (PROPOSED) | CPU (Linux, whisper-small) | GPU |
|---|---|---|
| FPT ≤ 500 / ≤ 1000 ms | MISS (1.3-3.7 s) | PASS (compute 93 ms; content-bound ~1.1 s) |
| Final ≤ 1 s | PASS with rolling commits (286 ms); MISS growing-window | PASS (974 ms worst) |
| Stability | PASS via LA2 display (monotonic, lag ~6 words) | PASS (same policy) |
| Long speech bounded | PASS | not run (expected PASS) |
| Accuracy vs offline | PASS short (0.0); 2-4% commit-seam delta long — VAD-aligned commits to close | — |
| Silence | PASS (VAD-gated; model alone hallucinates) | same law |
| Sessions / backpressure / auth | PASS / PASS / PASS | — |

## 30-31. Decision + next milestone

**B. REALTIME STT FEASIBLE WITH ARCHITECTURAL CHANGES.**

What the evidence says: the current ENGINES need no replacement for
English — whisper-small re-decode streaming works today; what is
MISSING is architecture: (1) a WebSocket session layer (none exists),
(2) the rolling-commit + VAD-aligned-seam policy, (3) the LA2 display
law, (4) VAD gating per window, (5) GPU serving IF the product wants
Sarvam-class sub-second partials (CPU gives an honest ~1.5 s-cadence
dictation UX; the FPT gate only passes on GPU). Hindi realtime is
blocked at the engine layer (E3 CPU RTF > 1; GPU E3 unmeasured) —
Hindi stays batch until its own milestone.

**Proposed M53 — Realtime English STT, local web implementation**:
WS session endpoint (gateway-adjacent adapter), whisper-small greedy
partials + beam-5 final, VAD-aligned commits (kills the 2-4% seam
delta), LA2 display in the Playground, final through the existing
provenance/punctuation/consent path, flag OFF, staging battery; GPU
serving measured as its explicit latency lever (incl. the E3-GGUF
CUDA question for Hindi's future). Not started — founder gate.

## 32. Deviations & limitations

- All numbers from ONE laptop (i7-14650HX / RTX 5070 Laptop); no
  multi-session load test; production-box re-measurement required at
  implementation time.
- Streaming sims assume one decoder slot and virtual mic timing (real
  compute); the WS prototype validated the numbers through real
  transport within ~0.2 s.
- Long-speech material = looped boss clip (only continuous real speech
  available); Hinglish probes are synthetic TTS audio, n=1, ROUTE
  behavior only.
- `condition_on_previous_text=False` used for streaming decodes
  (anti-loop standard); production batch path uses engine defaults —
  byte-parity on boss30 held anyway (WER 0.0 vs offline).
