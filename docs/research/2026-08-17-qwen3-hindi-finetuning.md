# Qwen3-ASR 0.6B Hindi Fine-Tuning — Experiment E1 (Milestone 21)

| | |
|---|---|
| **Status** | EXPERIMENT COMPLETE — research only; production untouched |
| **Date** | 2026-08-17 (training, evaluation, conversion, all evidence this date) |
| **Question** | Can fine-tuning on our governed 10 h public Hindi corpus improve the already-strong Qwen3 baseline (CER 0.1457)? |
| **Answer** | **Yes: CER 0.1457 → 0.12477 (−14.4% relative) on the frozen benchmark THROUGH THE REAL SERVING ADAPTER**, replicate within 0.0006, zero hallucination probes, English byte-perfect, long-audio chunked path intact, artifact serving-compatible on the pinned runtime |
| **Classification (Phase 18)** | **B. MODEST IMPROVEMENT** — real (~11× the replicate noise band), serving-proven, every deployability gate passed; "strong" is reserved for shifts of the 15E adoption's class (−60%) |

Labels: **[EVIDENCE]** committed record · **[FACT]** verified at source · **[LIMIT]** honest boundary.

## 1–2. Base model identity and license [FACT]

`Qwen/Qwen3-ASR-0.6B` @ revision `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`
(unchanged upstream since 2026-01-30; the same revision the 15E adoption
recorded). `model.safetensors` sha256 `79d6cbd4c98c7bbffe9db2edac07f56c…`
(1,876,091,704 bytes) — hash-verified after download, size-checked at every
load. License **apache-2.0**. 0.78B parameters total: a 596M-parameter
Qwen3-class text decoder (`thinker.model` + tied `lm_head`) and a 186M
audio tower (conv front-end + 24 layers + projectors, all inside
`thinker.audio_tower`). The serving GGUF artifacts kept their own identity
throughout; nothing was overwritten.

## 3–5. Data, governance, and the training manifest [FACT/EVIDENCE]

- Corpus: `hi-public-train@v1` — 4,988 clips / 10.0 h, IndicVoices Hindi
  (CC-BY-4.0) + Kathbath (CC0), the frozen manifest pinned at
  `a4748dee8a7a82ee4e1233587f3f4366fba91dfcb1e367415191e2e3388ee0df` and
  re-verified before every conversion (drift refuses to train).
- Eval disjointness: enforced at freeze time by content hash against
  `stt-hi-public-eval@v1` and its 32-speaker roster; re-verified forever
  by a new test (train and eval share no clip id and no audio path).
  Per-clip speaker ids for the train pool are not published upstream —
  content-hash disjointness is the provable guarantee, stated as at freeze.
- Deterministic conversion to the OFFICIAL Qwen JSONL (`{"audio", "text"}`
  with `language Hindi<asr_text>` headers — the exact format the serving
  adapter parses): train JSONL sha `1b69ce84b13b…` (4,822 rows),
  validation sha `2291ebff4e33…` (166 rows, id-hash split), relative
  paths, no audio copied. No customer or Speech Sample audio anywhere.

## 6–7. Training format and implementation [FACT]

Source of truth: the official `qwen3_asr_sft.py`
(QwenLM/Qwen3-ASR/finetuning) — chat-template prefix (empty system + one
audio user turn) masked to −100, target + EOS supervised, audio and text
through the wrapper's processor in one call, HF Trainer loop, `qwen-asr`
0.0.6 as the entry point (it pins transformers <5 → 4.57.6 in the
training venv). Our layer (`intelliai_training.qwen_manifest` /
`qwen_trainer`, committed `375fcef`) adds what the official script lacks
and our laws require — each divergence a recorded config field: seed
20260817, non-reentrant gradient checkpointing, Adafactor, frozen audio
tower (structural module search that refuses to freeze nothing),
validation at every checkpoint boundary, wrapper-loadable `inferable/`
composite snapshots beside every trainer checkpoint (the composite
implements no forward; the `thinker` is the training surface and mutates
the composite in place). Architecture quirks found and handled: nested
`thinker` layout, missing `get_input_embeddings`, forward-less composite,
upstream's invalid-but-inert sampling flags in `generation_config`.

