# Milestone 3 Engineering Design Review — Speech Synthesis Platform (v0.4)

**Approved:** 2026-08-03, after two founder refinement rounds. This document
is the reference every M3 step is reviewed against; material deviations go
through review, not through the sprint. Related decisions:
[ADR-0019](../adr/0019-runtime-core-shared-lifecycle-package.md) (shared
runtime lifecycle package), [ADR-0020](../adr/0020-binary-audio-transport-binding.md)
(binary audio transport binding).

## 1. Public product model philosophy

**One naming system, second instance.** `intelliai-tts` joins
`intelliai-stt` as a public model: a *promise* ("IntelliAI turns text into
natural speech"), served by replaceable artifacts (Kokoro-82M today,
IntelliAI-TTS tomorrow) behind the registry. Everything proven for STT
applies unchanged: catalog record, per-artifact-version license verdict,
leak-guard (no engine names in any response), `released` date,
OpenAI-compatible surface (`/v1/audio/speech`).

**The new element is voice identity.** A voice is a *second* public
identifier — customers script `voice: "..."` into their code, which makes
voice ids as unbreakable as model ids. Naming them is a founder decision
(Step 0). Launch shape: a small set of 2–4 English voices with
human-adjacent product names, never numbered SKUs — voices are the brand
surface of TTS.

**Law — voice ids never expose engine names.** The same identity
abstraction the platform enforces for models, stated for voices:

```
Engine-internal (never leaves the runtime):   af_heart
Public identity (permanent product name):     intelliai-aurora
```

The public identifier survives engine replacement: if a fine-tuned model or
a different engine later renders that voice better, the name stays and the
binding behind it changes — exactly as `intelliai-stt` will one day stop
meaning whisper-small without any customer noticing. The catalog leak-guard
test extends to voices: no engine voice token (`af_*`, speaker indices,
embedding names) may appear in any public response, ever.

**Core Speech Language Policy v1 (founder directive, recorded at Step 7
close, 2026-08-03).** IntelliAI's speech platform has three first-class
languages: **English, Hindi, Arabic**. This is a *product* requirement,
never an engine requirement: the customer-facing APIs must come to
provide complete support for these three languages across speech
capabilities over time, and every future decision — engine adoption,
model replacement, evaluation corpora, benchmarking, fine-tuning, voice
management, speech translation, speech-to-speech — optimizes toward that
target. If no single engine can serve all three under IntelliAI's
licensing and quality standards (as of this writing, none can: Kokoro is
license-clean for English only, Hindi is GPL-gated, Arabic absent),
different engines serve different languages internally while the
customer-facing API stays one and stable. "Complete support" is defined
measurably: a corpus, a quality baseline, and a production benchmark per
language — the policy is enforceable by evidence.

**Principle — product capabilities are permanent; individual engines are
temporary (founder directive, same date).** The platform evolves by
replacing engines beneath stable products. This is the one sentence the
whole architecture serves: the **Registry** exists so a capability's
public identity outlives every artifact that serves it; the **Runtime**
template + engine Protocol exist so an engine is a plug, not a
foundation; the **Evaluation plane** exists so each replacement is a
measured, cited decision rather than a rewrite; and **Registry V2** turns
replacement itself into governed workflow — promotion records, per-voice
switching tests, multi-engine routing under one public model. An engine
is adopted, measured, eventually beaten, and retired; the capability, its
API, its voices, its baselines, and the knowledge of every replacement
remain.

## 2. Speech synthesis runtime architecture

`services/tts-runtime` (renamed from `tts-kokoro` at Step 0) is the second
instantiation of the ADR-0018 template — HTTP binding / model lifecycle /
inference execution / pipeline — with one substitution:

- **The pipeline is a text pipeline**: validate (length caps, non-empty) →
  normalize (a reserved seam — v1 pass-through; future number/abbreviation
  expansion lives here, not in engines) → **voice resolution** (public
  voice id → engine voice reference). Stage-timed like STT's media
  pipeline.
- **Output encoding lives in the api layer**: engines return canonical
  PCM + sample rate; WAV containerization is the binding's job. Mirror
  image of "engines never see MP3s."
