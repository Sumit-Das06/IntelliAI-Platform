# IntelliAI Platform — Product Requirements Document

| | |
|---|---|
| **Status** | Living document — single source of truth for product decisions |
| **Version** | 0.8 (Milestone 4 closed) |
| **Last updated** | 2026-08-04 |
| **Update policy** | Reviewed and updated at the close of every milestone, in the same PR that closes the milestone. Material product decisions made between milestones are added when made. |

---

## 1. Product Vision

IntelliAI is a developer-first AI platform: one account, one API key, one coherent
API surface for production AI capabilities — beginning with Speech AI
(speech-to-text, text-to-speech) and expanding to LLMs, translation, vision, OCR,
embeddings, RAG, and agents.

Developers should be able to go from signup to a working API call in under five
minutes, and from prototype to production without changing platforms.

## 2. Mission

Make production-grade AI infrastructure boringly easy to consume: stable
OpenAI-compatible contracts, transparent usage-based pricing, honest documentation,
and model choice (IntelliAI's own models and external providers) behind one
unchanging API.

## 3. Target Users

| Segment | Need | Priority |
|---|---|---|
| Indie developers & early-stage startups | Cheap, fast integration of speech features; generous free tier | P0 (Phase 1 wedge) |
| Product engineering teams (SMB) | Reliable transcription/synthesis at predictable cost, without running GPU infra | P0 |
| ML engineers | Model comparison, evaluation data, fine-tuning on own data | P1 (Phase 2) |
| Enterprises | Compliance, SLAs, data residency, private deployment | P2 (post-1.0) |

## 4. User Personas

**"Priya" — indie full-stack developer.** Building a voice-notes app solo. Wants a
copy-paste quickstart, an SDK that feels like OpenAI's, and a free tier that doesn't
demand a credit card. Churns instantly on confusing docs or surprise bills.

**"Rahul" — backend engineer at a 40-person SaaS.** Integrating call transcription
into a CRM product. Cares about p95 latency, webhook reliability for batch jobs,
rate-limit clarity, and a status page. Evaluates three vendors in a spreadsheet;
switching cost and API stability decide the winner.

**"Ananya" — ML engineer at a data team.** Needs to benchmark STT accuracy on her
company's domain audio, then fine-tune. Cares about WER on *her* data, not marketing
numbers; wants an evaluation harness and eventually custom models served behind the
same API.

**"The buyer" (post-1.0) — engineering director.** Cares about SOC 2, DPAs, uptime
history, and vendor viability. Not a Phase 1 target; nothing in Phase 1 may
*foreclose* serving them (hence multi-tenancy, audit trails, metering from day one).

## 5. Competitive Analysis

Indicative published pricing, mid-2026 — re-verify before any pricing decision:

| Platform | Strengths | Weaknesses / gaps | Indicative pricing (STT) |
|---|---|---|---|
| **OpenAI** | Default choice; ecosystem gravity; API conventions are the industry standard | Speech is a side business; no diarization/streaming STT focus; no fine-tuning for audio | Whisper API ~$0.006/min |
| **Deepgram** | Speech specialist; excellent streaming latency; strong enterprise motion | Speech-only ceiling; less approachable free tier | Nova-3 ~$0.0043/min batch, ~$0.0077/min streaming |
| **AssemblyAI** | Best-in-class developer experience & docs; audio-intelligence add-ons | Speech-only; US-centric | Universal-2 ~$0.0025/min (~$0.37/hr) |
| **ElevenLabs** | TTS/voice quality leader; brand gravity in voice; diarization bundled in STT | Premium pricing; consumer-leaning; API surface churn | Scribe ~$0.004/min; TTS premium-priced per character |
| **Sarvam AI** | Indic-language depth (22+ languages, code-mixed, 8 kHz telephony); sovereign-AI positioning; aggressive pricing (STT ₹30/hr, chat LLMs free) | Niche wedge by design; smaller ecosystem | STT ₹30/hr (~$0.006/min) |

**Positioning hypotheses (to validate, not facts):**

1. **Multi-domain coherence** — speech specialists stop at speech; generalists treat
   speech as a checkbox. One platform where speech, LLM, and document AI share keys,
   metering, and conventions is a real gap for product teams.
2. **Model-agnostic routing** — customers want "best model for this job", not "the
   only model this vendor sells." Our provider-agnostic architecture makes model
   choice a feature.
3. **CPU-efficient economics** — CPU-first deployment of efficient models
   (faster-whisper int8, Kokoro) permits an unusually generous free tier and low
   floor prices (hardware-agnostic architecture per [ADR-0015](adr/0015-hardware-agnostic-architecture-cpu-first-deployment.md)).
4. **Regional depth as a later wedge** — Sarvam validates Indic-language demand;
   our fine-tuning phase (Phase 2) can target underserved languages/accents with
   benchmarked, published WER.

## 6. Feature Roadmap

Phase 1 (approved, in progress) — versions map to milestones M0–M12:

| Version | Capability |
|---|---|
| v0.1 | Foundations: infra, gateway skeleton — ✅ **shipped 2026-07-29** ([review](milestones/0-foundations-review.md)) |
| v0.15 | Engineering standards, CI — ✅ **shipped 2026-07-30** ([review](milestones/0.5-engineering-standards-review.md)) |
| v0.2 | Auth: orgs, users, API keys — ✅ **shipped 2026-07-31** ([review](milestones/1-identity-review.md)) |
| v0.25 | Foundation model evaluation & AI strategy (research/architecture only) — ✅ **shipped 2026-07-31** ([review](milestones/1.5-strategy-review.md); [index](STRATEGY.md)) |
| v0.3 | **STT API** (`/v1/audio/transcriptions` + `/v1/models`, public model **`intelliai-stt`**) — ✅ **shipped 2026-08-03** ([review](milestones/2-stt-review.md); [performance baseline](../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md); [quality baseline](../ml/evaluation/stt/results/2026-08-02-whisper-small.json)) |
| v0.4 | **TTS API** (`/v1/audio/speech` + `/v1/audio/voices`, public model **`intelliai-tts`**) — ✅ **shipped 2026-08-03** ([review](milestones/3-tts-review.md); [design](milestones/3-tts-design.md); [performance baseline](../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md); [quality baseline](../ml/evaluation/tts/results/2026-08-03-kokoro-82m.json)) |
| v0.5 | **Usage metering & rate limiting** (append-only usage ledger, admission control, quotas & spend limits, versioned pricing) — ✅ **shipped 2026-08-04** ([review](milestones/4-metering-review.md); [design](milestones/4-metering-design.md); [commercial baseline](benchmarks/2026-08-04-commercial-plane-baseline.md)) |
| v0.6 | Multilingual foundation (M5) — Hindi and Arabic engine adoption under the Core Speech Language Policy |
| v0.65 | Async batch jobs + webhooks |
| v0.7 | Developer console (signup → key → usage) |
| v0.8 | Playground |
| v0.85 | Streaming STT (WebSocket) |
| v0.9 | Model registry v2, evaluation harness, benchmark reports |
| v0.95 | Observability, load testing, security hardening |
| v1.0 | Docs site, Python SDK, deployment guide, launch |

**v0.5 release scope and known limitations (honest product statement).**
The platform can now *charge for what it serves*: every request is
metered into an append-only ledger, admitted against plan-derived rate,
concurrency, quota and spend limits, and priced by a versioned book with
reproducible rating. A **free tier ships from day one** so enforcement is
exercised rather than dormant.

What v0.5 deliberately does **not** include: invoices, payments, credits,
plan self-service, tax, and per-customer negotiated pricing. **Prices are
internal only** — the machinery exists so cost-to-serve and spend
ceilings are computable while customer evidence is gathered; nothing is
published. Rate-limit values are set generously: v0.5 validates the
mechanism, not the numbers.

Two known gaps, stated rather than implied:

- **Language analytics are complete for STT and blank for TTS.** The
  public synthesis API has no `language` parameter (v0.5 preserved all
  public APIs unchanged), so synthesis usage records no language. The
  Core Speech Language Policy is therefore currently tracked on half the
  evidence. Whether a customer states a language or it is inferred from
  the chosen voice is an M5 product decision.
- **A charge is explainable but not yet self-contained.** Every rated
  line carries its quantity, unit price, price book version and rating
  algorithm version, but that explanation is recomputed rather than
  stored. The invoice document closes it (post-v1.0) — see the
  Historical Explainability Invariant in the
  [design review §8.7](milestones/4-metering-design.md).

**v0.4 release scope and known limitations (honest product statement):**
English only, two launch voices under placeholder identities
(`reference-alto`, `reference-bass`) pending the founder naming decision;
WAV output; sub-second response for single-sentence utterances (longer
text scales with audio length until streaming — see §10); out-of-vocabulary
words (brand names, rare proper nouns) are currently dropped by the
license-clean pronunciation path — registered as platform work
(**Pronunciation Manager**: a versioned platform-owned lexicon rendered
per-engine, later extensible to customer lexicons and STT vocabulary
biasing; [design review §11](milestones/3-tts-design.md)).

**Core Speech Language Policy (v1, adopted 2026-08-03).** IntelliAI's
speech platform has three first-class languages: **English, Hindi,
Arabic**. This is a product requirement, not an engine requirement: the
customer-facing APIs must come to provide complete support for all three
across speech capabilities, and every engine-adoption, evaluation,
benchmarking, fine-tuning, voice, translation, and speech-to-speech
decision optimizes toward that target. Where no single engine meets
IntelliAI's licensing and quality standards for all three (none does
today), different engines serve different languages internally behind the
one stable customer API. Support is *complete* only when measured: a
corpus, a quality baseline, and a production benchmark per language.

