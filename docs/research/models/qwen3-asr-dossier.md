# Qwen3-ASR (Alibaba / Qwen) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `apache-2.0` verified at source; not gated; no remote code. Verdict does **not** generalise to Qwen text repositories, several of which ship custom LICENSE files. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

Qwen3-ASR — the speech-recognition line of Alibaba's Qwen family, released Jan 2026.
Published sizes: **`Qwen3-ASR-0.6B`** and **`Qwen3-ASR-1.7B`**, plus a
**`Qwen3-ASR-1.7B-hf`** Transformers-native variant **[FACT — all repositories exist]**.
Technical report: arXiv:2601.21337 **[FACT]**.

Companion model: **`Qwen3-ForcedAligner-0.6B`** **[FACT]** — a separate artifact, and
therefore a separate licence verdict if ever adopted.

## 2. Architecture

- **Design** **[CLAIM — technical report]**: audio-LLM. Derives from **Qwen3-Omni**, whose
  audio tower it shares; a language-model backbone decodes text.
- **Deliberately small** **[FACT]**: 0.6B / 1.7B, in contrast to the 2–3B audio-LLM norm
  of this generation.
- **Decoding** **[INFERENCE]**: autoregressive LM decode.
- **Timestamps — architecturally separated** **[FACT]**: the base ASR models do **not**
  emit timestamps. Alignment is a *second model*, `Qwen3-ForcedAligner-0.6B`, which
  **shares the audio tower and LM backbone but replaces the LM head with a classification
  head predicting time bins at `<timestamp>` token positions**. It consumes speech plus a
  transcript with `[time]` slots and predicts discrete timestamp indices —
  a **slot-filling, non-autoregressive** formulation covering **11 languages** **[FACT]**.
- **Tokenizer** **[INFERENCE]**: the Qwen text tokenizer family.
- **Streaming** **[FACT]**: no native streaming identified.
- **Multilingual strategy** **[CLAIM]**: one model covering 52 languages and dialects.

## 3. Languages

**[CLAIM — publisher]** 52 languages and dialects: ≈30 languages plus 22 Chinese dialects.
**Hindi is claimed in scope.** Arabic coverage is **not confirmed** at this gate
**[FACT — that it is unconfirmed]**. Timestamp support is narrower than transcription
support: **11 languages only** **[FACT]** — which languages, and whether Hindi is among
them, is an open question.

**[INFERENCE]** The 22-of-52 Chinese-dialect composition indicates where this lineage's
training emphasis lies; it says nothing about Hindi quality, which is unmeasured.

## 4. Licensing (Gate 1, verified 2026-08-05)

`apache-2.0` on the `Qwen3-ASR-1.7B` card; not gated; no `trust_remote_code` indicated; no
separate LICENSE file referenced **[FACT]**. The absence of a LICENSE file is itself the
finding: sibling **Qwen text** repositories *do* ship custom LICENSE files **[FACT]**, so
this verdict binds to the ASR artifacts alone.

## 5. Runtime and deployment profile

- **vLLM** **[FACT — technical report]**: both ASR sizes support vLLM inference in **offline
  batch and online asynchronous** modes. The ForcedAligner supports **offline batch in
  PyTorch only** — it has no vLLM path.
- **Reference configuration** **[FACT]**: reported experiments use vLLM v0.14.0, CUDA Graph
  enabled, **bfloat16** — i.e. the published operating point is explicitly GPU.
- **Transformers path** **[FACT]**: the `-hf` variant exists specifically for Transformers
  compatibility.
- **Remote code** **[FACT]**: none indicated.
- **Quantization / ONNX / CTranslate2** **[INFERENCE — open question]**: no first-party
  artifacts identified. CTranslate2 support is not expected for an audio-LLM **[INFERENCE]**.
- **CPU friendliness** **[INFERENCE]**: 0.6B is the smallest audio-LLM in this universe and
  therefore the most CPU-plausible of them — but "plausible" is not "measured", and every
  published operating point is GPU/bfloat16.
- **Cold start / batching / memory** **[INFERENCE]**: unmeasured; 0.6B implies a materially
  smaller artifact than the 2–3B entrants.
