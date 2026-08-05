# Voxtral (Mistral AI) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** for `Voxtral-Mini-3B-2507` only — `apache-2.0` verified at source; **gated** via privacy-policy notice. Other variants unverified; each needs its own verdict. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

Voxtral — Mistral's audio/speech line, first released July 2025 **[CLAIM]**. Family
members reported: **Voxtral Mini 3B** (verified), **Voxtral Small 24B** (repository
exists), plus **realtime** and **Transcribe** variants reported in 2026 landscape
material **[CLAIM]**.

**Scope note:** everything verified in this dossier concerns `Voxtral-Mini-3B-2507`.
Claims about the realtime and Transcribe variants are explicitly unverified and would
require their own Gate 1 verdicts.

## 2. Architecture

- **Design** **[CLAIM]**: audio-LLM — an audio encoder feeding a Mistral language-model
  backbone, retaining text capability alongside speech understanding.
- **Sizes** **[FACT — card]**: Mini card reports **3B**, with **~5B total parameters**
  including the audio encoder. Small is 24B **[CLAIM]**.
- **Realtime variant** **[CLAIM]**: ~4B total (≈3.4B LM + ≈970M audio encoder), with a
  **causal audio encoder trained from scratch** and **sliding-window attention on both
  halves**, enabling effectively unbounded streaming.
- **Context** **[CLAIM]**: 32k tokens; up to ~30 minutes of audio for transcription, ~40
  minutes for understanding — i.e. **no 30-second window constraint**, unlike Whisper.
- **Decoding** **[INFERENCE]**: autoregressive LM decode.
- **Timestamps** **[INFERENCE — open question]**: not documented in material reviewed here.
- **Tokenizer** **[INFERENCE]**: Mistral's text tokenizer (Tekken lineage).
- **Streaming** **[CLAIM — architecturally, not merely wrapped]**: the causal encoder plus
  sliding-window attention is a genuine streaming design, distinct from chunking an offline
  model. **[FACT — that this is the distinguishing claim of the lineage.]**
- **Multilingual strategy** **[CLAIM]**: one model with automatic language detection.

## 3. Languages

**[FACT — Mini card]** Eight languages: English, Spanish, French, Portuguese, **Hindi**,
German, Dutch, Italian. **[CLAIM]** The realtime variant is reported at 13 languages.

**No Arabic** in the primary set **[FACT]**. Hindi's presence is what makes this lineage
strategically live for us; its Hindi *quality* is entirely unmeasured **[FACT]**.

## 4. Licensing (Gate 1, verified 2026-08-05)

`apache-2.0` on the Mini card **[FACT]**. Distribution carries an `extra_gated_description`
referencing Mistral's privacy policy — **access gating, not a licence condition**
**[FACT]**. Mistral has a consistent Apache-2.0 posture for open weights **[CLAIM]**.

## 5. Runtime and deployment profile

- **vLLM** **[CLAIM]**: day-0 vLLM Realtime API support reported for the realtime variant.
- **Serving stack** **[INFERENCE]**: Transformers and vLLM are the expected paths; Mistral's
  own `mistral-common` tooling may be required for correct audio preprocessing.
- **Remote code** **[FACT]**: not indicated on the Mini card.
- **Quantization** **[INFERENCE — open question]**: no first-party quantized artifacts
  identified in this sweep. GGUF/llama.cpp support for audio-LLMs is uneven **[CLAIM]**,
  and no Voxtral-specific CPU path was found.
- **ONNX / CTranslate2** **[INFERENCE]**: none identified; not expected for this
  architecture class.
- **Hardware claim** **[CLAIM]**: the realtime variant reportedly runs on a **single 16GB
  GPU**. This is a *GPU-shaped* statement — it is the clearest available signal that the
  lineage's design centre is GPU serving.
- **CPU friendliness** **[INFERENCE — the decisive open question]**: a 3B model with ~5B
  total parameters is roughly 20× our incumbent's parameter count. Nothing indicates a
  CPU-viable path exists today.
- **Cold start / memory** **[INFERENCE]**: substantially larger artifact and memory
  footprint than anything we currently operate; unmeasured.