Phase 2 (directional): dataset pipeline, fine-tuning (Whisper-lineage adapters),
custom-model serving, TTS voice cloning on the Chatterbox lineage
(consent-gated, watermark-policied), diarization, speech translation
(composite-backed), additional providers behind the speech router. Model
lineage choices: [FOUNDATION_MODELS.md](FOUNDATION_MODELS.md).

**Operating principles adopted at Milestone 1.5** (apply to all future
milestones):

- **Evaluation seed from M2:** every capability ships with a fixed
  evaluation set and a measured baseline from its first release; the full
  harness (v0.9) formalizes what the habit already practices.
- **Customer discovery is a parallel company activity:** structured
  developer conversations and demand instruments run alongside every
  milestone, not after launch; product claims graduate from
  hypothesis-grade only through them.
- **Documentation governor:** every strategy document must name the
  milestone that consumes it, and no two consecutive milestones may both
  be documentation-only.

Phase 3 (directional): LLM APIs (chat, embeddings), document AI/OCR, translation,
billing/payments, enterprise features (SSO, audit exports, SLAs).

## 7. Non-functional Requirements

- **API stability:** `/v1` contracts are append-only once shipped in a stable
  release; breaking changes require a new version path, deprecation windows ≥6 months.
- **Multi-tenancy:** every request, record, and metric is organization-scoped from
  the first schema ([ADR-0010](adr/0010-organizations-first-tenancy.md)).
