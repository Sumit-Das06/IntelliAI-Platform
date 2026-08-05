# Cohere Transcribe 03-2026 (general) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `apache-2.0`. ⚠ Gated (contact-sharing; `/raw/` returned HTTP 401) and requires `trust_remote_code=True`. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

`CohereLabs/cohere-transcribe-03-2026` — the general multilingual member of Cohere's
open-weight ASR line, released March 2026 **[FACT]**. Arabic sibling documented separately.

## 2. Architecture

- **Design** **[FACT]**: dedicated audio-in / text-out **Conformer encoder + lightweight
  Transformer decoder**, **trained from scratch for transcription** — explicitly not an
  LLM with a speech adapter.
- **Size** **[FACT]**: 2B parameters.
- **Decoder** **[FACT — from the ONNX export]**: **8 Transformer layers, dimension 1024**,
  with **KV cache** for token generation. The **encoder pre-computes K/V projections for
  all 8 decoder layers**, matching the **Whisper-style encoder-decoder ONNX pattern**.
- **[INFERENCE]** That last detail is the most operationally significant fact in this
  dossier: the model's export topology is structurally the same shape our existing
  CPU-serving experience is built around, even though the specific engine differs.
- **Timestamps** **[INFERENCE — open question]**: not documented in material reviewed.
- **Tokenizer** **[INFERENCE — open question]**: unverified; a 14-language vocabulary
  spanning Latin, CJK, and Arabic scripts is a non-trivial design.
- **Streaming** **[FACT]**: not claimed.
- **Multilingual strategy** **[FACT]**: one model, 14 languages, trained from scratch.

## 3. Languages

**[FACT — card]** 14 languages: English, French, German, Italian, Spanish, Portuguese,
Greek, Dutch, Polish (European); Chinese (Mandarin), Japanese, Korean, Vietnamese (APAC);
**Arabic** (MENA).

**Hindi is absent** **[FACT]** — recorded as a commercial-scope fact at Gate 1, and it is
the decisive language finding for this candidate: it covers two of our three product
languages (English, Arabic) and cannot serve the third.

## 4. Licensing (Gate 1, verified 2026-08-05)

`apache-2.0` **[FACT]**. Gated — "You need to agree to share your contact information to
access this model" **[FACT]**; the `/raw/` frontmatter endpoint returned **HTTP 401**,
which was the first signal of the gate **[FACT]**. `trust_remote_code=True` required for
both Transformers and vLLM paths **[FACT]**. Contact: `labs@cohere.com` **[FACT]**.

## 5. Runtime and deployment profile

- **Serving stacks** **[FACT]**: Transformers and vLLM documented by the publisher.
- **ONNX** **[FACT]**: an **`onnx-community/cohere-transcribe-03-2026-ONNX`** export
  exists, plus independent community INT8 conversions and a CoreML/ONNX variant.
- **Quantization** **[FACT]**: ONNX Runtime **dynamic quantization** — INT8 weights stored
  as INT8, activations computed in FP32, **no calibration data required**; convolution and
  batch-norm layers in the audio front-end are protected from quantization to preserve
  accuracy. Encoder and decoder ship as separate INT8 graphs with external data files.
