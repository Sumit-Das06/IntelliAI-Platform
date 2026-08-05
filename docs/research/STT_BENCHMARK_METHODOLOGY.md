# IntelliAI STT Benchmark Methodology

| | |
|---|---|
| **Status** | PROPOSED (Gate 3 design, 2026-08-05) — becomes IN FORCE on founder approval |
| **Version** | 0.1 · **Methodology version: 1** (recognition) |
| **Nature** | PERMANENT. This document names no candidate and contains no measurement. |
| **Role** | The permanent measurement design for speech-to-text. It defines what is measured, with which ruler, under what conditions a number may be cited, and what makes a benchmark valid. It is the recognition-side companion to [SPEECH_EVALUATION.md](../../ml/evaluation/SPEECH_EVALUATION.md), which remains IN FORCE and unchanged. |
| **Companions** | [Record schema](STT_BENCHMARK_RECORD.md) · [Execution procedure](STT_BENCHMARK_PROCEDURE.md) · [Environment recording](STT_BENCHMARK_HARDWARE.md) · [Corpus specification](STT_BENCHMARK_CORPORA.md) · [Open prerequisites](2026-08-05-stt-gate3-prerequisites.md) |
| **Gate discipline** | Gate 3 designs benchmarking. **It never executes benchmarking.** No model is scored, ranked, compared, or recommended anywhere in this document set. |

---

## 0. Charter

**What this methodology owns:** the definition of every recognition metric, the ruler each
is computed with, the conditions under which two numbers may be compared, and the criteria
that make a run valid.

**What it must never own:** any decision about whether a model ships. Records describe
reality; promotion decisions interpret records. This is the evidence principle already in
force, and §7 makes it structural rather than procedural — the schema has no field whose
value is a shipping decision.

**Three standing laws inherited unchanged:**

1. **Append-only evidence.** Records are immutable; corrections and re-runs are *new*
   records.
2. **A changed ruler is a new metric name.** Normalisation is part of a metric's identity.
3. **Comparability is conditional, never assumed.** Two numbers may be compared only when
   the conditions in §6 hold.

---

## 1. The schema fork — the finding that shaped this design

**[FACT]** IntelliAI has **two** evidence schemas, not one:

| | `results.EvalRun` | `speech_results.SpeechEvalRun` |
|---|---|---|
| Covers | recognition (STT) | generation (TTS) |
| Metric registry validation | **none** | `_require_registered` |
| `methodology_version` | **absent** | present |
| Measured/human separation | **absent** | enforced |
| Required reproducibility set | **absent** | enforced |
| `EvaluationIdentity` / `SliceCoverage` (language, build, deployment, `.slug`) | **present** | absent |
| `judge` | not applicable — the reference *is* the truth | required |

Every discipline previously described as "in force across evaluation" exists **only on the
generation record**. Recognition evidence is the less-disciplined half.

**Arbitration A-0 — recognition evidence stays on `EvalRun`; the registry reaches across.**
`SpeechEvalRun` structurally cannot hold a recognition run: its `judge: JudgeIdentity` is
required, while the recognition runner records `judge=None` by law — STT's reference is a
human transcript, not a model. `promotion.switching_test` and `enablement_test` are typed
to `EvalRun` regardless. So `EvalRun` grows the disciplines it lacks, by importing the
*same* registry and the *same* validators rather than forking them.

**One registry, forever.** A recognition-only registry would make name collisions
undetectable instead of merely awkward.

---

## 2. Arbitration record — the reconciled vocabularies

Six independent designs collided on four append-only vocabularies. Because first-landing is
permanent, these are settled here, once, with rejected alternatives recorded.

### A-1 · Metric names: the ruler is in the name

**Decision:** every computation is registered **exactly once**, and the normalisation ruler
appears in the name. Bare `wer` / `cer` are **not** registered.

`wer_ascii` · `wer_unicode` · `cer_unicode` · `time_to_first_text_ms` · one
`partial_revision_rate` · `_ms` units throughout for startup phases.

**Why:** `SPEECH_METRICS` is a dict keyed by `spec.name`, so a duplicate name is silently
resolved by whichever spec is last in the tuple — a collision fails at runtime, not at
review. Registering both `wer` and `wer_ascii` for one computation creates a permanent
synonym pair that can never be cleaned up, because renaming is forbidden. Putting the ruler
in the name makes cross-ruler averaging a **type error rather than a policy breach**.

