# IntelliAI STT Benchmark Execution Matrix

| | |
|---|---|
| **Status** | PROPOSED (Gate 4, 2026-08-05) — IN FORCE only on founder approval |
| **Campaign** | `CAMP-STT-2026A` |
| **Role** | The complete set of planned benchmark sessions. **This is an execution matrix, not a score sheet** — it contains no results and no expectations about results. |
| **Gate discipline** | Nothing here is executed, scored, ranked, or compared. Candidate order within any group is alphabetical and carries no meaning. |
| **Scope exclusion** | The four Gate-1 BLOCKED lineages appear in **no session**. |

**Status legend:** `READY` · `BLK-P<n>` blocked on prerequisite *n* from the
[register](2026-08-05-stt-gate3-prerequisites.md) · `BLK-FOUNDER` blocked on a founder
decision · `BLK-M8` blocked on platform streaming work.

**Every session below is `BLOCKED-ON-FOUNDER` at minimum**, because no candidate holds
`Approved for Benchmark` — all 12 are `Researching`. That gate is not repeated per row.

---

## 0. The twelve measurement units

The twelve hypotheses reduce to twelve measurement units. Five (M1, M2, M8, M9, M10) are
identical in shape for every candidate — they are the **session skeleton**, not per-candidate
work. Scheduling a measurement once and letting several hypotheses read it is the campaign's
main efficiency.

| Unit | Measurement | Serves |
|---|---|---|
| M1 | Startup lifecycle (cold/warm, load, warmup, ensure) | all |
| M2 | CPU cost block (RTF, latency, memory, CPU max) | all |
| M3 | English accuracy on C2 | 9 of 12 |
| M4 | Hindi accuracy on C2 | 5 of 12 |
| M5 | Arabic accuracy on C2 | 3 of 12 |
| M6 | Empty-reference probe behaviour | 4 + the whole SALM class |
| M7 | Timestamp quality | 2 — **blocked, no metric exists** (P4.5) |
| M8 | Concurrency ladder, per language | all |
| M9 | Gateway overhead | all |
| M10 | Determinism replicate + reversed-order audit | all |
| M11 | Normalisation round-trip (V-7) | **candidate-independent** |
| M12 | Language-declaration cost | **candidate-independent** |

---

## P0 · Apparatus — no model, no candidate, no audio

**The shortest chain in the entire campaign.** These sessions need no model, no candidate, and
in two cases no audio at all. They are the only sessions whose prerequisites are purely code.

| Session | Language | Corpus | Level | Baseline | Metrics | HW | Repetitions | Outputs | Status |
|---|---|---|---|---|---|---|---|---|---|
| `S01-en-none-ruler` | en | control strings | — | none | V-7 round-trip | P1 | 1 | determination | `BLK-P1.4` |
| `S02-hi-none-ruler` | hi | control strings | — | none | V-7 round-trip | P1 | 1 | determination | `BLK-P1.1` |
| `S03-ar-none-ruler` | ar | control strings | — | none | V-7 round-trip | P1 | 1 | determination | `BLK-P1.2` |
| `S04-xx-probe-corpus` | per-lang | probe set | C1 | none | corpus validation | P1 | 1 | corpus release | `BLK-P2.9` |

**M11 and the probe corpus must complete before any candidate session.** The empty-reference
hazard is scoped to *non-empty non-Latin* references — probe cases carry `reference_text: ""`,
so probe sessions are **not** blocked behind the ruler work. That distinction prevents
over-blocking the plan.

---

## P1 · Incumbent re-baseline

Our existing baseline predates the Gate 3 methodology and would fail V-1, V-4, V-5, V-7, V-8
and V-9. **A challenger cannot be compared to it.** These sessions produce the legitimate
left-hand side every later comparison needs.

| Session | Language | Corpus | Level | Baseline produced | Metrics | HW | Reps | Status |
|---|---|---|---|---|---|---|---|---|
| `S10-en-ct2-incumbent` | en | `stt-en-c2` | C2 | **`stt-en-2026A-incumbent`** | M1, M2, M3, M6, M8, M9, M10 | P1 | 1 + replicate; ladder ≥20/level | `BLK-P2.1` |
| `S11-hi-ct2-incumbent` | hi | `stt-hi-c2` | C2 | **`stt-hi-2026A-incumbent`** | M1, M2, M4, M6, M8, M10 | P1 | as above | `BLK-P1.1, P2.2` |
| `S12-ar-ct2-incumbent` | ar | `stt-ar-c2` | C2 | **`stt-ar-2026A-incumbent`** | M1, M2, M5, M6, M8, M10 | P1 | as above | `BLK-P1.2, P2.3` |

Runtime: the incumbent's existing CTranslate2 path (S1), already operated — **no stack setup
cost**. This is why the campaign can begin here and nowhere else.

---

## P2 · Candidate quality sessions, grouped by stack

One session = one candidate, one language, one corpus version, one profile. Metrics are M1,
M2, M3/M4/M5 (by language), M6, M10 throughout. Baseline is the P1 baseline for that language.
All on **P1 hardware**. All `BLK` on their language's corpus and ruler, plus their stack.

### S2 · ONNX Runtime — 5 lineages, best amortisation

| Session | Lineage | Lang | Additional blockers |
|---|---|---|---|
| `S20-en-onnx-a` … `S24-en-onnx-e` | the five S2 lineages | en | `BLK-P4.1` (`cer_unicode`), stack setup once |
| `S25-hi-onnx-*` | the S2 lineages claiming Hindi | hi | + `BLK-P1.1` |
| `S26-ar-onnx-*` | the S2 lineages claiming Arabic | ar | + `BLK-P1.2`, `BLK-P5.2` (gated fetch) |

