# IntelliAI STT Benchmark Campaign — Master Plan

| | |
|---|---|
| **Status** | PROPOSED (Gate 4 campaign planning, 2026-08-05) — IN FORCE only on founder approval |
| **Campaign id** | `CAMP-STT-2026A` (permanent once issued) |
| **Version** | 0.1 |
| **Role** | The master execution plan for IntelliAI's first speech-to-text benchmark campaign. Instantiates the Gate 3 methodology as a concrete, ordered, resourced sequence of sessions. |
| **Gate discipline** | **This document plans. It executes nothing.** No candidate is benchmarked, scored, ranked, compared, preferred, or recommended — not by statement, not by ordering, not by emphasis. |
| **Companions** | [Execution matrix](benchmark-matrix.md) · [Order rationale](benchmark-order.md) · [Hardware profiles](hardware-profiles.md) · [Readiness review](gate4-review.md) · [Methodology](STT_BENCHMARK_METHODOLOGY.md) · [Prerequisites](2026-08-05-stt-gate3-prerequisites.md) |
| **Scope exclusion** | The four lineages BLOCKED at Gate 1 — IndicWhisper, Zipformer/sherpa-onnx checkpoints, MOSS-Transcribe, ARK-ASR-3B — are frozen and appear in **no session of this campaign**. |

---

## 1. Objectives

The campaign exists to convert twelve research hypotheses into **evidence records**, per
language, that a future adoption decision can be read from. Its objectives, in order:

1. **Establish an apparatus that measures correctly** — rulers, probes, and a validated
   normalisation round-trip — *before* any candidate is measured.
2. **Re-baseline the incumbent under the Gate 3 methodology**, so that every later comparison
   has a legitimate left-hand side. Our existing baseline predates the methodology and would
   fail six of its own validity conditions.
3. **Produce independent per-language evidence** for English, Hindi and Arabic.
4. **Record what cannot be measured**, as determinations — absence is evidence.

**Explicitly not an objective: selecting a model.** Selection happens at the adoption gate,
from evidence this campaign produces. A campaign that "finds a winner" has skipped a gate.

## 2. Philosophy

- **The instrument is proven before the subject is measured.** A benchmark that runs before
  its ruler exists produces plausible, permanent, wrong evidence in an append-only ledger.
- **Cheapest kill first, but never at the cost of record integrity.** Where the two conflict,
  integrity wins — a session run too early costs correctness forever; a session run late
  costs only calendar time.
- **Grouping is an engineering-cost decision.** Sessions are grouped by serving stack because
  standing up a stack is the dominant per-session cost. Grouping by expected quality would be
  a ranking, and worse engineering.
- **Measure once, read many times.** Twelve hypotheses reduce to twelve measurement units;
  five of those are identical in shape across all candidates and form the session skeleton.
- **Evidence records; it never decides.** Three-planes law, structurally enforced by the
  record schema.

## 3. Lifecycle

| Step | Owner | Output |
|---|---|---|
| Plan | Research | this document + matrix |
| Approve | **Founder** | `Approved for Benchmark` status per candidate; campaign funding |
| Execute | **Engineering** (via `ml/evaluation`) | raw records |
| Record | Evaluation plane | immutable `EvalRun` JSON, append-only |
| Derive | Research/tooling | summaries, regression and switching reports |
| Interpret | Research | recommendation (separate artifact) |
| Decide | **Founder** | status change in the ledger |
| Archive | Engineering | permanent record retention |

**Research neither executes nor decides.** Framework §1 is the constraint: research plans and
interprets, the evaluation plane measures, engineering executes, the founder decides.

## 4. Identifiers

Permanent once issued; never renamed, never reused.

```
campaign   CAMP-STT-2026A
phase      CAMP-STT-2026A/P<n>-<slug>
session    CAMP-STT-2026A/P<n>/S<nn>-<lang>-<stack>-<subject>
record     YYYY-MM-DD-<public-model>-<language>-<artifact>-<serving-class>
```

