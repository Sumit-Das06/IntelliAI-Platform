# Gate 4 — Campaign Readiness Review

| | |
|---|---|
| **Status** | PROPOSED (Gate 4 review, 2026-08-05) — a readiness assessment, not an approval |
| **Version** | 0.1 |
| **Role** | The honest answer to one question: *if the founder approved the STT benchmark campaign plan today, what would actually happen?* It states the assumptions the plan rests on, the risks to the validity of anything it would produce, what literally blocks execution, what only the founder can decide, and how far each class of session is from being runnable. |
| **Companions** | [campaign plan](gate4-benchmark-campaign.md) · [execution matrix](benchmark-matrix.md) · [order rationale](benchmark-order.md) · [hardware profiles](hardware-profiles.md) · [methodology](STT_BENCHMARK_METHODOLOGY.md) · [record schema](STT_BENCHMARK_RECORD.md) · [procedure](STT_BENCHMARK_PROCEDURE.md) · [environment spec](STT_BENCHMARK_HARDWARE.md) · [corpora](STT_BENCHMARK_CORPORA.md) · [open prerequisites](2026-08-05-stt-gate3-prerequisites.md) |
| **Gate discipline** | This document plans and reviews. **It executes nothing.** No model was run, downloaded, scored, ranked, or compared. No candidate is recommended, preferred, or de-prioritised anywhere in it. Where sessions are grouped, the grouping is by **serving stack** — an engineering-cost axis — and where they are ordered, the ordering is by **prerequisite depth**. Neither is a quality statement. |
| **Scope exclusion** | The four lineages **BLOCKED at Gate 1** (IndicWhisper, Zipformer/sherpa-onnx checkpoints, MOSS-Transcribe, ARK-ASR-3B) are frozen: **[FACT — MODEL_LEDGER.md, Gate 1 verdicts]** "work on BLOCKED lineages is halted". They appear in no session of this campaign and in no readiness statement below. |

**Labels used throughout:** **[FACT]** verified in this repository or read at source on the stated
date · **[CLAIM]** external assertion, unverified by us · **[INFERENCE]** reasoning over facts.

> **✅ VERIFICATION HAS SINCE RUN (2026-08-05).** Four adversarial passes — gate discipline,
> schema consistency, executability, cross-document coherence — produced **87 findings, 24
> critical**. The verdict: the five documents were *"individually well-argued and collectively
> incoherent at every seam where they had to agree without ever being reconciled"*, with the
> damage concentrated in the two orchestrator-written documents. The criticals have been
> applied: [benchmark-matrix.md](benchmark-matrix.md) was rewritten to v0.2 and
> [gate4-benchmark-campaign.md](gate4-benchmark-campaign.md) to v0.2. **The verdict on the
> plan as first committed stands: it was a coverage sketch, not an execution matrix.** The
> historical note below describes the gap that made that so.
>
> **⚠ Original verification gap — disclosed, not hidden.** Gate 4's design ran three planned
> adversarial verification passes. **All three failed to run** — the session hit its usage
> limit before they started, as did the agents for the campaign plan and the execution matrix.
> Consequently:
> - [gate4-benchmark-campaign.md](gate4-benchmark-campaign.md) and
>   [benchmark-matrix.md](benchmark-matrix.md) were written directly by the orchestrator from the
>   completed ground research, not by a designer agent.
> - This document, [benchmark-order.md](benchmark-order.md) and
>   [hardware-profiles.md](hardware-profiles.md) were produced as designed, but **received only an
>   orchestrator gate-discipline scan**, not the independent adversarial review that Gate 3's
>   deliverables received (which found 49 issues, 14 of them critical).
>
> **[INFERENCE]** Gate 3's experience is the relevant precedent: parallel designs were individually
> sound and collectively incoherent, and only adversarial review surfaced it. This document set has
> not had that test. Treat cross-document consistency — metric names, session identifiers, corpus
> names, prerequisite numbering — as **unverified** until a verification pass runs. That pass is
> itself a recorded prerequisite, not an optional polish step.

---

## 0. The verdict in one paragraph

**[INFERENCE]** The campaign is **fully plannable and almost entirely unexecutable**. Every
measurement the twelve Gate 2 hypotheses demand can be specified today using only the Gate 3
vocabulary; **zero** of them can produce a *valid* record today, because validity is defined by
[methodology §7](STT_BENCHMARK_METHODOLOGY.md) and at least five of its ten conditions fail for
every conceivable session — including a session against our own incumbent in our own strongest
language. The binding constraints are, in order: a founder ratification that has not happened, a
metric registry that contains none of the campaign's metric names, a corpus that does not exist in
any language at the size the methodology requires, and a status question that only the founder can
answer. **None of the top four constraints is about any candidate.** That distribution is the
single most important fact in this review, and it has not changed since Gate 3 recorded it.

---

## 1. Assumptions

Every load-bearing assumption the campaign plan rests on, with what breaks if it is wrong.
An assumption is not a fact; per [framework §2](RESEARCH_FRAMEWORK.md) it is "believed without
verification — must be flagged and dated". These are flagged and dated 2026-08-05.

### 1.1 Assumptions about our own instruments

