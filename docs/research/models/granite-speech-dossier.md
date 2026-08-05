# Granite Speech (IBM) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `apache-2.0` verified at source; not gated; **no remote code**. The only 2026-generation entrant carrying none of the three recurring commercial risks. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement,
> unverified by us · **[INFERENCE]** reasoning, not evidence.
> No scoring, ranking, comparison, or adoption recommendation appears here.

## 1. Identity

IBM Granite Speech — the speech member of IBM's Granite open-model family. Current
generation: **`granite-speech-4.1-2b`**, with a **non-autoregressive sibling
`granite-speech-4.1-2b-nar`** and an earlier `granite-4.0-1b-speech` **[FACT — all three
repositories exist under `ibm-granite`]**.

## 2. Architecture

A three-stage speech-adapter design bolted onto a text LLM — documented unusually
precisely on the model card **[FACT]**:

- **Encoder** **[FACT]**: 16 conformer blocks with **dual-head CTC**.
- **Projector** **[FACT]**: a 2-layer *window query transformer* (q-former) operating over
  blocks of 15 acoustic embeddings of dimension 1024, using 3 trainable queries per block
  per layer, downsampling ×5.
- **Backbone** **[FACT]**: Granite 4.0 1B LLM, 128k context.
- **Temporal rate** **[FACT]**: total downsampling ×10 (×2 encoder, ×5 projector) → a
  **10 Hz** acoustic-embedding rate into the LLM.
- **Decoding** **[FACT]**: autoregressive (LLM decode). The **NAR variant** replaces this
  with non-autoregressive editing for faster inference **[CLAIM — publisher framing]**.
- **Tokenizer** **[INFERENCE]**: the Granite LLM's text tokenizer; audio enters as
  projected embeddings, not discrete audio tokens.
- **Timestamps** **[INFERENCE — open question]**: not documented on the card. The dual-head
  CTC branch is architecturally capable of alignment, but whether timestamps are exposed as
  model output is unverified. Carried to §14.
- **Streaming** **[FACT]**: not claimed. Treat as absent.
- **Multilingual strategy** **[INFERENCE]**: one model, six languages, no per-language
  heads described.

## 3. Languages

**[FACT — model card]** English, French, German, Spanish, Portuguese, Japanese.

**No Hindi. No Arabic.** This lineage cannot serve two of IntelliAI's three product
languages **[FACT]**. Any role it played would be as a per-language (English) engine
behind the public model — a shape the architecture already permits.

## 4. Licensing (Gate 1, verified 2026-08-05)

`apache-2.0`, linking to the canonical Apache text **[FACT]**. Not gated **[FACT]**.
Usage examples use standard `AutoProcessor` / `AutoModelForSpeechSeq2Seq` with **no
`trust_remote_code`** **[FACT]**. No formal AUP; IBM's guidance is advisory only
("IBM recommends using this model for automatic speech recognition and translation tasks")
**[FACT]**. IBM publishes provenance and indemnification positions for Granite models
generally **[CLAIM]** — unusual among open weights and relevant to a commercial platform.

## 5. Runtime and deployment profile

- **Serving stack** **[FACT]**: native HuggingFace Transformers support — the model has an
  official `granite_speech` entry in the Transformers model documentation. This is the
  lowest-friction integration path of any new entrant here.
- **Required dependency** **[FACT]**: **PEFT must be installed** — the LoRA is part of the
  inference path, not an optional add-on (see §8).
- **Remote code** **[FACT]**: none.
- **Quantization / ONNX / CTranslate2** **[INFERENCE — open question]**: no first-party
  quantized or ONNX artifacts identified. CTranslate2 support is **not** expected — that
  engine targets specific architectures and an LLM-coupled q-former design is not among
  them **[INFERENCE]**.
- **vLLM** **[CLAIM]**: plausible given the Granite LLM backbone; unverified for the speech
  variant.
- **CPU friendliness** **[INFERENCE — the key open question]**: 2B parameters with a
  128k-context LLM backbone. Our incumbent is 244M at ~800 MiB. Nothing here is measured,
  and the LLM component implies memory overheads our current serving class does not carry.
- **GPU expectations** **[INFERENCE]**: comfortable on GPU; CPU viability unproven.
- **Batching** **[CLAIM]**: standard Transformers batching applies.
- **Cold start** **[INFERENCE]**: a 2B-parameter download is roughly 4–8× our current
  artifact size, implying materially longer first-boot; unmeasured.

## 6. Quality evidence