The **record** identity is the Gate 3 convention, unchanged — a session id names the *plan*,
a record identity names the *evidence*. They are deliberately different: re-running a session
produces a second record, never an overwritten one. Both are carried on the record via
`session_id`, so "which production benchmark accompanies this quality record" is a query.

## 5. Phases

Phases are separated because their **validity criteria, repetition requirements and failure
modes differ**. A failure in one does not invalidate another.

| Phase | What it measures | Entry condition | Invalidated by |
|---|---|---|---|
| **P0 · Apparatus** | Normalisation round-trip, probe corpus behaviour — **no model, no candidate** | rulers registered | V-7 round-trip failure |
| **P1 · Incumbent re-baseline** | The incumbent under the Gate 3 methodology, per language | P0 complete; corpus exists | any V-1..V-10 failure |
| **P2 · Quality** | Per-language accuracy on C2 | P1 complete for that language | corpus < 100; ruler mismatch |
| **P3 · Production** | Startup, ladder, memory, gateway overhead — **per language** | P1 complete | p95 cited under 20 samples |
| **P4 · Robustness** | Accuracy over C3 condition slices | P2 complete (needs a clean baseline to read against) | missing clean-condition reference |
| **P5 · Operational** | Timestamps, determinism, failure behaviour | P1 complete | — |
| **P6 · Streaming** | Streaming latency and partial revisions | **M8 landed** — the contract has no streaming method | — |
| **P7 · Regression** | New records against named prior baselines | ≥2 comparable records exist | comparability blocked |

## 6. Candidate grouping — by serving stack

Seven groups. **This is an engineering-cost axis and carries no quality meaning.** A lineage
appears in more than one group where more than one route exists; the campaign picks one route
per session and records it as `MeasurementRoute`.

| Group | Stack | Lineages in group | Setup cost |
|---|---|---|---|
| **S1** | CTranslate2 | the incumbent | none — already operated |
| **S2** | ONNX Runtime | 5 | best amortisation of any group |
| **S3** | transformers (+PEFT) | 5 | moderate; PEFT is an inference-path dependency for one |
| **S4** | NeMo | 2 | high — a distinct operational world |
| **S5** | fairseq2 | 1 | highest per-lineage — a whole research stack for one lineage |
| **S6** | vLLM | 4 | moderate; forces the GPU-tier decision |
| **S7** | moshi / Rust | 1 | high, and blocked on P6 regardless |

## 7. Language ordering

**English → Hindi → Arabic**, by prerequisite depth. Full argument in
[benchmark-order.md](benchmark-order.md). In brief: English is the only language with both an
incumbent baseline and a corpus, and `switching_test` is a binary function with no first
argument in the other two. Hindi's ruler is a smaller build than Arabic's; Arabic additionally
needs a corpus **and** a dialect verifier — a person, whom no engineering can shorten.

**This is not a product priority ordering.** The founder's research priorities list has its own
order. Ordering confers no advantage on any candidate: within a language phase every candidate
is measured on the same corpus version, the same ruler, and the same hardware profile.

## 8. Hardware classes and environments

Six profiles, defined in [hardware-profiles.md](hardware-profiles.md). **Only P1 exists.**

| Profile | Class | Existence |
|---|---|---|
| P1 CPU reference | `cpu-x86-consumer-2026` | **EXISTS** — every committed number is from this machine |
| P2 CPU production | `cpu-x86-server-2026` | PROCURABLE |
| P3 GPU reference | `gpu-nvidia-consumer-2026` | hardware present, **no software path** |
| P4 GPU production | `gpu-nvidia-datacenter-2026` | HYPOTHETICAL |
| P5 Edge | `cpu-arm-edge-2026` | HYPOTHETICAL |
| P6 Cloud | `cloud-x86-shared-2026` | PROCURABLE |

