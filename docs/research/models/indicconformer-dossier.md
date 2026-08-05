# IndicConformer (AI4Bharat) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `mit` verified at source; not gated. ⚠ `trust_remote_code=True` required (code served from the same MIT repository). |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

`ai4bharat/indic-conformer-600m-multilingual` — Conformer ASR purpose-built for Indian
languages by AI4Bharat, a research lab at IIT Madras **[FACT]**. Sibling lineages from the
same lab: IndicWhisper (**BLOCKED at Gate 1 — frozen**) and IndicWav2Vec.

## 2. Architecture

- **Design** **[FACT — card]**: **Multilingual Conformer-based hybrid CTC + RNN-T**. Two
  decoding heads over one encoder.
- **Size** **[FACT]**: 600M parameters.
- **Decoding** **[FACT]**: hybrid — CTC and RNN-T are both available. **[INFERENCE]** This
  is an operationally useful property: CTC decoding is fast and non-autoregressive, RNN-T
  is streaming-capable and typically more accurate. One artifact, two cost/quality
  operating points, selectable at inference.
- **Timestamps** **[INFERENCE]**: CTC and RNN-T are both frame-synchronous, so alignment is
  intrinsic to the decoding process rather than post-hoc. Whether timestamps are *exposed*
  through the model's interface is unverified **[open question]**.
- **Tokenizer** **[INFERENCE — open question]**: unverified. Critical for Devanagari:
  matra (combining-mark) handling determines whether errors like our recorded
  लगता → लकता case are representable at all. Our own `speech_normalize` already had to
  preserve Unicode category M for exactly this reason.
- **Streaming** **[INFERENCE]**: RNN-T is natively streamable in principle; no streaming
  path is documented on the card **[open question]**.
- **Multilingual strategy** **[FACT]**: one model spanning the scheduled Indian languages;
  no per-language checkpoints required for the multilingual variant.

## 3. Languages

**[CLAIM — publisher]** All 22 scheduled Indian languages, **Hindi included**.

**No English competitiveness claim. No Arabic.** **[FACT]** A specialist by construction —
it addresses exactly one of our three product languages, and does so deliberately.

## 4. Licensing (Gate 1, verified 2026-08-05)

`mit` on the model card **[FACT]**. Not gated **[FACT]**.
⚠ **`trust_remote_code=True` required** — the card's own example is
`AutoModel.from_pretrained("ai4bharat/indic-conformer-600m-multilingual",
trust_remote_code=True)` **[FACT]**. The remote code is served from the same MIT
repository, so the executing code is licensed **[FACT]**.
**[INFERENCE]** Training-data provenance for publicly funded Indic corpora remains a risk
note to examine — recorded, not a gate.

## 5. Runtime and deployment profile

- **Serving stack** **[FACT]**: **HuggingFace `transformers`**, not NeMo — notable, since
  Conformer/RNN-T models usually arrive NeMo-bound. Dependencies declared on the card:
  `transformers`, `torchaudio`, and pinned `onnxruntime==1.20.1`, `onnx==1.20.1`,
  `onnxruntime-gpu==1.20.1`.
- **ONNX** **[FACT — strongly implied]**: `onnx` and `onnxruntime` are **declared runtime
  dependencies with exact pins**, which indicates an ONNX execution path is part of the
  intended inference route rather than a community afterthought. **[INFERENCE]** This is
  the most CPU-relevant single fact about this candidate.
- **Pinned-version rigidity** **[FACT]**: exact `==` pins on three ONNX packages.
  **[INFERENCE]** This constrains our dependency resolution and could conflict with other
  packages in a shared runtime — a real integration consideration given our workspace
  layout.
- **Remote code** **[FACT]**: required.
- **CTranslate2** **[FACT — absent]**.
- **Quantization** **[INFERENCE — open question]**: ONNX Runtime quantization would be the
  natural route; no first-party quantized artifact identified.
- **CPU friendliness** **[INFERENCE]**: 600M, Conformer, ONNX-oriented — architecturally
  among the more CPU-plausible candidates, and the CTC head offers a cheaper decode mode.
  Unmeasured.
- **GPU expectations** **[INFERENCE]**: optional; `onnxruntime-gpu` is declared but a CPU
  path appears intended.
- **Cold start / memory / batching** **[INFERENCE]**: unmeasured; 600M implies a
  moderate artifact, larger than our current 244M but the same order.

## 6. Quality evidence

