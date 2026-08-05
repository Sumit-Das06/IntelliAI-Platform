# IntelliAI STT Benchmark Execution Matrix

| | |
|---|---|
| **Status** | PROPOSED v0.2 (Gate 4, revised 2026-08-05 after verification) — IN FORCE only on founder approval |
| **Campaign** | `CAMP-STT-2026A` |
| **Role** | The complete set of planned benchmark sessions. **An execution matrix, not a score sheet** — no results, no expectations about results. |
| **Revision** | v0.1 failed its verification pass (24 critical findings campaign-wide). This revision binds the vocabulary, names group membership, restores a wrongly-deleted group, and recomputes blocking. **Superseded content is not silently replaced — see §9.** |
| **Gate discipline** | Nothing here is executed, scored, ranked, or compared. Candidate order within a group is alphabetical and carries no meaning. |
| **Scope exclusion** | The four Gate-1 BLOCKED lineages appear in **no session**. |

---

## 0. Identifier namespaces — three different `P`s

v0.1 overloaded `P<n>` across phases, hardware profiles and prerequisite items **inside single
rows**. Disambiguated permanently:

| Prefix | Means | Example |
|---|---|---|
| `PH<n>` | campaign **phase** | `PH0` apparatus |
| `HW<n>` | **hardware profile** | `HW1` CPU reference |
| `PR<n.n>` | **prerequisite** register item | `PR1.1` Devanagari ruler |
| `S<nn>` | **session** | `S10-en-ct2-incumbent` |
| `M<n>` | **measurement unit** — an internal grouping only, never a metric | `M3` |

**`M<n>` is not a metric and never appears in a Metrics column.** §1 maps each to registered
names; the Metrics column carries the registered names.

---

## 1. Measurement units → registered metric names

The binding v0.1 omitted. Every name below is from
[STT_BENCHMARK_METHODOLOGY.md §3](STT_BENCHMARK_METHODOLOGY.md). No name here is invented.

| Unit | Registered metric names |
|---|---|
| **M1** startup | `cold_start_ready_ms`, `warm_restart_ready_ms`, `model_load_ms`, `model_warmup_ms`, `artifact_ensure_download_ms`, `artifact_ensure_verify_ms` |
| **M2** CPU cost | `recognition_rtf`, `end_to_end_latency_ms`, `peak_memory_mib`, `cpu_percent_max` |
| **M3** English accuracy | `wer_unicode` (primary), `cer_unicode`, `wer_ascii` (transition record only), `substitution_rate`, `insertion_rate`, `deletion_rate` |
| **M4** Hindi accuracy | `cer_unicode` (primary), `wer_unicode` (co-primary), `substitution_rate`, `insertion_rate`, `deletion_rate` |
| **M5** Arabic accuracy | `cer_unicode` (primary), `wer_unicode` (co-primary), `substitution_rate`, `insertion_rate`, `deletion_rate` |
| **M6** probes | `hallucinated_words`, `excess_word_ratio` |
| **M7** timestamps | **none — no timestamp metric is registered.** `PR4.5`. Unschedulable |
| **M8** ladder | `end_to_end_latency_ms` percentiles, `recognition_rtf`, `peak_memory_mib`, `cpu_percent_max` |
| **M9** gateway overhead | `end_to_end_latency_ms` (gateway vs direct) |
| **M10** determinism | no new metric — a replicate of the run's own accuracy metrics |
| **M11** ruler round-trip | no metric — a `Determination` (V-7) |
| **M12** declaration cost | `end_to_end_latency_ms`, `recognition_rtf` under differing `declared_language` |

**Per methodology §4.1, both WER and CER are recorded on every run in every language.** The
primary/co-primary designation governs *citation*, not *collection*.

---

## 2. Serving-stack route availability

v0.1 said "the five S2 lineages" — unresolvable, since no reading of the dossiers returns
five. Membership is published here with the **evidence level** that places each lineage on a
route. This is an engineering-cost fact, not a ranking.

| Lineage | CTranslate2 | ONNX RT | transformers | NeMo | fairseq2 | vLLM | moshi |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Whisper (incumbent) | **F** | C | F | — | — | — | — |
| Moonshine | — | **F** | — | — | — | — | — |
| Cohere Transcribe general | — | **F** | F¹ | — | — | F¹ | — |
| Cohere Transcribe Arabic | — | C | F¹ | — | — | F¹ | — |
| IndicConformer | — | **F** | F¹ | — | — | — | — |
| Granite Speech | — | — | **F**² | — | — | C | — |
| Qwen3-ASR | — | — | **F** | — | — | **F** | — |
| Voxtral | — | — | F | — | — | C | — |
| Parakeet TDT | — | C | — | **F** | — | — | — |
| Canary-Qwen | — | I | — | **F** | — | — | — |
| Omnilingual ASR | — | — | — | — | **F** | — | — |
| Kyutai STT | — | — | — | — | — | — | **F** |