| # | Assumption | If it is wrong |
|---|---|---|
| **A-1** | **The Gate 3 reconciled vocabulary is ratified as written** — the metric-name table, `AudioCondition`, `duration_bands@v1`, the `TextCategory` no-append rule (prerequisite 0.1). | Every session specification is rewritten. Worse: **[FACT — methodology A-1]** `SPEECH_METRICS` is a dict keyed on `spec.name` with **no** registration-time uniqueness assertion (4.13), so a *partial* landing — one name now, a revised name later — is not a mistake that can be corrected. First landing is permanent; a synonym pair can never be cleaned up. |
| **A-2** | **Recognition evidence extends `EvalRun`; the registry reaches across** (0.2, arbitration A-0). | The record schema, the `session_id` linkage, and both promotion functions change shape. **[FACT]** `switching_test` and `enablement_test` are typed to `EvalRun`; `SpeechEvalRun` structurally cannot hold a recognition run because its `judge` is required and recognition records `judge=None` by law. A fork would mean two registries and undetectable name collisions. |
| **A-3** | **Every new record field is optional-with-default, mandatory in the runner** (A-5). | **[FACT — record schema §0.1]** a required field breaks `model_validate` on all three committed STT records, so `find_dataset` can no longer locate the incumbent dataset and `switching_test` can no longer read the incumbent baseline — destroying the reproducibility of the only STT evidence we own. |
| **A-4** | **Metric withdrawal will be made safe before the first campaign record is written** (4.14). | **[FACT]** `_require_registered` is a pydantic `field_validator`, so it runs on **every read**. Withdrawing or reserving a name after records cite it makes those records unparseable — the ledger stops being readable by the five-year reader it was written for. This is why the vocabulary and its guards must land **in one change, before** any record, not alongside the campaign. |
| **A-5** | **Numbers we already hold can be re-expressed under registered names without changing their values.** | Not entirely true, and the plan must not assume it. **[FACT]** `EvalRun.mean_rtf` is a **mean of per-clip ratios**, while [methodology §3.1] mandates word-weighted aggregation for rate metrics and [§3.2] makes `recognition_rtf` comparable **only within one duration band**. **[FACT]** the ASCII WER computation *is* preserved by `wer_ascii`, so the accuracy continuity claim holds; the **RTF continuity claim does not**, and any campaign sentence that says "continuous with the 2026-08-03 baseline" must say *which metric*. |

### 1.2 Assumptions about the measurement environment

| # | Assumption | If it is wrong |
|---|---|---|
| **A-6** | **One CPU reference machine carries the whole campaign, and is not replaced mid-campaign.** | **[FACT — hardware spec §0]** "same hardware class" exists nowhere in code, `_comparability` emits no hardware finding, and the one machine we have measured on is **spelled three different ways** across committed records. A mid-campaign machine change without a bridging run ([hardware §6.2]) makes every performance number before and after it incomparable, **with no finding raised** — silent, not blocked. |
| **A-7** | **A session is single-language and each language slice gets its own process.** | **[FACT]** both committed M5 records carry identical `load_ms` 5500.2 / `warmup_ms` 2638.9 because **one process served both slices**. A plan that treats cold start or warm restart as a per-language number will record the same figure for every language and call it evidence. |
| **A-8** | **Thread configuration is capturable before any CPU number is cited** (3.4). | **[FACT — hardware §1.4]** no thread-count field exists anywhere in the current schemas, and CPU ASR throughput is strongly thread-sensitive. A CPU benchmark without it is not reproducible — meaning the resulting number is, by [framework §6.4], an anecdote. |
| **A-9** | **Resource numbers are obtainable.** | **[FACT]** `peak_memory_mib` / `cpu_percent_max` come **only** from `docker stats`, i.e. only when `--docker-container` is passed. **[FACT]** the M5 multilingual baselines were taken "Windows 11, native" — a native session produces **nothing** for either metric. A campaign that assumes memory evidence exists per session must first decide that every session is containerised. |

### 1.3 Assumptions about the measured system

| # | Assumption | If it is wrong |
|---|---|---|
| **A-10** | **The product path is the measurement route for quality and cost sessions.** | Partly false already, and the plan depends on the distinction. **[FACT — corpora §4.2]** our incumbent's zero-hallucination result was obtained **structurally** — the pipeline VAD short-circuits before the engine runs — so a product-path probe measures the *pipeline*. Engine-level probe evidence needs `MeasurementRoute = research_harness`, and **[FACT — methodology §6.1]** route is a comparability blocker: the two numbers may be read side by side and **never differenced**. |
| **A-11** | **Decode parameters can be held constant across a session.** | **[FACT]** `TranscriptionRequest` carries exactly `language` and `model` — no beam size, no temperature, no VAD knob. `decode_params` is therefore not merely *unrecorded*, it is **unsettable through the product path**. Holding them constant is achieved by having no access to them; a candidate whose published operating point requires a non-default setting cannot be measured at that point without a contract extension or a research route. |
| **A-12** | **The quality record and the production record of one session describe the same configuration.** | **[FACT]** They do not today. `run` sends `language` per clip; `bench` sends **none** (`cli.py:316`), so the ladder measures auto-detect while the quality pass measures explicit declaration — and **[FACT]** the declared language is a first-order cost variable on our own hardware. Prerequisite 4.7 must land before a session's two halves may be read as one session. |
| **A-13** | **Gate 1 licence verdicts still hold when a session runs.** | **[FACT — framework §2, §5]** verdicts decay and are per artifact **version**, never per family; re-verification at Gate 5 is mandatory regardless of the Gate 1 date (6.4). A campaign that runs months after 2026-08-05 on unre-verified verdicts risks measuring an artifact that has since become ineligible — and **[FACT — framework §3]** a licence change forces *any status → Rejected*, discarding the measurement's purpose, not its validity. |
| **A-14** | **Candidates can be made servable behind the existing contract unchanged.** | **[FACT]** the pipeline is fixed: ffmpeg to canonical 16 kHz mono s16le, `EnergyVad` in the pipeline, `max_upload_bytes` 25 MiB, `max_audio_seconds` 600, one artifact per slot, and a startup warm-up over 8000 deterministic samples with a bare `TranscriptionRequest()`. A lineage wanting its own VAD, a different sample rate, raw file bytes, or two models in one measured system does not fit; each is a design change, not a config flag. |

### 1.4 Assumptions about process