- **Worker pool, admission control, readiness, warm-up**: unchanged in
  design; sized by Step 7 measurement. **Warm-up executes a
  capability-defined deterministic probe** — reference audio for STT,
  reference text for TTS, a reference image for a future OCR runtime, a
  reference prompt for vision. The lifecycle machinery never knows which;
  it only knows a probe must succeed before readiness.

**The structural decision this milestone forces: extraction.**
ModelManager, ArtifactStore, WorkerPool, and `RuntimeServiceError`
currently live inside stt-runtime; the second consumer now exists, which
triggers the extract-at-second-consumer rule.

**Package: `packages/runtime-core`** (ADR-0019; `serving-core` rejected —
it names a function, and functions accrete; `runtime-core` names an owner
and completes an existing vocabulary: the runtime *plane* (ADR-0002), the
runtime *contract* (the language runtimes speak outward), the runtime
*core* (the machinery runtimes share inward)). Permanent home for
ModelManager, ArtifactStore, WorkerPool, `RuntimeServiceError`, and future
shared serving infrastructure.

**Principle — `runtime-core` owns lifecycle, never inference.** The
package understands `ensure → load → warm → ready → execute → shutdown`
and nothing else. It never understands Whisper, Kokoro, OCR, Qwen, or any
model-specific logic: inference always belongs to engines, behind
capability-local Protocols, with the warm-up probe supplied from outside.
Any change to `runtime-core` that mentions a model family is a design
error by definition.

**Does ModelManager change?** Structurally, no — ensure→load→warm→serve,
slots, hash-verify-every-boot all survive intact; multi-file voice assets
already fit (`ArtifactSpec.files` is a tuple). What changes is its
*address* (shared package) and its *typing* (generic over the engine
Protocol, probe injected). **The success criterion, stated as an
invariant: a diff of ModelManager's logic between M2 and M3 must be
empty.** If the extraction changes any behavior — one hash check, one
lifecycle transition, one failure path — the extraction has failed,
regardless of how green the build is.

## 3. Runtime contract evolution (all additive; contract stays v1)

- `Capability += SPEECH_SYNTHESIS` · `UsageUnit += CHARACTERS` (members
  land with their schemas — the append rule, honored a second time).
- **`SpeechSynthesisRequest`**: `text` (bounded), `voice: str | None`
  (public voice id; None → default), `language: str | None` (hint for
  multilingual voices), `speed: float | None` (typed now, semantics
  pinned), `model: str | None` (artifact selection — the slot pattern).
- **`SpeechSynthesisResult`** — metadata only, because audio travels as
  transport body: `duration_seconds`, `sample_rate_hz`, `voice` (the one
  that served), `characters`. `SpeechSynthesisResponse =
  RuntimeResponse[SpeechSynthesisResult]`.
- **Errors: zero new types.** `voice_not_found` = `invalid_input,
  param="voice"`; text-too-long = `invalid_input, param="text"`.
- **Streaming compatibility**: nothing here blocks it — streaming arrives
  (M8) as an additive method yielding audio chunks with the envelope as a
  trailer.

## 4. Binary transport (ADR-0020)

**Why TTS deserves different transport than STT:** the asymmetry flipped.
STT's *output* is text — tiny, JSON-native; its input was the big binary,
and multipart handled that. TTS's *output* is the big binary: a 30-second
WAV is ~1 MB. Structure and throughput have opposite needs.

| Option | Verdict |
|---|---|
| Base64 audio inside the JSON envelope | Rejected: +33% payload, double-buffering, clients must decode before playing — hostile to streaming. |
| Multipart response | Rejected: multipart *responses* have poor client-library support; it is a request-side convention. |
| **Raw audio body + envelope in `X-Runtime-Envelope` header** | **Chosen.** Playable bytes directly; ~1 KB envelope rides a header; OpenAI's `/v1/audio/speech` also returns raw bytes. Errors are **always JSON** with normal status codes — one error shape platform-wide, never binary. |
| Chunked/WebSocket streaming | Deferred to M8 by policy — the chosen binding is chunk-*ready* (a raw body can become a chunked body with a trailer without changing the request shape). |

**Invariant — the envelope header is operational metadata only.** It
carries usage counts, timing, runtime identity, contract version — and
nothing generated: never transcripts, never logs, never diagnostics or
debugging detail, never model-produced text. Operational metadata is
bounded by construction; generated content is unbounded, and one generated
field makes header size a function of model output — a production incident
waiting for a long sentence, since headers traverse proxies and load
balancers with hard limits (commonly 8 KB total). The header's size
ceiling is intentional and pinned by test, well under common proxy limits.
Anything large belongs in the body or in logs — never in the envelope.