- **Auditability:** usage events are immutable, append-only; money-relevant data is
  never mutated in place.
- **Portability:** runs on any Docker host; no cloud-vendor-proprietary service in
  the core path (S3 API and Postgres protocol are the only assumed interfaces).
- **Reproducibility:** pinned images, lockfiles, migrations-first schema; a fresh
  clone boots with two commands.
- **Model swappability:** replacing the model behind an endpoint requires zero
  client-visible change (registry + runtime contract).

## 8. API Philosophy

1. **OpenAI-compatible where compatibility is free** (`/v1/audio/transcriptions`,
   `/v1/audio/speech`, `/v1/models`, bearer keys, their error-envelope shape) —
   drop-in migration is our cheapest acquisition channel.
2. **Better where compatibility costs nothing** — additive fields (e.g. per-model
   language lists, job webhooks, richer voice metadata) never break the base shape.
3. **Boring and predictable** — plural-noun resources, Stripe-style prefixed IDs
   (`org_…`, `key_…`, `job_…`), cursor pagination, idempotency keys on mutating
   endpoints, explicit deprecation headers.
4. **The contract is the product** — models, providers, and infrastructure may
   change freely behind it; the contract may not.

## 9. Security Goals

- API keys: shown once, stored hashed (SHA-256+pepper or better), prefix-identifiable
  (`ik_live_…`/`ik_test_…`), revocable instantly, org-scoped.