| # | Assumption | If it is wrong |
|---|---|---|
| **A-15** | **Engineering executes; research plans.** | **[FACT — framework §1]** research must never own benchmark execution; measurements are produced by the evaluation plane and cited by research. If research executes, the evidence is invalid *by construction* — a broken link in the one-way chain, not a procedural lapse. Every "session" in the campaign plan is an **engineering** session that research specifies. |
| **A-16** | **Probe (empty-reference) sessions are not blocked behind the non-Latin ruler work.** | **[FACT — results.py:43-52]** on an empty reference `ClipResult.wer` returns `None` and `hallucinated_words` returns the whole hypothesis — which is the **intended** probe semantics. The Layer-1 hazard is scoped to **non-empty non-Latin references**. If this scoping is wrong in either direction the campaign either needlessly freezes its cheapest sessions, or lets a Devanagari reference through the ASCII ruler. The distinction must be written into the plan, not assumed by the reader. |
| **A-17** | **Corpora we build ourselves are contamination-clean.** | **[FACT — methodology §7.3]** contamination is *declared, never assumed absent*, and a corpus we built and **never published** is the only structurally clean position. **[FACT]** `corpus-inbox/` is **not** gitignored (only `data/` is) despite the recording protocol saying it is — so the act of doing the founder recording homework today would publish the corpus, converting a clean asset into a permanently contaminable one. The assumption is currently protected by nothing but the fact that the recordings do not exist. |

---

## 2. Risks to campaign validity

These are risks to *the meaning of the numbers*, not generic project risks. Schedule, budget and
staffing risks are out of scope for this document; they are the founder's, and they are real.

### R-1 · Silent corruption: a non-Latin reference scored before its ruler exists

**Severity: highest. Mechanism verified at source.**

**[FACT]** `wer.py:17` — `_STRIP = re.compile(r"[^a-z0-9\s']+")`. A Devanagari or Arabic reference
normalises to an empty word list → `reference_words == 0` → **[FACT — results.py:43-52]**
`ClipResult.wer` returns `None` **silently** and `hallucinated_words` returns the **entire
hypothesis word count**.

Three consequences compound, and each is worse than the last:

1. A **perfectly transcribed** Hindi or Arabic clip is committed to an **append-only** ledger as
   *N hallucinated words with no WER*. Not a crash — plausible, wrong, permanent evidence.
2. **[FACT — identity.py]** `SliceCoverage.reference_words` is summed from the *normalised*
   breakdown, so `is_quality_claim` returns **false for a perfect Hindi corpus**, and
   `enablement_test` then BLOCKS it as `no_natural_speech_in_corpus`. The mechanism M5 built to
   prevent overclaiming inverts into a false accusation.
3. **[INFERENCE, from `promotion.py`]** at the promotion layer, `switching_test` on such a slice
   computes `wer_delta = None` (both sides), fires `no_word_error_rate`, returns **TRADE**, and
   reports a `hallucination_delta` differenced from two whole-hypothesis word counts. **A perfect
   challenger and a broken one both read TRADE with a large hallucination number.**

**What prevents it:** prerequisites 1.1, 1.2, 1.3 land **before** any Hindi or Arabic audio is
recorded, let alone scored. This ordering is a safety requirement, not a preference.

**Answered, and worth recording as good news [FACT]:** Gate 3 VERIFY item **6.1** is discharged for
the STT results tree as committed. All three committed records were inspected; `stt-eval-seed@v2`'s
`hi` slice is two synthetic probes with `reference_text: ""`, and the manifest states in-file that
the slice carries no natural speech and is not a quality claim. **The zero-reference path was
reached by design, not by failure. No committed record is corrupted.** The hazard is entirely
prospective — which is exactly why it is preventable.

### R-2 · Comparability loss through hardware succession or host change

**[FACT]** Of the nine conditions in the [§6.1](STT_BENCHMARK_METHODOLOGY.md) comparability
predicate, `_comparability` checks **three and a half**: corpus name+version, language, and
judge-as-equality. It is blind to hardware class, pool configuration, normalisation profile, metric
name, measurement route, and duration-bands version — **no field exists for any of them**.

**[FACT]** For recognition the judge check is worse than partial: `judge=None` on both sides, so
`left.judge != right.judge` evaluates `None != None` → False and `different_judge` **can never
fire** on an STT comparison.

**[FACT]** The magnitude of the host effect is measured, in our own committed evidence: the
`kokoro-82m` / `-repro` pair, with **identical judge artifact and version**, differed on **9 of 25
transcripts**, moved `round_trip_wer` 0.5000 → 0.5042 and RTF **+27.5%** — because the judge ran on
a different **host**. That is the generation plane; the recognition analogue is the measurement
host itself, and recognition has *fewer* guards, not more.

**Risk:** a campaign spanning weeks compares performance numbers across a machine, a container
image, or a thread configuration that changed underneath it, and **nothing raises a finding**.
**What prevents it:** 3.1 (`hardware_class`), 3.4 (thread capture), 3.5 (succession policy), the
bridging run, and image **digests** rather than tags.

### R-3 · Contamination — in both directions

**[FACT — methodology §7.3]** This is an observed hazard, not hypothetical: **one lineage in the
current research universe publicly states it was RL-fine-tuned on a public leaderboard's training
splits.** **[FACT]** the dossiers do not resolve which measurements that taints — it is an open
VERIFY item that bears on every decision to measure on public data.

Two directions of risk, and the second is the one usually missed:

- **Inbound:** a candidate's number on public data may be memorisation. **[FACT]** no
  contamination field exists on any record today, so acceptance check **V-8 is uncheckable** and
  the declaration cannot be made even honestly.
- **Outbound:** **[FACT]** `corpus-inbox/` is not gitignored. Recording our own corpus and
  committing it publishes it — permanently, and to exactly the crawlers that build the next
  generation of training sets. **The only structurally clean position we have is one we could
  destroy in a single `git add`.**

### R-4 · A p95 cited below 20 samples

**[FACT]** `nearest_rank` is ceiling-based with no interpolation, so at n=3 or n=10 the p95 **is
the maximum**. **[FACT]** `bench`'s default `--repetitions 3` is *per worker*: level c=1 yields
**3** samples and c=5 yields 15 — both below the 20-sample floor. Only c≥7 clears it at defaults.

**[FACT]** The existing evidence is already worse than that: `prd_p95_actual_ms` in the committed
records is populated from `overhead.via_gateway_p50_ms` (`cli.py:351`) — **a p50 of an n=10 probe,
stored in a field named p95**. The prose in the baseline documents corrects it; the JSON does not.

