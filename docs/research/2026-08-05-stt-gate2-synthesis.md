# Gate 2 — Desk Research Synthesis: Speech-to-Text Universe

| | |
|---|---|
| **Gate** | 2 — Desk research ([RESEARCH_FRAMEWORK.md §4](RESEARCH_FRAMEWORK.md)) |
| **Date** | 2026-08-05 |
| **Scope** | The 12 lineages that PASSED Gate 1. The 4 BLOCKED lineages remain frozen and were not researched. |
| **Out of scope** | Benchmarking, scoring, ranking, cross-candidate winner selection, adoption recommendations, benchmark plans (Gate 3). |
| **Deliverable** | 12 complete dossiers + this synthesis + open questions + one benchmark hypothesis per candidate. |

**Nothing in this document scores, ranks, or recommends.** Where it says a lineage
"appears strongest for" a language, that is an observation about *claimed coverage and
architectural fit*, never about measured quality — we have measured none of these
candidates. Statements are labelled **[FACT]** (verified at source or from our own
evaluation records), **[CLAIM]** (publisher/third-party, unverified), or **[INFERENCE]**
(reasoning, not evidence).

---

## 1. Language coverage observations

**No candidate covers English, Hindi and Arabic together.** **[FACT]** This is the
central structural finding of Gate 2 and it constrains everything downstream.

| Lineage | EN | HI | AR | Note |
|---|:-:|:-:|:-:|---|
| Whisper | ✅ *(our evidence)* | ~ *(anecdotal)* | ? *(unevaluated)* | only lineage with any IntelliAI evidence |
| Qwen3-ASR | ✓ | ✓ claimed | ? unconfirmed | 52 langs/dialects claimed |
| Voxtral | ✓ | ✓ claimed | ✗ | 8 primary languages |
| Cohere Transcribe (general) | ✓ | ✗ | ✓ claimed | 14 languages; **EN + AR, never HI** |
| Cohere Transcribe Arabic | ✓ | ✗ | ✅ + dialects + code-switch | purpose-built specialist |
| Omnilingual ASR | ~ *(not the goal)* | ✓ claimed | ? plausible | 1,600+ langs claimed |
| IndicConformer | ✗ | ✓ claimed | ✗ | 22 Indian languages |
| Granite Speech | ✓ | ✗ | ✗ | EN + 5 European/JA |
| Parakeet TDT | ✓ | ✗ | ✗ | 25 European |
| Canary-Qwen | ✓ | ✗ | ✗ | English only |
| Kyutai STT | ✓ | ✗ | ✗ | EN/FR only |
| Moonshine | ✓ | ✗ | ✗ | English-centric |

**English** — the crowded end. Every one of the 12 addresses it, and eight address *only*
English or English-plus-European. **[INFERENCE]** English is where the 2026 generation
concentrated its effort, which means English candidates should be differentiated by cost,
latency, timestamps and streaming rather than by coverage.

**Hindi** — four claimants, in **three architecturally distinct shapes** **[FACT]**:
a dedicated Indic specialist (IndicConformer), and multilingual generalists of two kinds —
a small audio-LLM (Qwen3-ASR 0.6B) and a larger one (Voxtral). The fourth path, an
in-lineage Whisper fine-tune, is *frozen at Gate 1* (IndicWhisper BLOCKED), which removes
the cheapest option from the comparison for now — a consequence worth noticing, since it
was the option requiring no operational change at all.

**Arabic** — one purpose-built candidate (Cohere Transcribe Arabic), one incidental
coverage claim (Cohere general, Arabic among 14), one plausible-but-unverified
(Omnilingual), and the incumbent's entirely unevaluated Arabic. **[INFERENCE]** The
observation that matters is not which is strongest but that **the constraint has moved**:
before this intake Arabic had no candidate; now it has candidates and no corpus, no
baseline, and no benchmark. The bottleneck is our evaluation infrastructure, not the
model supply — and that is a problem fully within our control.

---

## 2. Architectural compatibility with IntelliAI

Assessed **only** against our existing architecture: CPU-first serving, an engine boundary
where foundation-model imports are confined to `engines/`, an ArtifactStore that pins
files by SHA-256 and fetches them unauthenticated at container boot, a pipeline that owns
VAD independently of engines, and a request/response runtime contract with no streaming
method.

