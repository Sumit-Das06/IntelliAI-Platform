# Gate 3 — Open Prerequisites for STT Benchmarking

| | |
|---|---|
| **Status** | Dated register, 2026-08-05. **Decays** — re-verify before use. |
| **Role** | Everything that does not exist yet and blocks execution of the benchmark methodology. |
| **Prioritisation** | **Deliberately absent.** Ordering below is *dependency* order only. Priority is the founder's. |
| **Gate note** | Nothing here recommends, de-prioritises, or judges any candidate. Items apply to artifact **classes**, never to named lineages. |

**Types:** **BUILD** (engineering) · **COLLECT** (data) · **DECIDE** (founder) · **VERIFY** (research).

---

## Layer 0 — must be settled before anything downstream is specified

| # | Item | Type | Blocks |
|---|---|---|---|
| 0.1 | **Ratify the reconciled vocabulary** — the metric-name table, `AudioCondition`, `duration_bands@v1`, and the no-append rule for `TextCategory`. These are append-only; first landing is permanent. | DECIDE | every schema and corpus item below |
| 0.2 | **Accept that recognition evidence extends `EvalRun`**, with the registry reaching across rather than forking | DECIDE | record schema, all metrics |
| 0.3 | **Approve a benchmark plan** (Gate 4) naming corpus, metrics, hardware and baseline | DECIDE | any execution at all |

**A circularity the founder must cut (recorded, not resolved):** Gate 4 requires a plan
naming a corpus, metrics, hardware and baseline **that exist**. Most of them do not yet
exist, and this register will not be funded without a plan. Something must be approved
before it is fully specified, or nothing starts.

---

## Layer 1 — rulers before data

These precede corpus collection. **This ordering is not a preference; it is a safety
requirement.**

| # | Item | Type | Blocks |
|---|---|---|---|
| 1.1 | **`devanagari@v1` normalisation profile** | BUILD | all Hindi measurement |
| 1.2 | **`arabic_orthographic@v1` normalisation profile** (enumerated codepoint folds — a category-M fold destroys Hindi) | BUILD | all Arabic measurement |
| 1.3 | **Guard the empty-reference path** so a non-Latin reference cannot be silently scored | BUILD | Hindi and Arabic recording |
| 1.4 | `unicode_generic@v1` and `ascii_en@v1` registered and pinned | BUILD | English continuity |

### Status update — 2026-08-05, engineering milestone B2

Recorded rather than edited into the table above: this is a dated register and what it
said on the day it was written stays said.

| # | State | Notes |
|---|---|---|
| **PR-1.1** | **Discharged, under a different name** | The corrected Devanagari ruler differs from `unicode_generic@v1` by exactly one rule — format characters (Cf) removed rather than spaced — and that correction is script-agnostic. Under the founder ruling that *a profile is an evidence object, not a language object*, naming it `devanagari@v1` would assert a language binding it does not have. Landed as **`unicode_generic@v2`**; Hindi binds to it. |
| **PR-1.2** | **Deferred, deliberately** | `arabic_orthographic@v1` requires an enumerated fold table (tashkeel, alef variants, tatweel). Those are linguistic decisions with permanent evidential consequences, item 2.6 already names a native verifier as a prerequisite, and there are zero Arabic clips to validate against. `profile_for("ar")` refuses rather than borrowing another language's ruler. |
| **PR-1.3** | **Discharged** | A profile that normalises a *declared* reference to nothing now raises `RulerFailureError` instead of scoring. Per founder ruling, this produces a Determination, never a numeric metric. |
| **PR-1.4** | **Discharged** | Both registered and pinned by golden test. `ascii_en@v1` wraps `normalize_words` unchanged; `unicode_generic@v1` pins `speech_normalize` **including its Cf defect**, because it is the ruler behind the committed synthesis baselines and a released version may never change meaning. |