**Risk:** the campaign inherits both defects at scale and publishes ladders whose headline
percentile is a maximum, or a median, under a p95 label — and those records are append-only.
**What prevents it:** the [procedure §5] rule enforced in the plan (≥20 successful samples per
level, or report the maximum and **name** it the maximum), plus fixing the field forward — never by
editing old records (6.3 is the VERIFY item that scopes the damage).

### R-5 · A mid-campaign vocabulary change landing in an append-only registry

**Severity: highest, because it is unrecoverable rather than merely wrong.**

Three verified mechanics combine:

1. **[FACT]** `SPEECH_METRICS` is a dict comprehension keyed on `spec.name` — a duplicate name is
   **silently resolved by whichever spec is last in the tuple**. There is no uniqueness assertion
   (4.13).
2. **[FACT]** `MetricSpec` has **no** `status` and **no** `superseded_by` field (4.14).
3. **[FACT]** `_require_registered` is a `field_validator` — it runs on **every read of every
   committed record**.

**Risk:** half the campaign is recorded under `wer_x` and half under `wer_x'` (a rename, a ruler
change, a granularity change); the two are averaged by a later reader because nothing types them
apart; or the wrong name is withdrawn and every record citing it becomes **unloadable**.
**What prevents it:** 0.1 ratification, 4.13 and 4.14 landing **in one change, before the first
campaign record**, and the standing law that a changed ruler is a new metric **name**.

### R-6 · Overreading a thin corpus

**[FACT]** `SliceCoverage.is_quality_claim` is true when `natural_speech_clips > 0 AND
reference_words > 0` — **a floor of one clip**. The committed English slice reads `true` on
**2 natural clips, 44 reference words — one speaker, one ~11-second utterance, two containers**.
**[FACT — methodology §7.1]** a quality claim for a language requires **≥100 cases**.

**Risk:** `is_quality_claim: true` is read as corpus adequacy and the English baseline is treated as
satisfying V-5. It does not — **V-5 fails for every language today, English included.** The flag
prevents overstating *emptiness*; it was never able to prevent overstating *thinness*.

### R-7 · Failures that produce silence instead of evidence

**[FACT]** `ClipResult` has no `failure` field (4.3), and `run_stt_eval` calls `raise_for_status()`
— **any HTTP error aborts the whole run** with no partial record. **[FACT — methodology §3.4, §7]**
the methodology's law is the opposite: *failures are evidence*; absence is recorded as a
`Determination`, never as a zero and never as a missing field. **[FACT]** three of the twelve Gate 2
hypotheses concern a candidate **failing to run at all** — i.e. the hypotheses whose expected
outcome the harness is structurally unable to record.

### R-8 · The promotion machinery blocks the most routine comparison

**[INFERENCE, from `promotion.py:90-137`]** `not_a_replacement` fires when `artifact` **and**
`build` match — `artifact_version` is not compared. So `whisper-small@v1/cpu-int8` versus
`whisper-small@v2/cpu-int8` — an **artifact upgrade**, the single most common regression case and
the first comparison any campaign schedules — returns **BLOCKED** on the grounds that there is
nothing to switch to. **[FACT]** conversely, a *different engine* on the same artifact and a
different build passes with **no finding at all**: `engine` and `engine_version` are never compared.

### R-9 · Route and registry provenance recorded nowhere

**[FACT]** `run` resolves the artifact from `resolution.json` and `--manifest` accepts **any**
path. **[INFERENCE]** a campaign can therefore point at a manifest exported from a branch catalog —
a legitimate mechanism — and produce a record whose `identity.deployment` and evidence chain
describe **registry state that was never shipped**, with no field in which to say so.
`MeasurementRoute` exists in the Gate 3 design precisely for this and does not exist in code.

### R-10 · Citing an anecdote as evidence

**[CORRECTED 2026-08-05 — the claim originally made here was wrong.]** The "9.4×"
language-declaration figure **is committed**, at
[`2026-08-05-multilingual-baselines.md` §2a](../../ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md),
as a **median of three runs per declaration** (`hi` 13698.1 ms, `en` 1462.4 ms, `ar` 1389.4 ms).
That makes it the **stronger** measurement; the 17859/1391 ms pair (12.8×) is single-sample.
The error was repeated to the founder and written into the append-only ledger before anyone
verified it at source — see ledger correction C-1. **[FACT — framework §6.4]** a number not reproducible from its
recorded metadata "may motivate a hypothesis but may never justify a status change". A campaign
document that cites 9.4× as a design input is citing an anecdote — and the campaign's own
[procedure §1] rationale currently does exactly that.

### R-11 · Two conventions for code-mixing inside one package

**[FACT]** `mixed` is a live language value in the committed synthesis corpus (4 of 25 cases), and
`speech_runner` maps `case.language == "mixed"` to `language=None`. **[FACT — methodology §4]** the
recognition methodology **forbids** a `mixed` pseudo-language: a code-mixed clip takes the matrix
language, carries `CODE_MIXED`, and records `embedded_languages`. **Risk:** code-mixed recognition
work inherits the generation convention from the same package and creates a bucket that belongs to
no product promise and satisfies no `enablement_test`.

### R-12 · Evidence hygiene defects that would be inherited

Three small ones, each capable of undermining a large claim:

- **[FACT]** committed result filenames are dated `2026-08-05` while `run_at` is
  `2026-08-04T20:4x`, and both records show byte-identical `run_at` at top level and inside
  `identity` where `runner.py` calls `datetime.now()` **twice**. **[INFERENCE]** the files were
  normalised after generation. "Records are runner-verbatim" is currently an assumption.
- **[FACT]** the `ml/evaluation/README.md` `run` example **no longer parses** — it cites a
  `--artifact` flag that does not exist and omits three required arguments. Any session step
  copying it fails at argparse.
- **[FACT]** run unscoped, the ladder-coverage check reports ~2000 synthesis requests each for
  `hi`/`ar` — dev-fixture residue written with `origin=customer` and fabricated timestamps. Any
  campaign citing demand evidence must scope by org or it will cite fixtures.

---

## 3. Blockers — what literally prevents execution today

