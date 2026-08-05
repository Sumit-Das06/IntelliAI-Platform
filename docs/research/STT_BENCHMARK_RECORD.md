# IntelliAI STT Benchmark Record & Output Artifacts

| | |
|---|---|
| **Status** | PROPOSED (Gate 3 design, 2026-08-05) |
| **Version** | 0.1 |
| **Role** | The schema of the immutable evidence record, and the four artifacts derived from it. Companion to [STT_BENCHMARK_METHODOLOGY.md](STT_BENCHMARK_METHODOLOGY.md). |
| **Governing law** | Records are **evidence**; reports are **derived and regenerable**. No report is ever the source of truth. Nothing in this document decides whether a model ships. |

---

## 0. Design constraints inherited

Three constraints shaped every decision below, all verified against committed artifacts:

1. **Additive-only.** **[FACT]** The committed STT record carries exactly
   `[dataset_name, dataset_version, capability, run_at, artifact, engine, engine_version,
   compute, hardware, notes, clips, load_ms, warmup_ms, identity, coverage]`. Any new
   **required** field breaks `model_validate` on every committed record, so `find_dataset`
   can no longer locate the incumbent dataset and `switching_test` can no longer read the
   incumbent baseline. **Every field below is optional-with-default and mandatory in the
   runner.**
2. **Two roots stay two.** Recognition grows `EvalRun`; generation keeps `SpeechEvalRun`.
   Shared sub-records live in one new `evidence.py` imported by both, so disciplines
   converge through *parts* rather than roots.
3. **`evidence.py` may import nothing beyond `pydantic`, `metrics`, and stdlib.**
   **[FACT]** `bench.py` imports `httpx` at module scope and shells out to `docker stats`.
   Embedding its classes into a record schema would mean reading a five-year-old JSON record
   requires an HTTP client to be installable — inverting the layering. The pure record
   classes (`LevelResult`, `OverheadResult`, `RequestSample`, `BenchReport`) and the pure
   function `nearest_rank` **move to** `evidence.py`; `DockerSampler` and the async request
   machinery stay in `bench.py`.

---

## 1. Benchmark Record — the primary evidence artifact

Immutable. Append-only. One record covers **one artifact, one language, one corpus
version, one deployment**.

### 1.1 Additions to `EvalRun`

```
execution:      ExecutionContext | None = None   # §1.2 — the single container
production:     ProductionEvidence | None = None # §1.5
determinations: tuple[Determination, ...] = ()   # §1.6
metrics:        dict[str, float] = {}            # registry-validated aggregates
completion:     Completion = COMPLETE            # complete | incomplete | invalid
methodology_version: int = 1
session_id:     str | None = None                # §1.7
```

`metrics` is guarded by the **existing** `_require_registered` and `_MEASURED` — imported,
not reimplemented. (**[FACT]** `_require_registered` is private with exactly three call
sites and no test imports it, so relocating it to `metrics.py` for shared use is
behaviour-preserving.)

**The bare name `conditions` is deliberately left unclaimed on `EvalRun`**, so the four-way
field collision the review found cannot recur.

### 1.2 `ExecutionContext` — one container, not four

```
route:            MeasurementRoute = PRODUCT_PATH   # product_path | research_harness
environment:      EnvironmentIdentity                # → STT_BENCHMARK_HARDWARE.md
deployment:       DeploymentIdentity
stack:            StackIdentity
normalization:    NormalizationProfileRef
duration_bands:   str = "duration_bands@v1"
declared_language: str
language_mode:    LanguageMode = EXPLICIT           # explicit | auto
emitted_unit:     EmittedUnit = WORD                # word | character | byte — recorded, never selects a metric
vad_owner:        VadOwner = PIPELINE               # pipeline | engine | none
timestamp_source: TimestampSource = NONE            # none | native | auxiliary_model | derived
auxiliary_artifacts: tuple[ArtifactRef, ...] = ()   # e.g. a separate alignment model
decode_params:    dict[str, str] = {}               # genuinely open-ended engine knobs only
seed:             int | None = None
```

**`MeasurementRoute` is a comparability blocker.** A number obtained through a research
shim is kept and labelled rather than laundered into a product-path comparison.

**`auxiliary_artifacts` exists because timestamps may come from a second model.** That model
is part of the measured system and must be identified, hashed, and licence-verified like any
other artifact.

### 1.3 `ClipResult` additions

```
metrics:  dict[str, float] = {}          # registry-validated, per clip
failure:  str | None = None              # [FACT] ClipResult has no failure field today
conditions: tuple[AudioCondition, ...] = ()
duration_band: str | None = None
```

**Failures are evidence.** A clip that failed keeps whatever partial metrics were obtained;
the failure text is recorded verbatim.

### 1.4 `Determination` — absence recorded as evidence

```
code:        str          # stable identifier
subject:     str          # what it concerns
state:       str          # e.g. not_supported | not_measured | undeterminable
producer:    str          # who established it: harness | engineering | research
basis:       str          # fact | inference
detail:      str
source:      str | None
verified_on: date
```

