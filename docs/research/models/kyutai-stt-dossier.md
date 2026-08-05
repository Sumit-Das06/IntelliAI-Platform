# Kyutai STT — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `cc-by-4.0` verified in raw frontmatter of `kyutai/stt-1b-en_fr`; not gated; no remote code. ⚠ Attribution obligation, with named authors published. |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

Kyutai STT — the speech-recognition side of Kyutai's real-time speech stack, from the lab
behind **Moshi** (full-duplex spoken dialogue) **[FACT]**. Published artifacts include
`kyutai/stt-1b-en_fr` (~1B), `kyutai/stt-2.6b-en` (~2.6B), and MLX variants **[FACT]**.
Framework repository: `kyutai-labs/delayed-streams-modeling` **[FACT]**.

## 2. Architecture

- **Design** **[FACT]**: **decoder-only, streaming-first**, built on **delayed streams
  modelling** — the technique pioneered in Moshi, which models a text stream conditioned on
  a speech stream using Moshi's multistream architecture.
- **[INFERENCE]** This is the architectural opposite of every other candidate here. Others
  are offline models that can be chunked; this one is a streaming model by construction,
  where latency is a *tunable design parameter* rather than a consequence of chunk size.
- **The delay parameter is explicit and per-model** **[FACT]**: `stt-1b-en_fr` has a
  **0.5-second delay**; `stt-2.6b-en` has a **2.5-second delay**. Latency and accuracy are
  traded openly at checkpoint level.
- **Semantic VAD** **[FACT]**: `stt-1b-en_fr` ships with a **semantic VAD** — a model-level
  determination of when a speaker has finished, not an energy threshold.
  **[INFERENCE]** Our pipeline currently uses a deterministic energy-RMS VAD
  (`EnergyVad`), deliberately placed behind a `VoiceActivityDetector` Protocol. A semantic
  VAD is exactly the kind of component that seam was designed to accept — though it
  arrives here bundled inside an engine rather than as a separate component.
- **Audio codec** **[FACT]**: Moshi's **Mimi** streaming neural audio codec underpins the
  stack.
- **Decoding** **[FACT]**: streaming, incremental.
- **Timestamps** **[INFERENCE — open question]**: not documented in material reviewed; a
  streaming decoder emits text progressively, which is a different alignment story from
  segment timestamps.
- **Tokenizer** **[INFERENCE]**: Moshi-family text tokenizer.
- **Multilingual strategy** **[FACT]**: none — per-checkpoint language scope (en, or en+fr).

## 3. Languages

**[FACT]** English and French only (`stt-1b-en_fr`); English only (`stt-2.6b-en`).

**No Hindi. No Arabic.** **[FACT]** This lineage cannot serve two of our three product
languages and shows no roadmap toward them in material reviewed.

## 4. Licensing (Gate 1, verified 2026-08-05)

`license: cc-by-4.0` in raw frontmatter; `library_name: moshi` **[FACT]**. Body states the
weights are "licensed under CC-BY 4.0" **[FACT]**. Nine authors are named on the card
**[FACT]** — relevant because CC-BY attribution has a concrete subject here.

⚠ Attribution obligation versus our engine-hiding public API — the same unresolved product
question as the NVIDIA candidates **[FACT]**.

## 5. Runtime and deployment profile

- **Serving stack** **[FACT]**: a **Rust server providing streaming access over
  WebSockets**, plus PyTorch and MLX implementations. The `moshi` library is the declared
  `library_name`.
- **Concurrency evidence** **[CLAIM — publisher]**: the Rust server serves **64 simultaneous
  connections at a real-time factor of 3× on an L40S GPU**; an **H100 can process 400
  streams in real time**; batching is supported for hundreds of concurrent conversations.
- **[INFERENCE]** These are the most concrete concurrency numbers published by any
  candidate here — and they are all GPU numbers. The lineage's engineering is
  serious and its target is unambiguous.
- **CPU friendliness** **[CLAIM — negative signal]**: a public issue on the framework
  repository reports **"Rust server real-time STT from mic is painfully slow"**.
  **[INFERENCE]** This is a third-party report, not a measurement, and its hardware context
  is unknown — but combined with GPU-only published operating points it is a meaningful
  signal that CPU is not the design target.
- **ONNX / CTranslate2 / vLLM** **[INFERENCE — none identified]**.
- **Quantization** **[INFERENCE — open question]**; MLX variants imply Apple-silicon
  optimisation rather than general CPU.