**Stack setup is paid once for five lineages** — the reason this group is scheduled first
among candidates. One lineage in this group additionally requires `BLK-P5.3` (remote-code
review) on its first-party path; whether the ONNX route avoids that is an open question the
session must record, not assume.

### S3 · transformers (+PEFT) — 5 lineages

| Session | Lang | Additional blockers |
|---|---|---|
| `S30-en-tfm-*` | en | PEFT-in-inference for one lineage; `BLK-P5.2` for two (gated) |
| `S31-hi-tfm-*` | hi | + `BLK-P1.1` |

### S4 · NeMo — 2 lineages

| Session | Lang | Additional blockers |
|---|---|---|
| `S40-en-nemo-*` | en | NeMo inside the engine boundary — an unresolved architecture question; `BLK-P5.1` (CC-BY attribution) applies to the licence class |

### S5 · fairseq2 — 1 lineage

| `S50-en-fs2-*` | en | Highest per-lineage setup in the campaign: a research framework for one lineage. Record the isolation outcome as a determination regardless of the accuracy result. |

### S6 · vLLM — 4 lineages

| `S60-*` | en/hi | **`BLK-FOUNDER`** — every published operating point for this group is GPU; requires the GPU-tier decision and profile P3/P4, neither of which exists as a software path. |

### S7 · moshi / Rust — 1 lineage

| `S70-*` | en | **`BLK-M8`** — streaming-shaped engine against a contract with no streaming method. |

---

## P3 · Production sessions — per language

**Per language, not per artifact.** `bench.py` currently sends no language, while the language
declaration is a first-order cost variable — the committed pair shows **12.8×** on identical
audio (17859 ms vs 1391 ms). A single ladder cannot serve a three-language product.

| Session | Language | Metrics | Reps | Status |
|---|---|---|---|---|
| `S80-en-prod-<subject>` | en | M1, M2, M8, M9 | ladder ≥20 successes/level to cite p95 | `BLK-P4.7` (language flag) |
| `S81-hi-prod-<subject>` | hi | as above | as above | + `BLK-P1.1` |
| `S82-ar-prod-<subject>` | ar | as above | as above | + `BLK-P1.2` |

Cold start is **n=1 by construction** and recorded as such, never averaged.

---

## P4 · Robustness — C3 condition slices

Requires a **clean-condition baseline to read against**, so it follows P2 for that language.
Metrics are the same accuracy metrics computed over `AudioCondition` slices — robustness is
not a separate metric family.

| `S90-<lang>-robust-<subject>` | per language | C3 | `BLK-P2.*`, `BLK-P4.9` (noise/augmentation tooling) |

---

## P5 · Operational

| Session | Measures | Status |
|---|---|---|
| `SA0-<lang>-ops-<subject>` | determinism, failure behaviour, timeouts | `BLK-P4.3` — `ClipResult.failure` does not exist, and `raise_for_status()` aborts the whole run, so **a candidate failing a clip is unrecordable today** |
| `SA1-<lang>-timestamps-<subject>` | M7 | `BLK-P4.5` — **no timestamp metric exists in the Gate 3 register.** Two hypotheses depend on this. It is a prerequisite, not a licence to invent a metric mid-campaign |

---

## P6 · Streaming

| `SB0-*` | all streaming candidates | `BLK-M8` — the runtime contract has no streaming method. Every streaming metric is RESERVED and therefore unrecordable by design. Platform work, not research work. |

---

## P7 · Regression

| `SC0-<lang>-regression` | Compares new records against the P1 baselines | Requires ≥2 comparable records; last by definition |

---

## Candidate-independent sessions

Scheduled once for the whole campaign; every hypothesis reads them.

| Session | Measures | Status |
|---|---|---|
| `SD0-xx-declaration-cost` | M12 — language declaration cost on byte-identical audio | `BLK-P4.7`. **Note:** must live in a single probe-only corpus identity declared for all languages, or the comparison is blocked by the comparability predicate on both corpus identity and language |
| `SD1-xx-probe-behaviour` | M6 across the SALM architecture class | `BLK-P2.9`. Requires **both** `product_path` and `research_harness` routes — our zero-hallucination result is a *pipeline* fact (VAD short-circuit), and `MeasurementRoute` blocks differencing between routes |
| `SD2-en-gateway-overhead` | M9 | `BLK-P2.1` |

---

## Sessions that cannot be scheduled at all

Recorded so the gap is visible rather than silently absent:

- **H-COHERE-AR's round-trip clause** is a *generation-plane* question. Recognition records
  `judge=None` by law, so it cannot be scheduled here — it must be re-homed, not planned.
- **Six hypotheses carry comparative or superlative clauses** ("cheapest of any candidate",
  "better than X"). A Gate 4 plan structurally cannot schedule a comparison. These are **read
  afterwards** from independent records under the §6.1 comparability predicate.
- **`enablement_test` currently refuses every language** while defect F-M5-3 is open — so no
  session can terminate in an enablement verdict regardless of its measurements.

---

## Readiness summary

| | Count |
|---|---|
| Sessions defined | ~40 across 8 phases |
| `READY` today | **0** |
| Blocked on prerequisites only | most |
| Blocked additionally on a founder decision | all (status gate) + the S6 group (GPU tier) |
| Blocked on platform work (M8) | S7 group, P6 phase |

**Zero sessions are executable today**, including a re-run against our own incumbent. The
shortest chain in the campaign is `S01`/`S02`/`S03` — ruler validation, which needs no model,
no candidate, and no audio.

*This matrix plans sessions. It contains no results, ranks nothing, and recommends nothing.*