- Tenant isolation enforced at the query layer (no cross-org data path), verified by
  tests.
- Secrets never in git, images, or logs; structured logs redact key material by
  construction.
- Least-privilege everywhere: non-root containers, scoped DB roles, localhost-bound
  dev ports.
- Supply chain: pinned base images, lockfiles, dependency/secret scanning in CI (M0.5).
- Customer audio/text is customer data: configurable retention, deleted on request;
  external-provider routing (when added) is opt-in and disclosed per model.
- Post-1.0 roadmap: SOC 2 readiness, SSO, audit log export.

## 10. Performance Goals

Phase 1 targets (CPU-serving; honest, revisited with benchmarks in v0.9).
First measured evidence: the v0.3 [production baseline](../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md).

| Metric | Target |
|---|---|
| Gateway overhead (auth+route+meter), p95 | < 15 ms — *measured v0.3: +14.7 ms, 0.86 % of inference (ADR-0002 validated)* |
| Sync STT (≤60 s audio, `small` int8), p95 | < 1.5× audio duration — *measured v0.3: PASS, ~9× headroom uncontended* |
| Batch STT throughput | ≥ real-time per worker core-set; horizontal scale-out |
| TTS time-to-first-byte (short text), p95 | < 1 s — *measured v0.4: PASS for single-sentence utterances (814 ms via gateway); FAIL for longer text (2237 ms @ 122 chars — TTFB scales with audio length unstreamed). Scope until streaming: the target holds for single-sentence inputs; [streaming verdict: GO for v0.85/M8](../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md), chunk-merging is the nearer runtime lever* |
| Streaming STT partial-result latency (v0.85) | < 800 ms |
| Availability (v1.0 launch target) | 99.9% monthly |

Every fine-tuned or newly-adopted model must beat (or consciously trade against) the
incumbent on the v0.9 benchmark harness before serving traffic: STT = WER/CER/RTF/
latency/throughput; TTS = MOS-proxy/latency/generation-speed/memory.

## 11. Scalability Goals

- **Stateless data plane:** gateway and inference services scale horizontally;
  state lives only in Postgres/Redis/object storage.
- **Independent scaling:** each inference service scales (and fails) independently
  of the control plane and of each other.
- **Queue-backed batch:** async jobs absorb spikes; workers scale by queue depth
  (Postgres `SKIP LOCKED` now; graduation criteria to a dedicated queue recorded in
  [ADR-0006](adr/0006-jobs-in-postgres-skip-locked.md)).
- **GPU adoption = deployment config** ([ADR-0004](adr/0004-cpu-first-gpu-ready.md)):
  scaling up quality/throughput never requires code changes.
- Designed-for ceilings (Phase 1): ~100 req/s sustained on the sync path, thousands
  of queued batch jobs — beyond that, the Kubernetes chapter opens (post-1.0).

## 12. Future Vision

By v1.0, IntelliAI is a credible, self-servable speech platform: sign up, get a key,
transcribe and synthesize in five minutes, watch usage live, read docs that don't
lie, at prices a solo developer can afford.

