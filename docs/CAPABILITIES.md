# IntelliAI Capability Map — Families, Dependencies, Contracts

| | |
|---|---|
| **Status** | IN FORCE — approved 2026-07-31 (M1.5 D2); governed by [CONSTITUTION.md](CONSTITUTION.md); indexed at [STRATEGY.md](STRATEGY.md) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Role of this document** | The long-term answer to *"what should IntelliAI become excellent at?"* — independent of which models implement it. Registry capability identifiers, `api/v1/<domain>/` packages, and runtime-contract schemas trace back to this map. Governed by [AI_STRATEGY.md](AI_STRATEGY.md); model selection lives in the M1.5 research report, never here. |

---

## 1. Three kinds of capability (the taxonomy)

Not everything customers buy is a model call, and not everything a model
does deserves an API. IntelliAI distinguishes three kinds:

1. **Primitive capabilities** — model-backed, one runtime contract each,
   one registry `capability` value each. The registry routes them; the
   contract outlives every engine (Constitution P2, P3). *These are the
   things IntelliAI must become excellent at serving and, over time,
   excellent at training.*
2. **Composite capabilities** — product surfaces built by *orchestrating*
   primitives (e.g. document intelligence = OCR + layout + chat +
   embedding). No model of their own; their quality is routing + prompt +
   pipeline engineering. They ship faster than primitives and are where
   much of the product differentiation lives. Crucially, a composite can
   later be re-backed by a *native* model (e.g. speech-to-speech
   translation) **without any API change** — composition is an
   implementation detail behind the contract, exactly like an engine.
3. **Artifact-producing capabilities** — capabilities whose output is not
   a response but a **new model artifact in the registry**: fine-tuning as
   a service, voice cloning (a customer-scoped TTS artifact). These plug
   into the lineage DAG and Registry v2's `owner` concept (customer-owned
   models), not into the inference path. They are the productized form of
   IntelliAI's own flywheel.

### The admission test for a primitive capability

A capability becomes a first-class primitive only if it passes all four:

| Test | Question |
|---|---|
| **Contract test** | Does it have a distinct input/output shape that isn't just another capability with different options? |
| **Registry test** | Will multiple interchangeable models/engines plausibly back it, worth routing independently? |
| **Metering test** | Does it have a natural, independently billable usage unit? |
| **Five-year test** | Is demand durable enough to promise contract stability for years? |

Applying the test is what keeps the primitive list short and the contracts
frozen. Examples of the test *rejecting* candidates:

- **Summarization** — fails the contract test: it is `chat` with a task
  prompt. Ships as a composite/convenience surface, never a primitive.
- **Reasoning models** — fail the registry test *as a capability*:
  reasoning is a **tier/property of `chat`** (an effort option, a routing
  decision to a stronger artifact), not a different shape. Registry v2
  models it as artifact metadata, not a capability.
- **Agent models** — same resolution: tool-use belongs *inside* the `chat`
  contract; the agentic loop is a **platform runtime feature** (§5), not a
  model capability.
- **Language identification (audio)** — fails independence: it is an
  output field and an option of `transcription`. A standalone detect
  endpoint can exist later as a thin convenience over the same service.
- **Speaker verification (voice biometrics)** — passes the contract test
  but is **deliberately excluded** (§7): biometric authentication is a
  regulatory and abuse minefield orthogonal to IntelliAI's trajectory.

---

## 2. The capability families

### Family S — Speech (Audio Intelligence)

| Capability | Kind | One-line definition |
|---|---|---|
| `transcription` | Primitive | audio → text (+segments, language, timestamps); streaming variant = contract v2 of the *same* capability |
| `speech_synthesis` | Primitive | text + voice → audio; streaming variant likewise |
| `diarization` | Primitive | audio → speaker-labeled time segments ("who spoke when") |
| `speech_translation` | Primitive (composite-backed first) | audio in language A → text (later: audio) in language B; launched as transcription→translation(→synthesis) pipeline, re-backed by native S2S models when they mature — invisibly |
| Audio intelligence (summaries, chapters, sentiment, action items) | Composite | transcription (+diarization) + chat |
| Voice cloning | Artifact-producing | consented voice samples → customer-owned synthesis voice artifact; consent-gated and watermark/disclosure-policied from day one |

### Family L — Language (Text Intelligence)