- **CPU-community uptake** **[FACT]**: an open **sherpa-onnx** integration request
  (issue #3442) and a request to add it as an engine type in a desktop STT app — i.e. the
  CPU-inference community is actively pulling this model toward CPU runtimes.
- **CTranslate2** **[INFERENCE]**: not supported; ONNX Runtime is the realistic CPU route.
- **Remote code** **[FACT]**: required for the first-party paths. **[INFERENCE]** The ONNX
  exports may sidestep this, since an exported graph carries no Python — worth verifying,
  as it would resolve both the remote-code and the CPU questions at once.
- **CPU friendliness** **[INFERENCE]**: of all 2B-class candidates here, this has the most
  concrete evidence of a CPU path — INT8 ONNX artifacts that already exist. Still
  unmeasured by us.
- **Cold start / memory / batching** **[INFERENCE]**: unmeasured; separate encoder/decoder
  graphs with external data files complicate artifact pinning relative to single-file
  checkpoints.

## 6. Quality evidence

**None from IntelliAI.** External figures excluded at this gate.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** A KV-cached 8-layer decoder of dimension 1024 is a
small decode workload; the encoder dominates. That is the same cost profile our Whisper
serving already exhibits.

## 8. Fine-tuning ecosystem

- **[INFERENCE — open question]** No first-party fine-tuning recipes, LoRA precedent, or
  PEFT integration identified. As with the Arabic sibling, a from-scratch bespoke
  architecture tends to attract less community tuning infrastructure than LLM-backboned
  models.
- **[INFERENCE]** Adapting it to a language outside its 14 — Hindi, most obviously — would
  be a research project with no established path, not a routine fine-tune.

## 9. Training support

**[FACT — unverified]** No released training pipeline identified. **[CLAIM]** Publisher
describes training from scratch on 14 enterprise-critical languages.

## 10. Ecosystem and research maturity

- **Maintenance cadence** **[FACT]**: March 2026 general model, July 2026 Arabic model —
  an active line.
- **Ecosystem** **[FACT]**: unusually strong third-party conversion activity for a
  five-month-old model — ONNX, INT8, CoreML variants and open runtime-integration requests.
- **Documentation** **[FACT]**: model card plus release blog.
- **Publication quality** **[INFERENCE]**: blog-level; no formal technical report verified.
- **Vendor posture** **[FACT]**: Cohere operates a competing commercial transcription API
  alongside these open weights — neutral for licensing, relevant when assessing how long
  weights stay open **[INFERENCE]**.

## 11. Known strengths

Permissive licence; classical encoder-decoder shape rather than an audio-LLM; **a real,
existing INT8 ONNX CPU path**; visible CPU-community adoption; covers English *and*
Arabic in one model; active release line; deliberately small at 2B for its class.

## 12. Known weaknesses

**[FACT]** No Hindi — cannot serve a first-class product language. **[FACT]** Gated.
**[FACT]** Remote code on first-party paths. **[FACT]** No streaming. **[INFERENCE]** No
fine-tuning ecosystem. **[INFERENCE]** Timestamps undocumented. **[INFERENCE]** Multi-file
ONNX graphs with external data complicate our checksum-pinning model.

## 13. Integration risks

- **[FACT]** Gated fetch versus unauthenticated pinned-URL ArtifactStore.
- **[INFERENCE]** Remote code in-process on first-party paths; possibly avoidable via ONNX.
- **[INFERENCE]** Artifact pinning becomes more complex: separate encoder/decoder graphs
  plus external data files means several hashes per artifact version, where our
  ArtifactStore currently pins a small file set per artifact.
- **[INFERENCE]** Third-party ONNX conversions are **not** the publisher's artifacts — if
  we adopted one, we would inherit a conversion we did not perform and whose provenance is
  a separate licence question.

## 14. Open questions carried to Gate 3

Whether the ONNX path avoids `trust_remote_code` entirely · CPU feasibility at INT8 ·
timestamp support · tokenizer behaviour across 14 languages and three script families ·
Arabic quality relative to the Arabic-specialised sibling (a *within-lineage* question,
not a cross-candidate comparison) · whether first-party ONNX artifacts will be published.

## 15. Strategic value to IntelliAI

- **English candidate** (priority #1) and **Arabic candidate** (priority #3) in a single
  model — the only registered lineage covering two of our three product languages.
- **CPU-first candidate** — the strongest existing evidence of a quantized CPU route among
  the 2026-generation entrants.
- **[INFERENCE]** Strategically it poses a shape question: one model covering EN+AR but
  never HI implies a two-engine deployment, which is a different topology from either
  "one multilingual engine" or "three specialists".

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-COHERE-GEN:** *The INT8 ONNX export will run within our CPU serving class without
> requiring remote code, making this the first 2026-generation candidate that fits our
> existing architecture unchanged — but its lack of Hindi will force a two-engine topology
> regardless of how well it performs.*

Falsifiable: the ONNX path may still exceed CPU budgets or still require Python-side
preprocessing.
