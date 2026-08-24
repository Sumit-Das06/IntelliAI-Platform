# Qwen3-TTS English Baseline + Public-Data Fine-Tuning (Milestone 44)

| | |
|---|---|
| **Status** | COMPLETE — MEASURED. Track A: Qwen Base beats Kokoro on clean-text WER but loses on OOV, latency and streaming. Track B: fine-tuning FAILED (text-conditioning collapse; verdict F). Kokoro stays production. |
| **Date** | 2026-08-24 |
| **Question** | Can fine-tuning materially improve Qwen3-TTS 0.6B English enough to become a better user-experience-oriented TTS candidate than the Kokoro incumbent — under the NEW rule that GPU serving is acceptable when the user experience is better? |
| **Scope** | Research only. Kokoro stays production (M42 posture untouched); no Hindi, no cloning product, no deployment. |
| **Evidence** | `research/experiments/44-qwen3-tts-finetuning/` (manifest, benches, round-trips) · WAVs outside git |
| **Labels** | MEASURED · WEB-RESEARCHED · REPO-VERIFIED · ESTIMATED · UNKNOWN · PROPOSED |

## 1. Model identity (Phase 1) — WEB-RESEARCHED at source + MEASURED by execution

| Fact | Value |
|---|---|
| Model | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` @ revision `5d83992436eae1d760afd27aff78a71d676296fc` |
| Codec/tokenizer | `Qwen/Qwen3-TTS-Tokenizer-12Hz` @ `7dd38ad4e9bad454aae9cd937d0cd577604fe229` |
| License | Apache-2.0 both repos (card tags, 2026-08-24) — **CLEAR** |
| Architecture | 12Hz talker + 16-codebook sub-talker over the NanoCodec-class speech tokenizer; "0.6B" repo carries ~0.9B params (the M34 fact, unchanged) |
| Interface | Base = reference-conditioned (voice-clone: `ref_audio` + `ref_text` per call); fine-tuning converts it to a named `custom_voice` speaker |
| Streaming | Card claims 97 ms E2E; **the released `qwen-tts` 0.1.1 runtime exposes NO streaming API** — re-introspected on this Base model (no `*_stream` method; `generate_voice_clone` returns the complete waveform). TTFA = full wall. MEASURED |
| Local artifacts | plain-dir downloads at the pinned revisions; `model.safetensors` sha256 `180b3b10…` (base), `836b7b35…` (tokenizer) — recorded at download |
| Official fine-tuning | `finetuning/{prepare_data.py, sft_12hz.py, dataset.py}` vendored at their 2026-08-24 state (sha256 in the run log): JSONL `{audio, text, ref_audio}` → codes via the 12Hz tokenizer → full-model SFT (Accelerate, bf16, grad-accum 4) → per-epoch full checkpoints with the speaker embedding written to codec row 3000, `tts_model_type=custom_voice` |

## 2. Hardware (Phase 2) — MEASURED

RTX 5070 Laptop 8151 MiB VRAM (driver 591.91) · 15 GiB WSL RAM ·
Python 3.12 · torch 2.11.0+cu128 (CUDA verified) · qwen-tts 0.1.1 ·
accelerate 1.12.0 · bitsandbytes 0.50.1. flash-attn NOT installed
(the official SFT script requests `flash_attention_2`; adaptation §8).

## 3. Dataset (Phases 4-8) — qwen-en-public-train@v1, FROZEN

- **Source**: LJSpeech-1.1 (keithito.com, archive sha256 in the
  manifest) — **public domain**, single English speaker, 13,100 clips
  @ 22.05 kHz mono. Chosen because the official recipe is
  single-speaker-only, and LJSpeech is the canonical, legally cleanest
  single-speaker corpus (secondary candidate VCTK not needed).
- **Validation**: decode + format + 1-15 s + non-empty unique
  transcript + chars/sec plausibility → **13,074 valid of 13,100**;
  rejections: 26 × duplicate_text (recorded per reason).
- **Frozen**: seed-44 utterance splits — **train 1000 / val 50 / test
  100** (~2.1 h total), held-out test never trains; per-row SHA-256 in
  `evidence/qwen-en-public-train-v1.json`. Frozen BEFORE any training.
- **Reference clip** (the official same-ref-everywhere rule):
  `LJ001-0004` (5.1 s, digit-free), pinned by hash; the SAME clip
  drives Base zero-shot cloning in every benchmark, so Base vs
  Fine-Tuned compares one target voice.

## 4. Track A — baselines on the frozen sets (Phase 9-13) — MEASURED

Judge = the production whisper route through the real gateway, frozen
normalization and metric code (the M2.5→M43 discipline).

| System | LJ held-out (100) RT-WER/CER | M33 trap set (25) RT-WER/CER | M44 OOV set (12) | GPU RTF | VRAM peak | notes |
|---|---|---|---|---|---|---|
| Kokoro hardened (gateway, CPU) | **0.0535 / 0.0317** | 0.0659 / 0.0251 (M35, unchanged) | 0.1085 / 0.0451 | CPU RTF 0.183 (OOV 0.249) | — | 100/100, zero failures |
| Qwen3-TTS Base (clone, LJ ref) | **0.0478 / 0.0299** | **0.0515 / 0.0236** | 0.1724 / 0.0582 | 1.42–1.60 median | 2.9 GiB alloc / 4.0 GiB reserved | 137/137 zero failures; names (Sumit/Priya/Rajesh) clean, tech brands slip |
| Qwen3-TTS Fine-Tuned (full, all checkpoints) | collapse — unjudgeable | collapse | collapse | runaway | 7.9 GiB (train) | §5: content ignores input text; generation often never terminates |

Qwen Base is the first system to beat Kokoro on clean-text WER (LJ
0.0478 vs 0.0535; trap 0.0515 vs 0.0659) — M34's terrible Qwen numbers
were a speaker-style artifact (expressive CustomVoice speaker), not
model quality. It loses on OOV (0.1724 vs 0.1085) and everywhere on
speed. CPU inference spot-run: RTF **2.85** float32 (12.1 s wall for
4.2 s audio, 1 probe, informative — M34 measured CustomVoice CPU RTF
3.05; the new rule does not require CPU, but this confirms CPU serving
is not viable).

Streaming (Phase 14): no streaming path exists in the released
runtime, so TTFA = total wall for every Qwen row (honest whole-shot);
vLLM's day-0 support is the EXPERIMENTAL route, not benchmarked here.

## 5. Track B — the fine-tuning experiment (Phases 15-18)

- **Recipe**: the official scripts, reproduced as-is except the
  documented environment adaptations (§8). Codes prepared once with
  the pinned 12Hz tokenizer; training JSONLs frozen from the manifest.
- **Tiny overfit (Phase 16)**: 4 utts × 12 epochs, lr 1e-4 — loss
  12.43 → 0.056: the pipeline CAN fit (learning proven); the
  checkpoint speaks the target voice on trained texts but runs away on
  unseen texts (expected overfit symptom). Pipeline test only.
- **Pilot (Phase 17)**: 100 utts × 2 epochs, lr 5e-6 — fluent LJ-voice
  speech with UNRELATED content ("The quick prompt function also
  relates to talking to the client." for the quick-brown-fox probe).
  Diagnosed before scaling: input assembly verified line-by-line
  against the model's own inference ICL path (they match); initial
  loss 12.27 > uniform ln(3072) ≈ 8.03 shows the custom-voice training
  pattern is far from the base model's operating distribution; loss
  still falling at pilot end → the full run was the honest test of the
  "under-trained" hypothesis.
- **Full run (Phase 18)**: **FAILED — text-conditioning collapse.**
  Config: 1000 utts × 3 epochs, batch 1, grad-accum 4 (750 updates),
  lr 5e-6, bf16 AdamW, ~21 min/epoch, VRAM 7882/8151 MiB, exit 0.
  Loss 12.27 → 3.83 (e0) → 3.53 (e1) → 3.33 (e2), plateaued through
  epochs 1-2 — so the collapse is NOT under-training. Checkpoint
  selected by frozen VAL evidence: **NONE selectable** — epoch-2 on 10
  in-domain VAL texts produced 1 WAV in 25 min, and that WAV is
  **655 s of audio for a 16-word sentence**; epoch-1 produced 0/2
  sanity WAVs; epoch-0's sole WAV transcribed as empty. Epoch-2 on
  short probes speaks fluent LJ-voice content unrelated to the input
  text ("Thank you for calling." → an expletive exclamation). Full
  detail: `evidence/qwen-ft-full-collapse.json`. Scope of the claim:
  the official recipe on **0.6B** in this environment failed — the
  script does not even run unmodified on 0.6B (2048-vs-1024 dim
  crash), consistent with a 1.7B-only recipe; 1.7B or an upstream fix
  may behave differently.

## 6. Out-of-domain retention (Phase 20) — HARD GATE

The M33 trap set and M44 OOV probes are NOT LJSpeech-domain text; the
Base-vs-Fine-Tuned delta there is the regression gate. **Gate not
reached**: the fine-tuned checkpoints fail before OOD is even a
question — they cannot reproduce in-domain text either. For the
record, Base's own OOV weakness (0.1724 vs Kokoro 0.1085) stands as
the OOD baseline any future fine-tune must not worsen.

## 7. Human axis (Phases 21-22) — UNSCORED

Audition pack (same texts across: original LJ recording · Base clone ·
Fine-Tuned · Kokoro) at the session scratchpad `m44-audition/`; rubric
(naturalness / intelligibility / pronunciation / speaker similarity /
prosody / overall, 1-5) ships UNSCORED until a human listens. Machine
WER is never called naturalness.

## 8. Documented environment adaptations (memory/compat-fit ONLY)

1. `attn_implementation="flash_attention_2"` → `"sdpa"` — flash-attn
   is not installed; SDPA is stock PyTorch attention, mathematically
   equivalent (slower).
2. `input_text_embedding` wrapped with `model.talker.text_projection(…)`
   — the 0.6B talker has `text_hidden_size` 2048 ≠ `hidden_size` 1024;
   the official script adds unprojected text embeddings and crashes on
   0.6B with a 2048-vs-1024 dim mismatch. The projection is exactly
   what the model's own inference path applies
   (`modeling_qwen3_tts.py` `generate_icl_prompt`), so this is the
   minimal faithful fix, not a recipe change.
   (A bitsandbytes AdamW8bit fallback was prepared but NOT needed —
   official AdamW at batch 1 fits in 7882/8151 MiB with bf16 moments.)
Nothing else in the official recipe was altered; both changes are
recorded in `sft_12hz_m44.py` (a separate copy — the pristine official
scripts and their SHA-256 are kept alongside) so the run is
reproducible.

## 9. User experience & GPU-candidate analysis (Phases 23-24)

The new rule says GPU serving is acceptable **when the user experience
is better**. Measured, the experience is not better:

- **Responsiveness**: Kokoro streams — first audio in 0.4–1.6 s
  regardless of text length (M36/M37). Qwen has no streaming API in
  the released runtime, so the user waits the FULL synthesis wall:
  at GPU RTF ~1.5, a 20 s answer means ~30 s of silence. Under the
  UX-first rule this is the decisive axis, and it is a regression.
- **Quality**: Qwen Base's clean-text WER win (0.0478/0.0515 vs
  0.0535/0.0659) is real but small — both are already in the
  "occasional slip" regime — while its OOV regression (0.1724 vs
  0.1085) hits exactly the product-critical text class (brands,
  tech terms).
- **Cost/ops**: Qwen needs a GPU (2.9 GiB alloc / 4.0 GiB reserved)
  to hit even RTF 1.4–1.6; Kokoro serves on the CPU we already run
  at RTF 0.18.

The honest UX statement: Qwen Base would give slightly cleaner
pronunciation of plain sentences at the price of length-proportional
silence before every utterance, worse brand/term pronunciation, and a
GPU bill. The EXPERIMENTAL path that could change this is vLLM's
streaming support for Qwen3-TTS — a future research thread, not part
of this verdict.

## 10. Decision matrix (Phase 27)

| System | WER (LJ) | WER (trap) | TTFA | RTF GPU | RTF CPU | VRAM | RAM | OOV | Naturalness | License | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kokoro hardened | 0.0535 M | 0.0659 M | 0.4-1.6 s streamed M | — | 0.17-0.28 M | — | ~2.4 GiB M | 0.1085 M | UNSCORED | Apache + exec-boundary espeak | **KEEPS PRODUCTION** |
| Qwen Base | 0.0478 M | 0.0515 M | = total (no streaming) M | 1.42-1.60 M | 2.85 spot M | 2.9 GiB alloc M | 2.7 GiB M | 0.1724 M | UNSCORED | Apache-2.0 | quality-promising, UX-losing; shelved pending streaming |
| Qwen Fine-Tuned | collapse M | collapse M | runaway M | — | — | — | — | collapse M | UNSCORED | Apache-2.0 derivative | FAILED (verdict F) |

## 11. Decision (Phase 28)

**D. KOKORO STILL WINS** (Track B sub-verdict: **F — fine-tuning
failed**).

- Track B produced no usable model: every full-run checkpoint ignores
  the input text and generation frequently never terminates. No
  checkpoint passed frozen-VAL selection, so no fine-tuned candidate
  exists to compare. Recorded honestly as F for the recipe-on-0.6B in
  this environment; not generalized beyond that.
- Track A's genuine discovery: **Qwen3-TTS 0.6B Base is the first
  system to beat Kokoro on clean-text WER** (M34's bad numbers were
  the expressive speaker's style, not the model). But under the
  UX-first rule the decision axis is responsiveness, and whole-shot
  synthesis at RTF 1.5 loses to Kokoro's 0.4–1.6 s streamed TTFA on
  every text longer than a phrase — plus a worse OOV class and a GPU
  requirement.
- Production posture unchanged: Kokoro serves English and Hindi
  exactly as promoted in M42. Nothing in this milestone touches it.

## 12. Next milestone (Phase 29)

PROPOSED research threads (no milestone commitment implied):

1. **Qwen streaming via vLLM** — the one change that could flip the
   UX verdict: if vLLM's day-0 Qwen3-TTS support delivers real chunked
   audio with TTFA under ~1 s, Base's clean-text quality win becomes
   product-relevant. Measure TTFA/RTF/VRAM under vLLM before any
   further fine-tuning thought.
2. **1.7B fine-tune** — the official recipe was evidently written for
   1.7B (0.6B needs a dim fix to even run). If the fine-tuning
   question returns, run the untouched official script on the 1.7B
   Base on rented GPU hours rather than re-fighting 0.6B.
3. **Standing threads unchanged** — Arabic open slots; Hindi gates
   (M38/M39 posture).