**None from IntelliAI.** **[FACT]** We also lack a Hindi corpus at the scale our own M2.5
condition C3 requires (≥100 cases) before any switching test — so this candidate cannot
currently be measured to our own standard, for reasons unrelated to the model.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** CTC decoding is non-autoregressive and would be
expected to have a materially different latency profile from RNN-T on the same weights —
making this one artifact that can occupy two points on the cost curve.

## 8. Fine-tuning ecosystem

- **[INFERENCE — open question]** No LoRA/PEFT precedent identified for this lineage.
  Conformer/RNN-T fine-tuning is conventionally full or partial fine-tuning rather than
  adapter-based.
- **[CLAIM]** AI4Bharat publishes training and evaluation code across its model suite.
- **[INFERENCE]** Because it uses `transformers` rather than NeMo, ordinary HuggingFace
  training loops may apply more directly than for NVIDIA's transducers — a genuine
  practical advantage, unverified.

## 9. Training support

**[CLAIM]** AI4Bharat publishes datasets, benchmarks, and training code across its Indic
programme. **[INFERENCE]** This lineage is therefore relevant to §12 (dataset research) as
much as to model adoption: the lab's *corpora* may be as strategically interesting to us as
its checkpoints, and they are a separate research thread with their own licence questions.

## 10. Ecosystem and research maturity

- **Publication** **[CLAIM]**: sustained Indic ASR publication record (Vistaar and related
  benchmarks).
- **Maintenance** **[INFERENCE]**: active lab, but funding-dependent continuity — a
  different institutional risk profile from a corporate publisher.
- **Documentation** **[FACT]**: model card with dependencies and usage; broader lab
  documentation exists.
- **Ecosystem** **[INFERENCE]**: smaller than Whisper's; operational knowledge would not
  transfer from our incumbent.
- **Adoption** **[CLAIM]**: the reference Indic ASR family in Indian NLP work.

## 11. Known strengths

MIT; Hindi plus 21 other Indian languages in one model; hybrid CTC+RNN-T giving two
decode modes; `transformers`-native rather than NeMo-bound; declared ONNX path; 600M is a
tractable size; a lab with genuine Indic depth and public datasets.

## 12. Known weaknesses

**[FACT]** No English claim, no Arabic. **[FACT]** Remote code required. **[FACT]** Rigid
exact-version ONNX pins. **[INFERENCE]** No adapter/LoRA precedent. **[INFERENCE]**
Timestamp exposure and tokenizer behaviour both unverified. **[INFERENCE]** Institutional
continuity risk relative to corporate publishers.

## 13. Integration risks

- **[FACT]** Exact `==` dependency pins may conflict inside our shared workspace — our M2
  experience showed workspace venvs mask per-package dependency problems that containers
  then expose.
- **[INFERENCE]** Remote code in-process requires the same security review discipline as
  other such candidates.
- **[INFERENCE]** Adopting it means a **dedicated Hindi engine** — a multi-engine topology
  our architecture permits but has never exercised.
- **[INFERENCE]** Devanagari tokenization must be verified against our evaluation
  normalisation, or measured errors may not mean what we think they mean.

## 14. Open questions carried to Gate 3

CPU feasibility at 600M in CTC vs RNN-T modes · timestamp exposure · Devanagari
tokenizer/matra handling · streaming capability of the RNN-T head · quantization ·
dependency-pin compatibility with our runtime · **whether we can build a Hindi corpus of
sufficient scale to measure it at all** (our own C3 gate).

## 15. Strategic value to IntelliAI

- **Hindi improvement candidate** — research priority #2, as the *dedicated-engine* arm of
  the three-way Hindi comparison (in-lineage fine-tune vs specialist vs multilingual
  generalist).
- **Evaluation baseline** — even if never served, measuring it tells us how much Hindi
  headroom exists above the incumbent, which is the evidence §9 needs to choose a rung.
- **CPU-first candidate** — 600M with a declared ONNX path and a cheap CTC decode mode.
- **Dataset-research lead** — the lab's public Indic corpora are a §12 thread in their own
  right.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-INDICCONFORMER:** *A dedicated Indic Conformer will reduce Hindi word error against
> whisper-small by a margin large enough to justify a second engine — but its Devanagari
> tokenization will differ from our evaluation normalisation in ways that make the raw
> WER comparison misleading until the corpus and normaliser are aligned.*

Falsifiable in both halves, and the second half is the more useful one: it tests our
measurement apparatus, not only the model.