**Architecturally closest to what we already run** **[INFERENCE]**:

- **Whisper** — trivially, it *is* what we run. MIT end to end, CTranslate2 int8, measured.
- **Moonshine** — the only candidate whose design centre is identical to our deployment
  constitution: ONNX-first, int8 by default, 27M, no GPU assumption, no remote code, no
  gate. Lowest integration risk in the set.
- **Cohere Transcribe (general)** — a classical encoder-decoder whose **INT8 ONNX export
  already exists**, using dynamic quantization with no calibration data, and whose export
  topology explicitly follows the **Whisper encoder-decoder pattern** **[FACT]**. Its
  first-party path needs remote code; whether the ONNX path avoids that is a key open
  question, because an exported graph carries no Python.
- **IndicConformer** — 600M, `transformers`-native rather than NeMo-bound, with `onnx` and
  `onnxruntime` as *declared, pinned* dependencies **[FACT]**. Hybrid CTC+RNN-T gives two
  decode cost points from one artifact.
- **Omnilingual CTC 300M** — architecturally the cheapest decode shape available (a linear
  head over an encoder, no autoregression), but see below.

**Architecturally distant** **[INFERENCE]**, each for a specific and different reason:

- **Omnilingual ASR** — `fairseq2` is a research framework, not a serving stack. Its
  architecture is attractive; its dependency is the heaviest in the set.
- **Parakeet / Canary-Qwen** — NeMo/Riva/Triton is a complete but *different* operational
  world; adopting either means importing NeMo into our engine boundary or maintaining our
  own ONNX export.
- **Voxtral / Canary-Qwen** — audio-LLM and SALM sizes (3B–5B total, 2.5B) with every
  published operating point on GPU. These do not fit the current serving class; they
  *force the GPU-tier decision* rather than fitting around it.
- **Kyutai STT** — a WebSocket-server-shaped streaming engine against a request/response
  contract with no streaming method. It also bundles a **semantic VAD inside the engine**,
  where our architecture deliberately places VAD in the pipeline, engine-independent.

**Three cross-cutting architectural frictions** worth recording as platform observations
rather than per-model notes:

1. **Gated fetch vs unauthenticated ArtifactStore** **[FACT]** — 3 of 12 (Cohere ×2,
   Voxtral) require credentials to download. Our ModelManager pins URLs and fetches at
   boot; none of it authenticates.
2. **Remote code vs engine isolation** **[FACT]** — 3 of the 12 PASS candidates require
   `trust_remote_code`. Our CI enforces that only `engines/` may import model libraries;
   vendor code executing in-process is a category that discipline has not yet had to model.
3. **Multi-file artifacts vs our pinning model** **[INFERENCE]** — ONNX exports ship
   separate encoder/decoder graphs plus external data files, where our ArtifactStore
   currently pins a small, fixed file set per artifact version.

---

## 3. Compatibility with the future training programme (§15)

Observations only — no candidate is proposed for training work.

**Strongest training-programme relevance** **[INFERENCE]**:

- **Omnilingual ASR** — the only lineage releasing a **standalone SSL (wav2vec 2.0)
  encoder** *separately from* finished ASR models, alongside a large open corpus **[CLAIM]**.
  "Here is a multilingual speech backbone you may build heads on" is a materially different
  offer from "here is a finished model", and it is the closest thing in this universe to a
  foundation for an IntelliAI-native model.
- **Whisper** — the largest fine-tuning ecosystem in ASR **[FACT]**, and the lineage where
  our own capital already compounds. Its constraint is that upstream is frozen and the
  original training corpus was never released.
- **Granite Speech** — uniquely, **LoRA is already in its inference path**: a
  modality-specific LoRA that activates when audio is present, trained jointly with the
  projector, at rank 128 in the NAR variant **[FACT]**. A lineage whose production
  inference is already an adapter is structurally ready for further adapters.
- **Moonshine** — at 27M, **training a language variant ourselves is economically
  conceivable**, which is true of nothing else here. The publisher's own *Flavors of
  Moonshine* line demonstrates the recipe works **[CLAIM]**.
- **Parakeet (NeMo)** — NeMo is a full training framework, not just a runtime **[FACT]**,
  so the lineage is a training-stack option independent of whether we serve its checkpoints.

