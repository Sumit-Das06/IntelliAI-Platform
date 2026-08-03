# Milestone 2 Review — STT Service & Runtime Contract (v0.3)

**Closed:** 2026-08-03 · **Opened:** 2026-08-02 · 9 steps (0–8), each
review-gated. This document is knowledge capture: what M2 *proved*, what
it deliberately did not, and what implementation taught that planning
could not.

**What shipped:** the platform's first production-capable AI API. A
customer with an API key can `POST /v1/audio/transcriptions` (OpenAI
shapes: json/text/verbose_json) and `GET /v1/models`, served end-to-end
by: gateway auth → registry resolution → transport-agnostic RuntimeClient
→ containerized stt-runtime (media pipeline → VAD → worker pool →
hash-verified whisper-small) → gateway translation → public envelope +
`transcription.completed` accounting event. 270 tests; every layer's
boundary machine-enforced.

Companion records: [ADR-0016](../adr/0016-runtime-contract-language.md)
(contract) · [ADR-0017](../adr/0017-registry-v1-code-declarative-resolution.md)
(registry v1) · [ADR-0018](../adr/0018-runtime-serving-architecture.md)
(runtime architecture) · [performance baseline](../../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md)
· [quality baseline](../../ml/evaluation/stt/results/2026-08-02-whisper-small.json).

---

## 1. Architectural Assumptions Validated

Every load-bearing assumption the strategy layer and ADRs made, with the
evidence that converted it from belief to fact:

| Assumption | Source | Evidence |
|---|---|---|
| Gateway isolation of inference costs a negligible fraction of inference | ADR-0002 | Measured: +14.7 ms = **0.86 %** of inference p50; PRD's <15 ms gateway-overhead target met on the first measurement |
| CPU-first serving is commercially viable for STT | ADR-0015 | RTF 0.155 uncontended (6.5× faster than real time); ~6.3× real-time aggregate throughput on one 9-core allocation; PRD p95 target passed with ~9× headroom |
| Engines are swappable without touching the platform | ADR-0003/0016 | ReferenceEngine → FasterWhisperEngine took one engine module + one config line; contract, pipeline, registry, gateway diffs: zero lines |
| The public surface can fully hide implementation | MODEL_IDENTITY | Customer surface contains only `intelliai-stt` and public envelopes; a leak-guard test forbids engine/artifact/license terms in catalog responses |
| Startup warm-up eliminates cold-request tax | M2 step 3 refinement | First request after startup: 1416 ms vs steady p50 1749 ms — no tax (measured at idle, hence slightly faster) |
| Bounded admission beats queuing under overload | M2 step 3 design | At 2× capacity: pool capped at exactly 10, 35 requests refused fast, accepted-p95 bounded (16.9 s vs 16.5 s at capacity) |
| Threads share one model safely; the GIL is not the bottleneck | step 5 debt | Memory flat ~800 MiB from c=1 to c=20; ~9 cores saturated — CTranslate2 releases the GIL. **Debt retired.** |
| VAD in the pipeline structurally prevents silence hallucination | step 4 design | Silence probe: RTF 0.000 (engine never ran), 0 hallucinated words; tone probe reached the engine, which correctly emitted nothing |
| Hash-verified weights, never trusted | Constitution/ADR-0005 | model.bin pin verified against Hugging Face's own LFS metadata; cache re-hashed every boot (0.26 s for 483 MB); tamper test proves delete+refuse |
| Whisper-small quality is a shippable floor | FOUNDATION_MODELS | WER 0.000 on the seed set's exact-reference clips, both container paths, zero hallucinated words |

## 2. Assumptions Still Unvalidated (deferred by design)

- **Streaming transcription (M8):** the contract's one-shot envelope and
  the pipeline/pool shape have never carried incremental results; ADR-0016
  and ADR-0018 both carry this as their first review criterion.
- **Second capability, second runtime (M3):** ADR-0018's claim that the
  runtime shape is a template has n=1 evidence; Kokoro TTS is the test.
  Also unlocks the enum-mismatch registry test (unconstructible with one
  Capability member).
- **Backup lineage swap (Qwen3-ASR):** engine swappability is proven for
  Reference→Whisper; a *cross-family* swap with different tokenization and
  language behavior is not yet exercised.
