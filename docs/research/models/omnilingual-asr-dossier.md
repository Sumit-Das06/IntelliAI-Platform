# Omnilingual ASR (Meta) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `apache-2.0` verified in the raw YAML frontmatter of `facebook/omniASR-LLM-300M`; no `extra_gated` fields. Discharges the Gate 0 flag that Meta's claim could not be inherited from a sibling. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

Meta's Omnilingual ASR — a **suite**, not a single model, published as `facebook/omniASR-*`
on HuggingFace with code at `github.com/facebookresearch/omnilingual-asr` **[FACT]**.
Paper: arXiv:2511.09690 **[FACT]**.

## 2. Architecture

**[CLAIM — paper/publisher]** Three model families sharing **one wav2vec 2.0 speech encoder
backbone**, at **300M, 1B, 3B, and 7B**:

1. **SSL encoders** — trained with the standard wav2vec 2.0 contrastive objective; after
   training the quantizer is discarded and the encoder serves as a representation backbone.
2. **CTC models** (`omniASR-CTC-*`) — a **simple linear layer** on top of the encoder,
   trained end-to-end with **character-level CTC loss**.
3. **LLM ASR models** (`omniASR-LLM-*`) — the encoder paired with a Transformer decoder
   using **Llama-like attention**.

Plus a **zero-shot variant** (`omniASR_LLM_7B_ZS`) trained to accept **in-context
audio/transcription pairs**, performing inference on unseen languages via in-context
learning **[CLAIM]**.

- **[INFERENCE]** The CTC-vs-LLM split is the strategically important structure here. The
  **CTC 300M** variant is a *fundamentally different deployment proposition* from
  everything else in this dossier set: a linear head over an encoder, no autoregressive
  decode, no LLM. That is the cheapest decode shape available anywhere in this universe.
- **Decoding** **[FACT]**: CTC (non-autoregressive) or LLM (autoregressive), depending on
  family.
- **Timestamps** **[INFERENCE]**: CTC is frame-synchronous so alignment is intrinsic;
  exposure through the interface is unverified **[open question]**.
- **Tokenizer** **[FACT]**: the CTC models operate at **character level** — notable for
  scripts like Devanagari and Arabic, where character-level output sidesteps subword
  vocabulary coverage problems but may interact awkwardly with our normalisation
  **[INFERENCE]**.
- **Streaming** **[INFERENCE]**: not claimed; wav2vec2 encoders are not inherently
  streaming as deployed here.
- **Multilingual strategy** **[CLAIM]**: one backbone, 1,600+ languages, with **CER below
  10% on 78% of them**.

## 3. Languages

**[CLAIM]** 1,600+ languages — by an order of magnitude the widest coverage in this
universe. Includes long-tail Indic languages no competitor covers, and plausibly Arabic
varieties **[INFERENCE]**.

**[INFERENCE — important]** The coverage claim is stated at the *language-count* level
with an aggregate CER threshold. That says nothing about per-language quality for the
three languages we actually sell. Our §7 per-language evidence bar exists precisely to
prevent a 1,600-language headline from being read as EN/HI/AR capability.

**[FACT]** English competitiveness is reportedly not the design goal.

## 4. Licensing (Gate 1, verified 2026-08-05)

`license: apache-2.0` read directly in the raw YAML frontmatter **[FACT]**. No
`extra_gated` fields **[FACT]**. The associated **Omnilingual ASR Corpus** dataset is a
separate asset reported as **CC-BY-4.0** **[CLAIM]** — relevant to dataset research (§12),
not to serving these weights.

**[FACT]** This verification mattered: the same organisation's SeamlessM4T v2 is
CC-BY-NC-4.0 and was rejected at Gate 0 the same day.

## 5. Runtime and deployment profile

- **Required stack** **[FACT]**: **PyTorch and `fairseq2`**. This is the defining
  operational fact of the lineage.
- **[INFERENCE]** `fairseq2` is a research framework, not a production serving stack. It
  is not `transformers`, not NeMo, and not ONNX-native. Every other PASS candidate can be
  loaded through a mainstream inference path; this one requires importing a research
  dependency into our runtime — precisely the kind of dependency our engine-isolation
  discipline scrutinises.
- **ONNX / CTranslate2 / vLLM** **[INFERENCE — none identified]**.
- **Quantization** **[INFERENCE — open question]**: no first-party quantized artifacts
  identified.
- **Remote code** **[FACT]**: not indicated on the card; the `fairseq2` dependency is a
  heavier equivalent concern.
