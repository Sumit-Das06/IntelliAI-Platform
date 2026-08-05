# Canary-Qwen 2.5B (NVIDIA) — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `CC-BY-4.0`; card states "ready for commercial use"; Deployment Geography Global; not gated; no remote code. ⚠ Attribution obligation. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

`nvidia/canary-qwen-2.5b` — a **Speech-Augmented Language Model (SALM)** pairing a
Canary-family speech encoder with a **Qwen LLM decoder** **[FACT]**.

**Not the rejected artifact.** `Canary 1B` is CC-BY-**NC** and permanently Rejected; this
is a separate artifact under CC-BY-4.0 **[FACT]**. The distinction was confirmed by direct
verification at Gate 1 and is the clearest evidence in our ledger for the
per-artifact-version law.

## 2. Architecture

- **Design** **[FACT]**: SALM — speech encoder → LLM decoder. Two operating modes are
  implied by the card's stated use case: transcription, **and transcript post-processing
  via prompting the underlying LLM**.
- **Size** **[FACT]**: 2.5B parameters.
- **Decoding** **[FACT]**: autoregressive LLM decode.
- **[INFERENCE]** The dual-mode design is architecturally distinctive: the same model can
  transcribe and then operate on its own transcript (summarise, punctuate, answer
  questions). For IntelliAI that is a *capability-boundary* question — our contract
  separates transcription from any downstream text capability, and a model that blurs
  them does not fit the contract without a deliberate decision.
- **Timestamps** **[INFERENCE — open question]**: not documented; LLM-decoder models
  generally do not emit alignment natively.
- **Tokenizer** **[INFERENCE]**: the Qwen text tokenizer.
- **Streaming** **[FACT]**: none identified. **[INFERENCE]** LLM-decoder architectures are
  not streaming-native.
- **Multilingual strategy** **[FACT]**: none — English only.

## 3. Languages

**[FACT]** English only. **No Hindi. No Arabic.** Two of three product languages
unaddressed; this could only ever be an English-tier engine.

## 4. Licensing (Gate 1, verified 2026-08-05)

**CC-BY-4.0** **[FACT]**. The card states the model **"is ready for commercial use"** and
lists **Deployment Geography: Global** **[FACT]** — an unusually explicit commercial
posture, and useful precedent for how NVIDIA signals intent. Not gated; NeMo-native loading
via `SALM.from_pretrained()` with no remote code **[FACT]**.

⚠ **Attribution obligation** under CC-BY **[FACT]**, same product question as Parakeet.
⚠ **Inherits a Qwen component** **[FACT]**, so Qwen concentration considerations partially
apply even though the publisher is NVIDIA **[INFERENCE]**.

## 5. Runtime and deployment profile

- **Native stack** **[FACT]**: NeMo (`SALM.from_pretrained()`).
- **Remote code** **[FACT]**: none.
- **ONNX / TorchScript** **[CLAIM]**: NeMo's general export path exists; whether a SALM
  exports cleanly is unverified **[INFERENCE — open question]**. An LLM-coupled model is
  materially harder to export than a transducer.
- **CTranslate2** **[FACT — absent]**.
- **Quantization** **[INFERENCE]**: no first-party quantized artifact identified.
- **CPU friendliness** **[INFERENCE]**: **the weakest of the PASS set**. 2.5B with an LLM
  decoder was assessed as GPU-bound in the 2026-07-31 sweep, and nothing found since
  contradicts that.
- **GPU expectations** **[INFERENCE]**: effectively required at practical latencies.
- **Batching** **[CLAIM]**: via NeMo/Triton serving.
- **Cold start / memory** **[INFERENCE]**: unmeasured; 2.5B implies the largest memory
  footprint among candidates other than Voxtral variants.

## 6. Quality evidence

**None from IntelliAI.** Its leaderboard history is explicitly out of scope at this gate.

## 7. Latency and memory expectations