- **Batching** **[CLAIM]**: standard vLLM batching applies.

## 6. Quality evidence

**None from IntelliAI.** External figures excluded at this gate.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** The realtime variant's entire design premise is
low latency, so latency-per-token is likely favourable *on GPU*; that says nothing about
our CPU serving class.

## 8. Fine-tuning ecosystem

- **[CLAIM]** Mistral models are broadly supported by the open fine-tuning toolchain
  (LoRA/QLoRA via PEFT, LLaMA-Factory, Unsloth) for the *text* lineage.
- **[INFERENCE]** Speech-variant fine-tuning support is unverified. Audio-LLM tuning
  typically requires either freezing the audio encoder or bespoke handling; no
  Voxtral-specific recipe was identified in this sweep.
- **[INFERENCE]** Adapter-based Hindi adaptation is *architecturally* conceivable but
  entirely unevidenced.

## 9. Training support

**[CLAIM]** A Voxtral paper exists (arXiv:2507.13264). Training data and recipes are not
verified as released **[FACT — unverified]**. Continued pretraining support unknown.

## 10. Ecosystem and research maturity

- **Publication** **[CLAIM]**: paper published alongside release.
- **Maintenance cadence** **[CLAIM]**: active; multiple variants shipped across 2025–2026.
- **Documentation** **[FACT]**: model cards plus Mistral's own API documentation for audio
  capabilities.
- **Adoption** **[CLAIM]**: strong attention in the 2026 landscape; commercial API offered
  alongside open weights.
- **Ecosystem** **[INFERENCE]**: benefits from Mistral's broad tooling integration, though
  the audio path is younger than the text path.

## 11. Known strengths

The only lineage in this universe claiming **permissive licence + Hindi + native streaming
simultaneously**; no fixed audio window (30–40 minute context); a genuine causal streaming
architecture rather than chunking; European vendor with consistent Apache-2.0 practice and
active cadence; strong ecosystem tooling.

## 12. Known weaknesses

**[FACT]** No Arabic. **[FACT]** Gated distribution. **[INFERENCE]** Largest CPU risk of
the small-model candidates — 3B/5B-total against our 244M incumbent. **[INFERENCE]** No
identified quantization or CPU path. **[INFERENCE]** Timestamps undocumented.
**[INFERENCE]** Audio-LLMs carry instruction-following and hallucination surface that
CTC/transducer models structurally do not — unmeasured, and a real robustness question.

## 13. Integration risks

- **[INFERENCE]** **CPU-first collision.** If this lineage is adopted, it likely forces the
  GPU-tier decision our constitution has so far deferred. That is a platform-level
  consequence, not an engine swap.
- **[FACT]** **Gated fetch** — our ArtifactStore pins URLs and downloads at container boot;
  a credentialled fetch is a pipeline change.
- **[INFERENCE]** **Multi-variant licence surface**: adopting "Voxtral" means picking a
  specific variant, and only Mini is verified.
- **[INFERENCE]** Streaming would exercise a runtime path (`M8`) we have not built; the
  contract currently has no streaming method.

## 14. Open questions carried to Gate 3

CPU feasibility (decisive) · quantization availability · timestamp support and quality ·
Hindi robustness · hallucination behaviour of an LM decoder on silence and noise ·
whether the realtime variant's streaming can be consumed through our runtime contract ·
per-variant licence verification.

## 15. Strategic value to IntelliAI

- **Hindi improvement candidate** — research priority #2, with a permissive licence.
- **Streaming research candidate** — the M8 streaming question, in a lineage that also
  claims Hindi; no other candidate combines both.
- **GPU-tier candidate** — the clearest forcing function for the CPU-vs-GPU decision.
- **[INFERENCE]** Its greatest research value may be *diagnostic*: measuring it tells us
  what the 2026 audio-LLM generation costs us, regardless of adoption.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-VOXTRAL:** *Voxtral Mini will transcribe Hindi more accurately than whisper-small on
> our corpus, but will not run within our CPU serving class at all — making it the
> candidate that forces IntelliAI's GPU-tier decision rather than one that fits the
> existing architecture.*

Falsifiable in both halves: Hindi may not improve, and a quantized CPU path may emerge.
