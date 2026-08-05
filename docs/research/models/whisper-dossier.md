# Whisper (OpenAI) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — MIT covering code *and* weights; full serving chain MIT; no gate, no remote code |
| **Status** | Approved for Adoption (small, incumbent) · Researching (large-v3 / turbo) |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source or from our own evaluation records ·
> **[CLAIM]** publisher or third-party statement, unverified by us ·
> **[INFERENCE]** reasoning from architecture or precedent — not evidence.
> No scoring, ranking, cross-candidate comparison, or adoption recommendation appears here.

## 1. Identity

OpenAI Whisper, released 2022. Weakly-supervised encoder-decoder trained on ~680k hours
of web audio **[CLAIM — publisher]**. IntelliAI serves `whisper-small` via faster-whisper
(CTranslate2) as the engine behind `intelliai-stt` **[FACT — production since v0.3]**.

Derivative families inheriting the licence and tooling: **Distil-Whisper** (distilled),
**IndicWhisper** (AI4Bharat Indic fine-tunes — BLOCKED at Gate 1, frozen).

## 2. Architecture

- **Design** **[FACT]**: Transformer encoder-decoder. Audio → log-Mel spectrogram → conv
  front-end → encoder; text decoder is autoregressive, cross-attending to encoder output.
- **Fixed 30-second window** **[FACT]**: all input is padded or truncated to exactly 30s.
  Cost is therefore constant per window regardless of actual speech length.
- **Multilingual strategy** **[FACT]**: a *single* multilingual model with special task
  tokens (`<|transcribe|>`, `<|translate|>`, `<|lang|>`), not per-language heads. Language
  is either specified or auto-detected from the first window.
- **Decoding** **[FACT]**: autoregressive beam or greedy search, with temperature fallback
  and compression-ratio / log-prob heuristics to catch degenerate loops.
- **Timestamps** **[FACT]**: segment-level via decoded timestamp tokens; word-level
  requires cross-attention alignment post-processing (implemented in faster-whisper and
  WhisperX), not native model output.
- **Tokenizer** **[FACT]**: byte-level BPE (GPT-2 lineage), multilingual vocabulary.
- **Streaming** **[FACT]**: none native. Streaming is an application-layer construction
  (chunking + VAD gating), which is what our pipeline already performs.

## 3. Languages

~99 languages claimed **[CLAIM]**. IntelliAI's own position, which is what matters:

- **English** — **[FACT]** WER 0.000 on `stt-eval-v1`; production baseline 2026-08-03.
- **Hindi** — usable; one anecdotal error observed (लगता → लकता, founder self-test).
  Unmeasured at corpus scale **[FACT — that it is unmeasured]**.
- **Arabic** — claimed by the card; **never evaluated by us** **[FACT]**.
- **Code-mixed** — no evidence either way.

## 4. Licensing (Gate 1, verified 2026-08-05)

MIT, stated verbatim in the repository README as covering **"Whisper's code and model
weights"** **[FACT]**. Transitive chain verified the same day: faster-whisper MIT,
CTranslate2 MIT **[FACT]**. No gating, no acceptable-use policy, no attribution beyond
the MIT notice, no field-of-use, MAU, or export restrictions found **[FACT]**.

## 5. Runtime and deployment profile

- **Serving stacks** **[FACT]**: the richest in ASR — CTranslate2/faster-whisper (ours),
  `whisper.cpp` (GGML/GGUF, CPU-first), HuggingFace Transformers, ONNX exports, WhisperX,
  vLLM support for encoder-decoder speech paths.
- **Quantization** **[FACT]**: int8 is production-proven *in our own stack*; CTranslate2
  supports int8/int8_float16/float16; `whisper.cpp` adds 4/5-bit GGUF variants.
- **Remote code** **[FACT]**: none required.
- **CPU friendliness** **[FACT — measured by us]**: `small` int8 runs at RTF 0.162
  (~6× realtime) at ~800 MiB steady-state on our reference hardware. This is the only
  CPU number in this entire dossier set that is *evidence* rather than claim.
- **GPU expectations** **[INFERENCE]**: optional, not required, at every size — the
  lineage predates the audio-LLM era's GPU assumptions.
- **Cold start** **[FACT — measured]**: 46s first boot including a 40.9s weights download;
  2.4s warm restart; load 713–907 ms; warm-up ~1.4 s.