**Rejected:** bare `wer`/`cer` (ruler invisible); `time_to_first_token_ms` (a token count is
a property of one tokenizer and is not comparable across candidates — the same document
that proposed it rejects token denominators elsewhere); `_seconds` units (inconsistent with
`load_ms`/`warmup_ms` already on `/info`).

**Required guard:** a registration-time uniqueness assertion, so a future duplicate raises
instead of overwriting.

### A-2 · `TextCategory` is not appended to

**Decision:** `corpus.TextCategory` is left **untouched**. Every recognition-only axis goes
on new recognition-owned enums.

**Why:** **[FACT]** `test_corpus.py:102-104` (`test_covers_every_planned_category`) asserts
`{c.category for c in corpus.cases} == set(TextCategory)` against the shipped, immutable
`tts-eval-v1.json`. Any append turns that test red until the *generation* corpus gains a
case in the new category — but a text-first synthesis corpus cannot honestly hold a
`NON_SPEECH` or `CLITICS` case, and released corpus versions may not be edited. The append
therefore forces either a fabricated `tts-eval-seed@v2` or a silent weakening of the
generation corpus's coverage guarantee. Two designs proposed the append; a third found the
test and refused. The third is right.

### A-3 · `AudioCondition`: one enum, tuple-valued, coarse at v1

**Decision:** a single recognition-owned `AudioCondition`, held as
`conditions: tuple[AudioCondition, ...]`, starting coarse:

`CLEAN` · `NOISY` · `REVERBERANT` · `TELEPHONY` · `ACCENTED` · `SPONTANEOUS` ·
`MULTI_SPEAKER` · `NON_SPEECH`

**Why tuple-valued:** real clips carry several conditions at once — telephony *and* babble
is one clip, not two. A scalar cannot express it. The cost is that `by_condition()` slicing
is non-partitioning, which is accepted and must be stated wherever such a slice is reported.

**Why coarse:** finer members (`NOISE_BABBLE` vs `NOISE_STATIONARY`, `CLEAN_STUDIO` vs
`CLEAN_DEVICE`) are genuine appends later. Appending is legal; renaming is not. Starting
coarse is the only reversible direction.

### A-4 · Duration bands are a versioned object, not a frozen enum

**Decision:** duration bands are **not** an enum with frozen edges. They are a registered,
versioned object — `duration_bands@v1` — recorded on both the run and the corpus.

**Why:** three designs each froze a different partition of the cost axis (5/30/300 s;
5/15/60 s; 2/10/30/300 s), and duration band is load-bearing — it is part of the
comparability key for real-time factor. Three frozen incompatible partitions make the
comparability law uncomputable, and whichever lands first silently invalidates the others'
composition targets. A versioned object lets a future architecture whose cost discontinuity
sits elsewhere be bracketed by `@v2` **without re-slicing or invalidating a single
historical band-sliced number**.

`duration_bands@v1`: `0-5s` · `5-15s` · `15-60s` · `60s+`. Edges are justified as
convention, not as physics; `@v2` may move them.

### A-5 · Every new field is optional-with-default, mandatory in the runner

**Decision:** **no** new field on `EvalRun`, `ClipResult`, `EvalDataset` or `EvalClip` is
required in the schema. Presence is enforced by the runner and by §7 acceptance checks.

**Why:** **[FACT]** the committed STT record carries exactly
`[dataset_name, dataset_version, capability, run_at, artifact, engine, engine_version,
compute, hardware, notes, clips, load_ms, warmup_ms, identity, coverage]`, and the shipped
dataset manifests carry `[name, version, capability, description, clips]`. A required field
makes every committed record fail `model_validate`, so `find_dataset` can no longer locate
the incumbent dataset and `switching_test` can no longer read the incumbent baseline —
destroying the reproducibility of the only STT evidence the company owns, and violating the
charter that "readers written in five years must parse the records written today". This is
the pattern `identity` and `coverage` already follow.

**One container, not four.** All run-scoped conditions live in a single
`execution: ExecutionContext | None` field. The bare name `conditions` on `EvalRun` is
deliberately **left unclaimed**, so the four-way collision cannot recur.