**None from IntelliAI.** External leaderboard positions exist but are explicitly excluded
from this gate. No claim of relative quality is made in this document.

## 7. Latency and memory expectations

Unmeasured **[FACT — that it is unmeasured]**. **[INFERENCE]** The NAR variant exists
specifically because autoregressive LLM decoding is slow, which is itself evidence that
the standard variant's latency profile is a real consideration rather than a hypothetical.

## 8. Fine-tuning ecosystem

The most architecturally interesting property of this lineage **[FACT]**:

- **LoRA is intrinsic, not added.** The model contains a **modality-specific LoRA that is
  enabled when audio features are present and disabled otherwise** — so the same weights
  serve as a text LLM and a speech model depending on input.
- **[FACT]** The projector and the LLM LoRA adapters were *trained jointly* on the training
  corpora; in the NAR variant, LoRA is applied at **rank 128 to both attention and MLP
  layers**.
- **[FACT]** PEFT compatibility is not merely supported — it is required for correct
  inference.
- **[INFERENCE]** A lineage whose production inference path is already a LoRA is, on its
  face, a natural target for *further* adapters: the tooling, the merge semantics, and the
  serving path for adapters all already exist. This is a structural observation about
  fine-tuning readiness, not a claim that tuning it would succeed.

## 9. Training support

**[FACT]** Training data sources are described on the card and a public
`ibm-granite/granite-speech-models` repository exists. **[INFERENCE]** Continued
pretraining of the LLM backbone is conceivable via the Granite text lineage, but no
speech-specific pretraining recipe was verified.

## 10. Ecosystem and research maturity

- **Maintenance** **[FACT]**: a versioned release train (4.0 → 4.1) plus a NAR variant
  shipped in the same generation — evidence of an active programme, not a one-off drop.
- **Documentation** **[FACT]**: among the best in this universe. The card documents
  q-former block sizes, query counts, downsampling factors, and LoRA ranks — a level of
  architectural disclosure most publishers omit.
- **Ecosystem** **[FACT]**: official Transformers integration; IBM enterprise support
  channel.
- **Publication quality** **[CLAIM]**: IBM publishes Granite technical reporting; not
  independently assessed here.
- **Community adoption** **[INFERENCE]**: smaller community than Whisper's, weighted toward
  enterprise rather than hobbyist users.

## 11. Known strengths

Cleanest commercial posture in the new-entrant set (permissive, ungated, no remote code);
exceptional architectural documentation; native Transformers path; LoRA-native design;
enterprise provenance/indemnification practices; an actively versioned release train.

## 12. Known weaknesses

**[FACT]** No Hindi, no Arabic — cannot satisfy two-thirds of the language policy.
**[FACT]** No streaming claim. **[INFERENCE]** LLM-coupled memory profile far above our
incumbent's. **[INFERENCE]** No quantization/ONNX path identified, so CPU deployment would
start from scratch. **[INFERENCE — open question]** Timestamp exposure undocumented.

## 13. Integration risks

- **[INFERENCE]** **PEFT in the inference path** is a new runtime dependency class for us;
  our engine isolation discipline would need to accommodate it.
- **[INFERENCE]** **No CTranslate2 path** means abandoning the quantized-CPU serving stack
  we have production experience with, for this engine.
- **[INFERENCE]** A 2B artifact changes ArtifactStore download, cold-start, and memory
  planning assumptions measured in M2.
- **[FACT]** Adopting it for English would necessarily mean a multi-engine deployment,
  since Hindi and Arabic would need other engines.

## 14. Open questions carried to Gate 3

CPU feasibility at 2B with an LLM backbone · timestamp availability and quality ·
quantization and ONNX viability · NAR-vs-autoregressive operational difference ·
whether PEFT-in-inference is compatible with our runtime isolation rules.

## 15. Strategic value to IntelliAI

- **English replacement candidate** — research priority #1, with the cleanest commercial
  posture of any new entrant.
- **Training-program candidate** — its LoRA-native architecture makes it a natural study
  subject for §15, independent of whether it is ever served.
- **Reference point** for what a 2B LLM-coupled model actually costs relative to a 244M
  encoder-decoder — a number our roadmap needs regardless of this model's fate.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-GRANITE:** *Granite Speech 4.1 2B will not meet our CPU serving-class latency and
> memory constraints without a quantization path that does not currently exist — meaning
> its viability for IntelliAI is decided by deployment engineering rather than by
> transcription quality.*

Falsifiable: it may prove CPU-affordable at int8, or a first-party quantized artifact may
appear. Either outcome resolves the question cheaply.
