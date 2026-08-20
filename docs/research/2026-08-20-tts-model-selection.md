# TTS Model Selection — Research, Baselines, and the Hindi Path (Milestone 32)

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — recommendation at §21-22; no runtime, API, or model change ships in this milestone |
| **Date** | 2026-08-20 |
| **Scope** | The whole speech-synthesis workstream: what exists (M1.5/M3 built a full TTS v1), what it measures today, which small models are worth adopting for English + Hindi, and the first fine-tuning experiment |
| **Evidence** | `research/experiments/32-tts-model-selection/` (probe set, harness, evidence JSONs) · re-verifications at source dated 2026-08-20 |
| **Labels** | VERIFIED FROM REPO · MEASURED (this milestone, this machine) · WEB-RESEARCHED (at source, 2026-08-20) · ESTIMATED · UNKNOWN · PROPOSED |

The one-paragraph story: **IntelliAI already has a TTS product** — designed
and shipped at M3 (v0.4, 2026-08-03), parked behind a compose profile when
v1 went STT-only. It serves English on Kokoro-82M with a espeak-free (GPL-free)
pipeline; Hindi is an honest catalog refusal because Kokoro's Hindi
G2P runs a GPL phonemizer. This milestone re-measures the incumbent,
measures the two license-compliant Hindi paths the M3 review left open,
re-verifies the 2026 candidate landscape at source, and recommends the
architecture and the first fine-tuning experiment.

---

## 1. Current TTS architecture — VERIFIED FROM REPO

The full text-to-playback path exists and is test-pinned:

```
Text (POST /v1/audio/speech: model, input, voice, speed, response_format=wav)
  ↓  apps/api/src/intelliai_api/api/v1/audio/speech.py  (SpeechRequest)
Gateway product plane
  ↓  registry resolve: intelliai-tts → service tts-runtime, artifact kokoro-82m
  ↓  voice validation on the product plane (VoiceNotFound before any plane crossing)
  ↓  services/speech.py SpeechService.synthesize → SpeechOutcome
Runtime plane (services/tts-runtime, ADR-0018 template instance #2)
  ↓  POST /v1/synthesize (raw WAV body + X-Runtime-Envelope header, ADR-0020)
  ↓  WorkerPool admission (2 executing + 8 queued; beyond → fast `overloaded`)
  ↓  TextPipeline: validate (2000-char cap) → normalize (v1 pass-through seam)
  ↓  voice resolution: public id → engine reference (per-slot VoiceCatalog)
  ↓  KokoroEngine.synthesize: sentence chunks ≤300 chars → misaki EN G2P
     (espeak poison-stubbed) → KModel pass per chunk → PCM concat
  ↓  api/wav.py: mono 16-bit WAV @ 24 000 Hz, whole body (unstreamed)
Response: audio/wav bytes; envelope stays internal (gateway re-emits nothing)
  ↓
Client playback: none today — no console playground for TTS ("Coming Soon" card),
no client app calls the endpoint. The only callers in the repo are the route's
own tests and the bench harness.
```

Exact facts (file:line in the repo):