### A-6 · Metrics can be withdrawn without breaking the ledger

**Decision:** `MetricSpec` gains `status: MetricStatus = ACTIVE` and
`superseded_by: str | None = None`. Recordability is enforced at **write** time by an
explicit `assert_recordable()` in the runner. The **read** path stays permissive: a record
citing a withdrawn name still loads.

**Why:** **[FACT]** `_require_registered` is wired as a pydantic `field_validator`
(`speech_results.py:103, 118, 161`), and field validators run on `model_validate` — i.e. on
**every read of every committed record**. Therefore removing a metric name, or moving it to
`RESERVED`, makes every historical record citing it raise on load. Without this change the
only options are to leave a known-misleading metric permanently recordable, or to render the
append-only ledger unparseable. Both are unacceptable, and this was the sharpest gap the
review found.

**[FACT]** additive-safe: `test_metrics_registry.py` compares only
(layer, direction, confidence) triples, so new `MetricSpec` fields do not break it.

### A-7 · `RESERVED` keeps one meaning

**Decision:** `RESERVED` means **"a capability we do not have yet"** — registerable,
unrecordable, expected to become active. It is **not** used to express "must never be
recorded".

**Why:** two designs used it with opposite intent. A registry holding both meanings with no
field distinguishing them means a future engineer cannot tell which reserved names await
implementation and could promote a deliberately-forbidden name to `HIGH` in good faith.
Forbidden names are expressed by simply **not registering them**, plus a documented
never-register list in §3.

### A-8 · Language is a scalar now, and translation stays expressible later

**Decision:** `EvaluationIdentity.language` remains a **required scalar** — the spoken
language of the corpus slice. Add `output_language: str | None = None`, defaulting to
`language`.

**Why:** the anti-merge guard (§4) is correct and must hold. But a speech-translation or
speech-to-speech run is *not* a merge — it has a source and a target language, and under a
strict scalar it would be recordable only by writing a false value or by amending the very
guard built to be unamendable. Adding the optional field now costs nothing (every committed
record is unchanged, every current guard still holds) and prevents a future forced choice
between the durability claim and a real product capability.

**Standing rule:** no WER-family metric may ever be recorded against a non-transcript
output. Translation quality is a separate registered family.

---

## 3. The metric register

All entries below are proposed additions to the **existing** `SPEECH_METRICS` registry,
using its existing field names and enum members. They must land in **one** change, together
with the single golden-test edit.

### 3.1 Accuracy — `MetricLayer.CORRECTNESS`

| Name | Direction | Unit | Confidence | Definition |
|---|---|---|---|---|
| `wer_ascii` | lower | ratio | HIGH | `align_words` over `normalize_words` (the frozen ASCII ruler). Preserves continuity with the 2026-08-03 English baseline. |
| `wer_unicode` | lower | ratio | HIGH | `align_words` over `speech_normalize` (Unicode-aware; preserves category M). |
| `cer_unicode` | lower | ratio | HIGH | `align_words` over the character sequence of `speech_normalize` output, spaces retained. |
| `substitution_rate` | lower | ratio | MEDIUM | Substitutions over reference words. |
| `insertion_rate` | lower | ratio | MEDIUM | Insertions over reference words. |
| `deletion_rate` | lower | ratio | MEDIUM | Deletions over reference words. |
| `excess_word_ratio` | lower | ratio | MEDIUM | `max(0, hyp − ref) / ref`. A symptom of over-generation, not a proof of hallucination. |
| `hallucinated_words` | lower | count | HIGH | Words emitted where the reference is empty. Already computed; now registered. |

**One aligner.** `align_words` is reused **unchanged** for every accuracy metric. Only the
normaliser and the granularity vary. This is what keeps WER and CER internally consistent.

**Why S/I/D are rates over reference words:** they are then exactly additive with WER.
Confidence is MEDIUM rather than HIGH because the *partition* between substitution and
insertion+deletion is a property of the frozen tie-break, not a physical fact — the total is
robust, the split is a convention.

**Aggregation:** all rate metrics are **word-weighted** across clips, never mean-of-rates.
Mean-of-rates destroys additivity and silently over-weights short clips.

**Never registered** (the forbidden list, per A-7): any metric that averages across
languages; any WER-family name computed over non-transcript output.

