# Parakeet TDT (NVIDIA) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `CC-BY-4.0` verified verbatim; not gated; no remote code. ⚠ Attribution obligation vs engine-hiding API. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

`nvidia/parakeet-tdt-0.6b-v3` — the multilingual member of NVIDIA's efficient ASR line,
distributed through the NeMo ecosystem **[FACT]**. Predecessor `parakeet-tdt-0.6b-v2` is
English-centric **[FACT]**.

## 2. Architecture

- **Design** **[FACT]**: **FastConformer encoder** with **TDT (Token-and-Duration
  Transducer)** decoding — a transducer variant that predicts both tokens and their
  durations, allowing frames to be skipped rather than decoded one-per-frame.
- **Size** **[FACT]**: 600M parameters — small by 2026 standards and deliberately
  throughput-oriented.
- **Decoding** **[FACT]**: transducer (RNN-T family), **not** autoregressive LM decoding.
  **[INFERENCE]** This is the structural reason the lineage is fast and streaming-friendly:
  transducers emit monotonically with the audio and have no free-running text decoder.
- **Timestamps** **[FACT]**: the v2 card documents **accurate timestamp prediction**
  alongside punctuation and capitalisation — timestamps are **native model output**, not
  post-hoc alignment. **[INFERENCE]** That is a meaningful architectural difference from
  Whisper, where word timestamps require cross-attention post-processing.
- **Tokenizer** **[INFERENCE]**: SentencePiece-family subword vocabulary, standard for NeMo
  transducer models.
- **Streaming** **[FACT]**: the v3 card documents a **dedicated streaming inference script
  with configurable context windows and chunk sizes**. Transducers are natively streamable.
- **Multilingual strategy** **[FACT]**: one model with **automatic language identification**
  across 25 languages.

## 3. Languages

**[FACT — card]** 25 European languages: Bulgarian, Croatian, Czech, Danish, Dutch,
English, Estonian, Finnish, French, German, Greek, Hungarian, Italian, Latvian, Lithuanian,
Maltese, Polish, Portuguese, Romanian, Slovak, Slovenian, Spanish, Swedish, Russian,
Ukrainian.

**No Hindi. No Arabic.** **[FACT]** English-and-European only; two of our three product
languages are out of scope.

## 4. Licensing (Gate 1, verified 2026-08-05)

**CC-BY-4.0**, stated verbatim: "Use of this model is governed by the CC-BY-4.0 license"
**[FACT]**. Not gated; no remote code **[FACT]**.

⚠ **Attribution obligation** **[FACT]**: CC-BY requires appropriate credit. Our public API
deliberately does not disclose engines, so this is a product-design question — satisfiable
via a third-party notices page **[INFERENCE]**, but undecided.

⚠ **Per-version licence drift** **[FACT]**: the same organisation ships `Canary 1B` under
CC-BY-**NC** (rejected) and has moved some newer checkpoints to a custom NVIDIA licence.
Every version needs its own verdict.

## 5. Runtime and deployment profile

- **Native stack** **[FACT]**: NVIDIA NeMo. Loading and fine-tuning are NeMo-native.
- **Export** **[FACT]**: NeMo models can be exported to **ONNX or TorchScript** for
  deployment in optimised environments — **Riva** and **Triton Inference Server** are the
  documented targets.
- **TensorRT / Triton** **[FACT]**: first-class targets in NVIDIA's documented pipeline.
- **ONNX on CPU** **[CLAIM — third-party]**: ONNX conversion of Parakeet has been
  requested and discussed in the community; independent research reports an ONNX-Runtime
  streaming ASR system under 1 GB running faster than real-time on CPU with sub-second
  latency **[CLAIM — separate research, not this model]**. **[INFERENCE]** A CPU path is
  therefore plausible in principle but is not a first-party, supported artifact.
- **CTranslate2** **[FACT — absent]**: no CTranslate2 support identified. Our existing
  quantized-CPU serving stack does not apply.
- **Quantization** **[INFERENCE]**: available via ONNX Runtime tooling rather than
  first-party quantized checkpoints.
- **CPU friendliness** **[INFERENCE]**: 600M is a favourable size and the transducer shape
  is CPU-tractable, but every published performance operating point is GPU (A100-class).
- **GPU expectations** **[FACT]**: the documented throughput story assumes GPU; up to ~24
  minutes of audio in a single pass on an 80 GB A100 **[CLAIM]**.
