# English TTS Model Selection — Incumbent vs the 2026 Field (Milestone 33)

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — recommendation at §21-22; nothing ships in this milestone (no runtime, API, billing, client, catalog, or deployment change) |
| **Date** | 2026-08-20 |
| **Question** | "Should we keep our current Kokoro English TTS, or is there a better small English TTS model that we should implement locally?" |
| **Evidence** | `research/experiments/33-english-tts-selection/` (fixed EN probe set, instruments, evidence JSONs) · M32 evidence where texts are shared · sources verified at origin 2026-08-20 |
| **Labels** | VERIFIED FROM REPO · MEASURED (this machine, this week; timing rows from solo serialized runs) · WEB-RESEARCHED · ESTIMATED · UNKNOWN · PROPOSED |

## 1. Current English TTS — VERIFIED FROM REPO (traced, not read from docs)

| Fact | Value |
|---|---|
| API | `POST /v1/audio/speech` (`apps/api/src/intelliai_api/api/v1/audio/speech.py` → `SpeechRequest{model, input(min 1), voice?, speed>0, response_format:"wav"}`, `extra="ignore"`, no public language field — the voice is the routing key) + `GET /v1/audio/voices` |
| Service | `services/speech.py::SpeechService.synthesize` → `SpeechOutcome{audio, media_type="audio/wav", public_model_id, voice, characters, audio_seconds}` |
| Runtime | `services/tts-runtime` (ADR-0018 template): WorkerPool 2 exec + 8 queue → `TextPipeline` validate(2000 chars)→normalize(**pass-through — NO text normalization exists in v1**)→voice resolve → engine |
| Engine | `engines/kokoro.py::KokoroEngine` — Kokoro-82M v1, 4 SHA-256-pinned files from `hexgrad/Kokoro-82M`, re-hashed every boot; misaki EN G2P, `fallback=None`; GPL espeak chain poison-stubbed + uninstalled; **image build fails if espeak is importable** |
| Model / voices | kokoro-82m v1 · public `reference-alto`→af_heart (F), `reference-bass`→am_michael (M) — placeholders pending founder naming |
| Audio contract | mono · 16-bit PCM · WAV · **24 000 Hz** · whole body (unstreamed → TTFA = full response) · errors always JSON · envelope header internal-only (≤4096 B) |
| Billing | `characters` @ $0.000015 ($15/M), free-plan quota 1M; `audio_seconds` also written "measured, not billed" — see §23 finding |
| Deployment | compose `profiles: [tts]` (dormant; `make up-tts`); **absent from prod/local-prod/staging overlays**; not in `seed-models`; gateway health roster deliberately excludes it; catalog serves 503 `runtime_unavailable` when absent |
| Clients | **No Web/Android/iOS TTS client exists** — console card is "Coming Soon"; the only in-repo callers are tests and the bench harness |
| Tests | 10 runtime suites incl. local real-model tier (`INTELLIAI_RUN_LOCAL_MODEL_TESTS=1`), gateway `test_speech_api.py` (14), registry voice laws, leak-guards (`af_*` ban) |

## 2. Incumbent baseline — MEASURED 2026-08-20 (M33 fixed text set)

The M33 probe set (`probe-texts-en-v1.json`, 25 texts) covers the spec's
A-O categories; texts shared with the frozen corpus/M32 are verbatim for
cross-milestone comparability. Historical context (M3, 2026-08-03):
EN round-trip WER 0.072, RTF 0.19-0.37, ~2.0 GiB, TTFB 814 ms
single-sentence / 2237 ms @122 chars (PRD FAIL beyond one sentence).
This week's re-measurements (M32+M33, same machine, current source):