- **Two-model timestamp deployment** **[INFERENCE]**: obtaining timestamps means loading and
  serving **two models**. Under our ModelManager's slot design that is two artifacts and two
  warm-ups, not a configuration flag — a real operational consideration.

## 6. Quality evidence

**None from IntelliAI.** External figures are out of scope at this gate.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** The 0.6B size is the single most interesting
unknown in this dossier set for CPU-first economics, precisely because it is the only
audio-LLM small enough to make the question non-rhetorical.

## 8. Fine-tuning ecosystem

- **[CLAIM]** The Qwen family has the most mature open fine-tuning toolchain of any
  lineage here — LLaMA-Factory, Unsloth, ms-swift all target Qwen models, with LoRA and
  QLoRA support standard.
- **[INFERENCE]** Whether that text-model tooling transfers cleanly to the *speech*
  variants is unverified and should not be assumed; audio towers frequently require
  bespoke handling.
- **[INFERENCE]** Adapter expertise developed here would transfer across other Qwen-based
  capabilities — the reuse argument that also drives the concentration risk in §12.

## 9. Training support

**[CLAIM]** A technical report is published (arXiv:2601.21337). Training data and full
recipes are not verified as released **[FACT — unverified]**.

## 10. Ecosystem and research maturity

- **Publication** **[FACT]**: a formal technical report exists — better research hygiene
  than most 2026 entrants in this set.
- **Maintenance cadence** **[CLAIM]**: among the highest-cadence open-weight publishers.
- **Documentation** **[FACT]**: cards plus report plus an inference toolkit.
- **Adoption** **[CLAIM]**: high download volume reported in the 2026-07-31 sweep.
- **vLLM upstream integration** **[FACT]**: `qwen3_asr_forced_aligner` appears in vLLM's
  own model-executor API documentation — third-party ecosystem uptake, not just
  self-published support.

## 11. Known strengths

Apache-2.0 with no gate and no remote code; the smallest audio-LLM sizes available;
first-party vLLM support with upstream integration; a published technical report; the
strongest fine-tuning toolchain of any lineage here; Hindi claimed in scope.

## 12. Known weaknesses

**[FACT]** Timestamps require a second model, and only for 11 languages.
**[FACT]** No streaming. **[FACT]** Arabic coverage unconfirmed.
**[INFERENCE]** Chinese-dialect-weighted training emphasis. **[INFERENCE]** Every
published operating point is GPU/bfloat16.

## 13. Integration risks

- **[INFERENCE]** **Two-artifact timestamp architecture** conflicts with the simple
  one-slot-one-artifact assumption in our ModelManager; supporting it is a design change,
  not a config change.
- **[FACT]** **Concentration risk**: Qwen already backs the primary or backup for several
  planned capabilities. FOUNDATION_MODELS §14 requires a warm non-Qwen alternative
  wherever Qwen is primary — adopting here would tighten an already-noted dependency.
- **[FACT]** Named watch triggers apply: a Qwen release under a non-Apache licence
  (precedent exists), and geopolitical/export-control action on Chinese open weights.
- **[INFERENCE]** No CPU-quantized serving path exists today.

## 14. Open questions carried to Gate 3

CPU feasibility at 0.6B · Arabic coverage · which 11 languages the aligner covers and
whether Hindi is among them · timestamp quality · quantization viability · whether Qwen
text fine-tuning tooling actually transfers to the speech variants · hallucination
behaviour of an LLM decoder on silence.

## 15. Strategic value to IntelliAI

- **Designated backup lineage** for transcription — the pre-positioned successor if the
  incumbent starts losing our evaluations.
- **Hindi improvement candidate** (claimed coverage, unmeasured).
- **GPU-tier candidate**, and simultaneously the **most CPU-plausible audio-LLM** — the
  cleanest single test of whether the 2026 architecture class can meet our economics.
- **Serving-stack reuse**: shares infrastructure with other Qwen capabilities we may run.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-QWEN3ASR:** *Qwen3-ASR-0.6B is small enough to be CPU-servable within our current
> serving class, but its timestamp story — a second model covering only 11 languages —
> will prove the binding constraint for our API's `verbose_json` contract, not its
> transcription capability.*

Falsifiable on both halves: 0.6B may still miss CPU targets, and the aligner may cover our
languages adequately.