**F** = FACT (verified at source) · **C** = CLAIM (vendor/third-party) · **I** = INFERENCE /
open question · **bold** = the route this campaign selects. ¹ requires `trust_remote_code`
(Gate 1). ² requires PEFT in the inference path.

**Selected-route counts:** CTranslate2 1 · ONNX RT 3 · transformers 3 · NeMo 2 · fairseq2 1 ·
vLLM 1 · moshi 1. v0.1's "S2: 5" was wrong at every evidence level.

**Remote code applies to 3 lineages, not 1** (both Cohere models on their first-party paths,
plus IndicConformer). Whether the ONNX route avoids it is an open question each session
records rather than assumes.

---

## 3. Universal prerequisites — true of every session, not repeated per row

v0.1's Status column understated blocking, making sessions look one prerequisite from ready
when they were eight or ten. Every row's Status is **additional** to all of these:

`PR0.1` vocabulary ratification · `PR0.2` schema fork decision · `PR0.3` founder plan approval ·
`PR3.1` hardware_class enforcement · `PR3.4` thread-config capture · `PR4.4` `store.ensure`
timing · `PR4.6` `EvalClip` local-path source · `PR4.13` metric-name uniqueness assertion ·
`PR4.14` write-time recordability

Plus the **status gate**: no candidate holds `Approved for Benchmark`; all 12 are
`Researching`, and framework §3 requires a Promising review first. That review is currently
ungrantable as specified (see [gate4-review.md](gate4-review.md)).

---

## 4. `PH0` · Apparatus — no model, no candidate

| Session | Lang | Metrics | HW | Reps | Output | Additional blockers |
|---|---|---|---|---|---|---|
| `S01-en-apparatus-ruler` | en | M11 | HW1 | 1 | apparatus record | `PR1.4` |
| `S02-hi-apparatus-ruler` | hi | M11 | HW1 | 1 | apparatus record | `PR1.1` |
| `S03-ar-apparatus-ruler` | ar | M11 | HW1 | 1 | apparatus record | `PR1.2` |
| `S04-xx-apparatus-probes` | per-lang | — | HW1 | 1 | corpus release | `PR2.9` |

**Apparatus record identity** (v0.1 left these unrecordable): candidate-free sessions use
`YYYY-MM-DD-apparatus-<subject>-<profile>` under `ml/evaluation/stt/results/apparatus/`. Each
emits a `Determination` with `code=ruler_roundtrip_v7`, `subject=<profile>@v1`,
`state=verified|failed`, `producer=harness`, `basis=fact`.

Probe cases carry `reference_text: ""`, so the empty-reference hazard does **not** apply —
probe sessions are correctly *not* blocked behind the ruler work.

---

## 5. `PH1` · Bridging and incumbent re-baseline

### 5.1 Bridging sessions — required before any re-baseline

Declaring a thread policy **is itself a succession boundary** (hardware-profiles §4.6/§6.3).
v0.1 scheduled none, which would have silently orphaned every historical number.

| Session | Purpose | Additional blockers |
|---|---|---|
| `S05-en-bridge-threads` | Two records either side of the thread-policy declaration, sharing a `session_id` prefix, incumbent first | `PR3.4` |
| `S06-en-bridge-topology` | P1-native ↔ P1-container boundary, already crossed unbridged | `PR3.1` |

### 5.2 Incumbent re-baseline

| Session | Lang | Corpus | Level | Baseline produced | Metrics | Reps | Additional blockers |
|---|---|---|---|---|---|---|---|
| `S10-en-ct2-incumbent` | en | `stt-en-c2@v1` | C2 | see §5.3 | M1,M2,M3,M6,M8,M9,M10 | accuracy 1+replicate; ladder §6 | `PR2.1`, `PR4.1` |
| `S11-hi-ct2-incumbent` | hi | `stt-hi-c2@v1` | C2 | see §5.3 | M1,M2,M4,M6,M8,M10 | as above | `PR1.1`, **`PR1.3`**, `PR2.2`, `PR4.1` |
| `S12-ar-ct2-incumbent` | ar | `stt-ar-c2@v1` | C2 | see §5.3 | M1,M2,M5,M6,M8,M10 | as above | `PR1.2`, **`PR1.3`**, `PR2.3`, **`PR2.6`**, `PR4.1` |

**`PR1.3` and `PR2.6` were missing from v0.1 — the single most dangerous omission in the
document.** Without `PR1.3` (empty-reference guard), a Hindi or Arabic session looks runnable
and would commit the exact silent corruption this campaign exists to prevent.

### 5.3 Baseline naming

v0.1 minted `stt-en-2026A-incumbent`, contradicting the record identity convention its own
campaign plan declares. **Corrected:** a baseline is named by the record identity of the run
that produced it — `YYYY-MM-DD-intelliai-stt-<lang>-whisper-small-cpu-v1` — and referenced by
that identity. No parallel naming scheme is introduced.

