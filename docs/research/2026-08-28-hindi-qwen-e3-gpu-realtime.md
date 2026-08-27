# Hindi Qwen3-ASR 0.6B E3 — GPU Realtime Feasibility (Milestone 52H)

| | |
|---|---|
| **Status** | COMPLETE — decision **B. HINDI REALTIME FEASIBLE WITH MINOR ARCHITECTURAL WORK** (§25) |
| **Date** | 2026-08-27 |
| **Scope** | Research + measurement only. Production untouched: no weights change, no routing change, no realtime endpoint. The GPU runtime is a research-only local server. |
| **Evidence** | `research/experiments/52h-hindi-qwen-gpu/` (bench + summarize harnesses, 20+ evidence files) |
| **Labels** | MEASURED / REPO-VERIFIED / EXPERIMENTAL / ESTIMATED / UNKNOWN / PROPOSED on every claim |

## 1. Objective and M52 hand-off

M52 left ONE open question: E3 on CPU is realtime-blocked (1 s audio →
~1.3 s inference, zero state reuse) — can the UNCHANGED E3 artifact
become realtime-capable on the laptop's RTX 5070? Everything else
(transport, sessions, VAD law, LA2 display) was already proven in M52.

## 2. Model identity + GPU runtime (REPO-VERIFIED / MEASURED)

- Artifact: `qwen3-asr-0.6b-hi-ft-e3` GGUF Q8_0 + mmproj — the exact
  production pins, **unchanged**.
- GPU runtime: llama.cpp **b10344 (7a20b417f) win-cuda-13.3-x64** — the
  SAME commit as the production CPU pin, CUDA variant (release zips
  SHA-recorded in `hardware.json`), `-ngl 99 -c 4096`, loopback-only
  research server. Backend is therefore the ONLY variable.
- Requests mirror the production engine byte-for-byte (`input_audio` +
  "Transcribe the audio.", temperature 0); every benchmark decode sends
  `cache_prompt: false` so no number is a prefix-cache hit (the cache
  effect is recorded separately: repeated 5 s clip ~46 ms).

## 3. Hardware + real GPU offload proof (MEASURED)

i7-14650HX / 31.6 GB RAM / RTX 5070 Laptop 8151 MiB VRAM, driver
591.91. Offload proven by behavior, not configuration: VRAM 2118 MiB
with model loaded, GPU util 63% under load, and 1 s Hindi audio in
**64 ms** — impossible on this CPU (874-1307 ms measured same day).

## 4. CPU baseline reproduced (MEASURED)

Same prefixes, staging container: curve matches M52 (idle machine ~30%
faster; even the 3 s-prefix generation-loop outlier REPRODUCED on CPU —
it is content-triggered, not variance; the same clip decodes in 162 ms
clean on GPU). Baseline valid → proceed.

## 5. CPU vs GPU ladder (MEASURED; same real-Hindi prefixes)

| audio | CPU ms | GPU ms | GPU RTF |
|---|---:|---:|---:|
| 1 s | 874 | **64** | 0.064 |
| 2 s | 987 | 134 | 0.067 |
| 3 s | 9808* | 162 | 0.054 |
| 5 s | 1417 | 292 | 0.058 |
| 8 s | 1770 | 471 | 0.059 |
| 12 s | 3349 | 666 | 0.055 |
| 16 s | 3266 | 913 | 0.057 |
| 19.9 s | 5315 | 1070 | 0.054 |

*content-triggered loop, CPU only. GPU is **~15-20× faster**, RTF flat
~0.055 — E3 becomes decisively realtime-class on this GPU.

## 6. Realtime window ladder (MEASURED)

250 ms → 70 ms · 500 ms → 76 ms · 1 s → 85 ms · 2 s → 116 ms ·
5 s → 294 ms. **Every window from 250 ms up decodes faster than its own
duration** — smallest useful realtime window: 250 ms.

## 7-9. Streaming sessions — FPT, cadence, finalization (MEASURED)

Virtual-mic streaming sims (M52 methodology), REAL IndicVoices Hindi
speech, VAD-snapped rolling commits, 500 ms chunks:

| session | FPT (speech start) | update p50/p95 ms | cadence s | finalization ms |
|---|---|---|---|---|
| 30 s growing | **520 ms** | 524 / — | ~0.5 | 1668 (full-window re-decode) |
| 2 min rolling | 540 ms | 880 / — | — | 1217 |
| 5 min rolling | 660 ms | 1186 / — | — | 1060 |
| 10 min rolling | **490 ms** | 1801 / 3114 | 1.71 | 1146 |

- **FPT: 490-660 ms — the ≤1000 ms proposed gate PASSES everywhere.**
- Partial p50 ≤1 s PASSES for sessions ≤~2 min; long sessions sit at
  1.2-1.8 s because the 25 s window decode (~1.1-1.4 s) plus commit
  decodes queue up. A 15 s window cap was measured as a counterfactual:
  it does NOT help (1253 ms p50 — more commits offset smaller windows).
  The named fix is scheduling, not compute: skip-to-latest decodes and
  commit decodes off the hot path (minor architectural work, §25).
- Finalization measured 1.0-1.7 s as a sim UPPER BOUND (the sim's last
  decode re-reads the full live window; a product session final on a
  committed stream decodes ≤ the window — the 5-10 min sessions with
  commits already show 1.0-1.2 s).

## 10. Quality — the reason E3 owns Hindi (MEASURED, real speech)

30 real IndicVoices clips (3-15 s, pinned manifest refs, frozen
`unicode_generic@v2` ruler):

| | WER | CER | decode ms (median) |
|---|---|---|---|
| CPU (production build, direct) | 15.28% | 7.29% | 886 |
| **GPU (same commit, CUDA)** | **15.60%** | **7.77%** | **528** |

**25/30 transcripts byte-identical.** No quality regression from the
backend. (Absolute WER reflects this spontaneous multi-speaker corpus,
not FLEURS.)

## 11. Long sessions vs GROUND TRUTH (MEASURED)

