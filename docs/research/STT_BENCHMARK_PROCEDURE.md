# IntelliAI STT Benchmark Execution Procedure

| | |
|---|---|
| **Status** | PROPOSED (Gate 3 design, 2026-08-05) |
| **Version** | 0.1 |
| **Role** | The exact procedure for executing an STT benchmark, such that a different engineer on different hardware five years from now can reproduce it or correctly interpret why they cannot. Companion to [STT_BENCHMARK_METHODOLOGY.md](STT_BENCHMARK_METHODOLOGY.md). |
| **Gate note** | This document *describes* execution. Gate 3 does not execute. Running this procedure requires a founder-approved benchmark plan (Gate 4) and the prerequisites in [the register](2026-08-05-stt-gate3-prerequisites.md). |

---

## 1. Scope of a session

**A session is single-language.** One artifact, one language, one corpus version, one
deployment. A three-language campaign is three sessions sharing a `session_id` prefix.

**Why:** a session that loops languages but runs one concurrency ladder produces a
production record belonging to no language, and quality records whose recorded language is
factually wrong for two of three. **[FACT]** The declared language is itself a first-order
cost variable — in our own M5 measurements, declaring `hi` on identical audio cost 13698 ms
against 1462 ms for `en`, a 9.4× difference. One ladder cannot serve a three-language
product.

---

## 2. Preconditions — fail closed

Measurement does not start until all nine hold. A failed precondition emits a
`Determination` and halts; it never produces a silent partial run.

| # | Precondition |
|---|---|
| P-1 | A founder-approved benchmark plan exists, naming corpus, metrics, hardware, and the baseline to be compared against. |
| P-2 | The corpus version is released, immutable, hash-verified, and single-language. |
| P-3 | The corpus meets the minimum size for the claim being made (methodology §7.1). |
| P-4 | Every metric named in the plan is registered and `ACTIVE`. |
| P-5 | The `NormalizationProfile` for the language is registered, and its control-string round-trip passes (methodology §4.2). |
| P-6 | Every artifact — including any auxiliary timestamp model — is fetched and hash-verified. |
| P-7 | The runtime reports ready; `/info` is captured verbatim. |
| P-8 | The environment record is complete (see [environment spec](STT_BENCHMARK_HARDWARE.md)); any unobtainable field is classified `not_applicable` or `unknown` **before** measurement, not after. |
| P-9 | The machine is otherwise idle, and that is asserted and recorded, not assumed. |

**Rule LF (low-friction):** *if a fact is observable at `/info`, the harness must have no
flag for it.* Testable against the CLI's own argument surface. A hand-typed value that the
system already knows is a transcription error waiting to be committed.

---

## 3. Warm-up — three named classes

Warm-up is not one thing, and conflating the three is how a cold-start number becomes
meaningless.

| Class | What | Included in |
|---|---|---|
| **W0 — lifecycle** | The ModelManager's own load + warm-up at startup | **Cold start** (deliberately included) |
| **W1 — session** | 3 requests over corpus-representative audio before measurement | **Recorded and excluded** — never discarded |
| **W2 — level** | 2 probes at each concurrency level | Excluded from that level's statistics |

**W1 is recorded, not thrown away.** **[FACT]** Our measured first-request-after-startup was
1416 ms against a steady p50 of 1749 ms — the first request was *faster*, not slower. Cold
and uncontended effects are therefore confounded in our own data, and their residual is a
property of the engine family worth keeping rather than discarding as noise.

---

## 4. Execution order

1. Record the environment (§P-8) and capture `/info` verbatim.
2. **Cold start**: deploy from a clean state; measure `artifact_ensure_download_ms`,
   `artifact_ensure_verify_ms`, `model_load_ms`, `model_warmup_ms`, `cold_start_ready_ms`.
   **n = 1 by construction** — recorded as such, never averaged.
3. **Warm restart**: restart with the artifact cached; measure `warm_restart_ready_ms`.
4. **W1 session warm-up** (3 requests, recorded, excluded).
5. **Accuracy pass**: the full corpus, in **fixed manifest order**, concurrency = 1.
   Per clip: transcript verbatim, timings, failures.
6. **Determinism replicate**: repeat step 5 once, same process, same order.
7. **Reversed-order audit**: repeat step 5 in reversed manifest order.
8. **Concurrency ladder**: levels from the plan, W2 probes at each, saturation and refusals
   counted and never hidden.
9. **Gateway overhead**: direct-to-runtime versus through-gateway at c=1.
10. **Teardown**, then emit records (quality + production, shared `session_id`).
11. Compute validity (methodology §7) and stamp `completion`.

### 4.1 Ordering: fixed, with a deterministic adversary

**Decision: fixed manifest order**, plus the reversed-order audit at step 7 and drift probes
at the opening and close.

**Why not randomisation:** randomisation destroys diffability between runs — the property
that makes a regression report readable — and our language slices are small enough that
randomisation adds variance without adding coverage. The reversed-order audit catches
order and cache effects deterministically, which is what randomisation was for.

Where randomisation is genuinely required (listening protocols), the **seed is recorded**.

### 4.2 A known ordering weakness, preserved deliberately

**[FACT]** Gateway overhead currently runs immediately after the ladder, i.e. on a
thermally- and cache-warmed machine. Our own record bounds the effect at about +1.18%
(ladder c=1 p50 1749.3 ms versus overhead direct p50 1770.0 ms).

This procedure **preserves the order** for continuity with the two existing baselines, and
records the weakness here so it is reviewed rather than inherited silently. Changing it
re-baselines both existing benchmarks.

---

## 5. Repetitions

| Metric class | Repetitions |
|---|---|
| Deterministic correctness | 1 + one same-identity replicate before any noise band is claimed |
| Wall-clock latency | ≥20 successful samples per level to cite a p95 |
| Cold start | 1 (structural) |
| Memory peak | max over the level, declared sampling interval |

**[FACT]** `nearest_rank` is ceiling-based with no interpolation, so at n=3 or n=10 the p95
**is the maximum**. Below 20 samples, report the maximum and call it the maximum.

**[FACT]** This makes the existing `prd_p95_actual_ms` field — populated from a p50 of an
n=10, c=1 probe — a misnomer in the committed records. The prose in those documents corrects
it; the JSON does not. Recorded here as a known defect in existing evidence, to be fixed
forward in new records rather than by editing old ones.

---

## 6. Reproducibility, repeatability, comparability

| Property | Question it answers |
|---|---|
| **Repeatability** | Same machine, same setup, same numbers? |
| **Reproducibility** | Different machine, same declared setup, same *correctness* numbers? |
| **Comparability** | May these two records be compared at all? (methodology §6.1) |

**[FACT]** The distinction is not theoretical. In the committed `kokoro-82m` /
`-repro` pair — identical judge artifact and version — 9 of 25 transcripts differed,
`round_trip_wer` moved 0.5000 → 0.5042, and RTF moved +27.5%, because the judge ran on a
different host. Correctness was *nearly* reproducible; wall-clock was not; and the residual
correctness movement was caused by the environment, not the model.

Two consequences, both folded into the methodology: judge identity must include deployment
and host, and the claim that "wall-clock timings are the only expected variance" is
corrected by our own evidence.

---

## 7. The reproducibility rule

**A record missing any required field is not a benchmark.**

This is enforced by the schema and by the validity computation, not by a checklist habit.
An underspecified benchmark must be unconstructible, in keeping with the existing principle
that a number which cannot be reproduced from its recorded metadata is an anecdote.

*Change log: 0.1 (2026-08-05) — initial design (Gate 3).*