### 3.2 Latency and throughput — `MetricLayer.PERFORMANCE`

| Name | Direction | Unit | Confidence | Note |
|---|---|---|---|---|
| `recognition_rtf` | lower | ratio | HIGH | Inference time over audio duration. **Comparable only within one duration band** (A-4). |
| `end_to_end_latency_ms` | lower | ms | HIGH | Request in → final transcript out. |
| `time_to_first_text_ms` | lower | ms | HIGH | Defined for **every** architecture: for non-streaming candidates it equals end-to-end by construction, never N/A. |
| `output_chars_per_second` | higher | ratio | MEDIUM | Characters, not tokens — token counts are tokenizer-specific and not comparable. |
| `partial_revision_rate` | lower | ratio | RESERVED | Normalised characters retracted from the emitted prefix over total emitted characters. Reserved: requires a streaming session we cannot yet hold. |

**`recognition_rtf`, not `rtf`.** **[FACT]** `rtf` is already registered and described as
"synthesis time over produced audio duration". Reusing it for recognition would make the
spec's own description false.

**A structural caveat, recorded not hidden [INFERENCE]:** RTF normalises by *audio*
duration. For an LLM-decoder candidate whose cost scales with *output* length, and for a
fixed-window candidate whose cost is constant below the window, RTF is a partially
misleading denominator. It remains the primary throughput metric for continuity, with
`output_chars_per_second` co-recorded so the distortion is visible rather than silent.

### 3.3 Resource — `MetricLayer.PERFORMANCE`

`peak_memory_mib` and `cpu_percent_max` are **reused unchanged** — already registered,
already capability-generic.

New: `cold_start_ready_ms` · `warm_restart_ready_ms` · `model_load_ms` ·
`model_warmup_ms` · `artifact_ensure_download_ms` · `artifact_ensure_verify_ms`.
`accelerator_memory_peak_mib` is **RESERVED** (no accelerator sampling capability exists).

**[FACT]** `store.ensure` is currently untimed, so the two `artifact_ensure_*` metrics are
unrecordable until that instrumentation lands. They are registered non-RESERVED anyway,
because the blocker is instrumentation we can add, not a capability we lack (A-7).

### 3.4 Robustness

Robustness is **not** a separate metric family. It is the *same* accuracy metrics computed
over corpus slices carrying the relevant `AudioCondition` (A-3). This is deliberate: a
robustness score independent of accuracy would be a new ruler with no baseline.

**Absence is evidence.** A candidate that cannot process a condition produces a recorded
`Determination`, never a missing field and never a zero.

---

## 4. Per-language independence

**English, Hindi and Arabic are measured separately, and their numbers are never merged.**
This is product law, and it is enforced structurally by seven mechanisms — six of which
already exist:

1. `EvaluationIdentity.language` is a required **scalar**; no plural field exists to hold a
   blend, and none is added (A-8 adds only a *target* field, not a list).
2. `language_slice` matches exactly and never widens.
3. `.slug` embeds the language, so a blended record is uncitable.
4. `_comparability` already emits `different_language` and **blocks**.
5. A new `_require_single_language` guard refuses to write a heterogeneous record.
6. Aggregation accepts only a homogeneous slice — this closes the real hole, since
   `aggregate_cases` currently groups by nothing and would yield one blended number.
7. **The ruler carries the language's normalisation profile** (§5), so cross-language
   averaging is a type error, not merely a rule.

**No roll-up field exists anywhere in the schema.** There is no place to put "overall WER
across languages", so it cannot be computed by accident.

**Code-mixed clips are not a fourth language.** A Hinglish clip takes the **matrix**
language as its `language`, carries `CODE_MIXED`, and records `embedded_languages`. There is
no `mixed` pseudo-language: such a bucket belongs to no product promise, satisfies no
`enablement_test`, and is exactly the shape that later gets averaged into something.

### 4.1 Per-language rulers

| Language | Primary | Co-primary | Rationale |
|---|---|---|---|
| English | `wer_unicode` | `wer_ascii` (transition only) | Word boundaries are stable. `wer_ascii` recorded alongside in a single transition record so the existing baseline stays comparable. |
| Hindi | `cer_unicode` | `wer_unicode` | Matras are sub-word; a matra error is invisible to a word-level ruler unless it changes the whole word. |
| Arabic | `cer_unicode` | `wer_unicode` | Clitic agglutination makes the orthographic word an unstable, convention-dependent denominator. |