- **Batching** **[CLAIM]**: supported through NeMo/Riva serving.
- **Operational maturity** **[FACT]**: NVIDIA's serving path (Riva/Triton) is
  enterprise-grade — but it is an **entirely different operational world** from our current
  FastAPI + CTranslate2 runtime **[INFERENCE]**.

## 6. Quality evidence

**None from IntelliAI.** External leaderboard figures excluded at this gate.

## 7. Latency and memory expectations

Unmeasured by us **[FACT]**. **[INFERENCE]** Among the strongest *architectural* cases for
low latency in this set — a 600M transducer with duration-based frame skipping — but the
absence of a first-party CPU artifact means our economics remain unknown.

## 8. Fine-tuning ecosystem

- **[FACT]** The model is explicitly published as usable "as a pre-trained checkpoint for
  inference **or for fine-tuning on another dataset**", with NeMo fine-tuning tutorials and
  active community discussion of data preparation for v3.
- **[CLAIM]** NVIDIA publishes domain-adaptation guidance for its speech ASR line
  (including cloud fine-tuning walkthroughs).
- **[INFERENCE]** Fine-tuning here means **adopting the NeMo training stack**. LoRA/PEFT
  are LLM-ecosystem conventions; transducer fine-tuning is conventionally full or partial
  fine-tuning within NeMo, not adapter-based. That is a different kind of investment from
  the Whisper/PEFT world our tooling currently assumes.
- **[INFERENCE]** Adding a language absent from the 25 (e.g. Hindi) would be a substantial
  training project, not an adapter.

## 9. Training support

**[FACT]** NeMo is a full training framework, not merely an inference runtime — recipes,
data preparation, and fine-tuning are all supported and documented. **[INFERENCE]** This
makes the lineage relevant to the training programme (§15) independently of serving.

## 10. Ecosystem and research maturity

- **Maintenance** **[FACT]**: active versioned line (v2 → v3) with ongoing community
  discussion.
- **Documentation** **[FACT]**: NeMo user guide, export documentation, model cards,
  fine-tuning discussions — thorough, if NVIDIA-centric.
- **Ecosystem** **[FACT]**: large, but concentrated in the NVIDIA/NeMo world.
- **Publication quality** **[CLAIM]**: FastConformer and TDT are published research.
- **Adoption** **[CLAIM]**: widely used where GPU serving is the norm.

## 11. Known strengths

Small (600M) with native streaming and **native timestamps**; transducer architecture with
duration-based frame skipping; commercially usable licence; NeMo is a complete training
stack; automatic language ID; documented ONNX/TorchScript export.

## 12. Known weaknesses

**[FACT]** No Hindi, no Arabic. **[FACT]** CC-BY attribution obligation. **[FACT]** No
CTranslate2 path. **[INFERENCE]** All published performance is GPU-referenced.
**[INFERENCE]** No first-party CPU or quantized artifact. **[FACT]** Organisational licence
drift requires per-version vigilance.

## 13. Integration risks

- **[INFERENCE]** **Stack divergence** is the dominant risk: NeMo/Riva/Triton is a
  different serving world from our runtime. Adopting it means either importing NeMo into
  our runtime or committing to an ONNX export path we would maintain ourselves.
- **[FACT]** Attribution must be reconciled with an engine-hiding public API before
  adoption — a product decision, not an engineering one.
- **[INFERENCE]** Language coverage guarantees a multi-engine topology for us.
- **[INFERENCE]** Third-party ONNX conversions carry their own provenance questions.

## 14. Open questions carried to Gate 3

CPU feasibility of an ONNX export at 600M · timestamp quality (native, so worth measuring
directly) · streaming quality and latency through our contract · quantization impact ·
whether NeMo can be isolated inside our engine boundary · how attribution is satisfied.

## 15. Strategic value to IntelliAI

- **English candidate** (priority #1) where **cost per hour**, not accuracy, is the lever.
- **Streaming research candidate** — a transducer is the classical answer to streaming ASR
  and the natural counterpoint to delayed-streams and causal-encoder designs.
- **Timestamp reference** — native timestamps are directly relevant to our `verbose_json`
  response format.
- **Training-program candidate** — NeMo is a full training stack we could eventually use.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-PARAKEET:** *An ONNX export of Parakeet TDT 0.6B will run within our CPU serving
> class and deliver native timestamps of higher quality than our current post-processed
> Whisper alignment — but the NeMo dependency, not the model, will be what determines
> whether it can live inside our engine boundary.*

Falsifiable: the export may not meet CPU targets, and NeMo may isolate cleanly.