| Metric (MEASURED, solo runs) | Value |
|---|---|
| Quality — M33 25-probe trap set, gateway path | RT-WER **0.1247** / CER 0.094 (whisper judge) |
| Quality — frozen 25-case corpus (official instrument, M32 re-run) | EN slice RT-WER **0.0759** (M3: 0.072 — reproduced) |
| Where the M33 errors live | **OOV word-drops**: "Hello, Sumit." → "Hello." (the founder's name); Priya/Rajesh/IntelliAI/QwikCart dropped; slash-date spelled as digits. Numbers/currency/% otherwise fine |
| RTF (gateway, Docker) | median **0.283**, p95 0.413; median wall 1.15 s |
| RTF (native WSL torch, same weights) | median 0.16-0.29 across runs — the Docker/WSL tax is real |
| TTFA | = full response (unstreamed by design); PRD <1 s: **FAIL** at 2406 ms on the pinned 120-char sentence (M3 verdict reproduced); single-sentence inputs pass |
| Concurrency ladder c=1/2/4/8 (3 reps) | 0.275 / 0.423 / 0.536 / **0.557 rps** saturation (~4.7 s audio per wall-second); zero refusals through c=8 (pool 2+8 holds); gateway overhead 25.8 ms |
| Model load / warmup (rebuilt image) | 5.1 s + 0.8 s (cold first-boot download ~38 s, M3) |
| Peak RAM | **2.39 GiB** container idle-loaded (torch fp32); 2.29-2.52 GiB native runs |
| Repeated-generation consistency (5×, same text) | **NOT byte-deterministic** (5 distinct hashes) but duration stdev 0.0 s, wall stdev 70 ms — stochastic sampling with stable output length. Consequence: no byte-level caching or byte-equality regression tests; feature-level checks only |
| Output | WAV mono 16-bit 24 000 Hz, whole body; failures on the probe set: **0** |

## 3. Current quality — what is measured vs UNKNOWN

- Intelligibility (machine round-trip through OUR whisper route):
  MEASURED — tables below.
- Automated audio sanity (silence/clipping/duration plausibility):
  carried by the frozen `speech-eval` instrument (M32 re-run:
  clipping 0.0; silence-ratio ~0.35 on EN — leading/trailing pauses,
  not dropouts).
- **Naturalness / prosody / pleasantness: UNKNOWN — no human listening
  has been performed.** The audition pack + rubric ship with this
  milestone ([audition/2026-08-20-en-tts/](audition/2026-08-20-en-tts/README.md));
  scores stay empty until someone listens.

## 4. Model research — the English field, verified at source 2026-08-20

| Candidate | Identity | Size | License (weights / code) | CPU story | Streaming | Verdict for M33 |
|---|---|---|---|---|---|---|
| **Kokoro-82M** (incumbent) | hexgrad, v1.0 2025-01 | 82M / 327 MB fp32 (community ONNX: 86-326 MB, Apache) | Apache-2.0 | MEASURED (production) | chunk-level possible | Benchmarked (incumbent) |
| **Magpie-TTS Multilingual 357M** (NVIDIA) | HF `nvidia/magpie_tts_multilingual_357m`, latest **v2607 (2026-07-21)**; measured artifact: **GGUF v2602 f16 (449 MB) @ rev `452ef560…`** via the runtime's verified pull | 364M AR transformer → **NanoCodec** (22.05 kHz) + local refiner | **NVIDIA Open Model License** (weights, incl. NanoCodec — conditioned-permissive: commercial YES, guardrail-preservation + Trustworthy-AI terms + NVIDIA-may-update-terms; NOT Apache-class) / runtime **NeMo-Speech.cpp Apache-2.0** | **GGUF on ggml — MEASURED here (CPU)**; NeMo python path is GPU-required per card | 20 s/utterance cap + sliding window; HTTP subset is whole-body (no streaming) | **Benchmarked — the spec's special-attention candidate** |
| **Chatterbox-nano** (Resemble) | 110M, EN-only, reference-audio-required, MIT, Perth watermark | 110M | MIT | "3× realtime on 8 cores" (claim) — MEASURED here | none documented | Benchmarked (lightweight challenger) |
| **Supertonic 3** (Supertone) | 99M ONNX, 31 langs | 99M / ~260 MB | **OpenRAIL-M** weights / MIT code | MEASURED (M32 + M33 refresh) | internal chunking, no incremental API | Benchmarked (modern small multilingual) |
| MeloTTS (MyShell) | VITS/Bert-VITS2 lineage; EN-US/BR/**IN**/AU accents | ~50M class | MIT | "CPU real-time" (claim) | none | Not benchmarked: M1.5 scored it below Kokoro; no axis where it plausibly wins today; Indian-English accent noted for the future |
| Piper / piper1-gpl | archived MIT / GPL successor | 20-60M | GPL-3.0 (successor) | excellent (claim) | sentence streaming | Stays exited (M1.5/M32); not re-benchmarked |
| KittenTTS nano | 15M ONNX preview | 15M | Apache weights, GPL espeak in-process | MEASURED (M32): RTF 0.34, WER 0.098, fails >1 k chars | none | Rejected M32 — no niche; not re-run |
| NeuTTS-Air (Neuphonic) | 748M Qwen2-backbone + NeuCodec; GGUF Q4/Q8; llama.cpp-compatible; 3 s voice cloning; Perth watermark | 748M | Apache-2.0 | CPU-realtime claim (GGUF) | unclear | Not benchmarked: 7-9× the incumbent's size — outside the small mandate; noted as the llama.cpp-native cloning option |
| Qwen3-TTS 0.6B | 0.9B actual, 10 langs | 0.9B | Apache-2.0 | GPU-oriented | true streaming (97 ms GPU claim) | Not benchmarked (size class; no CPU evidence; M32 row stands) |
| F5 / XTTS / Fish / MMS-en | — | — | NC / CPML | — | — | BLOCKED (ledger, unchanged) |

## 5. NVIDIA stack — what was verified vs what could not be

- **Supplied references**: the LinkedIn URL resolved to a different post
  (PersonaPlex-7B content — not the speech-stack post), and the YouTube
  video cannot be watched from this environment. **Neither social
  reference was usable as a source; every NVIDIA fact below comes from
  the official HF cards and the official GitHub repo** (as the spec
  instructs for this case).
- **Magpie-TTS Multilingual 357M** (card, 2026-08-20): 364M params;
  12 languages incl. English **and Hindi**; transformer AR over
  NanoCodec tokens + local refinement transformer; 22.05 kHz 16-bit
  mono; **5 preset voices** (Aria, Jason, Leo, Sofia, John Van Stan) —
  zero-shot cloning **removed** "for security reasons"; 20 s/utterance
  (sliding window for long-form); **"text normalization is required"**
  per card; NeMo python inference is **GPU-required** (L4/L40/A10/A30/
  A100/H100 listed); training 54,305 h across 12 langs (public +
  proprietary Riva data); revisions v2512 → v2602 → **v2607 latest**.
- **NeMo-Speech.cpp** (repo, 2026-08-20): Apache-2.0 NVIDIA code on
  ggml/llama.cpp submodules; CPU/Metal/Vulkan/CUDA backends; supports
  Magpie+NanoCodec TTS, Parakeet/Nemotron ASR (out of scope here),
  diarization, NMT, **Sparrowhawk text normalization** (optional
  `-DNEMO_SPEECH_WITH_NORM=ON` + FAR grammars), `synthesize` CLI, HTTP
  server with an OpenAI-compatible `/v1/audio/speech` subset
  (whole-body WAV/PCM — **streaming synthesis is explicitly not in the
  HTTP subset**; `speed` accepts only 1.0), Riva gRPC server. **Very
  young**: 8 commits, 64 stars at verification. Build: CMake ≥3.26,
  C++17, SentencePiece; `cpu-tts` preset builds cleanly in WSL (HTTP
  needs `-DNEMO_SPEECH_BUILD_HTTP=ON`).
- **NanoCodec** (`nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps`):
  the required codec decoder; **also NVIDIA Open Model License** — the
  whole Magpie model stack is NOML even though the runtime is Apache.
- Nemotron Speech Streaming / Parakeet: ASR — out of M33 scope by spec;
  recorded only as context that the same runtime family could host them.

## 6. License audit (Gate-1 discipline; classes per the standing law)

| Component | License (source, 2026-08-20) | Class |
|---|---|---|
| Kokoro-82M weights + kokoro/misaki pips | Apache-2.0 | **CLEAR** (incumbent posture unchanged; espeak stays banned in-process) |
| Community Kokoro ONNX (`onnx-community/Kokoro-82M-v1.0-ONNX`) | Apache-2.0 (community-maintained conversion) | CLEAR — adoption would re-pin + re-verify hashes ourselves |
| **Magpie GGUF + NanoCodec GGUF** | **NVIDIA Open Model License** — commercial use + distribution YES with attribution ("Licensed by NVIDIA Corporation under the NVIDIA Open Model License"); **conditions**: guardrail-circumvention auto-terminates, "Trustworthy AI" terms compliance, litigation termination, **NVIDIA may update terms and continued use requires compliance** | **REVIEW REQUIRED** — conditioned-permissive; the update-clause is the material product risk (a serving dependency whose terms can move) |
| NeMo-Speech.cpp runtime | Apache-2.0 (+ third-party notices) | CLEAR (code) |
| Chatterbox-nano weights + chatterbox-tts pip | MIT | **CLEAR**; note: library watermarks all output (Perth) — a product-disclosure fact, not a license term; reference-audio-required → our voice-asset governance applies (synthetic reference used here, no real voice cloned) |
| Supertonic 3 weights | OpenRAIL-M (code MIT) | **REVIEW REQUIRED** (unchanged from M32) |
| MeloTTS | MIT | CLEAR (not pursued on merit) |
| NeuTTS-Air | Apache-2.0 | CLEAR (size-class excluded) |
| KittenTTS / Piper / F5 / XTTS / Fish / MMS | (M32 verdicts) | Rejected / BLOCKED — unchanged |

## 7. Candidate filtering → the benchmark four

Filter: small (≤~400M), CPU-serviceable today, license not BLOCKED,
plausibly better than the incumbent on ≥1 product axis. Survivors:
**Kokoro (incumbent) · Magpie-357M GGUF/CPU (quality/brand-pronunciation
hypothesis + future Hindi) · Chatterbox-nano (smallest modern MIT
challenger) · Supertonic 3 (lightest RAM, M32 numbers refreshed on the
M33 set)**. Everything else is documented above with the reason it did
not earn a benchmark slot.

## 8. Benchmark methodology

Same texts (25-probe M33 set), same machine (i7-14650HX), same output
handling (16-bit mono WAV; per-engine native sample rate recorded),
same measurement code (M32 instruments reused verbatim: gateway/HTTP
bench, WSL in-process bench, round-trip judge through OUR gateway
whisper route with frozen normalization, prosody analyzer; M33 adds the
consistency probe and the nano adapter). **Timing rows come from solo
serialized runs only** — the M32 contamination lesson is now procedure;
contended first-pass runs are kept in task logs, not cited. Failures
are rows, not crashes. Audio never enters git; the audition manifest
carries SHA-256s.

## 9-15. Benchmark results — MEASURED 2026-08-20 (same texts, same machine, same instruments; solo timing)

**Quality — round-trip intelligibility on the M33 25-probe trap set**
(whisper route judge, frozen normalization):

| Path | RT-WER | RT-CER | The traps, verbatim |
|---|---|---|---|
| **Kokoro + espeak fallback** (research twin of the §21 fix) | **0.0716** | **0.0194** | names/brands SPOKEN; best overall |
| **Supertonic 3** (M1) | 0.0832 | 0.0270 | "Hello, Sumit." **perfect**; "Priya Sharma…Rajesh Ayer" near-perfect; "QX4-921" |
| **Kokoro production path** (espeak-free) | 0.1247 | 0.0940 | "Hello, Sumit."→"Hello."; Priya/Rajesh/IntelliAI/QwikCart dropped |
| **Magpie-357M** (CPU GGUF, John, **no TN grammars**) | 0.1991 | 0.0799 | numbers/dates catastrophic RAW: "1247 dollars"→"cheer dollars", "12/08/2026"→"Elliot Jones", phone→letters; names/brands GOOD ("Intelian Studio", "Quick Cart", "Kavya" clean) |

Magpie's number damage is exactly what its card predicts — "text
normalization is required" — measured here without the optional
Sparrowhawk build; with TN grammars those rows would verbalize first
(UNKNOWN how well — not built this milestone). Its name/brand handling
confirms the AR-frontend hypothesis: nothing is dropped, everything is
attempted.

**Latency / footprint (solo):**

| Path | RTF med | RTF p95 | TTFA | peak RSS | warm load | failures |
|---|---|---|---|---|---|---|
| Kokoro production (Docker, gateway) | **0.283** | 0.413 | = wall (unstreamed); 1.15 s median sentence | 2.39 GiB | 5.1+0.8 s | 0/25 |
| Kokoro native (WSL torch, fallback run) | 0.164 | — | chunk-level possible (M32: 0.68-1.26 s first-chunk) | 2.29 GiB | ~7 s | 0/25 |
| Supertonic 3 | **0.282** | 0.540 | none (single-shot API) | **0.65 GiB** | **1.3 s** | 0/25 |
| Magpie-357M CPU | **1.304** | 1.76 | = wall (HTTP whole-body); 5.4 s median sentence | 1.42 GiB | ~11 s | 0/25 (795-char long-form OK via sliding window) |
| Chatterbox-nano | — | — | — | — | — | **NOT MEASURED — packaging wall** (no released loader; card API absent from code; symlink attempt → architecture shape mismatch). CPU claim stays CLAIMED |

**Concurrency (call-center lens):** incumbent saturates at **0.557
rps ≈ 4.7 s audio/wall-s** on this box (c=1→8: 0.275/0.423/0.536/0.557,
zero refusals through the 2+8 pool). Magpie CPU at c=2/4 aggregates
only ~**1.2× audio/wall-s** (8.5 s wall for 2×5.1 s clips; 16.1 s for
4×4.9 s) — **~4× less capacity per box**, and each stream individually
falls behind live playback (RTF > 1). MEASURED LOCAL; production
capacity is a VPS re-ladder question (ESTIMATED PRODUCTION only via
these ratios).

**Streaming / TTFA:** nobody in the measured set streams over HTTP
today: our v1 is whole-body by design; NeMo-Speech.cpp's OpenAI subset
is whole-body ("streaming synthesis is not part of this compatibility
subset"); Supertonic's API is single-shot; nano undocumented. The only
real streaming stories remain chunk-level Kokoro (first-chunk 0.68-
1.26 s measured in M32) and Qwen3-TTS's GPU token streaming (CLAIMED).
For conversational TTFA the practical lever is unchanged since M3:
chunked transfer of early audio + chunk merging.

**Voice quality inventory (facts, not scores):** Kokoro EN = 2 shipped
public voices (af_heart grade A upstream, am_michael C+) from a 23-voice
community-ONNX/54-voice upstream pool, single-language, no cloning.
Magpie = 5 preset voices shared across 12 languages, cloning removed
upstream. Supertonic = ~10 preset style vectors shared across 31
languages. nano = reference-clip only (no presets), watermark always on.
**Naturalness rankings: UNKNOWN — audition pack ships unscored**
([audition](audition/2026-08-20-en-tts/README.md), 23 samples,
sha-256 manifest).

## 16. Punctuation / prosody — MEASURED (signal-level)

Same ±mark pairs across engines ("How are you?/.", "Hello, Sumit."/
"Hello Sumit.", question, exclamation):

- **Kokoro**: small responses — durations near-identical; "?" lifts
  mean F0 ~7 Hz and softens the terminal fall. Punctuation is honored
  for pacing, question intonation is mild. And the comma pair exposed
  something bigger than prosody: **"Hello, Sumit." → the name is
  dropped entirely** (§2 tables) — the OOV gap, not a prosody gap.
- **Magpie**: the strongest punctuation response measured — "?" turns
  the terminal slope from −2.94 (statement) to +0.28 (flat/rising);
  "!" flips the tail upward; F0 means move 10-25 Hz with punctuation.
  Consistent with AR-LM conditioning on raw text.
- Supertonic/nano: rows in the evidence files; whether any of this is
  *pleasant* is the audition's question — these are contours, not MOS.

Product take: our STT now produces punctuation (M30); every serious
candidate consumes it at least for pacing, Magpie most visibly.
No candidate ignores punctuation outright.

## 17. Text normalization — VERIFIED FROM REPO + MEASURED

The runtime's `normalize` stage is a **pass-through seam** (v1 design,
unchanged). Measured consequences on the M33 trap set (incumbent):
slash-dates spelled as digit runs ("12/08/2026" → "twelve zero eight…"),
brand/name OOV drops (IntelliAI, QwikCart, **Sumit**, Priya, Rajesh —
words silently absent), phone numbers acceptable, "%" acceptable,
"$4.99" correct. Magpie's card *requires* normalized input and its
runtime ships **Sparrowhawk TN** (FAR grammars, `-DNEMO_SPEECH_WITH_NORM=ON`)
— an off-the-shelf implementation of exactly the layer M32 §15
proposed; it is Apache-licensed code and reusable EVEN IF Magpie is not
adopted. Verdict: the normalization/pronunciation layer is needed for
EVERY engine; it lives at our reserved seam; not implemented here.

## 18. Local runtime compatibility ("can it run in our Docker stack?")

| Candidate | Runtime shape | Fits `services/tts-runtime` today? |
|---|---|---|
| Kokoro (incumbent) | torch CPU, python, in-process | **Already in production shape**; community ONNX (86-326 MB, Apache) is the PROPOSED RAM/simplicity lever |
| Magpie GGUF | separate C++ process (NeMo-Speech.cpp server/CLI), ggml | Runnable in Docker but as a SECOND serving process/image; upstream is 8-commits young; would mirror the llama.cpp pattern we use for STT — feasible, not trivial |
| Chatterbox-nano | torch CPU, python, in-process (chatterbox-tts pip) | Adapter-shaped like kokoro (engine module + artifact pins); needs a reference-clip voice-asset story + watermark disclosure |
| Supertonic 3 | onnxruntime, python pip | Adapter-shaped; lightest RAM measured |

## 19. Phase-20 findings assessment (from M32; investigated, NOT fixed)

- **Dual-unit billing**: confirmed still present (code unchanged this
  milestone). Effect on THIS comparison: **none** — candidate numbers
  come from research paths, and the incumbent's timing/quality numbers
  do not touch rating. Effect on the next implementation: **blocker
  before any TTS re-launch** (a real customer request would rate
  `characters` + `audio_seconds` together); the fix is a one-line
  intent decision (bill characters only for synthesis) + a two-unit
  pin test — belongs to the hardening milestone, not here.
- **Stale-image trap**: reproduced in miniature TWICE this week (M32:
  the M3-era image silently served the reference engine; M33: a
  just-rebuilt server binary raced its own relink and reported "no
  HTTP"). Effect on comparison: none (caught both times by verifying
  `/info`//`/ready` before measuring — now a written habit). Effect on
  implementation: the revival runbook must pin "rebuild image → verify
  `/info` artifact = expected" as a law, and the M31-style guard test
  should cover the tts image when TTS re-enters compose defaults.

## 20. Decision matrix

| Model | License | Params | EN quality (M33 RT-WER) | TTFA | RTF (CPU) | RAM | Streaming | Local runtime | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Kokoro (incumbent) + espeak-subprocess OOV fallback** | Apache-2.0 (+ GPL binary at exec boundary — same single policy call as the M32 Hindi path) | 82M | **0.0716** (fallback twin) / 0.1247 (today's espeak-free path) | full-response today; chunk-level 0.7-1.3 s available | **0.283** (0.16 native) | 2.39 GiB (ONNX q8f16 = 86 MB file, PROPOSED lever) | chunk-ready | in production shape TODAY | **KEEP + HARDEN** |
| Supertonic 3 | code MIT / **weights OpenRAIL-M** | 99M | 0.0832 | none (single-shot) | 0.282 | **0.65 GiB** | none exposed | pip/onnxruntime adapter — easy | **Measured runner-up**; blocked on the founder's OpenRAIL stance; strongest RAM story |
| Magpie-TTS 357M (GGUF/CPU) | **NOML** (weights+codec) / runtime Apache | 364M | 0.1991 without the TN its card requires | 5.4 s median sentence (whole-body) | **1.304** | 1.42 GiB | not in the HTTP subset | second C++ server process; upstream 8 commits old | **NOT for CPU serving**; GPU tier + TN unexplored; Hindi-in-one-stack noted for the future |
| Chatterbox-nano | MIT | 110M | — | — | — | — | — | **unloadable by any released library** | NOT MEASURED (packaging); revisit when upstream ships the loader |
| MeloTTS | MIT | ~50M | not benchmarked (no plausible win axis; M1.5 scored below Kokoro) | — | claim only | — | none | pip | pass |
| NeuTTS-Air | Apache-2.0 | 748M | not benchmarked | — | claim only | — | GGUF/llama.cpp | size-class out of mandate; the llama.cpp cloning option on record |

## 21. Recommendation — A. KEEP KOKORO, and harden it

The product-tradeoff answer, not the leaderboard answer:

1. **Quality**: the incumbent's only measured EN weakness is OOV word-
   dropping, and the fix is already evidence-backed — the espeak-
   subprocess fallback variant scores **0.0716 WER on the trap set,
   the best number measured this milestone**, beating every challenger
   on the same texts. One policy decision (GPL binary at an exec
   boundary, the ffmpeg posture) unlocks BOTH this and the M32 Hindi
   path — one call, two capabilities.
2. **Speed/capacity**: 0.283 RTF and 0.557 rps/box saturation beat
   Magpie-CPU by ~4.6x on both axes; Supertonic only ties it.
3. **License**: Apache beats OpenRAIL-M (Supertonic) and NOML (Magpie)
   under the permissive-only law; no new conditioned license enters
   the serving path.
4. **Runtime cost**: zero new engines, zero new images, the adapter and
   tests already exist and are green. Supertonic would buy ~1.7 GiB of
   RAM back at the price of a second engine + a conditioned license —
   the community-ONNX Kokoro build (86-326 MB, Apache) is the same RAM
   lever without either cost (PROPOSED, benchmark in the hardening
   milestone).
5. **Future Hindi**: M32 already measured the same engine's Hindi at
   clean-CER 0.035 — keeping Kokoro keeps the one-engine-two-languages
   path alive. Magpie's Hindi-in-one-NOML-stack is the GPU-tier
   alternative if a GPU class ever opens.

**Does NVIDIA Magpie-TTS beat Kokoro for our use case? NO** — measured:
4.6x slower than the incumbent on CPU (RTF 1.30, every stream slower
than playback), ~4x less concurrent capacity, WER 0.199 on practical
text without the separately-built TN layer its card requires, a
conditioned license on weights+codec, and an 8-commit-old serving
runtime. Its real strengths, measured honestly: never drops a name,
the strongest punctuation prosody of the field, Hindi+English in one
stack, disciplined model pulls. It is a GPU-tier candidate for a
future where IntelliAI runs a GPU serving class — not a replacement
for an 82M CPU engine that is currently 4.6x faster and
quality-fixable with one component.

Also explicitly rejected this milestone: switching to Supertonic for
EN alone (license class + second engine for a tie in speed and a loss
to the fixed incumbent in quality); adopting nano (unloadable);
"current TTS is already good enough" (it cannot say Sumit, IntelliAI,
Priya, or QwikCart — measured).

## 22. Exact next implementation milestone — "Kokoro English TTS hardening" (founder-gated)

Scope (implementation, NOT started here):
1. **Pronunciation fix**: subprocess-isolated espeak-ng OOV fallback
   behind the exec boundary (pinned build; the M32 parity transforms),
   gated by the founder's GPL-binary policy call — target: trap-set
   WER <= 0.08 through the production path (the fallback twin measured
   0.0716).
2. **Text normalization v1** at the reserved `normalize` seam:
   slash-dates, phone grouping, % and currency words (Sparrowhawk FAR
   grammars are the Apache-licensed reference implementation to
   evaluate vs a small in-house normalizer).
3. **ONNX build evaluation**: community Kokoro-ONNX (Apache; 86-326 MB)
   vs torch — RAM/RTF decision by measurement.
4. **Chunk merging** (M3 debt) + optional chunked transfer for TTFA.
5. **Billing-unit fix** (characters only) + two-unit pin test (§19).
6. **Revival guards**: tts image in the rebuild-verify law, `/info`
   artifact assertion in smoke, dormant-service notes refreshed.
7. **Voice naming** (founder listening on the audition pack —
   placeholders are M3 debt), and the consistency fact documented in
   the runtime README (stochastic output; no byte-caching).

Hindi TTS remains the SEPARATE next milestone after hardening (M32
§25), sharing items 1-2.

## 23. Known risks

- Naturalness is still ear-unmeasured (audition pack UNSCORED) — if
  listening ranks Kokoro's voice below a challenger, the quality
  calculus reopens; the pack exists precisely to test that cheaply.
- espeak-ng build pinning discipline (M32 risk, unchanged).
- Kokoro upstream stagnation (single maintainer; mitigation: E-TTS-1
  ownership path + a measured runner-up on file).
- Magpie GGUF lags the card (v2602 measured vs v2607 latest .nemo) —
  any future GPU-tier evaluation must re-pull and re-verify.
- The M33 numbers are one machine, dev-shaped; VPS ladder pending (M31
  law).

## 24. Unresolved questions

1. Founder listening on the audition pack (rubric ready, unscored).
2. The GPL-binary policy call (one decision, unlocks the EN fix +
   Hindi).
3. OpenRAIL-M stance (Supertonic stays the runner-up either way).
4. Sparrowhawk grammars vs an in-house normalizer for TN v1.
5. Kokoro-ONNX quantization quality (q8f16, 86 MB) — measure before
   adopting.
6. Magpie GPU-tier numbers on the 5070 (unmeasured; relevant only if a
   GPU serving class opens).

---

**Final answers (spec):**
1. *What English TTS do we have today?* A complete dormant v1: Kokoro-82M behind `/v1/audio/speech`, WAV/24 kHz, characters-billed, compose-profile-gated (§1).
2. *How good is it?* RTF 0.283, 0.557 rps/box, frozen-corpus WER 0.076; but trap-set WER 0.125 because it silently drops OOV names — including "Sumit" (§2).
3. *Better candidates?* As-is: none beat it end-to-end. The best measured quality is the incumbent PLUS the espeak fallback (0.0716); Supertonic ties speed at one-third the RAM but is license-gated; Magpie loses on CPU (§9-15, §20).
4. *Commercially safe?* CLEAR: Kokoro, MeloTTS, NeuTTS-Air (weights). CONDITIONED: Magpie/NanoCodec (NOML), Supertonic (OpenRAIL-M), espeak binary (GPL at exec boundary — policy call). Unloadable: nano (MIT but no released loader) (§6).
5. *Does Magpie beat Kokoro?* **No for our CPU-first use case** — measured 4.6x slower, ~4x less capacity, TN-dependent quality; GPU-tier candidate only (§21).
6. *Smallest viable?* Kokoro 82M remains the smallest model that passes quality+speed+license together (kitten 15M failed quality/license in M32; nano 110M unloadable).
7. *Fastest?* Kokoro (RTF 0.283 Docker / 0.16 native); Supertonic statistically ties (§9-15).
8. *Sounds best?* UNKNOWN until the audition pack is scored — machine intelligibility says Kokoro+fallback, but naturalness is ears-only (§16, audition).
9. *Least RAM?* Supertonic, 0.65 GiB measured; Kokoro's ONNX build is the path to close that gap without a new engine (§20).
10. *Implement next?* **"Kokoro English TTS hardening"** as scoped in §22 — founder-gated on the GPL-binary policy call and the listening verdict; Hindi TTS follows as its own milestone.