## 5. Voice architecture

| Concept | What it is | Lives in |
|---|---|---|
| **Voice** | The product: a named, stable identity customers select. | Public contract (request field) + gateway catalog (`/v1/audio/voices`) |
| **Speaker** | The acoustic identity inside a model. | Runtime — engine-internal, mapped from voice id by config; never public |
| **Style** | Delivery variation (narration, conversational). | Metadata on the voice record now; a request parameter only when an engine can honor it — additive later |
| **Language** | What a voice can speak. | Voice metadata (`languages: [...]`) + request `language` hint |
| **Accent** | A flavor of language rendering. | Metadata / separate voices — an accent is a different voice, not a parameter |

**The vertical stack — how a voice becomes sound:**

```
Voice                 intelliai-aurora             (product identity, permanent)
  ↓ resolved by catalog + runtime config
Voice Asset           hash-pinned file(s) in the artifact spec
  ↓ contains / yields
Voice Representation  e.g. a speaker embedding     (engine-internal)
  ↓ consumed by
Model                 kokoro-82m — renders ANY compatible representation
```

- **Voice** is a product fact: a permanent name, a catalog record, a
  promise. Its lifecycle is measured in years and governed by deprecation
  policy, not engine releases.
- **Voice Asset** is a technical fact — defined as **"the engine-specific
  representation required to reproduce a voice."** Today that is a file
  containing a speaker embedding; for other engines it may be an adapter,
  a LoRA, conditioning vectors, voice tokens, or representations that do
  not exist yet. The abstraction is deliberately engine-independent so it
  holds for the next 5–10 years of engines: an asset is *whatever the
  bound engine needs*, and the platform never assumes its shape — only
  that it is versioned, hash-pinned, license-audited, and stored like any
  artifact file. Assets belong to **artifacts** because they have
  everything artifacts have (versions, checksums, license verdicts,
  ArtifactStore residency) and nothing product identities have. When the
  artifact behind a voice is replaced, the asset is replaced; the voice is
  not.