Every session in this campaign is scheduled on **P1**. Sessions requiring any other profile are
`BLOCKED-ON-FOUNDER` pending the GPU-tier decision.

## 9. Reproducibility requirements

Per the Gate 3 procedure and environment spec, without exception: complete environment record
including **thread configuration**; image digest not tag; artifact hashes; corpus name, version
and hash; normalisation profile; `duration_bands` version; declared language; measurement
route. **A record missing any required field is not a benchmark.**

## 10. Campaign versioning

The matrix **will** change as prerequisites land. Therefore:

- The campaign version increments when the matrix changes (`CAMP-STT-2026A.v1`, `.v2`, …).
- **Records are stamped with the campaign version under which they were produced** and are
  never invalidated by a later version. A mid-campaign change adds sessions; it does not
  retroactively spoil completed ones.
- A change that alters a **ruler, corpus version, or hardware class** does not merely bump the
  campaign — it re-baselines everything downstream of it, and the plan must say so explicitly
  before it is approved.

## 11. Completion criteria

The campaign is **complete** when coverage is achieved — never when "a winner emerged".

1. P0 apparatus validated for every language in scope.
2. An incumbent baseline exists, under this methodology, for every language in scope.
3. Every unblocked candidate session in the matrix has produced a record, or a determination
   explaining why it could not.
4. Every one of the twelve hypotheses is either tested, or carries a recorded determination
   that it is untestable and why.
5. Every record passes validity, or is recorded as `incomplete`/`invalid` with the failing
   condition named.

**Partial completion is a legitimate terminal state.** A campaign that ends with English
complete and Arabic blocked on a corpus has succeeded at what it could reach.

## 12. Outputs

Per the [record schema](STT_BENCHMARK_RECORD.md): Benchmark Records (immutable, append-only) →
Benchmark Summaries (derived, regenerable) → Regression Reports → Switching Reports →
Promotion Package. The research recommendation is a **separate artifact the package manifest
cannot cite**.

## 13. Archive policy

- **Records are permanent.** Raw JSON under `ml/evaluation/stt/results/`, never edited, never
  deleted — including invalid ones, because deleting evidence is worse than keeping a labelled
  failure.
- **Baselines** additionally get a companion document under `ml/evaluation/stt/benchmarks/`.
- **Derived reports are regenerable** and may be discarded and rebuilt from records.
- **Campaign plans are versioned documents** under `docs/research/`, retained permanently so a
  record's context is recoverable.
- **Corpora are permanent company assets** with their own lifecycle (framework §12).

## 14. Non-goals

Selecting a model · ranking candidates · producing a headline cross-language number ·
benchmarking BLOCKED lineages · measuring anything on hardware we do not have · establishing
a GPU tier · executing anything (framework §1) · deciding promotion.

## 15. Rejected alternatives

**All candidates at once.** Rejected: twelve lineages across seven stacks with no validated
ruler would produce a large volume of uninterpretable records, and the non-Latin corruption
path would poison the ledger before anyone noticed.

**Group by expected quality ("most promising first").** Rejected on two independent grounds:
it is a ranking, which this gate is forbidden to produce; and it discards the stack-setup
amortisation that dominates real cost.

**One multilingual session per candidate.** Rejected: Gate 3 law makes a session
single-language, because a record cannot hold two languages and a production ladder that
spans languages belongs to none of them — and the language declaration is itself a
first-order cost variable.

**Benchmark first, build the corpus later.** Rejected: this is the failure the whole design
exists to prevent. With an 11-second single-speaker holding, any number produced would
describe the corpus, not the candidate.

**Skip the incumbent re-baseline and compare against the existing baseline.** Rejected: the
existing baseline predates the methodology and would fail V-1, V-4, V-5, V-7, V-8 and V-9. A
comparison against it would be blocked by the comparability predicate — correctly.

---

*This document plans a campaign. It contains no measurement, ranks nothing, names no winner,
and recommends no adoption.*