- **Batching** **[CLAIM]**: supported by most serving stacks; we do not currently batch.
- **Operational maturity** **[FACT]**: the only lineage here with which we have real
  production operating experience — failure modes, container behaviour, and admission
  characteristics are all known quantities.

## 6. Quality evidence

Our own records: `2026-08-02-whisper-small.json`, production baseline
`2026-08-03-whisper-small-cpu-baseline.md` **[FACT]**. Large-v3 and turbo have **no
IntelliAI evidence at all** — the delta over `small` on our corpus is unmeasured.

## 7. Latency and memory expectations

`small` int8: p50 ~1.75 s steady-state on our reference hardware, ~800 MiB flat across
concurrency levels **[FACT — measured]**. `large-v3` is ~6× the parameters of `small`;
CPU latency and memory at that size are **unknown to us** **[FACT — that it is unknown]**,
and the 30-second fixed window means cost does not fall for short utterances **[FACT]**.

## 8. Fine-tuning ecosystem

- **[FACT]** The largest fine-tuning ecosystem in ASR: HuggingFace training recipes, PEFT
  compatibility, LoRA and QLoRA precedent, and a mature *Indic* fine-tune community.
- **[CLAIM]** Community fine-tunes exist for a wide range of languages and domains.
- **[INFERENCE]** This is the lineage where fine-tuning capital compounds fastest for us,
  because our serving stack, evaluation tooling, and operational knowledge all already
  target it — the "capital compounds within a lineage" argument in FINE_TUNING_STRATEGY
  Part 4 applies here more strongly than to any other candidate.

## 9. Training support

Full training and fine-tuning recipes are public **[FACT]**; the *original training data*
is not released **[FACT]**. Continued pretraining is therefore possible in principle but
without the original corpus. Upstream itself is frozen — no new checkpoints **[FACT]**.

## 10. Ecosystem and research maturity

- **Publication** **[FACT]**: the original Whisper paper is among the most-cited works in
  modern ASR; the architecture is textbook-documented.
- **Maintenance** **[FACT]**: upstream repository effectively frozen (170 commits, no new
  checkpoints); the *ecosystem* is highly active — faster-whisper and CTranslate2 both
  show ongoing development.
- **Documentation** **[FACT]**: excellent, and reinforced by years of third-party writing.
- **Adoption** **[FACT]**: the de facto default open ASR model; 107k GitHub stars.
- **Strategic reading of "frozen"** **[INFERENCE]**: for a company that intends to
  fine-tune, a frozen base is a stability asset, not decay — the checkpoint stops moving
  under our evaluations. The risk is not staleness but the ecosystem eventually migrating.

## 11. Known strengths

Licence cleanliness end-to-end; proven CPU economics *in our own production*; the largest
fine-tuning ecosystem; broad language coverage; mature tooling; known failure modes;
zero operational unknowns for us.

## 12. Known weaknesses

**[FACT]** Hallucination on silence and non-speech — structurally mitigated in our stack
by VAD short-circuit (probes measure 0 hallucinated words), but the model behaviour itself
remains. **[FACT]** Fixed 30 s window: no cost benefit for short utterances.
**[FACT]** No native streaming. **[FACT]** No diarization. **[FACT]** Word-level
timestamps require post-processing rather than native output. **[CLAIM]** 2022-era
quality tier relative to the 2026 generation — untested by us.

## 13. Integration risks

Effectively none for `small` — it is already integrated. For `large-v3`/`turbo` the risks
are **cost, not correctness** **[INFERENCE]**: memory and latency could break our CPU-first
economics at current serving-class assumptions. Secondary risk **[INFERENCE]**: ecosystem
drift, if the tooling community migrates to newer lineages over a multi-year horizon.

## 14. Strategic value to IntelliAI

**Incumbent baseline and reference frame.** Every challenger in this research universe is
defined by the switching test against this lineage, so understanding its ceiling *is* the
research programme's spine. Two distinct strategic roles:

- **English incumbent** — the thing to beat (research priority #1).
- **Hindi improvement candidate** — via in-lineage fine-tuning, the cheapest rung of §9
  that could move Hindi without changing anything operational.

## 15. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-WHISPER:** *Whisper large-v3 will measurably reduce Hindi word error against
> whisper-small on our corpus, but at a CPU latency and memory cost that breaches our
> current serving-class assumptions — making the Hindi question a cost decision rather
> than a quality one.*

Testable, and falsifiable in both halves: large-v3 may fail to improve Hindi
meaningfully, or may prove affordable. Either result redirects the Hindi thread.