## 8–9. GPU compatibility and smoke test [EVIDENCE]

RTX 5070 Laptop (8,150 MiB), torch 2.11.0+cu128, CUDA 12.8, bf16.
Full-parameter AdamW was arithmetically impossible (fp32 states alone
≈ 7.2 GiB for 0.9B params). The measured configuration is not:

| Smoke (8 samples, 4 steps) | |
|---|---|
| Peak VRAM | **5,060 MiB** |
| Per-step losses | 8.94 / 16.02 / 10.30 / 8.91 |
| Checkpoint → wrapper reload → real Hindi transcription | OK |
| Trainable / total parameters | 596,049,920 / 782,426,112 |

## 10. Pilot [EVIDENCE]

30 optimizer steps at the full configuration: validation loss 1.7257 →
1.6401, VRAM 5,101 MiB, coherent Devanagari output. Two observations
recorded: windowed train-loss spikes (partly the corpus's verbatim
`<unintelligible>` markup) and one 2-s clip emitting Chinese — later
attributed to BASE behavior on very short clips (the base's own worst
frozen-benchmark clips score CER 1.0 on the same class).

## 11–15. Full run [EVIDENCE]

| | |
|---|---|
| Configuration | effective batch 16 (2×8), lr 1e-5 linear + 3% warmup, 2 epochs (604 steps), Adafactor, bf16, gradient checkpointing, tower frozen, seed 20260817 |
| Duration / peak VRAM | **31.4 min / 5,274 MiB** |
| Validation loss (per checkpoint) | 0.6239 → 0.2747 → 0.2173 → **0.2093** — monotonic, no overfitting signal |
| Train loss (display) | ~1.55 windowed — the known HF grad-accumulation display inflation (÷8 ≈ 0.19, consistent with validation) |
| Records | `research/experiments/21-qwen3-hi-finetuning/full-run-record.json` (config, hashes, environment, loss histories); checkpoints 150/300/450/600/604 preserved under `weights/qwen-e1-hi-sft/` |

## 16. Checkpoint sweep (HF-side selection instrument) [EVIDENCE]

Same wrapper + same ruler + same frozen clips for every row
(`hf-eval.json`); the BASE row calibrates the harness against the
adapter baseline (0.14781 vs 0.1457 — within 0.002):

| Model | CER | WER | vs base |
|---|---|---|---|
| base | 0.14781 | 0.28177 | — |
| ck150 | 0.13868 | 0.27440 | −6.2% |
| ck300 | 0.12518 | 0.26489 | −15.3% |
| ck450 | 0.12594 | 0.26182 | −14.8% |
| **ck600 (selected)** | **0.12401** | **0.25967** | **−16.1%** |
| ck604 | 0.12484 | 0.25998 | −15.5% |

Zero empty outputs and zero prompt-echo probes in every row. Selection:
ck600 — best CER and WER, matching its best validation loss.

## 17–19. The official verdict, through the REAL adapter [EVIDENCE]

The exported candidate served by the PINNED b10344 llama-server behind
the existing engine seam, resolved through the research manifest,
measured by the standard runner — the 15E methodology exactly:

| | Qwen3 baseline (15E) | **qwen3-asr-0.6b-hi-ft-e1** | Δ |
|---|---|---|---|
| CER | 0.1457 | **0.12477** (replicate 0.12414; spread 0.0006 < the 0.0011 band) | **−14.4% rel** |
| WER | 0.2851 | 0.26642 | −6.5% rel |
| Substitutions / insertions / deletions | — | 0.2001 / 0.0289 / 0.0374 | — |
| Hallucinated probe words | 0 | **0** | = |
| Recognition RTF | 0.207 | 0.237 | same class |
| Model size (text GGUF + mmproj) | 804.7 MB + 214.4 MB | 804.7 MB + 214.4 MB (mmproj shared) | = |

Records: `2026-08-17-research-qwen3-asr-0.6b-hi-ft-e1-hi-m21{,-replicate}.json`.

## 20–22. Safety, probes, English [EVIDENCE]

- **English (adapter-side): WER 0.0** — both JFK clips byte-perfect
  (22/22 words), RTF 0.10 (`…-en-m21-safety.json`).