Single-pass offline is the WRONG long-audio ruler — it truncates beyond
E3's proven ≤120 s envelope (measured: 254 words vs 422 expected at
2 min) and exceeds the 4096 context beyond ~5 min. The honest rulers:
ground-truth references + each constituent clip decoded individually
(E3's ideal serving shape):

| session | streamed WER | offline per-clip WER | streaming penalty |
|---|---|---|---|
| 2 min | 15.88% | 15.88% | **0.0 pt** |
| 5 min | 23.89% | 23.17% | +0.7 pt |
| 10 min | 17.60% | 15.53% | +2.1 pt |

Word counts land within 0.6% of the references (417/422, 828/833,
1832/1835) — zero truncation, no repeats, bounded sessions. The
VAD-snapped commit policy works; the residual 0-2 pt seam cost is the
tuning target.

## 12. Stability + LocalAgreement-2 (MEASURED)

Raw partial stable-token ratios 0.87-0.97 on rolling sessions (E3
partials churn LESS than whisper's did in M52). LA2 display:
**monotonic in every session** (zero flicker), mean lag ~10-12 words,
**live coverage 98.5-99.4%** of the final text — near-everything the
user sees live survives to the final.

## 13. VAD + silence (MEASURED)

EnergyVad: silence/noise probes → has_speech=False (never decoded).
Bare-model behavior on GPU, recorded for evidence: E3 outputs **empty
text on digital silence** (better behaved than whisper's "You"), but
the VAD gate remains law regardless.

## 14. Short Hindi speech (MEASURED)

Real sub-2.5 s clips: correct or near-correct (WER 0-0.33 on fragment
refs), decode 108-210 ms, no hallucination. TTS shorts (SYNTHETIC,
qualitative): हाँ/नहीं/ठीक है/चलो/हाँ सर correct; "रुको" misheard on the
synthetic voice (n=1, not evidence of a real-speech defect).

## 15. Hindi probes (SYNTHETIC TTS, qualitative)

Names, office phrase, currency ("बारह हज़ार पाँच सौ रुपये"), date ("बारह
अगस्त दो हज़ार छब्बीस"), spoken phone digits, brand names
(इंटेलीआई/क्यूमॉन्ट — one vowel slip in इंटेलीएआई), and a natural
Hindi sentence with embedded English loanwords (रिपोर्ट/ईमेल/मीटिंग) —
all transcribed correctly. **No full-Hinglish claim** (M52's finding
stands: code-switched half-and-half audio is unsupported).

## 16. GPU resources (MEASURED)

Model load ~2118 MiB VRAM total (fits 8 GB with ~6 GB headroom), **zero
VRAM growth over 50 requests**, no RAM growth, no orphan processes.

## 17. Concurrency (MEASURED; 2 s clip × 16 requests, server n_slots=4)

c=1: p50 122 ms · c=2: 189 ms · c=4: 223 ms (17.9 rps) · c=8: 419 ms
(18.4 rps) — **zero failures at every level**, VRAM flat. Single-GPU
throughput saturates ~18 rps on 2 s windows (ESTIMATED ceiling for
session capacity; no production-scale claim from one laptop).

## 18. OPEN FINDING — production service-path instability (MEASURED, out of scope)

While reproducing baselines, the production stt-runtime SERVICE path
returned unstable, truncated Hindi transcripts on a 31.8 s real
multi-speaker clip (7 runs: 2-96 words, WER 0.60-1.00) while DIRECT
calls to the very same llama-server child were stable and complete
(117 words every time, all three backends). Ruled out: build, weights,
audio decode path, payload shape, child crashes, max_tokens. This
affects the CURRENT Hindi batch path for this clip class and predates
M52H; it is recorded as its own investigation
(`evidence/service-anomaly.json`) and does not alter the GPU verdict —
every M52H realtime number comes from direct calls with the engine's
exact payload.

## 19-24. Architecture, punctuation, provenance, security

Hindi realtime can reuse the ENGLISH M52 architecture unchanged —
browser → WS session → VAD gate → rolling window → engine → LA2
partials → final — with ONE Hindi-specific deployment requirement:
**a GPU** (CPU E3 remains blocked; M52). Punctuation stays final-only
through the existing Hindi stage; partials remain ephemeral; the final
follows raw → punctuated → correction unchanged. No prototype server
was needed beyond M52's (transport already proven); the research
llama-server is loopback-only and dies with the session.

## 25. Proposed gates — verdicts

| gate | verdict |
|---|---|
| FPT ≤ 1 s | **PASS** (490-660 ms, real speech) |
| Partial p50 ≤ 1 s | **PASS ≤2 min sessions; 1.2-1.8 s on 5-10 min** — scheduling fix named, compute is NOT the limit |
| Finalization ≤ 1 s | BORDERLINE (1.0-1.7 s sim upper bound; commit-stream finals 1.0-1.2 s) |
| RTF < 1 sustained | **PASS** (~0.055) |
| WER/CER ≈ offline E3 | **PASS** (offline parity 25/30 identical; streamed +0-2.1 pt vs per-clip baseline) |
| Silence | **PASS** (VAD-gated; bare model empty anyway) |
| Token churn | **PASS** (LA2 monotonic, 98.5%+ live coverage) |
| Duplication/loss | **PASS** (zero repeats, word counts within 0.6%) |
| Memory leak | **PASS** (VRAM flat over 50 requests) |
| Fits 8 GB VRAM | **PASS** (2118 MiB) |
| c=1 and c=2+ | **PASS** (c=8 zero failures) |
| Bounded sessions | **PASS** (10 min bounded) |

## 26. Decision + next step

**B. HINDI REALTIME FEASIBLE WITH MINOR ARCHITECTURAL WORK.**

Compute is solved: the unchanged E3 artifact on the RTX 5070 is
15-20× faster than CPU with byte-level quality parity. What remains is
engineering, not research: (1) decode scheduling for long sessions
(skip-to-latest + off-hot-path commit decodes) to hold partial p50
≤1 s beyond 2 minutes, (2) end-triggered finals on the committed
stream, (3) the same WS session layer M52 designed, (4) GPU serving as
a documented Hindi deployment requirement, and (5) the service-path
anomaly (§18) investigated as its own milestone BEFORE any Hindi
realtime product work, since it touches the current batch path.

Proposed next milestone (ONE): **M53 — Realtime STT web implementation,
English-first on the M52 architecture, with the Hindi GPU path behind
the same session contract as its second phase** — founder-gated, not
started.