- **Registry V2** (lifecycle, lineage, DB-backed resolution, M9): V1
  deliberately implements none of it; the growth path is designed
  (ADR-0017) but unproven.
- **Multi-runtime routing:** one service, one client, no fleet concerns
  (weighted routing, failover between runtimes, canary artifacts).
- **Fine-tuned IntelliAI models:** the switching test exists on paper and
  the baseline it needs is now real, but no tuned artifact has ever run
  the ladder.
- **Hindi/Indic quality (the wedge):** the seed set is English + probes;
  wedge-aligned measurement starts with dataset v2 (founder recordings).
- **Gateway retry policy:** deliberately absent; needs production failure
  data, not simulation.
- **Real customer demand:** everything product-facing remains
  hypothesis-grade until customer discovery produces evidence (PRD
  operating principle, running behind schedule — see §6).

## 3. What Changed Our Mind

Lessons implementation taught that planning did not predict:

1. **Workspace venvs mask missing dependencies; containers are the honest
   test.** The gateway ran 270 tests green while missing a declared
   dependency (`python-multipart`) — the shared `.venv` supplied it via a
   sibling package. The isolated container failed in seconds. Rule
   adopted: containerization is part of validating a service, not a
   deployment afterthought (it also caught the api image's missing
   workspace-package COPY).
2. **VAD-as-a-model belongs behind a seam, not in a milestone plan.** The
   plan said "Silero VAD in step 4"; implementation revealed Silero is
   *weights + onnxruntime* — exactly what ModelManager governs, and a
   violation of our own isolation rule if imported by the pipeline. The
   deterministic energy detector behind a `VoiceActivityDetector` Protocol
   shipped instead; model-based VAD slots in later with zero
   restructuring. Plans name technologies; architecture must name seams.
3. **The tolerant-reader/strict-reader split is load-bearing.** Wire
   contracts want `extra="ignore"` (rolling upgrades; smuggled fields
   become useless), while in-repo catalogs want `extra="forbid"` (a typo
   must fail the build). Early drafts treated "pydantic strictness" as one
   policy; it is two, chosen by trust boundary.
4. **Precision is a build, and it matters in practice.** Keeping `int8`
   out of artifact identity (ADR-0015's bright line) looked academic until
   step 5: the same float32 artifact serves int8 today and could serve
   float16-on-GPU tomorrow with a config change and no registry churn.
5. **A gitignore pattern is code.** `models/` (for weight caches)
   silently swallowed the new `api/v1/models/` router package — main was
   briefly missing shipped code. Patterns now root-anchored; commit file
   lists get read.
6. **Measure the measurer.** The benchmark's hand-rolled percentile had a
   truncation bug caught by its own unit test before any number was
   published. Rulers need tests too.
7. **Native Windows held all milestone** (amended dev-env rule's first
   real test): ffmpeg installed natively (winget, 8.1.2) and worked; the
   only incidents were PATH refresh in new shells and one PowerShell
   text-pipeline corruption (lesson: file edits via proper tooling only).

## 4. ADR review criteria satisfied by M2 evidence

Recorded here per supersede-don't-edit (the ADRs themselves stay
untouched; this section is the evidence ledger):

- **ADR-0002** ("revisit if gateway hop cost proves significant"):
  measured 0.86 % of inference — criterion *retired by evidence*; the
  separation stands without caveat.
- **ADR-0015** ("CPU remains the default while measurements support it"):
  first measurement supports it (6.3× real-time throughput, PRD PASS).
  Standing criterion, now with a baseline to re-test against.
- **ADR-0003** ("streaming is the first stress test"): still open — M8.
- **ADR-0017** ("if V2 forces caller-visible changes, V1 leaked"): not
  yet testable; falls due at M9.

## 5. Technical debt — retired and carried

**Retired during M2:**
- Dependabot enablement (3 milestones old) — step 0, plus the CI
  token-permissions fix it exposed.
- Eval package's local `Capability` literal — step 1 (one-step debt, paid
  in one step as promised).
- Threads-vs-processes validation — step 7 measurements (see §1).
- Binding-constants single-source question — resolved structurally: each
  side owns its constants, a CI cross-pin test enforces equality.
- Dev-environment rule honesty gap — rule amended at step 0 and validated
  by the ffmpeg incident.

