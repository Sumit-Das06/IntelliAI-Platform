# Cohere Transcribe Arabic — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `apache-2.0`, card states verbatim "This model is governed by an Apache 2.0 license". ⚠ Gated (contact-sharing) and requires `--trust-remote-code`. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

`CohereLabs/cohere-transcribe-arabic-07-2026` — the Arabic-specialised member of Cohere's
open-weight ASR line, released **2026-07-07** **[FACT]**. Sibling: the general
`cohere-transcribe-03-2026` (separate dossier, separate verdict).

**This is the only registered candidate purpose-built for Arabic** — the language slot
that had no candidate at all before this intake **[FACT]**.

## 2. Architecture

- **Design** **[FACT — card]**: encoder-decoder, **not** an audio-LLM. A large
  **FastConformer/Conformer acoustic encoder** paired with a **lightweight autoregressive
  Transformer decoder**.
- **Size** **[FACT]**: 2B parameters.
- **Trained from scratch for transcription** **[CLAIM]** — i.e. not a speech adapter bolted
  onto a general-purpose LLM. **[INFERENCE]** This matters for robustness: a decoder that
  was never a general language model has less capacity to "converse" or hallucinate
  free-form text than an audio-LLM decoder, though it is not immune.
- **Decoder detail (from the sibling's ONNX export)** **[CLAIM]**: 8 Transformer layers,
  dimension 1024, with KV cache; the encoder pre-computes K/V projections for all decoder
  layers — **the same encoder-decoder ONNX pattern used for Whisper**. **[INFERENCE]** If
  the Arabic model shares this topology, the export path that already works for the sibling
  should apply, but that is an inference, not a verified fact for this artifact.
- **Timestamps** **[INFERENCE — open question]**: not documented on the card.
- **Tokenizer** **[INFERENCE — open question]**: unverified. Arabic tokenization is
  non-trivial (diacritics, clitics, orthographic variation), so this is a real question
  rather than a formality.
- **Streaming** **[FACT]**: not claimed. Treat as absent.
- **Multilingual strategy** **[FACT]**: deliberately *narrow* — Arabic, Arabic dialects,
  English, and Arabic-English code-switching. A specialist, by design.

## 3. Languages

**[FACT — card]** Arabic, Arabic dialects, English, Arabic-English code-switched speech.

**[CLAIM — publisher]** Training data was deliberately resampled across dialect groups, and
code-switching was an explicit design target reflecting how Arabic professionals actually
speak in business settings.

**[INFERENCE]** These two properties — dialect coverage and code-switching — are precisely
the hard parts of Arabic ASR, and they map directly onto our language policy's requirement
that code-mixed speech be a first-class corpus category. Whether the model delivers on
them is entirely unmeasured by us.

## 4. Licensing (Gate 1, verified 2026-08-05)

`apache-2.0`, with the card stating explicitly "This model is governed by an Apache 2.0
license" **[FACT]**. The surrounding Terms-of-Use paragraph uses research-flavoured
language; it does **not** narrow the grant — stated intent does not restrict a granted
licence **[FACT — reasoning recorded at Gate 1]**.

⚠ **Gated** — "You need to agree to share your contact information to access this model"
**[FACT]**. ⚠ **Remote code required** — `vllm serve ... --trust-remote-code` **[FACT]**.

## 5. Runtime and deployment profile

- **Serving stack** **[FACT]**: vLLM path documented on the card; Transformers path
  documented for the sibling.
- **Remote code** **[FACT]**: required. The code ships inside the Apache-2.0 repository, so
  it is licensed; the residual concern is security review of vendor code executing in our
  runtime process **[INFERENCE]**.
- **ONNX / quantization** **[CLAIM — for the sibling, not verified for this artifact]**:
  the general model has an **INT8 ONNX** export path (`onnx-community` plus community
  variants), using ONNX Runtime **dynamic quantization** — INT8 weights, FP32 activations,
  **no calibration data required** — with convolution and batch-norm layers in the audio
  front-end protected from quantization for accuracy. **[INFERENCE]** If the Arabic model
  shares the sibling's topology, the same export route is plausible; this is the single
  most valuable thing to verify about this lineage.
- **CTranslate2** **[INFERENCE]**: not supported; but the Whisper-style encoder-decoder
  ONNX pattern means ONNX Runtime is the realistic CPU route.
- **CPU friendliness** **[INFERENCE — open question]**: 2B is ~8× our incumbent's parameter
  count, but an INT8 ONNX encoder-decoder is a fundamentally more CPU-tractable shape than
  an audio-LLM. Unmeasured.
- **GPU expectations** **[INFERENCE]**: comfortable; not obviously mandatory.
- **Cold start / memory / batching** **[INFERENCE]**: unmeasured; a 2B artifact implies a
  materially longer first boot than our current ~483 MB download.

## 6. Quality evidence

**None from IntelliAI**, and — importantly — **no Arabic corpus, baseline, or benchmark
exists in our evaluation plane at all** **[FACT]**. This model cannot be measured by us
today for reasons that have nothing to do with the model.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** A lightweight 8-layer decoder over a large encoder
is a favourable shape for latency relative to LLM-backbone candidates, since decode cost
per token is low.

## 8. Fine-tuning ecosystem

- **[INFERENCE — open question]** No fine-tuning recipes, LoRA precedent, or PEFT
  compatibility identified for this lineage in this sweep. A bespoke encoder-decoder
  trained from scratch typically has *less* community tuning infrastructure than models
  built on popular LLM backbones.
- **[INFERENCE]** For a dialect-adaptation strategy — which is what Arabic would eventually
  demand — the absence of an established adapter path is a genuine strategic gap, not a
  minor one.

## 9. Training support

**[FACT — unverified]** No released training pipeline or data recipe identified. Continued
pretraining support unknown. **[CLAIM]** Cohere describes deliberate dialect resampling,
implying a curated corpus that is not public.

## 10. Ecosystem and research maturity

- **Maintenance cadence** **[FACT]**: general model March 2026, Arabic model July 2026 —
  a line under active development, not a one-off.
- **Documentation** **[FACT]**: model card with architecture, language scope, and usage;
  a release blog post exists.
- **Ecosystem** **[FACT]**: third-party ONNX and CoreML conversions of the sibling exist,
  and a **sherpa-onnx integration request** is open for the sibling — early evidence that
  the wider CPU-inference community is picking the line up.
- **Publication quality** **[INFERENCE]**: release-blog level; no formal technical report
  verified.
- **Adoption** **[INFERENCE]**: young — one month old at the time of this dossier.

## 11. Known strengths

The only purpose-built Arabic candidate we have; dialect and code-switching as explicit
design targets; permissive licence on a specialist model; classical encoder-decoder shape
with a plausible INT8 ONNX CPU route (via sibling evidence); active release line.

## 12. Known weaknesses

**[FACT]** Gated distribution. **[FACT]** Mandatory remote code. **[FACT]** No streaming.
**[FACT]** No Hindi. **[INFERENCE]** No fine-tuning ecosystem identified. **[INFERENCE]**
Timestamps and tokenizer both undocumented. **[FACT]** Single released version, one month
old, no track record.

## 13. Integration risks

- **[FACT]** Gated fetch conflicts with our unauthenticated pinned-URL ArtifactStore
  design.
- **[INFERENCE]** Remote code in our runtime process needs security review under the same
  discipline that produced the TTS licence firewall.
- **[INFERENCE]** Adopting it means a **multi-engine deployment by construction** — it
  cannot serve Hindi, so Arabic would be a dedicated engine behind the public model. Our
  architecture permits this; it has never been exercised.
- **[INFERENCE]** Evaluating it at all requires building Arabic evaluation infrastructure
  first — corpus, judge strategy, and metrics — which is a larger body of work than the
  model assessment itself.

## 14. Open questions carried to Gate 3

Does the Arabic model share the sibling's ONNX-exportable topology · CPU feasibility at
INT8 · timestamp support · tokenizer behaviour on Arabic orthography and diacritics ·
dialect robustness · code-switching behaviour · **how to judge Arabic at all** (our
round-trip methodology assumes a judge STT for the language) · fine-tuning path for
dialect adaptation.

## 15. Strategic value to IntelliAI

- **Arabic opportunity — the primary one.** Research priority #3 has had no candidate
  since Language Policy v1 was written; this is the first.
- **[INFERENCE]** Its arrival changes what blocks Arabic: the constraint is no longer "no
  model exists" but "no evaluation infrastructure exists". That is a *far more tractable*
  problem, and one entirely within our control.
- **Specialist-engine reference** — the concrete test of whether per-language engines
  behind one public model works in practice.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-COHERE-AR:** *An Arabic-specialised model will substantially outperform
> whisper-small on Arabic dialect and code-switched speech, but building the Arabic
> evaluation corpus and judge strategy will prove to be the larger and slower half of the
> work — and the round-trip methodology may not transfer to Arabic without modification.*

Falsifiable: the incumbent's Arabic may be adequate, and our existing methodology may
transfer cleanly. Both halves matter independently.