- **Endpoint** `POST /v1/audio/speech` + `GET /v1/audio/voices` (product
  facts only). Request: `model`, `input` (min 1 char, no gateway max —
  the runtime's 2000-char law is the only text ceiling), `voice`
  (optional → default), `speed` (>0), `response_format` literal `"wav"`.
  `extra="ignore"`: SDK extras and `language` are dropped — **the voice
  is the routing key**; no public language field exists for TTS.
- **Output contract**: mono, 16-bit PCM, WAV container, 24 000 Hz, whole
  body; errors always JSON; envelope header ≤4096 bytes, operational
  metadata only.
- **Engines**: `reference` (weightless deterministic tone engine — CI
  tier) and `kokoro` (kokoro-82m, 4 hash-pinned files from
  `https://huggingface.co/hexgrad/Kokoro-82M`, re-hashed every boot).
  Slot grammar `INTELLIAI_TTS_SLOTS="kokoro,reference:future-hi"` hosts
  several artifacts in one process (ADR-0026 law shared with STT).
- **Metering**: billed unit CHARACTERS ($15.00 per million;
  free-plan quota 1M). `audio_seconds` is *also* written to the ledger
  ("measured, not billed" by comment) — see §23 Risks for the pricing
  discrepancy this hides.
- **Deployment state**: compose `profiles: [tts]` — `make up` never
  starts it; `make up-tts` restores it. **Absent from every production
  overlay** (prod.yml, local-prod.yml, local-staging.yml). Not in
  `seed-models`. Gateway health roster deliberately excludes it (a
  dormant service must not train operators on permanent DEGRADED).
  Catalog still declares `intelliai-tts`; calls 503 cleanly
  (`runtime_unavailable`, retry_after 1) while the runtime is absent.
- **Console**: "IntelliAI TTS — Coming Soon" card; no languages listed;
  no playground page.

## 2. Existing engines — VERIFIED FROM REPO

| Engine | What it is | State |
|---|---|---|
| kokoro-82m v1 | Kokoro-82M (Apache-2.0, verified 2026-08-03), torch CPU float32, EN-only by license verdict; voices af_heart→`reference-alto`, am_michael→`reference-bass` | The incumbent behind `intelliai-tts`; dormant in deployments |
| reference | Deterministic tone-from-text, weightless | CI/test tier; also simulates future artifacts under `engine:artifact` relabeling |
| ~~Piper~~ | Planned M3 engine until M1.5 found the original archived and the successor fork GPL-3.0 | **Exited before adoption** (FOUNDATION_MODELS §3; ledger: Rejected) |
| gTTS / Coqui / XTTS / YourTTS | — | **Never present in this repo** (verified: no imports, no deps, no references) |

The M3 license firewall is the load-bearing invariant: `misaki[en]`'s
GPL espeak chain (phonemizer-fork, espeakng-loader) is poison-stubbed
before any kokoro import, uninstalled in the image, and the **build
fails if it is importable** — the deployment image is GPL-free by
construction. English G2P is misaki-native with `fallback=None`; the
known cost is that out-of-vocabulary words are silently dropped
(the founder-discovered "IntelliAI" case → the registered
**Pronunciation Manager** platform debt).

**Hindi TTS state: refused, not broken** — the catalog holds
`intelliai-tts × hi = UNAVAILABLE` ("the honest answer is refusal");
the M3 review left the **Hindi checkpoint** open with two compliant
paths: subprocess-isolated espeak-ng (the ffmpeg posture) or an
MIT-lineage Indic engine. Resolving that checkpoint with measurements
is the heart of this milestone.

## 3. Current English baseline — MEASURED (M3, re-measured M32)

The permanent M3 baseline (2026-08-03, same machine, containerized,
`ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md`):

| Fact | Value (M3) |
|---|---|
| Quality (frozen 25-case corpus, whisper-small judge) | EN round-trip WER **0.072**; corpus-wide 0.50 (the hi/mixed cases an EN-only engine cannot say) |
| RTF | 0.19–0.21 native · 0.25–0.37 containerized |
| TTFB via gateway | **814 ms** one sentence · 1122 ms two short sentences (two model passes) · **2237 ms** @ 122 chars — PRD <1 s: PASS single-sentence, FAIL beyond |
| Throughput plateau | 0.64 req/s (~5.4 s audio per wall-second), CPU-bound |
| Admission | at c=20: pool caps at 10, 38 refused fast, accepted p95 bounded |
| Memory | **flat ~2.0 GiB** containerized (1.4 GiB native) — one loaded model shared |
| Startup | cold ~38 s (download) · warm 7 s · load 3.6 s · warmup 0.33 s |
| Gateway overhead | +42.6 ms = 2.0% of inference |

M32 re-measurement on the current source (image rebuilt — the M3-era
image predated the M5 `slots` setting and silently served the reference
engine; see §23): `research/experiments/32-tts-model-selection/evidence/`
`gateway-kokoro-en-bench.json`, `bench-tts-kokoro-relbaseline.json`,
`speech-eval-kokoro-en-2026-08-20.json`. Headline (MEASURED 2026-08-20):
23/23 extended EN probes synthesized, 0 failures, median gateway wall
1110 ms, median RTF 0.279. Full comparison table in §19.

## 4. Current Hindi baseline — VERIFIED FROM REPO

**There is none, by design.** `language=hi` cannot even be expressed on
the public TTS API (no language field; both public voices are
`languages: ["en"]`), and the registry refuses the hi route
(`UNAVAILABLE`). The honest Hindi baseline of the *current product* is:
**refusal**. The measured Hindi baselines of the *candidate paths* are
new in this milestone (§19).

## 5. Requirements — the product bar for call-center TTS

Languages (Core Speech Language Policy v1, founder directive, VERIFIED
FROM REPO): **English, Hindi, Arabic** first-class across speech
capabilities over time. This milestone targets EN + HI; Arabic stays a
registered open slot (no candidate change — but see Supertonic in §10).

Behavior requirements (from the M3 design + this spec): short sentences,
paragraphs, conversational text, numbers, dates, currency, names,
Devanagari, Hindi-English code-switching where practical. The corpus
(`tts-eval-seed@v1`, 25 cases, OWNED) already traps exactly these
categories; the M32 probe set extends it with prosody pairs,
call-center code-switch lines, and paragraph/long stress texts.

Budgets:

| Metric | Target | Label |
|---|---|---|
| TTFB (short/conversational text), p95 | < 1 s | VERIFIED FROM REPO (PRD §10; measured-scoped: single-sentence PASS today) |
| Complete synthesis, typical sentence | ≤ ~2 s | PROPOSED (derives from TTFB law + chunking) |
| RTF (CPU, per stream) | ≤ 0.5 sustained | PROPOSED (0.64 rps plateau ≈ RTF 0.35 measured; 0.5 leaves headroom) |
| RAM per loaded synthesis model | ≤ ~2 GiB (today's measured incumbent); smaller preferred | MEASURED baseline; smallness is the management direction, not a hard SLA |
| Concurrency per process | 2 executing + 8 queued (runtime-owned knobs) | VERIFIED FROM REPO |
| Model load (warm) | ≤ ~10 s | PROPOSED (measured 3.6 s today; readiness gating already handles longer) |
| Quality | intelligibility: round-trip WER/CER vs input through OUR STT judges; naturalness: human listening protocol (no invented MOS) | VERIFIED FROM REPO (M2.5 speech-eval discipline) |
| Stability | zero crashes on the probe set; long text refused honestly above the 2000-char law, never truncated silently | VERIFIED FROM REPO (pipeline law) + MEASURED |

No hard production SLAs beyond the PRD's TTFB line exist, and none are
invented here: VPS-class numbers remain UNKNOWN until a deploy box
exists (M31 law: dev numbers are not SLAs).

## 6. Model research — the 2026-08-20 landscape, re-verified at source

The M1.5 sweep (2026-07-31, eight parallel sweeps, licenses verified at
source) and the M3 adoption predate this milestone by ~3 weeks; the
research framework's decay law required re-verification before anything
becomes load-bearing. Every row below was re-checked at its source on
2026-08-20 (WEB-RESEARCHED unless marked MEASURED).

| Candidate | Identity (verified at source) | Params / size | Languages (EN/HI/AR) | CPU | Streaming | License | Verdict this milestone |
|---|---|---|---|---|---|---|---|
| **Kokoro-82M** (hexgrad) | v1.0 (2025-01-27), StyleTTS2-lineage decoder + ISTFTNet; weights sha-pinned in repo | 82M / 330 MB fp32 | EN strong · **HI: 4 voices (hf_alpha, hf_beta, hm_omega, hm_psi), all grade C, minutes-scale training data** · AR none | **MEASURED RTF ~0.28 (prod path)** | chunk-level possible (per-sentence yield) | Apache-2.0 (weights, pip, misaki) — but **Hindi G2P = espeak-ng, GPL** | Incumbent; Hindi via subprocess espeak measured this milestone (§19) |
| **Supertonic 3** (Supertone) | 2026-04-29, ~99M ONNX, 31 languages, preset voices | 99M / ~260 MB | EN ✓ · **HI ✓** · **AR ✓** | claims CPU-fast (MEASURED §19) | chunked internally; package returns whole array | code MIT; **model weights OpenRAIL-M — use-restricted, NOT permissive → REVIEW REQUIRED** | Measured as the only small tri-language candidate; adoption is a founder license call |
| **Qwen3-TTS** (Alibaba) | open-sourced 2026-01-22; `Qwen3-TTS-12Hz-0.6B/1.7B` (Base/CustomVoice/VoiceDesign); 0.6B repo actually carries 0.9B params | 0.9B–1.7B / 2.5–4.5 GB | 10 languages — **no Hindi, no Arabic** | GPU-oriented (CUDA sample code); CPU UNKNOWN | **yes — 97 ms E2E claim (GPU)** | Apache-2.0 (verified per-repo) | Backup lineage on watch; wrong size class and no Indic today |
| **Chatterbox family** (Resemble) | base/multilingual/turbo/nano; Multilingual V3 = 0.5B, 23 langs **incl. HI + AR**; dedicated **Chatterbox-Multilingual-hi** finetune (2.14 GB); **nano = 110M EN-only, "3× realtime on 8 CPU cores", reference-audio-required** | 110M–0.5B | EN ✓ · HI ✓ (multilingual + hi finetune) · AR ✓ (multilingual) | nano CPU-viable (claim); 0.5B = GPU tier | not documented | MIT (base, multilingual, hi finetune, nano — verified per-card) | The ownership/cloning lineage (P2), unchanged; too heavy for the small-CPU serve tier; no official training code (community LoRA exists) |
| **IndicF5** (AI4Bharat) | 0.4B F5-lineage flow-matching, 11 Indic langs incl HI, reference-prompt (cloning-style) model, 24 kHz | 0.4B / ~1.6 GB fp32 | HI ✓ (EN not a target) | flow-matching multi-step: CPU-hostile (ESTIMATED RTF ≫1) | no | **Card says MIT, but: no LICENSE file in the GitHub repo; AI4Bharat's own study compares scratch vs fine-tuning from English F5 (CC-BY-NC weights, Emilia-trained) and finds fine-tuning wins — the released checkpoint's initialization is UNSTATED** | **BLOCKED (provenance)** — not downloaded, not benchmarked; revival needs AI4Bharat's written clarification |
| **KittenTTS nano** (KittenML) | 0.1/0.2, 15M ONNX, 8 preset voices, 24 kHz, "developer preview" | 15M / <25 MB | EN only | **MEASURED: median RTF 0.34 — NOT faster than 82M Kokoro; fails >~1000-char inputs (no chunking)** | no | Apache-2.0 weights — but the pip package phonemizes English through the **GPL espeak chain in-process, unconditionally** | Rejected: no niche (not faster, not license-cleaner, EN-only, preview-grade) |
| **MMS-TTS-hin** (Meta) | VITS 36.3M, single Hindi voice | 36M | HI | VITS = CPU-friendly | no | **CC-BY-NC 4.0 — verified** | BLOCKED (non-commercial); useful only as an architecture datapoint: VITS-36M is the CPU-viable size class |
| **MeloTTS** (MyShell) | VITS-lineage, EN/ES/FR/ZH/JP/KR | ~52M class | EN ✓ · no HI | CPU real-time (claim) | no | MIT (M1.5-verified; re-verify at adoption) | Not pursued: no Hindi, EN quality tier below Kokoro (M1.5 scoring), stale cadence |
| **Piper** (rhasspy → OHF-Voice) | original MIT repo **archived read-only 2025-10-06**; successor `piper1-gpl` GPL-3.0; community `piper-plus` MIT fork (espeak-free) exists, maintenance unproven | ~20-60M ONNX | many langs incl HI voices | excellent CPU | sentence streaming | GPL-3.0 (successor); archived MIT (original) | Stays exited (M1.5); its *architecture class* (small VITS, ONNX, per-language voices) is exactly what §22's experiment builds in-house |
| F5-TTS / XTTS-v2 / Fish-Speech | — | — | — | — | — | NC / CPML — unchanged | Stay Rejected (ledger) |

Claims not independently re-verified here are labeled in place; anything
this table calls CLAIMED becomes load-bearing only after our own
measurement (research framework law).

## 7. License audit — Gate 1 discipline (verified at source, 2026-08-20)

Classification per the M32 spec: **CLEAR / REVIEW REQUIRED / BLOCKED.**

| Component | License (source, date) | Class |
|---|---|---|
| Kokoro-82M weights + `kokoro` pip + `misaki` | Apache-2.0 (HF card + repos, 2026-08-20) | **CLEAR** |
| espeak-ng (binary and library) | GPL-3.0+ (repo LICENSE, 2026-08-20) | **REVIEW REQUIRED as a platform component** — legally clean for a server-side SaaS even in-process (GPL obligations trigger on distribution, and we do not distribute the backend); *policy*-gated by IntelliAI's permissive-only standing law. The M3-blessed shape — GPL **binary behind an exec boundary** (the ffmpeg posture) — keeps even the policy surface minimal: no linking, no derivative-work argument, binary swappable. Parity measured in §19. |
| Supertonic 3 weights | **OpenRAIL-M** (HF card, 2026-08-20); code MIT | **REVIEW REQUIRED** — commercial use permitted but behavioral use-restrictions attach and flow downstream; not permissive. Founder call required before adoption; benchmarking (internal evaluation) is unrestricted. |
| Qwen3-TTS 0.6B/1.7B | Apache-2.0 (per-repo, 2026-08-20) | CLEAR (but out of scope: no Hindi, GPU class) |
| Chatterbox base / multilingual / **-hi** / nano | MIT (per-card, 2026-08-20) | **CLEAR** (weights); note: library applies Perth watermark to all output — a product decision if ever served |
| IndicF5 | Card: MIT. Repo: **no LICENSE file**. Provenance: likely initialized from CC-BY-NC F5 (AI4Bharat's own paper compares the strategies and fine-tuning from English F5 wins; released checkpoint's init unstated) | **BLOCKED (provenance)** until AI4Bharat clarifies in writing. We did not download or benchmark it. |
| KittenTTS | Apache-2.0 weights; pip package imports GPL `phonemizer`/espeak unconditionally for EN | REVIEW REQUIRED at best; **Rejected on merit anyway** (§6) |
| MMS-TTS-hin | CC-BY-NC 4.0 | **BLOCKED** |
| Piper successor (`piper1-gpl`) | GPL-3.0 | REVIEW REQUIRED class; stays exited on maintenance + policy grounds |
| gTTS / edge-tts style scrapers | Undocumented Google/Microsoft endpoints; no license to use commercially | **BLOCKED** on ToS grounds (never present in this repo; recorded so nobody reaches for them as a "fallback") |

Datasets (for §16-17): SYSPIN **CC-BY-4.0** (IISc; Hindi male+female,
40+ h/speaker studio); AI4Bharat **Rasa CC-BY-4.0** (22 langs incl. HI,
expressive, ~1145 h); **IndicVoices-R CC-BY-4.0** (1704 h, 22 langs,
TTS-refined); IndicTTS (IIT Madras) — custom sign-up license, terms not
public → REVIEW REQUIRED; LJSpeech public domain; LibriTTS-R CC-BY-4.0
(both WEB-RESEARCHED, standard facts — re-verify at ingestion). FLEURS
hi (CC-BY-4.0) already governed in-repo for eval text.

**The audit's teeth this milestone**: IndicF5 — the M1.5 sweep's "MIT
wedge" — went from build-list to BLOCKED on one deep look. Verify at
source, then verify the source's sources.

## 8-10. Candidates by track

- **English (serve today)**: Kokoro-82M remains alone in its
  quality-per-cost class with a proven GPL-free path — MEASURED §19.
  KittenTTS rejected (§6). Qwen3-TTS: wrong size class, watch.
  Chatterbox-nano: CPU-viable claim but EN-only, reference-audio-only,
  and a second 110M engine that still needs a G2P/watermark story — no
  reason to displace a working incumbent.
- **Hindi (the checkpoint)**: three real paths measured/assessed —
  (a) **Kokoro-hi via subprocess espeak-ng** (MEASURED: quality §19,
  license path parity §19); (b) **Supertonic 3 hi** (MEASURED; license
  REVIEW); (c) Chatterbox-Multilingual-hi (MIT, GPU tier — the quality
  ceiling and ownership lineage, not the CPU serve tier).
  IndicF5 BLOCKED (§7). MMS BLOCKED.
- **Multilingual one-model**: Kokoro (EN+HI in one 82M process, voices
  are +0.5 MB packs) and Supertonic 3 (EN+HI+**AR**, 99M ONNX, but
  OpenRAIL-M + preset-only voices). Qwen3-TTS multilingual lacks Indic.

## 11. Small-model / call-center analysis

Management's frame: concurrent per-customer language mixes (A:hi, B:en,
C:ta, D:ar) on CPU boxes.

Measured anchors (this machine, containerized unless noted):

| Anchor | Value | Label |
|---|---|---|
| kokoro-82m loaded process | ~2.0 GiB flat across c=1..20 (M3); **2.39 GiB container idle-loaded (M32)** | MEASURED |
| kokoro throughput plateau | 0.64 req/s (M3, fresh machine) · 0.40-0.45 req/s (M32 ladder, loaded machine) → plan on the 0.4-0.6 band per process | MEASURED |
| kitten-nano-0.2 loaded process | ~0.57 GiB peak (onnx) | MEASURED |
| supertonic-3 loaded process | **0.66-0.73 GiB peak** (onnx, en/hi) | MEASURED |
| Chatterbox 0.5B / Qwen3-TTS 0.9B on CPU | not measured; autoregressive-LM class → RTF ≥1 risk on CPU | ESTIMATED |

The multi-language RAM math (ESTIMATED, from the measured anchors):

- **One multilingual small model** (Option A shape): ONE ~2 GiB process
  serves EN+HI; each additional voice is a ~0.5 MB pack, each
  additional Kokoro-supported language is a G2P config, not a new
  model. Language concurrency shares the same worker pool — no
  RAM multiplication, but also no per-language capacity isolation
  (a Hindi burst queues English too; the pool/queue knobs and
  horizontal replicas are the isolation levers, ADR-0026 already
  supports `kokoro,kokoro:second-slot`-style splits only via distinct
  artifacts, so per-language isolation = per-process replicas).
- **Per-language specialists** (Option B shape): RAM stacks per
  DISTINCT engine process — e.g. Kokoro-EN (2.0 GiB) + a VITS-class
  Hindi specialist (~0.3-0.5 GiB ONNX, MMS-36M size class) ≈ 2.5 GiB,
  NOT 2×2 GiB — small specialists are cheap; big ones are not.
  Per-language admission isolation comes free (separate slots/pools).
- Torch→ONNX for Kokoro (community export exists) is the single
  biggest RAM/simplicity lever if Option A proceeds — PROPOSED,
  unbenchmarked here.

Streams-per-process: the measured pool behavior (2 exec + 8 queue,
plateau 0.64 rps) is the honest capacity unit; call-center sizing =
replicas × that unit until a VPS ladder exists (UNKNOWN there).

## 12. CPU/GPU analysis — the RTX 5070 8 GB question (§16 of the spec)

| Task | Fits 8 GB? | Label |
|---|---|---|
| Benchmark every candidate above on CPU | n/a (CPU) — done for kokoro/kitten/supertonic | MEASURED |
| Chatterbox-Multilingual-hi inference on GPU | yes (~2.1 GB weights fp16 + activations) | ESTIMATED (not run this milestone) |
| Qwen3-TTS 0.6B inference | yes (2.5 GB bf16) | WEB-RESEARCHED sizes; not run |
| **VITS-class Hindi specialist training (~36M, 22-24 kHz)** | **yes — comfortable** (batch 16-32; the MMS/Piper size class trains on consumer 8 GB) | ESTIMATED from architecture class; the §22 experiment validates it |
| Chatterbox 0.5B LoRA fine-tune | borderline: community Indic LoRA exists (reenigne314/chatterbox-indic-lora), no official recipe; grad-ckpt + small batch | WEB-RESEARCHED + ESTIMATED |
| F5/IndicF5-class 0.4B flow-matching fine-tune | typically >8 GB for sane batches; also license-BLOCKED | ESTIMATED + BLOCKED |
| Kokoro fine-tune | **no path at any VRAM: no training pipeline released** (re-verified) — Kokoro is a serve lineage, not an ownership lineage | WEB-RESEARCHED |

STT findings do NOT transfer: the E3 recipe (llama.cpp GGUF, audio-LLM
LoRA) has no TTS analogue; TTS training is a different toolchain.

## 13. Streaming / first-audio

- v1 is deliberately unstreamed (whole-body WAV): TTFA == full response.
  M3's measured verdict stands: **streaming = GO** (2237 ms @ 122 chars
  cannot meet 1 s TTFB unstreamed); chunk merging is the nearer lever
  for short texts (two short sentences currently cost two ~500 ms
  passes).