---

## 6. `PH3` · Production ladder — concurrency levels bound

v0.1 named no levels, so the CLI default (`--levels 1,5,10,20`, `--repetitions 3`) would
silently yield 3 samples at c=1 — a p95 that `nearest_rank` returns as the **maximum**.

**Bound for HW1:** levels `1,5,10,20`; `--repetitions` set so **every level clears 20
successful samples** (≥20 at c=1). A level that saturates before 20 successes records the
maximum, labelled as the maximum, and **no p95 is cited for it**.

Ladders are **per language** (`PR4.7` — `bench` sends no language today, and the declaration
costs ~9.4×).

---

## 7. Session templates — `<subject>` bound

v0.1 left `<subject>` unbound across four phases, making them unexecutable at step zero.
**These are templates, instantiated once per artifact measured in `PH2` for that language:**

| Template | Instantiation rule |
|---|---|
| `S80-<lang>-prod-<artifact>` | one per artifact per language |
| `S90-<lang>-robust-<artifact>` | one per artifact per language, after its `PH2` session |
| `SA0-<lang>-ops-<artifact>` | one per artifact per language |
| `SA1-<lang>-timestamps-<artifact>` | **unschedulable** — M7 has no registered metric (`PR4.5`) |
| `SC0-<lang>-regression-<artifact>` | one per artifact, once ≥2 comparable records exist |

The `<artifact>` token is the record-identity artifact name, so each instantiation has a
constructible identity.

---

## 8. `PH2` · Candidate sessions — including the group v0.1 wrongly deleted

One session = one candidate, one language, one corpus version, `HW1`. Metrics M1, M2,
M3/M4/M5 by language, M6, M10. Baseline is the §5.2 re-baseline for that language.

Sessions are enumerated **per named lineage** (§2), not by group letter. Additional blockers
per session: its language's ruler and corpus items, `PR4.1`, its route's setup, plus
`PR5.2` (authenticated fetch) for gated lineages and `PR5.3` (remote-code review) where §2
marks ¹. **`PR5.4`** (multi-file/external-data artifact pinning) applies to every ONNX-route
session — missing entirely from v0.1.

**`PR5.1` (CC-BY attribution) is NOT a scheduling blocker.** The register states it "does not
block measurement"; it is a Gate 5 pre-adoption condition on a licence class. v0.1 wrongly
promoted it to a blocker.

### 8.1 The restored CPU-viability sessions

v0.1 deleted the vLLM-route group on the premise that "every published operating point is
GPU". That premise **is the hypothesis under test**, is contradicted by a `[FACT]`-labelled
dossier line, and is overruled by [benchmark-order.md §8.2](benchmark-order.md).

**Restored:** every lineage whose only published operating point is GPU gets an `HW1`
**CPU-viability session** terminating in a `Determination` — `state=not_supported` with the
failure recorded, or a measurement. Failures are evidence. The GPU claim is recorded as a
`[CLAIM]` the session tests, never as a premise that deletes it.

---

## 9. Candidate-independent sessions

| Session | Measures | Additional blockers |
|---|---|---|
| `SD0-xx-declaration-cost` | M12 | `PR4.7`, `PR2.9`. **Must live in one probe-only corpus identity declared for all languages** — otherwise `_comparability` blocks on both corpus identity and language, and the comparison is uncitable. v0.1 planned a comparison the law forbids |
| `SD1-xx-probe-behaviour` | M6 across the SALM class | `PR2.9`. Requires **both** `product_path` and `research_harness` routes; `MeasurementRoute` blocks differencing between them |
| `SD2-en-gateway-overhead` | M9 | `PR2.1` |

---

## 10. Unschedulable, recorded so the gap is visible

- **M7 / timestamps** — no registered metric exists (`PR4.5`). Two hypotheses depend on it.
- **The generation-plane clause** in one hypothesis — recognition records `judge=None` by law.
- **Six hypotheses carry comparative clauses.** A plan cannot schedule a comparison; these are
  read afterwards from independent records under methodology §6.1.
- **`enablement_test` refuses every language** while defect F-M5-3 is open.
- **All streaming** — the contract has no streaming method (M8 platform work).

---

## 11. Readiness

| | |
|---|---|
| Sessions defined | ~45 across 8 phases |
| `READY` today | **0** |
| Shortest chain | `S01`/`S02`/`S03` — ruler validation: no model, no candidate, no audio |

**Superseded by this revision (v0.1 → v0.2), recorded not erased:** unmapped `M<n>` codes in
Metrics columns · "the five S2 lineages" · the deleted vLLM group · unbound `<subject>` ·
unnamed concurrency levels · the `stt-en-2026A-incumbent` naming scheme · `PR5.1` as a
blocker · the overloaded `P<n>` namespace · missing `PR1.3`/`PR2.6`/`PR5.4`.

*This matrix plans sessions. It contains no results, ranks nothing, and recommends nothing.*