Beyond 1.0: the platform absorbs new AI domains behind the same account/key/
metering spine (LLM, documents, translation); Phase 2 fine-tuning turns evaluation
data into differentiated models — including underserved languages where published,
benchmarked accuracy is the marketing; billing turns usage into revenue; and the
model registry grows from an internal routing table into a public, honest model
catalog with per-model benchmarks, licenses, and lifecycle status — the platform's
public proof that it treats model choice as a feature, not a lock-in.

---

*Change log:*
- *2026-08-03 — v0.7: Milestone 3 closed — TTS shipped as a product:
  `/v1/audio/speech` + `/v1/audio/voices` live behind API keys; public
  model **`intelliai-tts`** ratified (kokoro-82m artifact serves it,
  Apache-2.0 verified, identity hidden; English-only per the license
  verdict — Hindi gated on a GPL-clean phonemization path). Platform
  hardening shipped en route: `packages/runtime-core` (shared runtime
  lifecycle, extracted behavior-frozen), speech-synthesis contract
  additions (CONTRACT_VERSION still 1), binary audio binding
  (ADR-0020), GPL-free deployment image (espeak chain absent by
  construction, build-verified), evaluation wired end-to-end
  (`speech-eval` CLI; day-one baseline + live reproduction committed).
  **Core Speech Language Policy v1 adopted (EN/HI/AR first-class,
  product-level)**; capabilities-permanent principle recorded; TTFB
  target honestly scoped (single-sentence PASS; streaming = GO for
  v0.85/M8); Pronunciation Manager registered from the
  founder-discovered OOV limitation. Voice identities remain
  placeholders pending the founder listening decision.*
- *2026-08-03 — v0.6: Milestone 2 closed — first production-capable AI API:
  `/v1/audio/transcriptions` (OpenAI-compatible, json/text/verbose_json) and
  `/v1/models` product catalog live behind API keys; public model id
  **`intelliai-stt`** ratified (whisper-small artifact serves it; identity
  hidden by design); runtime contract v1 + registry v1 + stt-runtime
  service shipped (ADRs 0016–0018); measured baselines published (WER
  0.000/zero hallucination on seed set; gateway overhead 0.86 % of
  inference; PRD p95 target PASS ~9× headroom; ~800 MiB flat runtime
  memory). Founder-owed items carried: dataset v2 recordings, customer
  discovery kickoff ([review §6](milestones/2-stt-review.md)).*
- *2026-07-31 — v0.5: Milestone 1.5 closed — AI strategy layer adopted
  ([STRATEGY.md](STRATEGY.md) + [CONSTITUTION.md](CONSTITUTION.md));
  TTS engine decision changed Piper → Kokoro (Piper archived upstream,
  GPL fork; see FOUNDATION_MODELS.md); hardware framing superseded by
  ADR-0015 (hardware-agnostic architecture, CPU-first deployment);
  operating principles added (evaluation seed from M2, parallel customer
  discovery, documentation governor). Roadmap scope otherwise unchanged.*
- *2026-07-31 — v0.4: Milestone 1 closed — organizations/users/memberships/API
  keys live; HMAC-peppered shown-once credentials; AuthContext pipeline;
  key management API with tenant-isolation guarantees (ADRs 0012-0014).
  No product-scope changes.*
- *2026-07-30 — v0.3: Milestone 0.5 closed — engineering standards enforced by
  tooling (ruff/mypy/pre-commit), CI on clean machines, platform error contract
  (nine types, one envelope), ADRs 0002–0010, six engineering handbooks.
  No product-scope changes; M1 (auth) scope note: recommendation is API-key
  auth only, console login deferred.*
- *2026-07-29 — v0.2: Milestone 0 closed — full stack boots with one command
  (api container + Postgres + Redis + MinIO); health, logging, config,
  persistence foundations shipped as specified. No product-scope changes.*
- *2026-07-29 — v0.1: initial PRD (Milestone 0).*