Each row states what it stops, and traces to the register. **[FACT]** The register carries **44
numbered items** across Layers 0–6; its own summary counts "roughly 60 open prerequisites" once
sub-items are included. Both counts are honest; they count different things.

### 3.1 Blockers on *every* session, in every language

| # | Blocker | Stops | Register |
|---|---|---|---|
| **B-1** | **No candidate holds `Approved for Benchmark`.** All twelve are `Researching`; none has passed a Promising review. | Precondition **P-1**. Everything. | 0.3 (and §5 below) |
| **B-2** | **The reconciled vocabulary is not ratified.** | Every schema and corpus item downstream. | 0.1, 0.2 |
| **B-3** | **Zero of the ~20 Gate 3 metric names are registered, and no recognition number is recorded under *any* metric name.** `EvalRun` has no `metrics` field; `_require_registered` exists only on the generation root. | Precondition **P-4**, validity **V-4**. | 4.1, 4.2, 4.13, 4.14 |
| **B-4** | **`NormalizationProfile` does not exist** as a type, a registry, or a field; no control-string round-trip test exists. | Precondition **P-5**, validity **V-7**. | 1.1–1.4 |
| **B-5** | **No corpus meets the size rule in any language.** **[FACT]** `stt-eval-seed@v2` holds 8 clips, of which **2 are natural speech — the same utterance in two containers**; a C1 is specified as 10–20 clips and a C2 as ≥100. Zero Arabic clips of any kind. | Precondition **P-3**, validity **V-5**. | 2.1, 2.2, 2.3 |
| **B-6** | **`EvalClip` has no local-path source** — `_exactly_one_source` permits only a pinned URL+sha256 or a synthetic generator. **Audio we record ourselves is unregisterable.** | Blocks 2.1, 2.2 **and** 2.3 simultaneously — i.e. every corpus in every language. | 4.6 |
| **B-7** | **The environment record cannot be completed**: no `hardware_class`, no thread capture, no accelerator sampling; `EvalRun.hardware` is one free string, already spelled three ways. | Precondition **P-8**, validity **V-1**. | 3.1, 3.3, 3.4 |
| **B-8** | **No `session_id`, no `methodology_version`, no `completion`, no `ExecutionContext`, no `Determination` on `EvalRun`.** | Validity **V-1**; and "the production benchmark accompanies the quality benchmark" stays a human memory rather than a query. | record schema §1 |
| **B-9** | **Contamination cannot be declared** — no field exists on record or corpus. | Validity **V-8**. | 5.5 |
| **B-10** | **W1 session warm-up does not exist.** `run` performs no warm-up at all; `bench` runs W2 probes and **discards** them where the procedure requires W1 be *recorded*. | Validity **V-9**. | procedure §3 |

### 3.2 Blockers on specific classes of session

| # | Blocker | Class it stops | Register |
|---|---|---|---|
| **B-11** | **`cer_unicode` is implemented nowhere**, and `wer_unicode` is not wired to recognition at all. `cer_unicode` is the **primary ruler for both Hindi and Arabic**. | **All** Hindi and Arabic quality measurement. | 4.1 |
| **B-12** | **The ASCII ruler corrupts non-Latin references silently** (R-1). | Any recording *or* scoring of Hindi/Arabic audio. Ordering: **ruler before corpus.** | 1.1, 1.2, 1.3 |
| **B-13** | **No Arabic dialect verifier** — a person, not a build. Plus convention sheet and double-transcription capacity. | Arabic C2/C3 references. | 2.4, 2.5, 2.6 |
| **B-14** | **`store.ensure` is untimed**, and `ModelManager.startup` starts its clock *after* `ensure` returns — download+verify cost falls into neither `load_ms` nor `warmup_ms`. **[FACT]** cold start and warm restart have **no harness phase at all**; the committed 46 s / 2.4 s figures were read by hand from container logs. | Procedure steps 2–3 (the startup lifecycle block, which serves all twelve hypotheses). | 4.4 |
| **B-15** | **`bench` sends no language and writes no per-language production record.** | Every production ladder, in every language — and the [procedure §1] single-language session rule on its production half. | 4.7, 4.8 |
| **B-16** | **No `ClipResult.failure`; `raise_for_status()` aborts the run** (R-7). | Every hypothesis whose expected outcome is "it does not run". | 4.3 |
| **B-17** | **The runtime contract has no streaming method** — no chunk envelope, no partial-result type, one POST. | Every streaming session; `partial_revision_rate` is RESERVED **by construction**, not by oversight. Blocked behind M8, not behind a prerequisite. | 4.12 |
| **B-18** | **Artifact fetch is unauthenticated by construction** — `ArtifactStore._download` and `fetch.materialize_clip` pass no headers. Gated artifacts exist in the candidate universe. | Any session on a gated artifact: **cannot be downloaded, therefore cannot be measured, therefore cannot be scheduled**. | 5.2 |
| **B-19** | **`ArtifactSpec` is a flat, enumerated file list** — no directories, no globs, no external-data side files. | Any multi-graph / external-data artifact. | 5.4 |
| **B-20** | **No remote-code security review process exists**, and our isolation discipline has never had to model vendor code executing in-process. | Any artifact requiring `trust_remote_code`. | 5.3 |
| **B-21** | **No noise/augmentation tooling and no `AudioCondition` field on `EvalClip`.** | The entire robustness class — which [corpora §4.1] nevertheless makes **mandatory in every C2**. | 4.9 |
| **B-22** | **No timestamp scoring.** `TranscriptionSegment` is populated by the adapter and transported; the runner reads `output.text` only. Timestamps are **transported and discarded**, and the Gate 3 register contains **no alignment metric family**. | Any timestamp-quality claim. Presence is recordable (`timestamp_source`); quality is not. **This is a prerequisite, not a licence to invent a metric.** | 4.5 |
| **B-23** | **No GPU profile is schedulable**: the decision itself is open, accelerator sampling does not exist, and `accelerator_memory_peak_mib` is RESERVED — so even an approved GPU session records no accelerator memory. | Every GPU-shaped session. | 3.2, 3.3 |