| Capability | Kind | One-line definition |
|---|---|---|
| `chat` | Primitive | messages (+tools, +response schema) → message / tool calls / structured output; subsumes completion, "reasoning" tiers, JSON mode |
| `embedding` | Primitive | texts (later: images) → vectors |
| `rerank` | Primitive | query + candidate documents → relevance-ordered scores |
| `translation` | Primitive | text A→B; distinct from chat by shape (source/target contract, glossary/formality options) and by the existence of dedicated MT models worth routing to |
| `moderation` | Primitive | text / transcript / image → policy category scores; **dual-use: public API product AND internal trust-&-safety dependency** of every generative capability |
| Retrieval / RAG pipelines | Composite | embedding + rerank + chat over customer corpora; managed-retrieval product surface, not a model |
| Fine-tuning as a service | Artifact-producing | customer dataset + base lineage → customer-owned artifact (the flywheel, sold as a product) |

### Family V — Vision (Visual Intelligence)

| Capability | Kind | One-line definition |
|---|---|---|
| `ocr` | Primitive | image/PDF page → structured text + layout blocks + confidence |
| `image_understanding` | Primitive | image(s) + prompt → text (VQA, captioning, chart/diagram reading) |

### Family D — Documents (Document Intelligence)

| Capability | Kind | One-line definition |
|---|---|---|
| Document parsing/extraction | Composite | file → clean structured output (markdown/JSON-by-schema); orchestrates `ocr` + `image_understanding` + `chat` + `embedding` |
| Document classification/splitting | Composite | same primitives, pipeline recipes |

Documents is a *family of composites by design*: its excellence is
pipeline and schema engineering on top of V- and L-primitives. It earns no
new primitives unless a distinct-shape model class emerges (re-run the
admission test then).

### Family A — Agents & Realtime (integration layer)

| Capability | Kind | One-line definition |
|---|---|---|
| Agent runtime | Platform feature | server-side tool-calling loops where **every IntelliAI capability is a tool**; sits above the registry, not in it |
| Realtime voice sessions | Composite (session-class) | streaming `transcription` + `chat` + streaming `speech_synthesis` in one bidirectional session |

This family is deliberately last (§6): it is the integration payoff of
everything below it and the strongest lock-in surface — but only once the
primitives it composes are excellent.

**Total: 11 primitive capabilities** (`transcription`, `speech_synthesis`,
`diarization`, `speech_translation`, `chat`, `embedding`, `rerank`,
`translation`, `moderation`, `ocr`, `image_understanding`) — small on
purpose. Eleven frozen contracts is a platform; thirty is a maintenance
museum.

---

## 3. Dependencies between capabilities

```
                         ┌────────────── agents / realtime voice ─────────────┐
                         │   (every primitive becomes a tool / session leg)   │
                         └──▲──────────▲──────────▲──────────▲──────────▲─────┘
                            │          │          │          │          │
 audio intelligence ────► chat   transcription  speech_synthesis  …all…
 document intelligence ─► chat + ocr + image_understanding + embedding
 RAG pipelines ─────────► embedding + rerank + chat
 speech_translation ────► transcription + translation (+ speech_synthesis)
                          [until re-backed by a native S2S artifact]
 streaming variants ────► their batch capability's contract + realtime infra
 moderation ◄──────────── consumed internally by every generative capability
 evaluation harness ◄──── consumes ALL capabilities (cross-cutting, M9)
```

Three structural observations:

1. **Dependencies flow composite → primitive, never sideways between
   primitives.** No primitive contract references another primitive —
   that is what keeps eleven contracts independently evolvable
   (Constitution P2).
2. **`chat` is the gravitational center of the composite layer.** Audio
   intelligence, document intelligence, RAG, and agents all orchestrate
   through it. That makes chat's contract quality — tools, structured
   output, streaming — a platform-wide concern from the day it ships, and
   it is why the Language family cannot be deferred past year ~2.
3. **`moderation` is load-bearing before it is a product.** Every
   generative capability needs it internally (abuse, safety, acceptable
   use). Building it as a served capability from the start means the
   internal dependency and the sellable product are one implementation.

---

## 4. Shared infrastructure — the three serving classes

Eleven primitives do **not** mean eleven kinds of infrastructure. Every
capability maps onto one of three serving classes, and the platform builds
each class **once**:

| Serving class | Shape | Capabilities |
|---|---|---|
| **T — Task services** | request → result in seconds; bounded worker pool; load-shedding backpressure (the M2 STT design) | transcription, speech_synthesis, diarization, ocr, embedding, rerank, translation (small MT), moderation |
| **K — Token-stream services** | continuous-batching token servers (KV cache, SSE out) | chat, image_understanding, translation (LLM-backed), all reasoning tiers |
| **R — Realtime session services** | stateful bidirectional WebSocket sessions; contract v2 framing | streaming transcription, streaming synthesis, realtime voice |

Other shared substrates, each built once and reused across families:

- **Media ingestion** (upload limits, ffmpeg/image decoding, format
  normalization, object-storage staging): transcription, diarization,
  ocr, image_understanding, document intelligence.
- **Binary-output path** (typed audio/file responses + `X-Runtime-Envelope`
  metadata — solved in the M2 design): synthesis today, any binary-out
  capability later.
- **Async jobs + webhooks** (M5, Postgres `SKIP LOCKED`): batch
  transcription, document pipelines, *and* all artifact-producing
  capabilities (fine-tuning, voice cloning) — training jobs are jobs.
- **Vector substrate** (storage + ANN search): embedding, rerank, RAG
  composites.
- **Session substrate** (auth for long-lived connections, session tokens,
  time-based metering): class R and agents.
- **Evaluation harness + dataset registry** (M9): consumed by every
  capability — the eval sets are per-capability, the machinery is one.

The strategic point: **choosing a new capability = choosing a serving
class + a contract**, not inventing infrastructure. When D3+ evaluates
foundation models, "which serving class does its natural engine fit?" is a
scoring input — a model demanding a fourth serving class carries its cost.

---

## 5. First-class platform primitives

The eleven primitives in §2 are the registry's `capability` enum for the
next five years. Around them, five **platform primitives** (not model
capabilities — the machinery the Constitution already mandates): the
registry (P3), the evaluation harness (P5), the dataset registry (P6, P7),
the metering/usage spine, and the moderation layer. These five appear in
every family's story above; they are the difference between "hosts
models" and "is a platform."

One boundary rule, stated once: **nothing becomes a public primitive to
serve an internal need, and nothing internal is denied productization if
it passes the admission test.** Moderation passes both ways; evaluation
stays internal (its public face is published benchmarks, not an API — until
the day customers want eval-as-a-service, which re-runs the test).

---

## 6. Phased capability roadmap (3–5 years)

Phases sequence by three rules: (a) each phase reuses the serving classes
and substrates of the previous one; (b) a family's composites ship only
after its primitives are excellent; (c) own-model investment (the
flywheel) starts where the wedge is, not everywhere at once.

| Phase | Horizon | Capabilities introduced | New infrastructure | Flywheel state |
|---|---|---|---|---|
| **P1 — Speech core** *(current roadmap M2–M12, unchanged)* | now → yr 1 | `transcription`, `speech_synthesis`; streaming STT (M8) | serving class T; media ingestion; jobs; registry v1→v2; **evaluation harness (M9) — the flywheel's ignition** | serving only; eval sets accumulate |
| **P2 — Speech depth** | yr 1 → 2 | `diarization`, `speech_translation` (composite-backed), audio-intelligence composites, streaming synthesis; voice cloning (artifact-producing, consent-gated) | serving class R matures; artifact-production pipeline v1 | **first fine-tuned intelliai-stt/tts artifacts in wedge languages/domains; first published own benchmarks** |
| **P3 — Language** | yr 2 → 3 | `chat`, `embedding`, `rerank`, `translation`, `moderation`; RAG composites | serving class K (the big one: GPU token servers); vector substrate | fine-tuned STT/TTS in production; chat served on open weights, fine-tuning begins where wedge data exists |
| **P4 — Vision & documents** | yr 3 → 4 | `ocr`, `image_understanding`; document-intelligence composites | reuses T + K + media ingestion (nothing new — the payoff of §4) | own speech models mature; language fine-tunes promoted; doc pipelines generate eval data |
| **P5 — Integration & ownership** | yr 4 → 5 | agent runtime, realtime voice sessions; fine-tuning-as-a-service GA (customer-owned artifacts) | session substrate at scale | `intelliai-*` artifacts back the majority of routed traffic in wedge segments; customers train on the platform |

Two honesty notes. First, **P3 is the capital-intensive phase**: serving
class K and credible LLM serving is where GPU economics arrive
(AI_STRATEGY §6 made hardware a posture, not a wall — P3 is when the
posture shifts). Second, the phases overlap deliberately — P2's flywheel
work runs *while* P1's later milestones ship; capability launch dates and
own-model dates are independent tracks (Constitution P9's spirit applied
to roadmaps).