**Primacy is fixed per (language, corpus version) — never per candidate.** A rule that
selected the primary metric from a candidate's emission granularity would give two
candidates on the same corpus different headline metrics, so the switching test would have
no common ruler and the comparison would be decided by ruler choice rather than by
measurement. Emitted granularity is recorded as a condition (`emitted_unit`) that a reader
interprets; it never selects the citation.

**Both WER and CER are recorded on every run, in every language.**

### 4.2 The normalisation trap

**[FACT]** Arabic tashkeel and Devanagari matras are **both Unicode category Mn**. A
normalisation profile that strips category M to de-diacritise Arabic **destroys Hindi**.

Therefore `NormalizationProfile.codepoint_folds` is an **enumerated codepoint table**, and a
profile that names a Unicode *category* is rejected at registration.

**[FACT]** A second trap: `speech_normalize` maps every non-L/M/N character to a **space,
not to nothing**. ZWJ/ZWNJ and bidi controls are category Cf, so they **split words** —
inflating both reference and hypothesis counts for exactly the two languages that have no
corpus yet. Acceptance check V-7 (§7) tests for this.

### 4.3 The live hazard this must fix first

**[FACT, verified at source]** `normalize_words` strips to `[^a-z0-9\s']+`
([wer.py:17](../../ml/evaluation/src/intelliai_evaluation/wer.py#L17)). A Devanagari or
Arabic reference normalises to an **empty word list** → `reference_words == 0`. Then
([results.py:43-52](../../ml/evaluation/src/intelliai_evaluation/results.py#L43-L52)):
`ClipResult.wer` returns `None` **silently**, and `hallucinated_words` returns the **entire
hypothesis word count**.

A perfectly-transcribed Hindi clip would therefore be committed to an append-only ledger as
*N hallucinated words*, contributing nothing to WER. It does not crash — it produces
plausible, wrong evidence.

Note the asymmetry: `WerBreakdown.wer` **raises** `ValueError` on an empty reference. The
low-level metric is honest; the *record* layer is where the failure goes silent.

**Consequence for ordering: a per-language ruler is a prerequisite that precedes corpus
collection.** Hindi and Arabic audio must not be recorded through this path.

---

## 5. `NormalizationProfile` — the text metric's judge

Metric identity is *computation + normalisation*. Judge identity is already law for
generation metrics; recognition needs the same discipline for its ruler.

A `NormalizationProfile` is versioned, registered, recorded on the run, and
comparison-gating: `_comparability` emits `different_normalization_profile` and blocks.

Registered at v1: `ascii_en@v1` · `unicode_generic@v1` · `devanagari@v1` ·
`arabic_orthographic@v1`.

---

## 6. Comparability

Three distinct properties, routinely confused:

| Property | Meaning | Conditions |
|---|---|---|
| **Repeatability** | same result, same machine, same setup | deterministic metrics only |
| **Reproducibility** | same result, different machine, same declared setup | correctness metrics only; wall-clock excluded |
| **Comparability** | valid to compare two records | all of §6.1 |

### 6.1 Comparability predicate

Two records may be compared only when **all** hold: same corpus name **and** version · same
language · same `NormalizationProfile` · same metric name · same measurement route · same
`duration_bands` version (for band-sliced numbers) · same hardware class and pool
configuration (for performance metrics) · same judge identity **including deployment/host**
(where a judge is involved).

### 6.2 Judge identity is insufficient as currently defined

**[FACT]** In the committed `kokoro-82m` / `-repro` pair, with **identical judge artifact
and version**, 9 of 25 transcripts differed, `round_trip_wer` moved 0.5000 → 0.5042, and RTF
moved +27.5% — because the judge ran on a different host.

Two consequences: `JudgeIdentity` must carry `judge_deployment` and `judge_host`; and the
existing claim that "wall-clock timings are the only expected variance" is **contradicted by
our own committed evidence** and is corrected here.

### 6.3 Noise versus signal

**There is no "any non-zero delta is a real change" rule.** That rule was proposed and is
rejected: the repro pair above refutes it directly, and a regression report built on it
would manufacture a regression from a 0.0042 WER movement caused by a judge host.

A correctness delta is `real` only when the metric's determinism class is deterministic,
the reference is the corpus's own text, and judge deployment and host are identical.
Otherwise the reading is **`no_band_established`** until a same-identity replicate exists.

**No threshold is invented.** Wall-clock bands come from observed replicate spread. Where no
replicate exists, the answer is `no_band_established` — never "noise".

### 6.4 Percentiles

**[FACT]** `nearest_rank` uses ceiling with no interpolation, so at n=3 or n=10 the p95
**is the maximum**. A p95 may therefore be cited only at levels with **≥20 successful
samples**. Below that, report the maximum and name it the maximum.

---

## 7. Acceptance criteria — what makes a benchmark valid

A run is **valid**, **incomplete**, or **invalid**. These are properties of the record, not
judgements about a candidate.

**Validity requires all of:**

- **V-1** The complete reproducibility set is present (see [environment spec](STT_BENCHMARK_HARDWARE.md)). A record missing a required field is not a benchmark.
- **V-2** Corpus name, version and hash recorded; the corpus version is released and immutable.
- **V-3** Single language per record (`_require_single_language`).
- **V-4** Every metric name is registered and `ACTIVE` at write time.
- **V-5** Minimum corpus size for the claim being made (§7.1).
- **V-6** Minimum repetitions for the metric class (§7.2).
- **V-7** Normalisation profile recorded, and its round-trip checked against control strings covering category-Mn and category-Cf hazards (§4.2).
- **V-8** Contamination status declared (§7.3).
- **V-9** Warm-up class recorded and correctly scoped (procedure §3).
- **V-10** No metric cited outside its comparability conditions (§6.1).

**Incomplete** — a run that measured less than planned: some metrics absent, some cases
failed. **Failures are evidence.** Partial metrics are preserved; absent measurements are
recorded as `not_measured` or as a `Determination`, never as zero. An incomplete record is
citable for what it contains and may not be named a baseline.

**Invalid** — a run whose measurements cannot mean what they claim: a validity condition
above is violated. An invalid record is still *written* (deleting evidence is worse), marked
`invalid` with the failing condition named.

**Nobody "invalidates" a record.** Validity is computed from recorded facts. The harness
refuses to write what it cannot describe; engineering records what happened; the founder
weighs it. Research may **append determinations**, never revoke measurements — research
authored the hypothesis and must not hold a lever over which measurements count.

### 7.1 Minimum corpus size

| Claim | Minimum |
|---|---|
| Smoke / liveness only | any (C1) |
| A quality claim for a language | **≥100 cases** in that language (the standing C3 condition) |
| A switching claim | ≥100 cases **and** a second-judge spot-audit where a judge is involved (the standing C2 condition) |

### 7.2 Minimum repetitions

| Metric class | Repetitions |
|---|---|
| Deterministic correctness | 1 (plus one same-identity replicate before any band is claimed) |
| Wall-clock latency | ≥20 successful samples per level for a p95; ≥3 levels for a ladder |
| Cold start | **n=1 by construction** — recorded as such, never averaged |
| Memory peak | max over the level, sampled at a declared interval |

### 7.3 Contamination

Contamination is **declared, not assumed absent**. Each corpus records whether it is
public, private, or derived, and each record declares the candidate's known training-data
overlap as one of: `none_known` · `possible` · `known_overlap` · `undeterminable`.

**[FACT]** This is a real, observed hazard: one lineage in the current research universe
publicly states it was RL-fine-tuned on a public leaderboard's training splits. A corpus we
built ourselves and never published is the only structurally clean position.

---

## 8. Extension rules

This methodology grows by **adding**, never by replacing:

1. A new capability adds metric families; it never redefines existing ones.
2. A new language adds a `NormalizationProfile` and its corpora; §4's mechanisms hold unchanged.
3. A new architecture adds recorded *conditions*; it never changes a metric's definition.
4. A wrong metric is **withdrawn** (A-6), never edited or deleted.
5. Duration bands advance by version (A-4); historical band-sliced numbers stay valid.

*Change log: 0.1 (2026-08-05) — initial design (Gate 3). Arbitrates 14 critical review
findings across six parallel designs into one reconciled vocabulary. Status PROPOSED.*