- **Speaker Embedding** (today's representation) is intentionally hidden
  from customers, for three reasons. It is engine-coupled — embeddings
  from one model family are meaningless to another, so exposing them would
  weld the public API to today's engine. Anything exposed becomes API
  surface forever — the opaque voice id is the abstraction that keeps
  representations free to change. And embeddings are the raw material of
  cloning — a quasi-biometric representation of a person's voice — so the
  consent-gated cloning future requires they exist only behind platform
  governance, never as customer-visible values.
- **Model** is the renderer: it consumes any compatible representation
  and produces audio. It has no identity opinion — which is what makes
  voices rebindable and cloning an addition, not a redesign.

**Ownership boundary — the model split, mirrored for voices:**

| Gateway / Product owns | Runtime owns |
|---|---|
| Voice identity (the public id) | Engine voice mapping (voice id → engine reference) |
| Voice metadata | Rendering configuration |
| Voice lifecycle (release, deprecation, grace) | Voice assets (the files) |
| The catalog (`/v1/audio/voices`) | Embeddings / representations |
| The public API surface | Inference mechanics |

Registry answers "is this voice real and what is it called"; runtime
answers "make it." This mirrors the Registry-vs-Runtime separation
established for models (ADR-0017): identity and promise on the product
side, mechanics and replaceability on the runtime side.

**Direction (recorded at Step 4 close, 2026-08-03): public voices follow
the same evolution path as public models.** V1 keeps voice records
code-declarative in the gateway beside the model catalog. Registry V2
(M9) will own public voice resolution exactly as it will own model
resolution — records in the database plane, resolution behind the same
interface — and the runtime's role converges to consuming
already-resolved voice assets (hash-pinned artifact files plus a
deployment binding), never public identity. Future identity work
(cloning's org-owned voices, per-voice promotion, the switching test
applied per-voice) hangs off the registry's voice records, not off
runtime configuration.

**Law — voice metadata is append-only.** Voice metadata evolves exactly
like the runtime contract (ADR-0016 evolution rules): future additions —
preview audio, recommended speed, age group, sample rate, tags — arrive as
new optional fields with defaults; existing fields never change meaning or
disappear; existing clients never break. A voice record written at launch
must still parse, unmodified, under every future catalog schema.

**Evolution without breaking APIs:** voice ids are immutable; metadata is
append-only; the artifact behind a voice can be rebound (a fine-tuned
engine *inherits* a voice id if it wins the listening comparison — the
switching test applied per-voice); retirement is `status: deprecated` plus
a grace period, never deletion.

**Cloning** fits without renovation because the stack pre-built its
slots: a cloned voice = a per-organization **Voice Asset** (org-owned
artifact per the model-identity policy) yielding a new representation for
an unchanged **Model**, with the reserved `speaker_similarity` metric and
`ComparisonContext` ready to judge it, and the STT media pipeline
validating the customer's reference audio. Cloning later adds `owner_org`,
`reference_artifact`, and consent/watermark fields to the voice record —
all additive.

## 6. Model identity mapping

```
Capability        speech_synthesis                 (frozen enum)
Public model      intelliai-tts                    (registry; the promise)
   ↓ routing      registry record → service tts-runtime, artifact kokoro-82m
Artifact          kokoro-82m v1                    (weights + voice assets,
                                                    per-version license verdict)
   ├─ files       model weights + voice asset files (one ArtifactSpec, SHA-256-pinned)
Build             CPU float32                       (precision = build, never identity)
Runtime           tts-runtime                       (capability-named service)
Voice (public)    catalog record → asset → representation
                                                    (the ONE new identity layer,
                                                     beside — not inside — the artifact axis)
```

## 7. Evaluation integration — M2.5 plugs in with zero framework changes

**The three permanent planes (recorded at Step 5 close, 2026-08-03).**
The platform now consists of three planes, and the boundary between them
is architectural law:

- **Inference Plane** — serves customer requests (runtimes, engines,
  artifacts). Optimized for latency, capacity, and honesty under load.
- **Evaluation Plane** — produces evidence about model behavior (corpus,
  runner, judges, metrics, the immutable ledger). Optimized for
  reproducibility and permanence.
- **Control Plane** — decides what should serve customers (registry,
  license gate, catalog, routing; the gateway is its enforcement point).

**Evaluation never participates in inference and never makes deployment
decisions directly.** No inference path invokes evaluation code;
inference code does not know evaluation exists. No evaluation output
mutates routing; the ledger records, it never decides. The causal chain
runs one direction only:

```
Serving creates evidence.
Evidence informs promotion.
Promotion changes registry state.
Registry changes routing.
```

Every future arrival — multiple engines behind one public model,
fine-tuned artifacts climbing the ladder, cloned voices, Registry V2's
promotion workflows — plugs into this chain at exactly one link: new
engines create evidence through the evaluation plane's adapters;
promotion decisions cite that evidence and land as registry record
changes; routing follows the registry. Nothing ever shortcuts a link.

**The permanent asset (recorded at Step 6 close, 2026-08-03).** The
company's permanent asset is not models. It is accumulated knowledge
about models:

- **Models are replaceable.** Every foundation model this platform
  serves will one day be retired — that is the plan, not a risk.
- **Artifacts are replaceable.** A registry row edit, invisible to
  customers; the whole architecture exists to make this cheap.
- **Evaluation evidence is permanent.** The ledger is append-only and
  self-contained; a record outlives the artifact it measured.
- **Promotion history is permanent.** Every "what replaced what, and on
  what evidence" is a fact the company keeps forever.
- **Benchmark history is permanent.** Production measurements are
  company memory: what this hardware could do, proven, dated.
- **Customer-visible baselines are permanent.** "What baseline did it
  beat?" must be answerable for every model the company ever ships.

**Models depreciate. Knowledge compounds.**

This is why Registry V2, the evaluation plane, promotion workflows, and
future research systems exist at all: they are the institutions that
preserve knowledge after individual models disappear. A model's weights
stop mattering the day something beats it; the *evidence that it was
beaten, by how much, on which corpus, judged by whom* is what makes the
next decision faster and safer than the last. Companies that keep only
models start over with every generation; companies that keep knowledge
get faster with every generation. Every plane of this platform is built
to be the second kind.

```
run_speech_eval (frozen)
  ├─ SynthesisSource ← HttpTtsSynthesisSource   NEW: ~30 lines. POSTs the binding,
  │                                              reads WAV body + envelope header
  ├─ Judge           ← HttpSttJudge              EXISTS. whisper-small judges Kokoro
  └─ scoring/schema/baseline                     FROZEN. Day-one output:
                                                 baseline_name = "<date>-kokoro-82m-cpu-v1"
```

The deferred CLI (`speech-eval`) lands with the adapter; Kokoro's first
`SpeechEvalRun` — including the first listening-protocol execution
(founder, n=1, honestly labeled) — is a Step 6 gate. M2.5 conditions carry
into M3 as gates: **C2** (second-judge spot-audit) at the first promotion
decision; **C3** (corpus ≥100 cases) before any switching test.

## 8. License review — fresh adoption verification (2026-08-03, at source)

| Component | License (verified) | Verdict |
|---|---|---|
| Kokoro-82M weights (hexgrad, HF) | Apache-2.0 | ✅ Commercial use, redistribution, derivative training (fine-tuning) permitted with attribution/notice preservation |
| `kokoro` pip package | Apache-2.0 | ✅ |
| `misaki` G2P | Apache-2.0 | ✅ — *native* G2P for English (and ja/ko/zh/vi) |
| espeak-ng | GPL-3.0 | ⚠ English OOD fallback and the G2P path for non-native languages — **including Hindi**. In-process linking of GPL code into a proprietary service is a derivative-work risk; a subprocess exec boundary (the ffmpeg posture) is the defensible shape. |

**Verdicts.**

- **English TTS v1: APPROVED** — condition: espeak-free configuration
  verified (misaki-native English, fallback disabled) and the isolation
  denylist gains the espeak wrappers, proven by test at Steps 3–4.
- **Hindi TTS: GATED, not shipped in v1.** Two compliant paths, decided by
  spike: subprocess-isolated phonemization (espeak-ng *binary* behind an
  exec boundary, GPL-clean the way ffmpeg is) or serving Hindi on the
  IndicF5 lineage (MIT; re-verified at its own adoption). Revisited with
  Step 7 evidence at close.
- Informational: Kokoro's training data includes synthetic audio from
  third-party models — a provenance note for the registry record.

**Principle — commercial cleanliness has higher priority than feature
completeness.** This is why English ships before Hindi: a capability that
cannot yet satisfy IntelliAI's licensing standards ships *late but clean*,
never on time but dirty. The wedge language is a strategy; the license
posture is a constitution.

Sources: [hexgrad/Kokoro-82M (HF)](https://huggingface.co/hexgrad/Kokoro-82M),
[hexgrad/kokoro](https://github.com/hexgrad/kokoro),
[hexgrad/misaki](https://github.com/hexgrad/misaki).

## 9. Implementation roadmap — review-gated steps

**Ordering: extraction precedes the contract.** The `runtime-core`
extraction is a pure refactor whose entire proof is "nothing changed," and
that proof is only airtight against the M2-frozen, production-validated
stt-runtime with no other change in flight. The two steps have no
technical dependency in either direction (the generic ModelManager never
imports contract schemas), so ordering is purely about evidence quality:
refactor-before-feature. Step 1 ends with a bit-identical platform on a
better foundation; Step 2 adds new semantics to a settled base.

| Step | Concept / Trade-off | DoD sketch |
|---|---|---|
| **0 Governance** | Decisions before code: license verdicts + Hindi gate recorded; `tts-kokoro → tts-runtime` rename; founder names the launch voices; ADR-0019/0020; C-gates logged | This document committed; ADRs indexed; rename merged; voice slate decided |
| **1 Extraction** | `packages/runtime-core` (ArtifactStore / WorkerPool / generic ModelManager / `RuntimeServiceError`); stt-runtime refactored **behavior-frozen** | Full stt suite green with zero test-behavior edits; **M2↔M3 ModelManager logic diff is empty**; baseline re-run confirms no drift |
| **2 Contract** | `SPEECH_SYNTHESIS` + schemas + `CHARACTERS`; registry capability-mismatch guard becomes testable — purely additive | Golden tests updated; contract minor-bumped; mismatch test lands |
| **3 Skeleton** | tts-runtime + `ReferenceSynthesisEngine` (deterministic tone-from-text) + binary binding proven end-to-end with no model | Binding e2e tests incl. envelope-header size bound + cross-pin; isolation suite active from day one |
| **4 Kokoro** | Engine module + pinned artifact spec + `kokoro` extra + local real-model tier — EN-only per license gate. **Permanent rule: every new engine must satisfy the engine Protocol before a single model is downloaded** — the ReferenceEngine proved the discipline in M2; every future capability keeps it | Local tier passes; CI stays model-free; espeak absence proven by isolation test |
| **5 Gateway** | `/v1/audio/speech` + `/v1/audio/voices` + translation + `speech.completed{characters}` + `intelliai-tts` catalog row | E2E demo: key → text in → audible WAV out; leak-guard extended to voices |
| **6 Evaluation** | `HttpTtsSynthesisSource` + `speech-eval` CLI + day-one baseline + first listening run | Baseline committed with `baseline_name`; listening scores in the ledger |
| **7 Production validation** | Compose service + bench ladder (TTFB, RTF, memory, concurrency) vs PRD TTFB < 1 s; streaming go/no-go evidence | Benchmark doc published beside the STT baseline |
| **8 Close** | ADR review-criteria ledger, PRD v0.7, milestone review, version 0.4.0; Hindi checkpoint revisited with Step 7 evidence | Review doc; founder homework status re-asserted |

## 10. Non-goals of Milestone 3

Each is anticipated by the architecture (nothing in M3 forecloses it) but
deliberately not built. A request for any of these during M3 is a scope
change and goes through review, not through the sprint.

- **Voice cloning** — the §5 stack reserves its slots (org-owned assets,
  consent fields, `speaker_similarity`); awaits the cloning-capable
  lineage and the consent framework.
- **Emotion control** — no `emotion` parameter; expressiveness arrives as
  new voices or an additive style parameter backed by an engine that can
  honor it.
- **SSML** — the pipeline's normalize seam is where markup interpretation
  would live; v1 accepts plain text only.
- **Streaming synthesis** — M8, platform-wide, unless Step 7 measurement
  shows the unstreamed path missing the PRD TTFB target.
- **Speech-to-speech** — a future capability enum member with its own
  pipeline; not a TTS feature.
- **Voice personalization** (per-customer tuning of stock voices) —
  cloning-adjacent, gated behind the same governance.
- **Multilingual automatic switching** — v1 uses the explicit `language`
  hint; code-switching within one voice's ability is measured by the
  corpus, not engineered around.
- **Dialogue synthesis** (multi-speaker conversation rendering) — an
  orchestration product atop TTS, not a runtime concern.
- **Voice marketplace** (third-party or customer-published voices offered
  to other customers) — a marketplace is a governance, licensing, and
  revenue-sharing product; intentionally outside M3 scope.

## 11. Registered platform work (from M3 evidence)

- **Pronunciation Manager** (platform component, NOT an engine fix) —
  registered from the founder-discovered limitation: the espeak-free
  English G2P is dictionary-only, so out-of-vocabulary words (brand
  names, proper nouns — including "IntelliAI" itself) are silently
  dropped. Pronunciation is a product promise that must survive engine
  swaps, so the platform owns a versioned lexicon (word → canonical
  pronunciation) and each engine adapter renders it into its own phoneme
  scheme — the voice-identity split, applied to words. Lives at the
  pipeline's reserved normalize/G2P seam; measured by the corpus's
  proper-noun and technical trap categories; later extends to
  customer-supplied lexicons (a product feature) and STT vocabulary
  biasing.
- **Chunk merging** (tts-runtime) — short multi-sentence utterances pay
  one model pass per sentence (~500 ms fixed cost each); merging chunks
  under the phoneme limit puts every short utterance under the PRD TTFB
  target (measured at Step 7).
- **Streaming synthesis: GO** — Step 7's measurement (unstreamed TTFB
  2237 ms for the pinned 122-char sentence vs the 1 s target) is the
  go/no-go evidence this review deferred; streaming enters M8 with
  measured justification.
- **Hindi TTS checkpoint** — decision open per §8: subprocess-isolated
  phonemization spike vs the IndicF5 (MIT) lineage; now governed by the
  Language Policy above, which also adds **Arabic** to the engine-research
  pipeline (no current engine candidate).