- Candidate streaming reality: Kokoro yields per-sentence chunks — the
  M32 harness MEASURED time-to-first-chunk (kokoro-hi solo run):
  median 1.26 s, minimum 0.68 s, even on paragraph inputs — so chunked
  transfer puts TTFA at first-sentence cost instead of full-response
  cost. Supertonic chunks internally but the package returns one array
  (no incremental API). KittenTTS: none. Qwen3-TTS: true token
  streaming (97 ms E2E claim, GPU). Chatterbox: none documented.
- Consequence: the binding's chunk-ready design (raw body → chunked
  body, same request shape) remains the right M8 path; no candidate
  changes that conclusion.

## 14. Code-switching — measured behavior (§13 of the spec)

Probes: the spec's three call-center lines + Devanagari-with-English
lines from the frozen corpus. Facts from the M32 runs (§19 evidence):

- **Devanagari + English tokens through the Hindi espeak path
  (kokoro-hi) — WORKS for loanword-class English**: measured rows show
  "policy number 12345 … please confirm" rendered as पॉलिसी नंबर …
  प्लीज़ कन्फर्म (audio correct; E3 heard every word), "laptop" →
  लैपटॉप — while rarer technical terms degrade ("Python" → "पाइसन").
  The 0.57-0.59 mixed-CER means are dominated by the Latin-reference
  vs Devanagari-transcript script gap, not by unintelligibility —
  the per-row transcripts in the evidence files carry the honest
  picture (worst-looking row, CER 0.96, is a semantically perfect
  rendering).