**Weak training-programme relevance** **[INFERENCE]**: the Cohere models (bespoke
from-scratch architectures with no identified tuning infrastructure), Kyutai (bespoke
`moshi` stack), and Canary-Qwen (dual NeMo+Qwen ecosystems, no documented adapter recipe).

**A note connecting to §12 (dataset research)** **[INFERENCE]**: two lineages are as
interesting for their *corpora* as their weights — Omnilingual's open corpus and
AI4Bharat's public Indic datasets. Both are dataset-research threads with their own
licence questions, and neither depends on adopting the associated model.

---

## 4. Open technical questions before any benchmarking

Grouped by what they block. **[FACT]** None of these can be answered by desk research;
all require either measurement or a decision.

**CPU feasibility — blocks nearly everything.** We have exactly one CPU measurement in
this entire universe: our own whisper-small at RTF 0.162 / ~800 MiB. Every other CPU
statement in all 12 dossiers is inference. Specifically unresolved: 2B-class INT8 ONNX
(Cohere), 600M ONNX (IndicConformer, Parakeet), 300M CTC under `fairseq2` (Omnilingual),
0.6B audio-LLM (Qwen3-ASR), 27M int8 (Moonshine), and whether any audio-LLM runs on CPU at
all (Voxtral, Canary-Qwen).

**Timestamp support and quality.** Our `verbose_json` response format already returns
timestamped segments **[FACT]**, so this is a contract requirement, not a nicety. Status
across candidates: native output (Parakeet **[FACT]**); a *separate model* covering only 11
languages (Qwen3-ASR **[FACT]**); intrinsic to frame-synchronous decoding but exposure
unverified (IndicConformer, Omnilingual CTC); undocumented (Granite, both Cohere models,
Voxtral, Kyutai, Moonshine, Canary-Qwen).

**Hallucination behaviour.** Our silence and tone probes measure 0 hallucinated words
today, achieved structurally via VAD short-circuit **[FACT]**. LLM-decoder architectures
(SALM class: Canary-Qwen, Voxtral, and the blocked ARK/MOSS) can generate fluent text
unsupported by audio. **[INFERENCE]** This is the property most worth measuring across the
whole 2026 architecture class, because a single result generalises.

**Multilingual robustness beyond the coverage table.** Claimed language lists are counts,
not quality. Unresolved for every candidate: per-language quality on EN/HI/AR
specifically, code-mixed behaviour, accent and dialect robustness.

**Tokenization vs our evaluation normalisation.** **[FACT]** Our `speech_normalize`
preserves Unicode category M so Devanagari matras survive — built because `isalnum()`
would erase them. Unverified: how IndicConformer tokenizes Devanagari, how the Cohere
models tokenize Arabic (diacritics, clitics), and whether Omnilingual's **character-level**
CTC output is compatible with our normaliser at all. **[INFERENCE]** If tokenization and
normalisation disagree, measured WER will not mean what we think it means — this could
invalidate a comparison before it is run.

**Streaming quality.** Three distinct architectural answers now sit in the universe —
transducer (Parakeet), delayed-streams (Kyutai), causal-encoder audio-LLM (Voxtral) — plus
our current chunk-plus-VAD approach. Our contract has **no streaming method** **[FACT]**,
so none can be consumed today without M8 work.

**Quantization.** First-party quantized artifacts exist for: Moonshine (int8 default,
**[FACT]**) and Cohere general (INT8 ONNX via `onnx-community`, **[FACT]**). For everything
else, quantization is either community-provided, inferred, or absent.

**Diarization.** No candidate in this universe claims diarization **[FACT]**. It remains an
unaddressed capability, not a differentiator among these models.

**Two non-technical questions that gate technical work** **[FACT]**: how CC-BY attribution
is satisfied under an engine-hiding API (Parakeet, Canary-Qwen, Kyutai), and whether our
artifact pipeline will support authenticated fetch (Cohere ×2, Voxtral). Both are decisions,
not measurements.

---

## 5. Benchmark hypotheses — one per PASS candidate

Each is a **testable proposition**, not a prediction, and each is falsifiable in more than
one direction. Full reasoning sits in the corresponding dossier. **These are not benchmark
plans** — plans are Gate 4 work and require founder approval.