Unmeasured **[FACT]**. **[INFERENCE]** LLM decode dominates cost; latency scales with
output length rather than input duration, which is a different cost model from both
Whisper (fixed window) and transducers (frame-synchronous).

## 8. Fine-tuning ecosystem

- **[INFERENCE]** Two ecosystems collide here: NeMo (for the speech encoder and SALM
  assembly) and the Qwen/PEFT world (for the LLM decoder). LoRA on the decoder is
  *architecturally* plausible; no first-party recipe was identified.
- **[CLAIM]** NVIDIA publishes domain-adaptation guidance for its speech ASR line
  generally.
- **[INFERENCE]** The absence of a documented adapter path for this specific SALM makes
  fine-tuning readiness an open question rather than a strength.

## 9. Training support

**[FACT]** NeMo provides full training infrastructure. **[INFERENCE]** SALM assembly
(encoder + LLM + connector) is a documented research pattern, so the lineage is
instructive for anyone building such a model — relevant to §15 as a *study* subject.

## 10. Ecosystem and research maturity

- **Publication** **[CLAIM]**: SALM is published research; the model held the top
  leaderboard position for an extended period.
- **Maintenance** **[FACT]**: part of NVIDIA's actively maintained speech line.
- **Documentation** **[FACT]**: NeMo docs plus a card carrying explicit commercial-use and
  deployment-geography statements.
- **Adoption** **[CLAIM]**: significant in GPU-serving contexts.
- **[INFERENCE]** Architecturally this is the **reference implementation of the pattern**
  that ARK, MOSS, Voxtral and Qwen3-ASR all instantiate. Understanding it once explains a
  whole class of 2026 candidates — efficient research even if the artifact never ships.

## 11. Known strengths

Explicit commercial-use statement; no gating; no remote code; reference SALM
implementation; NeMo training infrastructure; dual transcription/post-processing capability.

## 12. Known weaknesses

**[FACT]** English only. **[INFERENCE]** Most GPU-bound candidate in the PASS set.
**[FACT]** CC-BY attribution obligation. **[INFERENCE]** No streaming, no documented
timestamps, no quantized path, no documented adapter recipe. **[INFERENCE]** Largest
hallucination surface class — an LLM decoder can produce fluent text unsupported by audio.

## 13. Integration risks

- **[INFERENCE]** **Poorest fit with CPU-first economics** of anything that passed Gate 1.
- **[INFERENCE]** **Capability-boundary blur**: a model that both transcribes and
  post-processes text sits awkwardly against a contract that treats transcription as a
  single capability. Adopting it would require deciding whether we expose only its ASR
  behaviour.
- **[INFERENCE]** Dual-ecosystem dependency (NeMo + Qwen) doubles the surface to maintain.
- **[FACT]** Attribution reconciliation required.

## 14. Open questions carried to Gate 3

CPU feasibility (likely unfavourable, unmeasured) · whether a SALM exports to ONNX ·
timestamp availability · hallucination behaviour on silence and noise — the property most
worth measuring for this architecture class · whether decoder-only LoRA is workable.

## 15. Strategic value to IntelliAI

- **Architectural reference** — the clearest instance of the SALM pattern, which several
  other candidates share. Its greatest value to us is explanatory.
- **GPU-tier candidate** — if a GPU class is ever created, this is a natural occupant.
- **English-tier candidate** (priority #1), subject to the deployment questions above.
- **[INFERENCE]** Also a useful **hallucination-behaviour probe**: measuring an LLM-decoder
  ASR on our silence and tone probes would tell us something generalisable about the whole
  2026 architecture class, not just this model.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-CANARYQWEN:** *An LLM-decoder ASR will hallucinate fluent text on our silence and
> non-speech probes where our VAD-gated transducer/encoder-decoder path emits nothing —
> making hallucination behaviour, not accuracy, the decisive property of the SALM
> architecture class for IntelliAI.*

Falsifiable and generalisable: if it holds, it informs every SALM candidate; if it fails,
it removes a standing concern about the whole class.