- **Remote code** **[FACT]**: none; but a `moshi`-library dependency is required.
- **Cold start / memory** **[INFERENCE]**: unmeasured; 1B–2.6B.
- **Operational maturity** **[FACT]**: a production-shaped WebSocket server with documented
  batching is more operationally complete than most research releases.

## 6. Quality evidence

**None from IntelliAI.** Publisher accuracy/latency claims are excluded at this gate.

## 7. Latency and memory expectations

**[FACT]** Delay is a documented per-checkpoint property (0.5 s / 2.5 s) rather than an
emergent one. **[INFERENCE]** For a streaming product this is the most directly useful
latency disclosure in the set — it states the model's structural floor, which no amount of
serving optimisation can beat.

## 8. Fine-tuning ecosystem

- **[INFERENCE — open question]** No LoRA/PEFT precedent or fine-tuning recipes identified.
  The `moshi` stack is bespoke, and adding a language would be a research project, not an
  adapter.
- **[INFERENCE]** Community tuning infrastructure is minimal compared with Whisper or Qwen.

## 9. Training support

**[CLAIM]** The delayed-streams-modelling paper ("Streaming Sequence-to-Sequence Learning
with Delayed Streams Modeling") is published, and the framework repository is public.
**[INFERENCE]** The *method* is more transferable than the checkpoints — this is a lineage
to learn an architecture from, more than one to tune.

## 10. Ecosystem and research maturity

- **Publication** **[FACT]**: named paper plus open framework repository — strong research
  hygiene.
- **Maintenance** **[FACT]**: active; multiple checkpoints, several implementations
  (PyTorch, Rust, MLX), open issue tracker.
- **Documentation** **[FACT]**: model cards, project site, repository docs.
- **Ecosystem** **[INFERENCE]**: narrow but deep — concentrated on real-time speech.
- **Institutional profile** **[FACT]**: a French non-profit research lab. **[INFERENCE]**
  Lower long-term product-continuity assurance than a corporate publisher, though CC-BY
  weights remain irrevocable once released.

## 11. Known strengths

Genuinely streaming-first architecture with an explicit, published latency floor;
**semantic VAD**; a production-shaped Rust WebSocket server with documented batching;
strong research publication; commercially usable licence; concrete concurrency figures.

## 12. Known weaknesses

**[FACT]** Two languages only. **[FACT]** CC-BY attribution obligation. **[CLAIM]** Reported
CPU slowness. **[INFERENCE]** No quantization/ONNX path, no fine-tuning ecosystem, bespoke
`moshi` dependency, timestamps undocumented, non-profit continuity profile.

## 13. Integration risks

- **[INFERENCE]** **Our contract has no streaming method.** Consuming this lineage properly
  would require the M8 streaming work first — this is not an engine swap but a platform
  capability change.
- **[INFERENCE]** A WebSocket-server-shaped engine does not match our current
  request/response runtime binding; we would either wrap it or adopt its server.
- **[INFERENCE]** Semantic VAD arrives *inside* the engine, whereas our architecture places
  VAD in the pipeline, engine-independent. Adopting it would blur a boundary we set
  deliberately in M2.
- **[FACT]** Attribution reconciliation required.

## 14. Open questions carried to Gate 3

CPU feasibility (the reported slowness needs verification, not repetition) · timestamp
availability in a streaming decoder · whether semantic VAD can be separated from the engine
or must be swallowed whole · how streaming output maps onto our runtime contract ·
quantization options.

## 15. Strategic value to IntelliAI

- **Streaming research candidate — the reference case.** It is the strongest open
  expression of "streaming as a first-class design" rather than "offline model plus
  chunking", which is exactly the choice the M8 decision will face.
- **Semantic VAD reference** — a concrete instance of the model-based VAD our pipeline
  Protocol was designed to accommodate but has never been given.
- **[INFERENCE]** Its value is most likely **architectural knowledge rather than
  adoption**: two languages and a GPU-shaped runtime make it a poor product fit, while its
  design answers a question we will have to answer ourselves.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-KYUTAI:** *A streaming-first architecture will deliver materially lower
> time-to-first-token than chunked Whisper at equivalent audio, but its structural delay
> floor (0.5 s) and GPU-shaped runtime will make the streaming benefit unreachable within
> our CPU serving class — making this a lineage we learn from rather than serve.*

Falsifiable: CPU streaming may prove viable, in which case the conclusion inverts entirely.