- **Silence/tone probes (adapter-side): empty hypotheses** — the
  pipeline VAD short-circuits no-speech audio before any engine
  (inference 0.00003 s), exactly as designed.
- **[LIMIT] HF-side silence finding, recorded honestly:** called
  directly (no VAD in front), the fine-tuned model emits a repeated
  nonsense token on pure digital silence where the base emits nothing —
  10 h of speech-only supervision taught it to always answer. Structurally
  unreachable through the product path (VAD), invisible on the frozen
  benchmark (zero empties), but a real behavioral regression to fix in
  the next arm (add silence/noise examples to the training manifest).
- **Long audio (M19 chunked path): intact** — 300 s through the runtime:
  200, 4 segments, join == text, Devanagari, complete.
- Language id: Hindi Devanagari intact; the base's short-clip language
  flips are not worsened (frozen-benchmark tails comparable).

## 23. Serving/export compatibility [EVIDENCE — the strongest result]

Mainline llama.cpp registers NO Qwen3-ASR conversion; the official text
GGUF is encoded as `qwen3vl` and its 311 tensors are exactly the
thinker's text side. Export therefore works by **template rewrite**:
copy the official artifact's structure (every metadata key, tensor name,
ordering, per-tensor ggml type) and replace only tensor payloads,
quantized from the fine-tuned weights with the b10344-exact gguf-py
(0.19.0). The pipeline's control: applied to the BASE weights it
reproduces the official artifact **byte-for-byte** (sha256
`bca259818b50…` — the exact supply-chain pin). Conversion adds nothing;
every measured delta is training. The mmproj is the official artifact
reused byte-for-byte (tower frozen). The candidate loads and serves on
the pinned runtime — proven live by the entire §17 evaluation.

## 24. Artifact identity [FACT]

`qwen3-asr-0.6b-hi-ft-e1@v1`, registered in the engine's admission table
(research-only, `.invalid` URL, locally placed, hash-verified at load):

| Link | Hash |
|---|---|
| Base revision / weights | `5eb144179a02…` / `79d6cbd4c98c…` |
| Train manifest / derived JSONL (train/val) | `a4748dee…` / `1b69ce84b13b…` / `2291ebff4e33…` |
| Selected checkpoint (ck600 safetensors) | `49d772cae524…` |
| Exported text GGUF (Q8_0) | `63e98aae609d…` |
| mmproj (official, shared) | `41a342b5e4c5…` |
| Training code commit | `375fcef` |
| Decoding config | identical to the incumbent (greedy, ctx 4096, same prompt/marker — `describe()` unchanged) |

## 25–26. Ledger, tests, CI

Ledger appended (`long_audio_ready_600s` unchanged for the incumbent; the
candidate enters as a new dated entry). Tests: 16 training-layer tests +
3 engine registration guards + anchor-table updates; full sweep green
(runtime 74, training 16, evaluation 595, datasets — 843 total in the ML
sweep), ruff and mypy clean. CI on the milestone commits.

## 27. Final decision

**B. MODEST IMPROVEMENT** — decided on the frozen-benchmark adapter
numbers, not training loss: −14.4% relative CER at zero hallucinations,
English intact, serving-proven on the pinned runtime, one recorded
VAD-mitigated silence regression. NOT promoted: production Hindi still
routes to whisper-small; the M18 promotion proposal still names the
INCUMBENT qwen artifact; replacing the candidate inside that proposal is
a founder decision this experiment deliberately does not make.

## 28. Recommendation for the next experiment

1. **Data first:** the corpus's verbatim markup (`<unintelligible>`) and
   the silence regression share one fix — a curation pass (strip/skip
   markup, add silence/noise negatives) before any second epoch count or
   LR sweep. The loss spikes say data, not optimizer.
2. Scale test: 10 h → 25–40 h (Kathbath is barely tapped) at the same
   conservative configuration; the ck300→ck600 plateau suggests data,
   not steps, is the binding constraint.
3. Then, if promoted past the incumbent: the full M16-style switching
   battery + M17 canary prep on the winner, and only then a proposal
   edit.