**Numbering.** Normalization-profile work is **PR-1.1–PR-1.4**, never "D-2".
[gate4-review.md](gate4-review.md) §4.1 already assigns **D-2 = recognition evidence extends
`EvalRun`, registry reaching across rather than forking** — which milestone B1 satisfied by
building one registry with capability scoping per spec instead of per-namespace registries.
This project has renumbered twice already (the framework/session gate drift, and the `P<n>`
collision that forced `PH<n>`/`HW<n>`/`PR<n.n>`); a third overload is not worth the
convenience.

### The live hazard justifying this ordering

**[FACT, verified at source]** `normalize_words` strips to `[^a-z0-9\s']+`
([wer.py:17](../../ml/evaluation/src/intelliai_evaluation/wer.py#L17)). A Devanagari or
Arabic reference therefore normalises to nothing → `reference_words == 0` → `ClipResult.wer`
returns `None` **silently** and `hallucinated_words` returns the **whole hypothesis**
([results.py:43-52](../../ml/evaluation/src/intelliai_evaluation/results.py#L43-L52)).

A perfectly transcribed Hindi clip would be committed to an **append-only** ledger as *N
hallucinated words*. Not a crash — plausible, wrong, permanent evidence.

**Until 1.1–1.3 land, Hindi and Arabic audio must not be run through the evaluation path.**

**Not yet verified:** whether any committed record already contains this corruption. There
is a signal it was fenced by convention — the released `stt-eval-seed@v2` declares its `hi`
slice carries no natural speech and is not a quality claim. **VERIFY** item.

---

## Layer 2 — corpora

**[FACT] Current holdings:** the entire STT natural-speech corpus is **one speaker, one
~11-second utterance, 21 reference words, one language**, delivered twice across two
containers. **Zero Arabic clips of any kind — not even a probe.** The TTS text corpus is 25
cases (en/hi/mixed, no Arabic), below the ≥100 condition.

| # | Item | Type |
|---|---|---|
| 2.1 | English C1 / C2 / C3 | COLLECT |
| 2.2 | Hindi C1 / C2 / C3 (after 1.1, 1.3) | COLLECT |
| 2.3 | Arabic C1 / C2 / C3 (after 1.2, 1.3) | COLLECT |
| 2.4 | Reference convention sheet, per language | BUILD |
| 2.5 | Double-transcription and reconciliation capacity | COLLECT |
| 2.6 | **Arabic dialect verifier** — a person competent in the dialects covered | COLLECT |
| 2.7 | Speaker roster and pseudonymisation scheme | BUILD |
| 2.8 | Consent, licensing and PII policy for recorded audio | DECIDE |
| 2.9 | Empty-reference probe set, shared or per-language (§4.2 decision) | BUILD |

### Founder homework — three live problems

**[FACT]** The recording protocol at `ml/evaluation/README.md` (5 EN + 5 HI passages →
`ml/evaluation/corpus-inbox/`) has three defects:

1. **The recordings do not exist.**
2. **`corpus-inbox/` is not gitignored** (only `data/` is), despite the protocol describing
   it as gitignored — so recorded audio would be committed to the repository.
3. **The README describes a `v2` that does not exist.** The released `stt-eval-seed@v2` is
   the M5 probe set, not the README's recordings-v2. Immutability forces the recordings to
   v3+.

Also: **`EvalClip` has no local-path source**, so the homework is blocked by schema even
once recorded (item 4.6).

---

## Layer 3 — hardware and environment

| # | Item | Type |
|---|---|---|
| 3.1 | Define the CPU reference machine and its `hardware_class` label | DECIDE |
| 3.2 | Decide whether a GPU/accelerator tier exists at all | DECIDE |
| 3.3 | Accelerator sampling capability (**[FACT]** no `nvidia`/`cuda`/`nvml` reference exists anywhere in `ml/evaluation`) | BUILD |
| 3.4 | Thread-configuration capture (no such field exists today) | BUILD |
| 3.5 | Hardware-succession bridging-run policy | DECIDE |

---

## Layer 4 — harness

| # | Item | Type |
|---|---|---|
| 4.1 | `cer_unicode` implementation (**[FACT]** CER is named in PRD §10 and `ml/README.md`, implemented nowhere) | BUILD |
| 4.2 | S/I/D rate metrics from the existing `align_words` core | BUILD |
| 4.3 | `ClipResult.failure` field (**[FACT]** absent today; three benchmark hypotheses concern candidates failing to run) | BUILD |
| 4.4 | `store.ensure` timing (untimed today; two registered metrics unrecordable without it) | BUILD |
| 4.5 | Timestamp scoring — timed references and an alignment metric family (**[FACT]** `TranscriptionSegment` exists in the contract but the runner reads `output.text` only; timestamps are transported and discarded) | BUILD |
| 4.6 | `EvalClip` local-path source | BUILD |
| 4.7 | Language parameter in the production ladder (**[FACT]** `bench` sends none, while declaring `hi` cost 9.4× on identical audio) | BUILD |
| 4.8 | Per-language ladder, per-language production record | BUILD |
| 4.9 | Noise/augmentation tooling (**[FACT]** no `snr`/`augment`/`babble`/`reverb` reference exists) | BUILD |
| 4.10 | 503 discriminator — `overloaded` vs `not_ready` (status code alone matches both; the body's `type` is never parsed) | BUILD |
| 4.11 | `_require_hosted`-equivalent guard on `bench` | BUILD |
| 4.12 | **Streaming harness** — the runtime contract has **no streaming method**; every streaming metric is RESERVED until it exists | BUILD |
| 4.13 | Registration-time uniqueness assertion on metric names | BUILD |
| 4.14 | `MetricSpec.status` / `superseded_by` + write-time `assert_recordable()`, keeping the read path permissive | BUILD |

**4.14 is load-bearing.** **[FACT]** `_require_registered` is a pydantic `field_validator`,
which runs on **every read**. Without this change, withdrawing a wrong metric makes every
historical record citing it unparseable — breaking the charter that readers written in five
years must parse records written today.

---

## Layer 5 — policy and process

| # | Item | Type |
|---|---|---|
| 5.1 | **CC-BY attribution mechanism** vs an engine-hiding public API. Applies to **any artifact under a CC-BY-class licence**. It is a Gate 5 pre-adoption condition and **does not block measurement**. | DECIDE |
| 5.2 | **Authenticated artifact fetch** (**[FACT]** `ArtifactStore._download` and `fetch.materialize_clip` pass no headers — unauthenticated by construction; gated artifacts exist in the candidate universe) | BUILD |
| 5.3 | Remote-code security review process | DECIDE |
| 5.4 | Multi-file / external-data artifact pinning | BUILD |
| 5.5 | Contamination declaration procedure | BUILD |

---

## Layer 6 — verification items

| # | Item | Type |
|---|---|---|
| 6.1 | Whether any committed record already contains empty-reference corruption (Layer 1) | VERIFY |
| 6.2 | `_comparability`'s actual behaviour on cross-corpus probe comparison | VERIFY |
| 6.3 | Whether the existing `prd_p95_actual_ms` misnomer affects any published verdict | VERIFY |
| 6.4 | Per-candidate licence re-verification at Gate 5 (all Gate 1 verdicts decay) | VERIFY |

---

## Summary

Roughly **60 open prerequisites** across six dependency layers. The distribution matters more
than the count: a large share are **DECIDE** and **BUILD** items about *our own
infrastructure*, not about models. **[FACT]** We hold exactly one CPU measurement in the
entire candidate universe, and one 11-second natural-speech clip in one language.

The methodology is designed to survive for years. Executing it currently requires
prerequisites that do not exist — and the largest of them is a corpus, in three languages,
that no model research can substitute for.

*This document is a dated register. It decays. Re-verify before use.*