### 3.3 Blockers on the campaign *terminating* in anything

| # | Blocker | Stops |
|---|---|---|
| **B-24** | **[FACT]** **F-M5-3 is open** — no absolute per-language quality bars exist, so `enablement_test` passes `max_word_error_rate=None` and returns **REFUSED for every language regardless of results**, by design. | Any rung change. |
| **B-25** | **[FACT]** **F-M5-8 / F-M5-6 are open** (Hindi / Arabic speech corpora), so the ADR-0027 corpus precondition **BLOCKS before the bar is even reached**. | Any rung change in Hindi or Arabic. |
| **B-26** | **[FACT]** **No promotion, regression-report, or switching-report CLI exists.** `promotion.py` is reachable only from Python or a test. Plus R-8: the artifact-version upgrade case is BLOCKED by the guard. | Every derived output artifact the record schema defines (§§2–5). |
| **B-27** | **[FACT]** **A challenger cannot be quality-evaluated without first being routed in the registry** — `resolve()` is an exact lookup that never falls back, and `_require_hosted` refuses to record against a runtime not hosting the resolved artifact. Today the manifest names **one artifact on one deployment** for all three STT languages. | Every quality session on every challenger. This is the Layer-0 circularity's mechanical twin (§6). |
| **B-28** | **[FACT]** **Each new serving library needs an isolation-denylist entry**, an optional extra, and an `engines/` adapter. `fairseq2`, `nemo`, `moshi`, `peft`, `mistral_common`, `onnx` are **not** on the denylist today. **[FACT — ADR-0026]** deployments may not be engine-named, so stack-grouped sessions must not surface stack names as deployment names. | Every session on a stack we do not already run. |

---

## 4. Open founder decisions