**Carried forward (owned, not forgotten):**
- Model-based VAD behind the existing Protocol (with ModelManager-owned
  weights) — when Indic/noisy-audio evidence demands it.
- Dataset v2 awaiting founder recordings (protocol published in
  [ml/evaluation/README.md](../../ml/evaluation/README.md)).
- Gateway retry policy — deliberately deferred to production evidence.
- `services/tts-kokoro` violates capability-naming — rename to
  `tts-runtime` at M3 open (decision queued).
- Local manifest source (`path`) for private eval clips — with dataset v2.
- Runtime contract package: TTS schemas (speech synthesis request/result,
  `characters` usage unit) — M3's first step.

## 6. Milestone 3 readiness assessment (honest)

**Technical readiness — READY.** Everything M3 (TTS, Kokoro) needs
already exists as reusable machinery: the contract package (add
`SPEECH_SYNTHESIS` enum member + schemas — additive), registry v1 (one
catalog record: Kokoro-82M, Apache-2.0, verdict pending re-verification at
adoption per §14 protocol), ArtifactStore/ModelManager/pool (unchanged),
the runtime template (ADR-0018), RuntimeClient + translation layer
(gateway), the eval package (needs a TTS metric decision — MOS-proxy is
NOT seeded yet, the one genuinely new evaluation problem), CI/compose
patterns. The M2 design's binary-out + `X-Runtime-Envelope` header binding
for TTS is designed but unimplemented.

**Architectural readiness — READY, with two open decisions for the
founder at M3 open:**
1. Ratify `intelliai-stt` as the permanent public model id (PRD v0.6
   records it as shipped; renaming later is a client-visible break).
2. Approve the `tts-kokoro → tts-runtime` rename (Constitution P1/P2
   consistency).

**Remaining risks:**
- *Kokoro licensing/practicality:* Apache-2.0 verdict is from 2026-07-31
  research; per-artifact-version re-verification at adoption is mandatory
  (Registry law), and Kokoro's phonemizer dependency chain (espeak-ng
  lineage, GPL adjacency) needs the same isolation scrutiny ffmpeg got.
- *TTS evaluation is genuinely harder than STT:* no WER equivalent;
  MOS-proxy methodology must be chosen *before* the first model download
  (same discipline as M2 step 0) or the eval-seed principle breaks.
- *Two runtimes on one dev machine:* memory (~800 MB each) is fine;
  compose topology and port/naming conventions must not be improvised.
- *Schedule risk is people, not code:* M2 ran 9 gated steps in ~2 days;
  the founder-owned parallel threads (below) are the milestone's actual
  critical path.

**Founder responsibilities (blocking or aging):**
1. **Dataset v2 recordings** — 5 EN + 5 HI scripted passages per the
   published protocol. Blocks the first wedge-aligned quality
   measurement; every week unrecorded is a week the wedge stays
   unmeasured.
2. **Customer discovery** — adopted as an operating principle at M1.5,
   zero conversations logged through M2. The suggested instrument (a
   ten-developer conversation script) remains undone; M3 should not close
   without the first logged conversations, or the principle is decoration.
3. **Merge/close the parked Dependabot PRs** (#3/#4 merge-ready, #5/#6
   close-recommended, #1/#2 deliberate migrations).
4. **Rotate any dev keys** per standing hygiene (all step-demo keys were
   revoked in-session; the older "Sumit AI Labs" chat-exposed key remains
   the founder's homework from M1).

## 7. Dev-environment incidents (per the amended rule)

| Incident | Outcome |
|---|---|
| ffmpeg absent on dev machine (step 4) | Installed natively (winget Gyan.FFmpeg 8.1.2); native Windows held; no WSL2 fallback needed; new shells need a PATH refresh |
| PowerShell text-pipeline corrupted ci.yml UTF-8 (step 0) | Restored from git; rule: file edits only via proper editor tooling, never shell text round-trips |
| Postgres container down mid-development (twice) | Test suite's infra-skip behaved as designed; two runtime-client tests showed order-sensitivity only in the degraded env — clean everywhere else; watching |

## 8. Verdict

Milestone 2 is **closed**. The platform went from "no AI" to a measured,
containerized, customer-facing transcription API in nine gated steps,
with every major architectural bet converted to evidence and the
evaluation ruler in place before the first model was downloaded. v0.3.0.
