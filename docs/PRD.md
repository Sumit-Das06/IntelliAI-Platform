# IntelliAI Platform — Product Requirements Document

| | |
|---|---|
| **Status** | Living document — single source of truth for product decisions |
| **Version** | 0.3 (Milestone 0.5 closed) |
| **Last updated** | 2026-07-30 |
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
3. **CPU-efficient economics** — CPU-first serving of efficient models (faster-whisper
   int8, Piper, Kokoro) permits an unusually generous free tier and low floor prices.
4. **Regional depth as a later wedge** — Sarvam validates Indic-language demand;
   our fine-tuning phase (Phase 2) can target underserved languages/accents with
   benchmarked, published WER.

## 6. Feature Roadmap

Phase 1 (approved, in progress) — versions map to milestones M0–M12:

| Version | Capability |
|---|---|
| v0.1 | Foundations: infra, gateway skeleton — ✅ **shipped 2026-07-29** ([review](milestones/0-foundations-review.md)) |
| v0.15 | Engineering standards, CI — ✅ **shipped 2026-07-30** ([review](milestones/0.5-engineering-standards-review.md)) |
| v0.2 | Auth: orgs, users, API keys *(next)* |
| v0.3 | **STT API** (`/v1/audio/transcriptions`, faster-whisper) |
| v0.4 | **TTS API** (`/v1/audio/speech`, Piper; voices catalog) |
| v0.5 | Usage metering & rate limiting |
| v0.6 | Async batch jobs + webhooks |
| v0.7 | Developer console (signup → key → usage) |
| v0.8 | Playground |
| v0.85 | Streaming STT (WebSocket) |
| v0.9 | Model registry v2, evaluation harness, benchmark reports |
| v0.95 | Observability, load testing, security hardening |
| v1.0 | Docs site, Python SDK, deployment guide, launch |

Phase 2 (directional): dataset pipeline, fine-tuning (Whisper LoRA), custom-model
serving, TTS premium tier (Kokoro), voice cloning (license-clean), diarization,
speech translation, additional providers behind the speech router.

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

Phase 1 targets (CPU-serving; honest, revisited with benchmarks in v0.9):

| Metric | Target |
|---|---|
| Gateway overhead (auth+route+meter), p95 | < 15 ms |
| Sync STT (≤60 s audio, `small` int8), p95 | < 1.5× audio duration |
| Batch STT throughput | ≥ real-time per worker core-set; horizontal scale-out |
| TTS time-to-first-byte (Piper, short text), p95 | < 1 s |
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
- *2026-07-30 — v0.3: Milestone 0.5 closed — engineering standards enforced by
  tooling (ruff/mypy/pre-commit), CI on clean machines, platform error contract
  (nine types, one envelope), ADRs 0002–0010, six engineering handbooks.
  No product-scope changes; M1 (auth) scope note: recommendation is API-key
  auth only, console login deferred.*
- *2026-07-29 — v0.2: Milestone 0 closed — full stack boots with one command
  (api container + Postgres + Redis + MinIO); health, logging, config,
  persistence foundations shipped as specified. No product-scope changes.*
- *2026-07-29 — v0.1: initial PRD (Milestone 0).*