- **CPU friendliness** **[INFERENCE]**: the **CTC 300M** variant is the smallest
  non-autoregressive candidate in the entire PASS set and is, on architecture alone, the
  most CPU-plausible thing here. Whether `fairseq2` serves it acceptably on CPU is
  unverified and is the crux.
- **GPU expectations** **[INFERENCE]**: 7B variants are clearly GPU; 300M CTC need not be.
- **Cold start / memory / batching** **[INFERENCE]**: unmeasured across all sizes.

## 6. Quality evidence

**None from IntelliAI.** External CER figures are aggregate across 1,600+ languages and
are excluded from this gate regardless.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** CTC 300M would be expected to have the lowest decode
cost of any candidate — a single linear projection per frame, no autoregression — while the
7B LLM variants would be the most expensive. The suite therefore spans nearly the entire
cost range of this research universe by itself.

## 8. Fine-tuning ecosystem

- **[INFERENCE]** Fine-tuning means working in `fairseq2`, which has a far smaller
  community than HuggingFace or NeMo. No LoRA/PEFT precedent identified.
- **[CLAIM]** The SSL encoder is explicitly published as a representation backbone,
  implying it is *intended* to be built upon — encoder + custom head is the designed
  extension path.
- **[INFERENCE]** For a company intending to own models, "here is a pretrained
  multilingual speech encoder you may build heads on" is a genuinely different and
  potentially more valuable offer than a finished ASR model. That is a §15 observation, not
  an adoption argument.

## 9. Training support

**[FACT]** SSL encoders are released separately from the ASR models — i.e. the *backbone*
is available for continued pretraining or new-head training. **[CLAIM]** A large
open corpus accompanies the release. **[INFERENCE]** This is the most complete
"train your own" package in the PASS set: encoder + corpus + published recipes.

## 10. Ecosystem and research maturity

- **Publication** **[FACT]**: full paper (arXiv:2511.09690) plus documentation site.
- **Maintenance** **[INFERENCE]**: active as research; Meta's long-term product commitment
  to any single checkpoint is historically uncertain.
- **Documentation** **[FACT]**: a dedicated documentation site plus repository inference
  README — better than most research releases.
- **Ecosystem** **[INFERENCE]**: constrained by `fairseq2` adoption, which is narrow.
- **Adoption** **[CLAIM]**: significant research attention; production adoption unclear.

## 11. Known strengths

Apache-2.0 verified; unmatched language breadth; a **released SSL backbone** suitable for
building on; **character-level CTC** variants at small sizes; an accompanying open corpus;
zero-shot in-context adaptation to unseen languages; genuine research-grade publication.

## 12. Known weaknesses

**[FACT]** `fairseq2` dependency — the heaviest integration friction in the PASS set.
**[FACT]** English competitiveness not a design goal. **[INFERENCE]** No mainstream
serving path, no ONNX, no quantized artifacts. **[INFERENCE]** Aggregate quality claims
say nothing about our three languages. **[INFERENCE]** Meta's checkpoint-continuity record
is uneven.

## 13. Integration risks

- **[INFERENCE]** **`fairseq2` inside our runtime** is the dominant risk. Our engines
  package is the only place foundation-model imports are permitted, and a research
  framework with its own build requirements is a materially larger surface than a
  `transformers` import.
- **[INFERENCE]** Character-level output may require changes to our evaluation
  normalisation before its errors are interpretable.
- **[INFERENCE]** Suite-not-model means adoption requires choosing a variant *and*
  verifying that variant's licence independently.

## 14. Open questions carried to Gate 3

Can `fairseq2` be isolated inside our engine boundary · CPU feasibility of CTC 300M ·
per-language quality for EN/HI/AR specifically · Arabic dialect coverage · timestamp
exposure from CTC · whether character-level output is compatible with our normalisation ·
licence and terms of the accompanying corpus (§12 thread).

## 15. Strategic value to IntelliAI

- **Arabic opportunity** — plausible dialect coverage in a permissive licence, though
  entirely unverified for Arabic specifically.
- **Hindi and long-tail Indic** — the widest claimed Indic coverage available.
- **CPU-first candidate** — the CTC 300M variant, on architecture alone.
- **Training-program candidate — the strongest in the PASS set.** A released SSL encoder
  plus an open corpus is the closest thing available to a foundation we could build an
  IntelliAI-native model on, which is a §15/§12 asset rather than a serving decision.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-OMNILINGUAL:** *The CTC 300M variant will be the cheapest candidate to run on CPU of
> anything in this research universe, but the `fairseq2` dependency — not the model's
> quality or size — will be what prevents it from fitting inside our engine boundary.*

Falsifiable: `fairseq2` may isolate acceptably, or the CTC variant may underperform its
architectural promise on CPU.