- **Romanized Hinglish is the real gap**: through the EN pipeline the
  Hindi words are OOV-dropped ("Aap kal office aaoge?" → "Cal
  Office"); through the hi pipeline espeak reads Latin as English-ish
  ("aaoge" mangled to आरेंज, though the short policy-number line
  survived). Scores are labeled `metric_not_computable` (Latin
  reference vs Devanagari judge); transcripts recorded verbatim. The
  fix is roman→Devanagari transliteration in the normalization layer,
  not an engine change.
- No candidate measured here natively code-switches within one voice;
  Chatterbox-multilingual CLAIMS it (23-lang single model) — GPU tier,
  unverified on our probes.

## 15. Punctuation / text normalization (§12 of the spec)

- **Prosody pairs** (same words ± mark) were synthesized and analyzed
  signal-level (duration, mean F0, terminal F0 slope):
  `evidence/kokoro-hi-prosody.json`. Numbers in §19; whether differences
  are *natural* is explicitly a listening question.
- **The danda fact**: Kokoro's sentence splitter is
  `(?<=[.!?;:])\s+` — **। (danda) is not a split boundary** (VERIFIED
  FROM REPO, `engines/kokoro.py:81`): a multi-sentence Hindi paragraph
  with dandas reaches espeak as ONE chunk today. espeak-ng itself
  treats the danda as a sentence break, so audio pauses survive, but
  chunking (latency) and the 510-phoneme guard interact badly with
  long danda-only paragraphs — a runtime detail the Hindi milestone
  must fix (split law gains `।`, one line).
- **Normalization layer verdict**: needed, and the seam already exists
  (`TextPipeline.normalize`, reserved since M3, pass-through today).
  Measured traps that justify it: ₹/currency verbalization, digit
  strings (12951), dates, English acronyms in Devanagari. The M30
  punctuation work is UPSTREAM of TTS (it restores marks into STT
  text); for TTS the flow is the reverse — expand text INTO speakable
  words before G2P. **Do not implement yet** (spec law); design lands
  with the Hindi runtime milestone, joint with the Pronunciation
  Manager debt (same seam, same owner).

## 16. Public datasets (evaluation now, fine-tuning later)

| Dataset | License | HI | Hours / speakers | TTS-grade? | Role |
|---|---|---|---|---|---|
| **SYSPIN** (IISc) | CC-BY-4.0 (verified) | ✓ (+8 other Indic) | 40+ h × 2 speakers (M+F) per language, studio | **yes — built for TTS** | **The fine-tuning anchor for §22** |
| **Rasa** (AI4Bharat) | CC-BY-4.0 (verified) | ✓ (22 langs) | ~1145 h total; ~21-30 h/speaker; 6 Ekman emotions | yes, expressive | Expressive extension after the neutral voice works |
| **IndicVoices-R** | CC-BY-4.0 (verified) | ✓ (22 langs) | 1704 h, 10 496 speakers | refined-from-ASR (multi-speaker, variable) | Pre-training-scale diversity, speaker-pool experiments; NOT the first single-voice tune |
| IndicTTS (IIT Madras) | custom sign-up license — terms not public | ✓ | ~10+ h/lang | yes | REVIEW REQUIRED before any use |
| LJSpeech | public domain | – | 24 h, 1 speaker EN | yes | EN fine-tune classic; not needed while Kokoro serves EN |
| LibriTTS-R | CC-BY-4.0 | – | 585 h EN | yes | EN scale option, same note |
| Common Voice hi | CC0 | ✓ | crowd, multi-speaker, variable mic | no (for TTS voices) | eval-text source at most |
| FLEURS hi | CC-BY-4.0 (already governed in-repo) | ✓ | – | – | Eval TEXT reuse: `hi-punct-eval` texts are punctuated Hindi — ready-made TTS input probes (already exercised via the frozen corpus lineage) |

Nothing was ingested for training this milestone (spec law); the
downloads above that did occur are candidate model weights + their
bundled voice assets only.

## 17. Future fine-tuning pipeline — what the STT machinery already gives us

The conceptual TTS pipeline (spec Phase 15) mapped onto what exists:

```
Public TTS data → Dataset → DatasetVersion → validation → SPEAKER split
→ training manifest → fine-tune → checkpoint → synthesis evaluation
→ model artifact → production
```

| Stage | Reuse from STT plane? |
|---|---|
| Source registry, license rows, provenance manifests, sha-frozen DatasetVersions | **REUSE AS-IS** (`ml/datasets`: sources.py, manifests.py, hf.py ingesters — capability-agnostic by construction) |
| Audio validation | PARTIAL: rate/duration/silence checks reuse; TTS adds speaker-consistency, SNR/studio-quality, and text-audio alignment gates (new validators in the same validate.py pattern) |
| Splits | CHANGES MEANING: STT splits by utterance/content; TTS voices split by SPEAKER (a voice is the unit of leakage) — new split law, same manifest mechanics |
| Training harness | **NOT reusable**: `ml/training` is audio-LLM/ASR-specific (qwen_trainer, GGUF export). A TTS trainer (VITS-class first) is a new module beside it, same config/manifest discipline |
| Evaluation | **REUSE AS-IS**: the speech-eval runner + STT judges + corpus + baselines are LIVE for TTS since M3 (adapter proven; day-one baseline exists). C2 (second judge) and C3 (corpus ≥100) remain the scheduled gates |
| Artifact + registry + rollout | **REUSE AS-IS**: ArtifactSpec/store, slots, registry routes, proposals, model-rollout runbook — all capability-neutral (proven twice) |

## 18. Benchmark methodology (M32 instruments — research-only)

- **Probe set**: `probe-texts-v1.json` — the 25 frozen `tts-eval-seed@v1`
  cases verbatim + 28 M32 probes (questions, ₹/currency, dates, names,
  brand-OOV "IntelliAI", paragraphs, ~1200-char long stress, the spec's
  code-switch trio, 4 prosody pairs). Identical texts for every engine.
- **Instruments** (`harness/`): `wsl_synth_bench.py` (candidate engines
  in disposable WSL venvs; wall/TTFA/RTF/RSS/load; GPL-chain presence
  recorded per run), `gateway_synth_bench.py` (the shipping path),
  `roundtrip_judge.py` (ASR round-trip via OUR gateway: whisper route
  judges EN, E3 judges HI — frozen normalization profiles +
  `intelliai_evaluation.accuracy`, zero parallel metric code),
  `espeak_parity_probe.py` (subprocess CLI vs in-process GPL chain,
  phoneme-string equality per text), `prosody_analyze.py` (duration/F0
  deltas on the ± punctuation pairs). Plus the FROZEN instruments:
  `bench-tts` ladder and `speech-eval` (unchanged, re-run).
- **Audio hygiene**: WAVs live outside the repo (WSL `~/m32/audio`,
  scratchpad copies); only JSON evidence is committed. Synthetic audio
  only; no customer or private audio anywhere.
- **Honesty rails**: engines that download from the hub record the
  resolved revision; failures are rows, not crashes; every aggregate
  ships with its per-row table; subjective quality is nobody's number
  until the founder listens (three-WAV audition protocol from M3 reused
  — sample paths listed in the evidence files).

## 19. Benchmark results — MEASURED 2026-08-20

All quality numbers are round-trips through OUR OWN production STT
plane (whisper route judges EN, the promoted E3 route judges HI/mixed),
frozen normalization profiles, `intelliai_evaluation.accuracy` — the
same judging discipline as M2.5/M3. Timing rows marked *solo* were
re-run serialized after the first pass was found contaminated by
concurrent benches (methodology note in the evidence files).

**Intelligibility — English probes (18 EN texts incl. traps):**

| Path | RT-WER | RT-CER | Note |
|---|---|---|---|
| **Production kokoro EN** (gateway, espeak-free) | **0.0773** | 0.0556 | frozen-corpus official re-baseline: **0.0759** — reproduces M3's 0.072 |
| kokoro EN + espeak fallback (research venv) | **0.0344** | 0.0189 | the OOV rescue: "IntelliAI", "Kavya" spoken instead of dropped — **the dictionary-only verdict costs ~2× WER on trap-dense text** |
| Supertonic 3 EN (M1) | 0.0738 | 0.0344 | ties production kokoro |
| KittenTTS nano EN | 0.0979 | 0.0592 | worst of the four; also fails >~1 k chars |

Measured OOV exemplar (production path): *"Welcome to IntelliAI
support, my name is Kavya."* → judge heard *"Welcome to AI Support, my
name is."* — the M3 founder finding, now a number.

**Intelligibility — Hindi probes (24 HI texts), E3 judge:**

| Path | all-24 WER/CER | clean-slice (20) WER/CER | Verdict |
|---|---|---|---|
| **Kokoro-hi, hf_alpha (F)** — espeak `hi` G2P | 0.1615 / 0.1190 | **0.0834 / 0.0347** | zero failures incl. the long paragraph |
| Kokoro-hi, hm_omega (M) | 0.1635 / 0.1183 | — | male voice equally intelligible |
| **Supertonic 3 hi, F1** | 0.1524 / 0.1211 | 0.0846 / 0.0419 | zero failures; paragraph CER 0.0 |

Reading: E3's CER on *real* Hindi speech is 0.11612 — clean synthetic
speech round-trips at ~0.035-0.042 **including** the judge's own error.
Both paths are intelligible at better-than-real-speech level; they are
statistically tied. The all-24 numbers conflate verbalization with
error: on digit probes the TTS *correctly* expands numbers to words
(ट्रेन संख्या 12951 → "बारह हज़ार नौ सौ इक्यावन") and CER punishes the
digits-vs-words mismatch, and on ₹1,499 the **rupee symbol is dropped
and the comma breaks number parsing** — the two real defects the
normalization layer (§15) must fix; both are text-frontend, not
acoustic.

**Code-switching (measured, §14 updated):** Devanagari + English
loanwords works ("policy number… please confirm" → पॉलिसी नंबर …
प्लीज़ कन्फर्म — audio correct; the 0.59 mixed-CER mean is mostly the
Latin-reference-vs-Devanagari-transcript script gap, shown row-by-row
in the evidence). Romanized Hinglish through the hi pipeline is
unreliable ("aaoge" mangled), and through the EN pipeline it drops the
Hindi words entirely — **roman→Devanagari transliteration is a
normalization-layer requirement**, not an engine property.

**Latency / footprint (solo runs):**

| Path | median RTF | p95 RTF | TTFA | peak RSS | load (warm) |
|---|---|---|---|---|---|
| Production kokoro EN via gateway (Docker) | 0.279 | — | = wall (unstreamed); median wall 1.11 s | 2.39 GiB container | 5.1 s + 0.8 s warmup |
| Kokoro-hi (WSL venv, torch CPU) | **0.288** | 0.349 | first-chunk 0.68–1.26 s median | 2.17 GiB | 6.8 s |
| Kokoro-en upstream (WSL) | 0.285 | — | same mechanism | 2.52 GiB | — |
| Supertonic 3 (en / hi) | 0.437 / 0.446 | ~1.0 | none (single-shot API) | **0.66 / 0.73 GiB** | 2.9 s (38.8 s cold download) |
| KittenTTS nano | 0.338 | 0.346 | none | 0.57 GiB | 19.7 s (download) |

**Production concurrency ladder (official `bench-tts`, solo, current
source; compare M3 baseline):** c=1 p50 2.97 s (120-char pinned
sentence, ~8.6 s audio), plateau ~0.40-0.45 req/s (M3 measured 0.64 on
a fresher machine — treat 0.4-0.6 as the per-process band), admission
law intact at c=20 (28 served, 32 refused fast), PRD TTFB 2 335.6 ms
vs 1 000 ms target → **FAIL beyond one sentence, reproducing the M3
verdict** (chunk-merge + streaming remain the levers), gateway
overhead 46.2 ms = 2.1 % (reproduces ADR-0002's 2.0 %).

**Prosody pairs (± punctuation, signal-level):** punctuation
measurably changes output on every engine (durations, pauses, mean F0,
terminal slope — full table in `evidence/*-prosody.json`), but a
reliable interrogative RISE from "?" is NOT observed on either small
engine (Kokoro-hi "?" pair: tail slope −2.7 vs −1.0 Hz/frame — flatter
*with* the mark; Supertonic noisy in both directions). Danda vs no
danda on a single sentence: near-identical. Conclusion: keep feeding
punctuation (pauses and pacing respond), do not promise question
intonation, and treat naturalness as the founder-listening question it
is.

**espeak parity (the license path):** 16/29 texts byte-identical
between the espeak-ng 1.51 CLI (subprocess) and the in-process GPL
chain; all 13 mismatches are three mechanical transforms (punctuation
preservation; `(en)/(hi)` language-switch-marker stripping; misaki's
Apache-licensed diphthong table `aɪ→I`, `eɪ→A`). Zero divergent
phonemizations. Production requirement: pin ONE espeak-ng build and
replicate those transforms — engineering, not research.

## 20. Decision matrix

| Model / path | EN | HI | License | Params | RAM (meas.) | CPU RTF (meas.) | TTFA | Streaming | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Kokoro-82M (incumbent) + subprocess espeak for HI (+ EN OOV fallback)** | WER 0.077 → **0.034** with fallback | clean CER **0.035**, 4 voices (2F/2M) | Apache-2.0; GPL **binary at exec boundary** (ffmpeg posture — founder policy call) | 82M | 2.2-2.5 GiB (torch; ONNX = PROPOSED lever) | **0.28-0.29** | chunk-level 0.7-1.3 s possible | chunk-ready | **RECOMMENDED** — one process, both languages, incumbent runtime, best RTF |
| Supertonic 3 | WER 0.074 | clean CER 0.042; +**Arabic** claimed | code MIT; **weights OpenRAIL-M — REVIEW REQUIRED** | 99M | **0.7 GiB** | 0.44 | none (single-shot) | internal chunking only | **Runner-up** — lightest RAM + the only ar-capable small model; blocked on the license call; second engine to maintain |
| Chatterbox-Multilingual(-hi) / nano | claims strong | hi finetune exists | MIT | 110M-0.5B | not meas. | ≥1 expected (0.5B AR-LM) | — | not documented | **P2 ownership/cloning lineage** — GPU tier, not the CPU serve answer |
| Qwen3-TTS 0.6B | capable (claim) | **none** | Apache-2.0 | 0.9B | not meas. | GPU-oriented | 97 ms (GPU claim) | **true streaming** | Watch-list backup; no Indic |
| KittenTTS nano | WER 0.098 | none | Apache + GPL-in-process G2P | 15M | 0.57 GiB | 0.34 | none | none | Rejected — no niche |
| MMS-TTS-hin | — | (VITS-36M class proof) | **CC-BY-NC** | 36M | — | — | — | — | BLOCKED |
| IndicF5 | — | — | **provenance-contaminated MIT claim** | 0.4B | — | flow-matching, CPU-hostile | — | none | BLOCKED (provenance) |
| Current production state (Option D) | ships | **refusal** | — | — | — | — | — | — | Rejected: Hindi is Language-Policy law, and the gate is now measurably crossable |

## 21. Recommended architecture

**Option A — one small multilingual serve engine: keep Kokoro-82M and
extend the SAME artifact to Hindi through subprocess-isolated espeak-ng
phonemization**, with the identical component doubling as the English
OOV fallback. (Recommendation; every production change remains
founder-gated and belongs to the next milestone.)

Why the evidence says A:

1. **Quality ties, so structure decides.** Both viable Hindi paths
   round-trip at the same clean-slice band (0.035 vs 0.042 CER); no
   quality argument forces a second engine.
2. **Smallest total system.** One 82M model already integrated, hash-
   pinned, slot-hosted, leak-guarded; Hindi arrives as two ~0.5 MB
   voice packs + one G2P component — no new engine, no new image, no
   second RAM footprint. Supertonic would add a second engine (its
   0.7 GiB is attractive; the ONNX port of Kokoro is the equivalent
   PROPOSED lever without a second lineage).
3. **License posture.** Apache weights end-to-end; the only non-
   permissive element is a GPL *binary* behind the same exec boundary
   as ffmpeg — a shape the M3 review pre-blessed as defensible and the
   parity probe proved faithful. Supertonic's OpenRAIL-M restrictions
   attach to the *weights* and flow to derivatives — a materially
   bigger policy step.
4. **The EN product improves too** — the fallback halves trap-set WER
   and finally says the company's own name (with the Pronunciation
   Manager remaining the platform-owned fix above it).
5. **Voice inventory**: 2 female + 2 male Hindi voices exist as
   artifact-shaped files; Supertonic exposes preset styles shared
   across languages.

Options B (per-language specialists) has no licensable small Hindi
engine today (MMS NC, Piper GPL-exited, IndicF5 provenance-blocked);
Option C (multilingual base + per-language fine-tunes) is the FUTURE
via §22 — Kokoro cannot be fine-tuned (no training pipeline), so the
owned specialist grows beside it, not on it; Option D (stay EN-only)
contradicts Core Speech Language Policy v1 with the gate now measured
crossable. **Runner-up**: if the founder rejects the GPL-binary
posture but accepts OpenRAIL-M, Supertonic 3 is the measured fallback
(and brings an Arabic claim worth measuring); if both are rejected,
Hindi TTS waits for E-TTS-1.

## 22. Recommended first TTS experiment — E-TTS-1 (defined, NOT run)

**Goal:** IntelliAI's first OWNED voice — a small Hindi specialist that
removes both the espeak dependency and the C-grade-voice ceiling, and
gives the platform its TTS fine-tuning muscle (the STT playbook, applied).

| Field | Value |
|---|---|
| Model | **VITS-class end-to-end TTS, ~36-45M params, trained in-house** (the architecture class MMS-hin proves CPU-viable and Piper productized) via the maintained MPL-2.0 Coqui-TTS fork (code license compatible; MPL is file-level copyleft, not weights-touching) |
| Input ablation | **Devanagari graphemes vs subprocess-espeak phonemes** — Devanagari is near-phonemic; a grapheme-input winner deletes the GPL question from the owned lineage entirely |
| Languages | Hindi first (one female voice = SYSPIN's female speaker); male voice second |
| Dataset | **SYSPIN Hindi female, 40+ h studio, CC-BY-4.0** (verified) — ingested through the existing `ml/datasets` governance (source row, license row, sha-frozen DatasetVersion, SPEAKER-split law from §17); Rasa hi (CC-BY-4.0, expressive) reserved for the expressive follow-up |
| Hardware | RTX 5070 Laptop 8 GB — VITS at 22.05 kHz, batch 16-32, fp16: fits (ESTIMATED; first-day smoke run validates before the long run) |
| Duration/cost | ESTIMATED 5-10 days of local GPU time across ~2-4 training runs incl. the ablation; $0 cloud |
| Evaluation | The M32 instruments unchanged: round-trip CER via E3 on the probe set; the frozen corpus (grown to ≥100 cases per C3) for the eventual switching test; founder listening protocol A/B vs the Kokoro-hi audition WAVs; RTF/RAM via the same harness on ONNX export |
| Success criteria (PROPOSED) | clean-slice RT-CER ≤ 0.05 (parity band with Kokoro-hi's 0.035); founder listening preference ≥ Kokoro hf_alpha on a majority of A/B pairs; ONNX CPU RTF ≤ 0.3; loaded RSS ≤ 0.5 GiB; zero failures on the probe set incl. paragraph + long |
| Sequencing gate | Run AFTER the Hindi serving milestone ships (serve first on the incumbent; own in parallel) — or immediately INSTEAD of serving Kokoro-hi if the founder listening verdict on the C-grade voices is "not launchable" |

## 23. Risks

- **Naturalness is the unmeasured axis**: intelligibility is proven;
  whether C-grade, minutes-trained Hindi voices sound GOOD enough for a
  call-center product is exactly the founder-listening question.
  Audition WAVs: `~/m32/audio/` (WSL) mirrored at the session scratchpad
  `m32-wsl-audio/` — hf_alpha vs hm_omega vs supertonic F1, same texts.
- **espeak-ng pinning**: phoneme stability requires pinning one
  espeak-ng build (CLI 1.51 measured vs loader-bundled data differ on
  3 mechanical transform classes); the production component must vendor
  its espeak build the way ffmpeg is pinned.
- **Kokoro upstream stagnation**: v1.0 is 2025-01; single-maintainer;
  no training pipeline — mitigated by E-TTS-1 (owned successor path)
  and by the runner-up being measured.
- **Billing discrepancy found during the audit (pre-existing, dormant)**:
  TTS ledger rows carry BOTH `characters` (billed, $15/M) and
  `audio_seconds` — and `pricing/rating.py` prices every unit with a
  book price, while `books.py` prices `audio_seconds` for STT — so a
  TTS success row would rate BOTH units (the code comment says
  "measured, not billed"; the rating engine disagrees; no test covers
  the two-unit case). Dormant only because TTS is dormant. **Must be
  fixed before any TTS re-launch**; one-line intent decision (bill
  characters only) + a pin test.
- **Stale-image trap (found live)**: the M3-era tts image predates the
  M5 `slots` setting and silently serves the reference engine under a
  current compose file (env ignored by old code — "healthy, and
  wrong"). The tripwire only covers the reverse direction. Runbook law
  for TTS revival: rebuild image + verify `/info` artifact, never trust
  container status alone.
- **Romanized Hinglish input** (Android keyboard reality) is served
  badly by both pipelines — transliteration in the normalization layer
  is product-critical for call-center text sources that arrive
  romanized.
- VPS-class performance remains UNKNOWN (M31 law); the 0.4-0.6 rps
  per-process band re-ladders on the deploy box.

## 24. Open questions

1. **Founder listening verdict** on Kokoro-hi (hf_alpha/hm_omega) and
   Supertonic-hi samples — the launchability call (protocol: M3's
   3-WAV audition, extended to the Hindi set).
2. **Policy call: GPL binary at an exec boundary** — does the
   permissive-only law accept the ffmpeg posture for espeak-ng?
   (Legal exposure differs from in-process linking; M3 §8 called it
   defensible; adoption needs the explicit decision recorded.)
3. **OpenRAIL-M stance** — accept/reject as a class (affects Supertonic
   now, and future OpenRAIL releases generally).
4. **IndicF5 provenance outreach** — one email to AI4Bharat could
   revive the wedge lineage; worth sending regardless of A's outcome.
5. **Kokoro ONNX build** — RAM/RTF measurement (PROPOSED lever to close
   the 2.2 GiB vs 0.7 GiB gap without a second engine).
6. Arabic TTS corpus + baseline (the slot has its first candidate but
   nothing to measure it against).
7. At implementation time: danda in the sentence splitter, chunk
   merging (M3 debt), normalization layer v1 scope (₹/digits/dates/
   transliteration), and whether the EN OOV fallback ships in the same
   milestone as Hindi.

## 25. Next milestone

**M33 — Hindi TTS serving path (founder-gated implementation):**
subprocess espeak-ng phonemization component (pinned build, parity
tests from §19's transform table), Hindi voice packs as hash-pinned
artifact files, danda-aware chunking + chunk merging, normalization
layer v1 (currency/digits/dates; transliteration decision), registry
`hi` route flip UNAVAILABLE→AVAILABLE behind the founder listening
verdict, the billing-unit fix (§23), staging battery + leak-guard
extension — production stays OFF until the promotion procedure, exactly
like M30's punctuation. **E-TTS-1 (§22)** follows as the ML milestone.
STOPPED here per the M32 stop condition: research, baselines, and
recommendation only — nothing above ships in this milestone.

---

**The eleven questions the spec requires answered, in one place:**
1. *What TTS do we have today?* A complete, dormant v1 product: `/v1/audio/speech` + voices catalog on Kokoro-82M EN, compose-profile-gated, absent from prod overlays (§1-2).
2. *How good is it?* EN round-trip WER 0.076 (reproduced), RTF 0.28, 2.4 GiB, PRD TTFB pass only for single sentences (§3, §19).
3. *What is weak?* No Hindi (license-gated), OOV word-dropping (measured 2× WER cost), unstreamed TTFB beyond one sentence, per-sentence fixed cost, torch RAM, placeholder voices, dormant deployment (§2, §19, §23).
4. *Which small models are worth trying?* Kokoro-hi via subprocess espeak and Supertonic 3 — both measured; Chatterbox as the GPU/ownership lineage; Qwen3-TTS on watch (§6, §20).
5. *Which are commercially safe?* CLEAR: Kokoro, Chatterbox, Qwen3-TTS. CONDITIONAL: espeak-subprocess (policy call), Supertonic (OpenRAIL-M call). BLOCKED: IndicF5 (provenance), MMS (NC), F5/XTTS/Fish (NC), scraper "fallbacks" (§7).
6. *Same model for EN and HI?* Yes — Option A, one multilingual small engine; evidence in §20-21.
7. *What data first?* SYSPIN Hindi (CC-BY-4.0) for training; the OWNED corpus + M32 probe set for eval; Rasa/IndicVoices-R next (§16).
8. *Can the 8 GB 5070 handle the first experiment?* Yes for the VITS-class E-TTS-1 (ESTIMATED, smoke-validated day one); no for F5-class; nothing to train on Kokoro (§12, §22).
9. *First fine-tuning experiment?* E-TTS-1 as specified in §22.
10. *Success metrics?* Round-trip CER through E3, founder listening preference, RTF/RAM budgets, zero-failure probe set — thresholds in §22.
11. *Exact next milestone?* M33 as scoped in §25.
