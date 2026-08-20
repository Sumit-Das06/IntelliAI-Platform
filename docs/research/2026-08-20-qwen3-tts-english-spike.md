# Qwen3-TTS 0.6B English Spike — vs the Kokoro Incumbent (Milestone 34)

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — decision at §21-22; nothing ships (no runtime/API/billing/client/catalog/deploy change; no fine-tune) |
| **Date** | 2026-08-20 |
| **Question** | "Does Qwen3-TTS 0.6B provide a better English TTS product tradeoff for IntelliAI than Kokoro-82M?" |
| **Method** | The EXACT M33 instruments and 25-text probe set (`probe-texts-en-v1.json`), same machine, same whisper judge, same solo-timing law; plus the M34 long-text ladder |
| **Evidence** | `research/experiments/34-qwen3-tts/` · M33 evidence for the Kokoro sides (measured this week, same set) |
| **Labels** | VERIFIED FROM REPO · MEASURED · WEB-RESEARCHED · ESTIMATED · UNKNOWN · PROPOSED |

## 1. Model identity — VERIFIED AT SOURCE (2026-08-20)

| Fact | Value |
|---|---|
| Repo / variant chosen | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` — chosen per the spec's preference: it ships **9 preset speakers** (Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee), so no reference-audio/cloning complexity enters the benchmark. Base = voice-clone-from-reference; VoiceDesign = text-described voices — both out of scope |
| Revision measured | pinned via HF API at run time; recorded in every evidence JSON (`identity.hub_revision`) |
| Params | **0.9B actual** (card "0.6B" name vs "0.9B params" shown — the name undercounts; BF16 ~2.5 GB download) |
| Languages | 10 (zh, en, ja, ko, de, fr, ru, pt, es, it) — **no Hindi, no Arabic** |
| Architecture | AR transformer over a 12 Hz codec tokenizer (codec assets bundled in the repo); released 2026-01-22 (family) |
| Runtime | official pip **`qwen-tts` 0.1.1** (Apache-2.0, Alibaba Qwen Team): `Qwen3TTSModel.from_pretrained(...)`, `generate_custom_voice(text, language, speaker)` |
| Streaming | **The released library exposes NO streaming API** — methods are exactly `generate_custom_voice / generate_voice_clone / generate_voice_design` (introspected). The "97 ms end-to-end streaming" figure belongs to Qwen's own serving stack, not to anything we can run. TTFA here = whole response, honestly |
| Voice used | **Ryan**, `language="English"`, one voice for every run (Serena for one audition sample) |
| Determinism | `torch.manual_seed(0)` set; AR sampling may remain stochastic (recorded per run) |

## 2. License audit

| Component | License (source, 2026-08-20) | Class |
|---|---|---|
| Qwen3-TTS-12Hz-0.6B-CustomVoice weights (incl. codec + preset voices) | Apache-2.0 (per-repo card) | **CLEAR** |
| `qwen-tts` pip runtime | Apache-2.0 (pip metadata) | **CLEAR** |
| transformers/torch chain | Apache/BSD | CLEAR |

Notable: this is the **only challenger measured this week whose entire
stack is permissive-clean** (Supertonic weights = OpenRAIL-M; Magpie
weights+codec = NOML; espeak = GPL-at-boundary policy call). License is
NOT the axis that eliminates Qwen3-TTS.

## 3. Environment — MEASURED

| Fact | Value |
|---|---|
| GPU | RTX 5070 Laptop, 8151 MiB VRAM, driver 591.91, CUDA 13.1 visible inside WSL2 (`nvidia-smi` verified) |
| Torch | 2.11.0+cu128 in the research venv — `torch.cuda.is_available() == True` on the 5070 (Blackwell/sm_120 supported by this build) |
| CPU | i7-14650HX (24 threads), 15.4 GiB visible to WSL |
| Realism check | 0.9B BF16 fits 8 GB VRAM comfortably; CPU float32 run attempted with the SAME official runtime (subset — §12); no third-party CPU wrapper used anywhere |

## 4-19. Benchmark results — MEASURED 2026-08-20 (same 25 texts, same machine, same judge as M33)

**Identity of the measured artifact**: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
@ revision `85e237c12c02…` (pinned snapshot; recorded in every evidence
JSON), voice **Ryan**, `language="English"`, official `qwen-tts` 0.1.1,
torch 2.11.0+cu128. Output: **24 000 Hz mono 16-bit** (same contract shape
as Kokoro — no conversion needed).

**Quality — round-trip intelligibility (whisper judge, frozen normalization):**

| Path | RT-WER | RT-CER |
|---|---|---|
| Kokoro + espeak fallback (M33) | **0.0716** | **0.0194** |
| Supertonic 3 (M33) | 0.0832 | 0.0270 |
| Kokoro production path (M33) | 0.1247 | 0.0940 |
| Magpie-357M CPU (M33) | 0.1991 | 0.0799 |
| **Qwen3-TTS 0.6B (GPU, this milestone)** | **0.2449** | **0.1524** — the weakest of the field |

**Where Qwen's errors come from (per-row transcripts):**
- **Expressive insertions on short/dry prompts** — the model ADDS
  disfluencies and vocalizations: "Hello, Sumit." → *"Heh heh heh heh
  heh. Hello, Sumit!"*; "That is wonderful news…" → *"Ah, ah, ah, ah,
  that is…"*; "You are coming to the office tomorrow" → *"You are, uh,
  um, coming…"*. This is the conversational-expressiveness training
  showing through — a feature for chatty agents, a defect for
  deterministic call-center prompts, and it is the main WER driver.
- **OOV preservation: GOOD** — Sumit, Kavya, Priya Sharma, Rajesh
  (Ayer), IntelliAI (Studio), QwikCart, Coimbatore: all SPOKEN, none
  dropped. On the axis where Kokoro's dictionary path fails, Qwen
  behaves like Magpie: attempts everything.
- **Raw formats need TN**: "12/08/2026" → *"12 divided-bass Juo8…"*;
  number fidelity shaky ("1247 dollars" heard as "$127"). Same
  normalization-layer requirement as every other engine (M33 §17).

**Latency / RTF — the decisive axis:**

| Run | RTF med | RTF p95 | TTFA | Notes |
|---|---|---|---|---|
| **GPU (RTX 5070, bf16)** | **1.486** | 1.565 | **= full wall (no streaming API in the released lib)** — "How are you?" costs 2.9 s; the 246-char paragraph 23.2 s; 795 chars 68.2 s | 25/25 ok |
| Long ladder (GPU) | 1.46 → **1.65** (degrades with length) | — | 2 039 chars → **205.7 s** wall for 124.3 s audio; no truncation, no repetition-loop failures up to 2 039 chars | correctness clean |
| **CPU (official runtime, float32, 6-probe subset)** | **3.054** | — | = full wall | works, but 3× slower than playback; peak RSS **6.0 GiB** |
| Kokoro (M33, same set) | 0.283 Docker / 0.164 native | 0.413 | 1.15 s median sentence (whole-body today; 0.7-1.3 s chunk-level available) | 25/25 ok |

The released `qwen-tts` library exposes NO streaming method
(introspected: `generate_custom_voice / generate_voice_clone /
generate_voice_design` only) — Qwen's "97 ms end-to-end" streaming
belongs to their own serving stack and is not reproducible locally.
TTFA through anything we can actually run equals the full walls above.

**Memory (kept separate as required):** GPU run — VRAM 2 057 MiB after
load, 2 834 MiB peak allocated, 3 736 MiB peak reserved (fits 8 GB
comfortably); process RSS peak 2 702 MiB. CPU run — RSS peak
**6 017 MiB**, no VRAM. Model load 15.7 s (GPU, warm cache).

**Concurrency:** the research runtime is a single in-process
`generate` loop — no server, no batching; c>1 was NOT measured
(sequential queue by construction; MEASURED LOCAL would only restate
RTF). At RTF 1.49/stream on GPU, concurrent call-center serving would
need roughly one GPU per ~0.67 concurrent streams — ESTIMATED, and
already disqualifying next to the incumbent's measured 0.557 rps on
CPU alone.

**Punctuation / prosody (signal-level):** Qwen renders the question
contour MOST convincingly of anything measured this week — "?" flips
the terminal F0 slope to **+3.24** Hz/frame (rising) vs −0.11 without.
But the same pairs expose duration instability from the insertion
behavior (the bare question variant ballooned 3.3 s → 10.8 s with
added "uh, um"). Exclamation/comma pairs in `evidence/qwen-prosody.json`.

**Human audition:** the M33 pack is extended in place — labels
**E = Qwen3-TTS (Ryan)** and **F = Kokoro+espeak fallback** added, 45
samples total, sha-256 manifest regenerated
([audition](audition/2026-08-20-en-tts/README.md)). **UNSCORED** —
machine intelligibility above is not naturalness; the ears may well
rank Qwen's voice pleasantness high. That axis stays UNKNOWN until
someone listens.

## 20. Decision matrix

| Axis | Kokoro (prod) | Kokoro+espeak (twin) | Qwen3-TTS 0.6B |
|---|---|---|---|
| English RT-WER | 0.1247 M | **0.0716 M** | 0.2449 M |
| English RT-CER | 0.0940 M | **0.0194 M** | 0.1524 M |
| OOV preservation | drops (M) | speaks via espeak (M) | **speaks natively (M)** |
| TTFA | 1.15 s median sentence (M) | same engine (M) | 2.9 s shortest; = full wall, no streaming (M) |
| Total latency (795 chars) | ~2.4 s @122 c; scales ~RTF 0.28 (M) | same (M) | 68.2 s GPU (M) |
| RTF med / p95 | **0.283 / 0.413 (M)** | 0.164 native (M) | 1.486 / 1.565 GPU (M) |
| RAM | 2.39 GiB (M) | same (M) | 2.7 GiB RSS GPU-run · 6.0 GiB CPU (M) |
| VRAM | 0 (M) | 0 (M) | 2.8 GiB peak alloc (M) |
| CPU support | **production-proven (M)** | same (M) | works at RTF 3.05 — infeasible (M) |
| GPU support | unneeded | unneeded | required for even RTF≈1.5 (M) |
| Streaming | chunk-ready (M32 M) | same | none in released lib (M); vendor-stack claim (CLAIMED) |
| Long text | 2 000-char law; chunked (M) | same | clean to 2 039 chars, RTF degrades to 1.65 (M) |
| Punctuation/prosody | mild (M) | same engine | **best question contour** but insertion instability (M) |
| Text normalization need | dates/₹ etc. (M) | same | same + slash-date mangling (M) |
| License | **Apache (M)** | + GPL binary at exec boundary (policy call) | **Apache end-to-end (M)** |
| Deployment complexity | in place (M) | + one subprocess component | new torch runtime, GPU class, no server (M) |
| Concurrency | 0.557 rps/box CPU (M) | same | ~0.67 streams/GPU (E) |
| Voice quality (ears) | UNKNOWN | UNKNOWN | UNKNOWN (pack ready) |
| Future Hindi | **measured path (M32)** | same | **none — 10 langs, no Hindi (M)** |

M = MEASURED · E = ESTIMATED · UNKNOWN as marked.

## 21. Final decision — **B. KOKORO WINS → proceed with Kokoro hardening**

Per the decision rule: Qwen3-TTS offers real advantages on exactly two
axes — a fully-Apache stack and native OOV preservation (plus the best
question intonation signal) — but both are matched or beaten by the
Kokoro+espeak hardening path (0.0716 WER, OOV solved, Apache weights,
one policy call), while Qwen brings **unacceptable regressions on the
non-negotiables**: CPU feasibility (RTF 3.05, 6 GiB), latency/TTFA
(RTF ≈ 1.5 even on GPU, no streaming in anything we can run),
intelligibility on deterministic prompts (insertion behavior, worst
WER of the field), and zero future-Hindi value. This is not close, and
it is not "newer = better": we measured it.

Not chosen: **A** (loses the measurement); **C — GPU candidate only**
(rejected deliberately: even on our GPU the released runtime is slower
than playback, so there is no GPU tier to defer to — unlike Magpie,
which at least has an unmeasured NeMo-GPU path); **D/E** (nothing
inconclusive or blocked: every axis measured cleanly). ONE focused
follow-up is licensed for the future, not scheduled: re-test ONLY if
Qwen ships a locally-runnable streaming/vLLM serving path for TTS —
that single change could flip the TTFA axis; nothing else here would
move.

## 22. Exact next milestone — unchanged: "Kokoro English TTS hardening" (M33 §22 verbatim)

espeak OOV fallback (policy-gated) · text normalization v1 · ONNX
evaluation · chunk merging/TTFA · billing-unit fix · stale-image
guards · voice naming · determinism documentation. This spike changes
nothing in that scope — it retires the "but should we switch to
Qwen3-TTS first?" question with numbers.

---

**Answers to the milestone's framing:**
- *Does Qwen3-TTS 0.6B beat Kokoro-82M for IntelliAI English?* **No — measured on identical texts, same judge, same machine**: worst intelligibility of the field (insertion behavior), RTF ≈ 1.5 on GPU / 3.05 on CPU vs Kokoro's 0.283 CPU, no runnable streaming, no Hindi future. Its genuine strengths (Apache stack, OOV preservation, question contour) are already covered or beaten by the approved hardening path.
- *What would change this verdict?* A locally-runnable official streaming runtime (TTFA axis) plus suppression of expressive insertions on dry prompts (quality axis) — both upstream events, both re-testable in a day with these instruments.