---

## 7. Explicitly out of scope (and why)

| Excluded | Reason |
|---|---|
| Image/video/music **generation** | Different market (media/creative), different serving economics (diffusion), heavy moderation burden, brand dilution for a developer-intelligence platform. Re-evaluate only on strong customer pull. |
| **Speaker verification / voice biometrics** | Authentication-grade biometrics = regulatory + abuse surface disproportionate to strategic value. Diarization ("which speaker") is in; identity claims ("who is this person") are out. |
| **Wake-word / on-device edge models** | Edge inverts the trust boundary (AI_STRATEGY §6); post-1.0 at the earliest. |
| **Video understanding** | Parked, not rejected: composable later from frames→`image_understanding` + audio→`transcription`; earns primitive status only if native video models pass the admission test when the time comes. |
| **Eval-as-a-service** | Internal primitive for now; public face = published benchmarks. |

---

## 8. Abstract runtime contracts per primitive

Model-free contract sketches — enough shape to freeze *identity* (what the
capability is), while field-level schemas arrive with each capability's
milestone. All eleven inherit the M2 envelope (`output` + `usage[]` +
`timing` + `model`), the transport-per-direction rule, the error-mapping
discipline, and capability-level-options-only (the portability test).

| Capability | Input | Output | Core options (capability-level) | Usage units | Class | Streaming posture |
|---|---|---|---|---|---|---|
| `transcription` | audio (binary) | text, segments[], detected language, duration | language, timestamp granularity, vocabulary/bias hints | `audio_seconds` | T | v2: partial-result frames over WS |
| `speech_synthesis` | text | audio (binary) | voice, format, sample rate, speed | `characters` (+`audio_seconds_out` reported) | T | v2: chunked audio frames |
| `diarization` | audio (binary) | segments[]: {start, end, speaker_label} | speaker-count hint, min/max speakers | `audio_seconds` | T | later, joined with streaming STT |
| `speech_translation` | audio (binary) + target language | translated text (later: + audio) | source/target language, output voice (when audio out) | `audio_seconds` (+`characters` when synthesizing) | T (composite-backed) | later |
| `chat` | messages[] (+ tool definitions, + response schema) | message \| tool_calls[] \| schema-conforming JSON | max output, temperature, tool choice, response format, reasoning effort *(tier knob, not a new capability)* | `input_tokens` + `output_tokens` | K | SSE from day one — streaming is the primary shape |
| `embedding` | texts[] (later: images) | vectors[] + dimensions | output dimensions (where supported), normalization | `input_tokens` | T | none |
| `rerank` | query + documents[] | ranked {index, score}[] | top_n, return_documents | `input_tokens` (query+docs) | T | none |
| `translation` | text + target language | translated text + detected source | source/target language, formality, glossary ref (later) | `characters` | T or K (backend's business, invisible) | optional SSE |
| `moderation` | text \| image \| transcript | per-category scores + flags + policy version | policy version | `requests` (+`input_tokens` at scale) | T | none |
| `ocr` | image/PDF (binary) | blocks[]: {text, bbox, type, confidence} + reading order | language hints, output format (raw/markdown), page range | `pages` | T | none |
| `image_understanding` | image(s) (binary/ref) + prompt | text | max output, detail level | `input_tokens` (incl. image tokens) + `output_tokens` | K | SSE |

Contract-design notes that already bind future milestones:

1. **Streaming is a contract *version* of the same capability, never a new
   capability** — `transcription` v1 (batch) and v2 (realtime frames)
   share identity, registry entry lineage, and evaluation history.
2. **`usage[]` as {unit, amount} list absorbs every row above** — designed
   into M2, validated here against all eleven: no capability needs a new
   metering shape. (P1's metering spine survives five years untouched.)
3. **Composites meter as the sum of their primitives plus a pipeline
   surcharge decision** — a *pricing* decision (product), never a new
   contract shape (platform). P9 applied to billing.
4. **Every binary-input contract shares the media-ingestion front** — one
   place for size caps, format allow-lists, and decode hardening; security
   review happens once, not per capability.

---

*Change log:*
- *2026-07-31 — v0.1: initial capability map (Milestone 1.5, Deliverable 2)
  — taxonomy (primitive/composite/artifact-producing), admission test, five
  families, 11 primitives, dependency graph, three serving classes, phased
  P1–P5 roadmap, exclusions, abstract contracts. Pending approval.*