| # | Lineage | Hypothesis |
|---|---|---|
| H-WHISPER | Whisper | large-v3 will measurably reduce Hindi error vs small on our corpus, but at CPU latency and memory that breach our serving class — making Hindi a **cost** decision, not a quality one. |
| H-GRANITE | Granite Speech | Will fail our CPU serving class without a quantization path that does not currently exist — its viability is decided by **deployment engineering**, not transcription quality. |
| H-QWEN3ASR | Qwen3-ASR | 0.6B is small enough to be CPU-servable, but the **two-model, 11-language timestamp story** will be the binding constraint on our `verbose_json` contract, not accuracy. |
| H-VOXTRAL | Voxtral | Will transcribe Hindi better than whisper-small but will not run in our CPU class at all — the candidate that **forces the GPU-tier decision**. |
| H-COHERE-AR | Cohere Transcribe Arabic | Will substantially outperform whisper-small on Arabic dialect and code-switched speech, but **building the Arabic corpus and judge strategy will be the larger half of the work** — and round-trip methodology may not transfer to Arabic unmodified. |
| H-COHERE-GEN | Cohere Transcribe | The INT8 ONNX export will run in our CPU class **without remote code** — the first 2026-generation candidate fitting our architecture unchanged — but its missing Hindi forces a two-engine topology regardless. |
| H-PARAKEET | Parakeet TDT | An ONNX export will run in our CPU class and deliver **native timestamps** better than our post-processed Whisper alignment — but the **NeMo dependency**, not the model, decides whether it fits our engine boundary. |
| H-CANARYQWEN | Canary-Qwen | An LLM-decoder ASR will **hallucinate fluent text on our silence and non-speech probes** where our current path emits nothing — making hallucination, not accuracy, the decisive property of the SALM class. |
| H-OMNILINGUAL | Omnilingual ASR | CTC 300M will be the **cheapest CPU candidate in the universe**, but `fairseq2` — not quality or size — will prevent it fitting inside our engine boundary. |
| H-KYUTAI | Kyutai STT | Streaming-first will deliver materially lower time-to-first-token than chunked Whisper, but its **0.5 s structural delay floor and GPU-shaped runtime** put the benefit out of reach of our CPU class — a lineage to learn from rather than serve. |
| H-MOONSHINE | Moonshine | On short utterances it will beat whisper-small on latency and memory at a quality cost acceptable for *some* traffic — making its real question **whether we ever want length-based routing**, not replacement. |
| H-INDICCONFORMER | IndicConformer | Will reduce Hindi error enough to justify a second engine, but its **Devanagari tokenization will differ from our normalisation** in ways that make raw WER misleading until corpus and normaliser are aligned. |

**[INFERENCE]** Four of the twelve hypotheses predict that the *binding constraint is not
model quality* — it is deployment engineering (Granite), dependency isolation
(Omnilingual), evaluation infrastructure (Cohere Arabic), or measurement validity
(IndicConformer). That pattern is itself the most useful output of Gate 2: it suggests the
next research effort should be weighted toward **our own infrastructure** at least as much
as toward the models.

---

## 6. What Gate 2 changed

- **[FACT]** The Arabic bottleneck moved from *model supply* to *evaluation
  infrastructure*.
- **[FACT]** No candidate serves EN+HI+AR, so a multi-engine topology is now the
  most likely shape of any future STT deployment — a hypothesis §7 of the framework
  reserved, now with coverage evidence behind it.
- **[FACT]** Exactly two candidates have first-party quantized CPU artifacts today
  (Moonshine, Cohere general).
- **[FACT]** The cheapest Hindi option (in-lineage Whisper fine-tune) is frozen at Gate 1,
  which raises the cost of every remaining Hindi path.
- **[INFERENCE]** Our own measurement apparatus — Arabic corpus, Hindi corpus at C3 scale,
  tokenization/normalisation alignment — is now a more immediate blocker than any model
  question.

**Statuses unchanged.** All 12 remain `Researching`; promotion to `Promising` is a Gate 3
review requiring an explicit hypothesis against a named baseline, and is not proposed here.

*This document is a research record. It recommends no model for adoption and selects no
winner.*