Enumerated precisely, each with what it unblocks and what it costs to defer. **[FACT — the
prerequisite register's own note]** prioritisation among these is deliberately absent from the
register: *priority is the founder's*. Research states the decisions; it does not order them.

### 4.1 Must be answered before any plan can be approved at all

| # | Decision | Notes |
|---|---|---|
| **D-1** | **Ratify the Gate 3 reconciled vocabulary** — the metric-name table, `AudioCondition` (tuple-valued, coarse at v1), `duration_bands@v1`, and the `TextCategory` no-append rule. (0.1) | Append-only; **first landing is permanent**. Must land as **one change** together with the single golden-test edit, the uniqueness assertion (4.13) and the withdrawal mechanism (4.14). Deferring costs nothing today and everything after the first record is written. |
| **D-2** | **Accept that recognition evidence extends `EvalRun`, with the registry reaching across rather than forking.** (0.2) | The alternative — a recognition-only registry — makes name collisions undetectable instead of merely awkward. |
| **D-3** | **Approve a benchmark plan** naming corpus, metrics, hardware and baseline. (0.3) | This is the Gate 4 act itself, and it is the subject of §6's circularity. |
| **D-4** | **THE STATUS QUESTION.** **[FACT]** All twelve PASS lineages are `Researching`. **[FACT — framework §3]** `Approved for Benchmark` is granted by the **founder**, and the legal transition is `Promising → Approved for Benchmark` — so a Promising review (framework Gate 3) must precede it, and **no candidate has had one**. | Three sub-questions, and only the founder can answer any of them: **(a)** does the Promising review happen per candidate before plan approval, or does the founder approve a plan covering candidates that have not passed Promising, recorded as an explicit deviation? **(b)** **[FACT]** framework §3 lists *score per FOUNDATION_MODELS §1* among the minimum evidence for Promising, and **[FACT, verified 2026-08-05]** the twelve Gate 2 dossiers use a 16-section structure that contains **no weighted score and no Recommendation section** — so either scoring work is commissioned, or the requirement is waived in writing. This applies identically to all twelve; it is a process gap, not a judgement about any candidate. **(c)** whichever path is chosen, it is **appended** to the ledger — never edited in. |

### 4.2 Gate specific classes of session

| # | Decision | Unblocks |
|---|---|---|
| **D-5** | **Does a GPU / accelerator tier exist at all?** (3.2) | Every GPU-shaped session. Two honest riders: even after a YES, **3.3 (accelerator sampling) is a BUILD** — **[FACT]** no `nvidia`/`cuda`/`nvml` reference exists anywhere in `ml/evaluation` — and `accelerator_memory_peak_mib` is **RESERVED**, so an approved GPU session **still records no accelerator memory**. This is a decision about our serving economics, not about any candidate. |
| **D-6** | **Define the CPU reference machine and its `hardware_class` label** (3.1), and **the hardware-succession bridging-run policy** (3.5). | The only hardware profile that exists today, and every comparison that crosses a machine. |
| **D-7** | **The CC-BY attribution mechanism versus an engine-hiding public API.** (5.1) | **Applies to a licence CLASS — every artifact under a CC-BY-class licence — and never to named candidates.** **[FACT]** it is a **Gate 5 pre-adoption condition and explicitly does not block measurement**; recorded here so it is not mistaken for a scheduling blocker. |
| **D-8** | **Authenticated artifact fetch** (5.2) — two parts: *may* we accept credentialled fetch and gated-distribution access terms at all (DECIDE), and then the BUILD. | Every gated artifact — which today cannot be downloaded, therefore cannot be measured. |
| **D-9** | **Remote-code security review process.** (5.3) | Every artifact requiring `trust_remote_code`. **[INFERENCE]** structurally this is the espeak-ng failure mode in a new shape: permissive weights, unverified in-process code — and the licence screen alone does not catch it. |
| **D-10** | **Consent, licensing and PII policy for recorded audio** (2.8); **speaker roster and pseudonymisation scheme** (2.7); and **whether corpus audio is committed to this repository at all** (the `corpus-inbox/` gitignore defect, plus `publication_status`). | All corpus collection. The third part is also a **contamination** decision (R-3): publication is irreversible. |
| **D-11** | **Empty-reference probes: one shared probe-only corpus, or per-language probes?** (2.9, [corpora §4.2]) | Decides whether a **computed** cross-language hallucination delta is possible at all: byte-identical probes carried across language corpora may be read side by side but **never differenced**, because the predicate blocks on corpus identity *and* language. **[FACT]** the current probe set also has silence and tone but **no music probe**, against a spec requiring ≥3 in every tier. |
| **D-12** | **May we measure an artifact converted by a third party** (community quantizations, exports we did not perform)? | **[INFERENCE]** measuring one means inheriting a conversion whose provenance carries its own licence verdict (6.4). A DECIDE **before** scheduling, not after. |
| **D-13** | **May an engine own VAD?** | **[FACT]** our architecture places VAD in the pipeline behind a Protocol; at least one registered lineage bundles it in the engine. `ExecutionContext.vad_owner` exists to *record* the answer; it does not make it. It changes what a probe measures, so it is a comparability question, not a preference. |

### 4.3 Gate the campaign ending in anything

| # | Decision | Unblocks |
|---|---|---|
| **D-14** | **Absolute per-language quality bars** (F-M5-3). | Until set, `enablement_test` **REFUSES every language regardless of results**. |
| **D-15** | **Corpus ownership for Hindi and Arabic** (F-M5-8, F-M5-6) — collect, purchase, or adopt. | The ADR-0027 corpus precondition, which blocks *before* the bar is reached. |
| **D-16** | **Contamination declaration procedure** (5.5) and the publication status of our corpora. | Validity V-8 on every record. |
| **D-17** | **Funding order across the prerequisite register.** | The register is deliberately unprioritised — dependency order only. Nothing in it is scheduled until the founder orders it. |

---

## 5. The gate-numbering discrepancy — recorded plainly

**[FACT]** [RESEARCH_FRAMEWORK.md §4](RESEARCH_FRAMEWORK.md) defines its own numbering, and the
working session numbering has drifted from it. The two are not the same, and this document does not
pretend they are.

| Framework numbering (governing) | Session working numbering (as used in file names and prompts) |
|---|---|
| Gate 0 — Intake | Gate 0 — intake sweep *(agrees)* |
| Gate 1 — Licence screen | Gate 1 — licence screen *(agrees)* |
| Gate 2 — Desk research / dossier | Gate 2 — desk research *(agrees)* |
| **Gate 3 — Promising review** (research review; grants `Promising`) | **"Gate 3" — benchmark methodology design** *(a different act entirely; grants nothing)* |
| **Gate 4 — Benchmark plan** (founder approves; grants `Approved for Benchmark`) | **"Gate 4" — campaign planning** *(agrees in substance; this document)* |
| **Gate 5 — Adoption recommendation** (founder approves; grants `Approved for Adoption`) | **"Gate 5" — execute the campaign** *(a different act entirely)* |

**Two consequences, recorded rather than hidden:**

**(a) No candidate holds `Approved for Benchmark`, and none can today.** **[FACT]** all twelve PASS
lineages are `Researching` in the ledger; **[FACT]** the only legal transition into `Approved for
Benchmark` is from `Promising`; **[FACT]** no Promising review has been performed. A campaign plan
may therefore be **written** for them — that is what Gate 4 is — but **it cannot be executed** until
statuses move through the founder gate. Every session in the plan carries a status precondition,
and this is not a formality: it is the difference between a plan and a benchmark. What *does* exist
for all twelve is the evidence a Promising review consumes — a dossier, a dated licence verdict, and
a falsifiable hypothesis against a named baseline. What is missing is **the review itself, the
weighted score the framework names as minimum evidence, and the founder's act** (see D-4).

**(b) Research never owns benchmark execution.** **[FACT — framework §1]** measurements are produced
by the evaluation plane (`ml/evaluation`), and its records are the only numbers research may cite.
So "Gate 5 = execute" in the session numbering is doubly misleading: it names an act research does
not own, using a number the framework has already assigned to the adoption recommendation. Every
"session" this campaign specifies is an **engineering** session; research authored the hypothesis
and must not hold a lever over which measurements count.

**[INFERENCE] Recommended remedy — a naming decision, not a process change:** the ledger and all
permanent documents adopt the **framework numbering**; session-working numbers survive only inside
session titles, each carrying this mapping table by reference. Renumbering the framework to match
the drift would be the wrong direction: the framework is IN FORCE and founder-approved; the drift
is not.

---

## 6. The circularity

**[FACT — prerequisite register, Layer 0]** Stated there and restated here because it governs the
whole campaign:

> Gate 4 requires a plan naming a corpus, metrics, hardware and baseline **that exist**. Most of
> them do not yet exist, and this register will not be funded without a plan. **Something must be
> approved before it is fully specified, or nothing starts.**

**It has at least two mechanical twins in the code, both verified:**

1. **Registry admission (B-27).** A challenger cannot be quality-evaluated without first being
   *routed* in the registry — and the production ladder that a route's promotion requires is the
   ladder only a registered route can fully measure. **[FACT]** `bench` can run against an
   unregistered candidate on slot declaration alone, but then the gateway-overhead phase is skipped
   with `--api-key ""`, which silently drops overhead, `prd_p95_actual_ms` and the PRD verdict.
2. **Ruler before corpus (B-12).** The languages with the most product urgency have the deepest
   prerequisite chains, because a ruler that does not exist must precede audio that does not exist,
   which must precede a baseline that does not exist.

**Research cannot cut this.** **[FACT — framework §1]** the causal chain is one-way — *research →
evidence → recommendation → founder decision → engineering adoption* — and approving expenditure is
not on research's side of it. Three cuts are available to the founder; this document names them and
chooses none:

- **Approve the plan as a specification, unlock execution per session.** The plan is approved as
  the campaign's permanent design; each session becomes executable only when its own named
  prerequisites land. Cost: the approval grants `Approved for Benchmark` to candidates whose
  sessions may not run for months, and status decay (A-13) then applies to their licence verdicts.
- **Fund a prerequisite tranche first, plan afterwards.** Cost: the register is unprioritised by
  design, so the founder is ordering ~44 items without the plan that would explain which matter
  most — and the register will decay while it is worked.
- **Approve a reduced plan scoped to what exists today.** Cost: honest scope is close to nothing
  (§7), and a reduced plan risks becoming the campaign by default rather than by decision.

---

## 7. Execution readiness

**No candidate is named, ordered, or preferred in this section.** Readiness is a property of *our
apparatus*, and every statement below is true for every candidate equally.

### 7.1 What could run tomorrow

**Producing a valid record: nothing.** Not one session, in any language, against any artifact —
including our own incumbent.

The precise reason, worth stating because it is more useful than the headline: a re-run of the
incumbent on `stt-eval-seed@v2` **is** possible tomorrow — the harness works, the artifact is
pinned, the route is registered. It would produce a record of exactly the shape of the two committed
M5 records. Under [methodology §7] that record is **invalid**, failing at minimum:

| Condition | Why it fails today |
|---|---|
| **V-1** reproducibility set complete | No environment block, no thread config, no `hardware_class`, no `session_id`, no `methodology_version` |
| **V-4** every metric registered and ACTIVE | **Zero** Gate 3 metric names are registered; `EvalRun` has no `metrics` field |
| **V-5** minimum corpus size | 2 natural clips, 44 reference words, against ≥100 cases |
| **V-7** normalisation profile recorded and round-trip checked | `NormalizationProfile` does not exist |
| **V-8** contamination declared | No field |
| **V-9** warm-up class recorded and scoped | W1 does not exist in the harness |

**So the honest verdict is:** *what can run tomorrow is the pre-methodology run we already have.*
Repeating it is legitimate engineering — it is not a benchmark under this methodology, and the plan
must not let it be cited as one.

**What is genuinely available tomorrow, and is not benchmarking:** founder decisions (§4), desk
verification that needs no measurement (6.3 and 6.4 remain open; 6.1 and 6.2 were discharged during
this Gate 4 groundwork), and engineering builds from the register. That is real, valuable work. It
is not a measurement.

### 7.2 Distance to executability, by class of session

Distance is counted in **named prerequisite items**, not in effort. A one-item chain can be a
month's work; a six-item chain can be a week's. **[INFERENCE]** throughout.

| Class of session | Distance | Named items |
|---|---|---|
| **Ruler validation** — the V-7 control-string round-trip for the normalisation profiles. **No model, no audio, no candidate.** | **Shortest chain in the campaign.** | 0.1 · 1.4 (+1.1, 1.2 for the non-Latin profiles) |
| **English empty-reference probes** (pipeline route) | ~5 | 0.1 · metric registration + 4.13 + 4.14 · 2.9 probe decision · 3.1 |
| **English empty-reference probes** (engine route) | ~6 | the above + a `research_harness` route capability + 4.3 |
| **English liveness / cost, single artifact** | ~8 | the above + **2.1 English C1 (10–20 clips — does not exist)** · 4.6 · 4.4 · 3.4 |
| **English production ladder** | ~10 | + 4.7 · 4.8 · 4.10 · 4.11 · the ≥20-sample rule enforced |
| **English quality claim** | ~15 | + **2.1 English C2 (≥100)** · 2.4 · 2.5 · 2.7 · 2.8 · 4.2 · contamination declaration |
| **Hindi anything that scores a reference** | English chain **+5**, and the ruler items are **hard-ordered first** | 1.1 · 1.3 · 4.1 · 2.2 · 4.6 |
| **Arabic anything that scores a reference** | Longest chain in the campaign | 1.2 · 1.3 · 4.1 · **2.3 (zero clips exist)** · **2.6 — a person, not a build** · 2.4 · 2.5 |
| **Robustness / C3** | Not yet chained | 4.9 · `AudioCondition` on the clip · C3 corpora — and **[FACT]** *no* Gate 2 hypothesis targets these conditions, while [corpora §4.1] makes them mandatory in every C2. The corpus spec governs; the hypothesis set does not shrink it. |
| **Timestamp quality** | Blocked, not chained | 4.5 — **there is no alignment metric in the register**. A prerequisite, never a licence to invent one. |
| **Streaming** | Blocked at the contract, not at the register | 4.12 + M8. The contract has no streaming method; `partial_revision_rate` is RESERVED by construction. |
| **Any GPU session** | Blocked on a founder decision, then a build | 3.2 → 3.3 — and accelerator memory is unrecordable even then. |
| **Regression / switching reports** | Blocked on inputs that do not exist | Two comparable records (we have one baseline, in one language, on a corpus that fails V-5) + fixing `not_a_replacement` (R-8) + a CLI (B-26). |
| **Anything terminating in a rung change** | Blocked on founder rulings | F-M5-3 · F-M5-8 / F-M5-6. `enablement_test` REFUSES today by design. |

### 7.3 Why the ordering is what it is

**[INFERENCE, confirmed against the register]** The campaign's ordering — English, then Hindi, then
Arabic, then streaming, then stress, then regression — is a **prerequisite-depth** ordering and
nothing else, and the table above is its justification:

- **English is shallowest** because it is the only language with an incumbent baseline *and* a
  corpus, however thin — and even it needs a C1 built before its cheapest session.
- **Hindi is second** because its ruler build is smaller than Arabic's and its corpus need is
  monolingual; the ruler is nonetheless hard-ordered before any recording.
- **Arabic is third** because its chain is ruler **plus** corpus **plus** a human verifier, from a
  starting position of zero clips of any kind.
- **Streaming is after all three** because it is blocked at the runtime contract, not at the
  register.
- **Regression is last** because it compares against results that do not exist yet.

**None of that ordering says anything about any candidate**, and no reader should infer otherwise.
Eleven of the twelve lineages have **no CPU measurement of any kind in our possession**; the twelfth
is our incumbent. There is nothing to rank, and this campaign exists precisely because there is not.

---

*Change log: 0.1 (2026-08-05) — initial Gate 4 readiness review. Assumptions, risks, blockers,
founder decisions, the gate-numbering discrepancy, the circularity, and an execution-readiness
verdict. Nothing here executes, ranks, scores, compares, or recommends.*