This is the mechanism for "the candidate emits no timestamps" or "the accelerator exposes no
memory counter" — recorded as a dated fact carried **with** the record, never as a missing
field and never as a zero. It also gives the ~15 open questions that are *determinations
rather than measurements* somewhere to live, instead of decaying into prose.

### 1.5 `ProductionEvidence`

Nests `LevelResult` / `OverheadResult` (relocated per §0.3) plus pool configuration and the
saturation counts. **Per language**, because declaring a language is itself a cost variable
of the same order as model choice.

### 1.6 Identity and naming

Filenames follow the convention **already present inside committed records**:
`YYYY-MM-DD-<public-model>-<language>-<artifact>-<serving-class>`, e.g.
`2026-08-05-intelliai-stt-en-whisper-small-cpu-v1`. The file is named by the record's own
identity; lookup is by identity, not by filename.

Location follows the existing ledger: raw `.json` under `ml/evaluation/stt/results/`,
companion `.md` under `ml/evaluation/stt/benchmarks/` when the record is a baseline.

### 1.7 `session_id`

One benchmark session emits several records — a quality record per language, a production
record per language. A shared `session_id` makes "the production benchmark accompanies the
quality benchmark" a **query** rather than a hyperlink somebody must remember to write.

---

## 2. Benchmark Summary — derived, regenerable

A human-readable document, **regenerated** from the record. It is never edited by hand and
is never cited as a source; citations name the record.

Required sections, continuous with the existing baseline documents so a reader recognises
the shape: title (capability · artifact · language · serving class) → permanence preamble
with a link to the raw record → identity block → startup lifecycle → per-language accuracy →
concurrency ladder → gateway overhead → PRD target verdict → reproduction command block →
determinations → open questions.

**One summary per language.** There is no cross-language summary, because there is no
cross-language record.

---

## 3. Regression Report

Compares a new record against a **named prior baseline of the same artifact lineage**.

- Direction of change is **computed from `MetricSpec.direction`**, never authored — a
  report cannot accidentally call an improvement a regression.
- Every comparison first evaluates the §6.1 comparability predicate. A blocked comparison is
  **reported as blocked**, with the blocking finding named. It is never silently skipped.
- Each delta carries a reading: `real` · `within_band` · `no_band_established`
  (methodology §6.3). **There is no "any non-zero delta is real" rule** — our own committed
  replicate pair refutes it.
- Per-language, always. A regression in Hindi is a Hindi fact.

**A regression report decides nothing.** It states what moved, by how much, and whether the
movement is distinguishable from noise.

---

## 4. Switching Report

The evidence artifact for the switching test: challenger versus incumbent.

It encodes the standing switching-test law — *a challenger must beat our tuned incumbent by a
margin exceeding the full switching cost* — **without itself performing the test**:

- Per-language evidence blocks, never a roll-up.
- `CostFactor` entries (re-tuning capital, re-evaluation, serving-stack change, recipe
  knowledge reset, operational unknowns) carry a **description and an owner but no
  magnitude, no weight, and no total** — so the report structurally cannot compute a verdict.
- The second-judge spot-audit (standing condition C2) is recorded where a judge is involved.
- Comparability findings are surfaced prominently: if the two records are not comparable,
  that fact is the headline.

**[FACT]** `switching_test` / `enablement_test` are typed to `EvalRun` only, so this report
is recognition-shaped today; generation would need its own path.

---

## 5. Promotion Package

The bundle handed to the founder at Gate 5. **A dossier of evidence, not a recommendation.**

Contents: the benchmark records (all languages) · their summaries · the regression report
against the incumbent · the switching report · the re-verified licence verdict (Gate 1
format) · the deployment evidence · the risk-register entry · the open-questions list · the
determinations.

**The research programme's recommendation is a separate document.** The package manifest
**cannot cite it** — a structural separation, so the evidence bundle and the argument never
travel as one object.

---

## 6. Structural guarantees

Five devices make the three-planes law structural rather than procedural:

1. **No field anywhere holds a shipping decision.**
2. **No roll-up field exists** across languages.
3. **`CostFactor` has no magnitude, weight, or total field.**
4. **The recommendation is uncitable from the package manifest.**
5. **Direction of change is computed from the registry**, never authored.

---

## 7. Additive-safety verification

Every default below is a **checked fact** about all committed records, so no new validity
finding can fire retroactively on history:

`route = product_path` (every committed record went through `_require_hosted`) ·
`determinations = ()` · `decode_params = {}` · `completion = complete` ·
`metrics = {}` · `execution = None` · `production = None` · `session_id = None`.

**Two known asymmetries, recorded:** `SpeechEvalRun.cases` has `min_length=1` while
`EvalRun.clips` does not — so "the run produced nothing" is recordable on the recognition
root but not the generation root. Relaxing that validator is a *loosening*, not an addition,
and is therefore **not** proposed here; it is carried as an open question.

*Change log: 0.1 (2026-08-05) — initial design (Gate 3), reconciled against review findings.*
