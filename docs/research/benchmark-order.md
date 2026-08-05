# IntelliAI STT Benchmark Campaign — Execution Order

| | |
|---|---|
| **Status** | PROPOSED (Gate 4 design, 2026-08-05) — becomes IN FORCE only with the campaign plan it belongs to, on founder approval. **Received an orchestrator gate-discipline scan only; no independent adversarial verification ran** (see [gate4-review.md](gate4-review.md) verification gap). |
| **Version** | 0.1 |
| **Nature** | PERMANENT reasoning, temporary sequence. The **rule** in §1 is intended to outlive this campaign; the **order** in §7 is what the rule returns when applied to the register dated 2026-08-05. Re-derive; never copy. |
| **Role** | Why the campaign's phases run in the order they do, what each phase owes the next, what would legitimately change the order, and the mechanism by which ordering confers no advantage on any candidate. |
| **Companions** | [Methodology](STT_BENCHMARK_METHODOLOGY.md) · [Record schema](STT_BENCHMARK_RECORD.md) · [Procedure](STT_BENCHMARK_PROCEDURE.md) · [Environment spec](STT_BENCHMARK_HARDWARE.md) · [Corpora](STT_BENCHMARK_CORPORA.md) · [Open prerequisites](2026-08-05-stt-gate3-prerequisites.md) |
| **Gate discipline** | This document plans. **It executes nothing.** No candidate is scored, ranked, compared, or recommended — not by statement, not by ordering, not by emphasis. |

Every statement below is labelled **[FACT]** (verified in this repository or at a cited
source, dated), **[CLAIM]** (external, unverified), or **[INFERENCE]** (reasoning).

---

## 0. Preliminaries that bound this document

### 0.1 What ordering is, and what it is not

An execution order is a **partial order over benchmark sessions**: a statement of what may
not precede what. It is not a schedule, not a staffing plan, and not a priority list. It
allocates *dependency*, and dependency only. Calendar, parallelism and effort belong to the
engineering sessions that execute via `ml/evaluation` — per
[RESEARCH_FRAMEWORK §1](RESEARCH_FRAMEWORK.md), research never owns benchmark execution.

### 0.2 The gate-numbering discrepancy, recorded rather than reconciled

**[FACT]** [RESEARCH_FRAMEWORK §4](RESEARCH_FRAMEWORK.md) numbers its gates:
Gate 3 = **Promising review** (grants `Promising`), Gate 4 = **benchmark plan** (founder
approval grants `Approved for Benchmark`), Gate 5 = **adoption recommendation**.

**[FACT]** The working session numbering has drifted: "Gate 3" was used for methodology
design (the six `STT_BENCHMARK_*` documents), and "Gate 5" is being used to mean *execute*.
The numbers do not match. This document does not pretend they do.

Two consequences that bear directly on ordering:

**(a) No candidate currently holds `Approved for Benchmark`.** **[FACT]** All twelve Gate-1
PASS lineages are `Researching` in [MODEL_LEDGER.md](MODEL_LEDGER.md), and none has passed a
Promising review — which is the framework's actual Gate 3 and has not been performed. A
campaign plan, and this ordering, may be **written** for them. Neither may be **executed**
until statuses move through the founder gate. The order below therefore describes a sequence
that is currently unstartable, and says so.

**(b) Research does not own execution.** **[FACT]** Framework §1 places benchmark *execution*
outside the research programme: measurements are produced by the evaluation plane, and its
records are the only numbers research may cite. This document orders sessions; it does not
commission them, cannot start them, and confers no authority over whether they are funded.

### 0.3 Exclusions that hold throughout

**[FACT]** Four lineages are BLOCKED at Gate 1 — IndicWhisper, Zipformer/sherpa-onnx
checkpoints, MOSS-Transcribe-preview-2B, ARK-ASR-3B. Work on them is halted pending named
clarifications. They appear in **no** phase, no group and no session below, and their absence
is a licence fact, not a judgement about them.

---

## 1. The ordering rule

State the rule first, so the sequence in §7 is *derived* rather than asserted, and so a
campaign in 2029 can re-derive its own sequence instead of inheriting ours.

> **Order benchmark sessions by prerequisite depth; among sessions of equal depth, by
> serving-stack setup cost; and never place a session before evidence it must read.**

Applied lexicographically:

**Criterion 1 — prerequisite depth.** The length of the chain of things that must exist
before the session can write its **first valid record**. Measured in dependency layers of
the [open-prerequisites register](2026-08-05-stt-gate3-prerequisites.md) (Layers 0–6), not in
effort, cost, or calendar time. A session whose deepest unmet prerequisite is Layer 1 is
shallower than one whose deepest unmet prerequisite is Layer 2, regardless of how many items
each has at its own layer.

**Criterion 2 — serving-stack setup cost, amortised.** Among sessions of equal depth, order
by the cost of standing up the serving stack, and group sessions that share one. **[FACT]**
The candidate universe spans CTranslate2, ONNX Runtime, `transformers`+PEFT, NeMo, fairseq2,
vLLM and moshi/Rust ([STT_BENCHMARK_HARDWARE §5](STT_BENCHMARK_HARDWARE.md) records the same
span as the reason `StackIdentity.serving_stack` is a free string). **[INFERENCE]** The
dominant per-session cost is standing the stack up, not running the corpus through it, so
grouping by stack and ordering groups by how many sessions share them is the only cost axis
that is a property of *our infrastructure* rather than of any candidate.

**Criterion 3 — dependency on prior evidence.** A session that must read another session's
records cannot precede it. This is a hard constraint, not a tiebreak; it is listed third only
because it is rarely the binding one. Where it binds — regression, switching, bridging — it
dominates the other two absolutely.

### 1.1 The two negative clauses, which are load-bearing

**Nothing about a candidate enters the ordering function.** Not expected quality, not
leaderboard standing, not parameter count, not release date, not organisational prestige, and
not how interesting the hypothesis is. **[FACT]** Framework §2 already makes the sharpest
version of this law: *"'Newer' is a fact, never an argument."* Ordering by interest would be
a covert ranking — the exact output Gate 4 is forbidden to produce — and it would also be
worse engineering, because it optimises a variable (curiosity) that no cost model contains.

**Founder research priorities order attention, not measurement sequence.** **[FACT]**
Framework §16 states it in its own words: priorities *"order research attention; they never
skip gates or lower the evidence bar."* §3.2 below deals with the case where the two orders
happen to agree.

### 1.2 Why depth is the first criterion, not the cheapest-first criterion

**[INFERENCE]** The intuitive rule would be "cheapest session first". It is wrong here, and
the reason is specific to an append-only evidence ledger.

**[FACT, verified at source]** `normalize_words` strips to `[^a-z0-9\s']+`
([wer.py:17](../../ml/evaluation/src/intelliai_evaluation/wer.py#L17)). A Devanagari or
Arabic reference normalises to an empty word list; `ClipResult.wer` then returns `None`
**silently** and `hallucinated_words` returns the **entire hypothesis**
([results.py:43-52](../../ml/evaluation/src/intelliai_evaluation/results.py#L43-L52)). A
perfectly transcribed Hindi clip is committed as *N hallucinated words*.

That failure has three properties that together decide the rule:

1. **It is silent.** No exception, no warning, no missing field. The record validates.
2. **It is plausible.** "This candidate hallucinated" is a believable finding, so it does not
   trip a reviewer's disbelief.
3. **It is permanent.** Records are append-only by law
   ([methodology §0](STT_BENCHMARK_METHODOLOGY.md), framework §3). A correction is a *new*
   record; the wrong one stays in the ledger forever, and anyone who cited it in between
   cited a falsehood.

So a session run before its prerequisites are met does not produce a *weak* record. It
produces a **wrong and irrevocable** one. Ordering by prerequisite depth is therefore a
correctness requirement, not an efficiency preference — and it is the same
cheapest-kill-first logic the framework already uses between gates (§4: "never spend a later
gate's effort on a candidate that hasn't passed an earlier gate"), applied *inside* a gate,
between sessions.

**[INFERENCE]** Note the asymmetry that makes this rule cheap to obey: a session run *late*
costs calendar time and nothing else. A session run *early* costs the integrity of the
permanent record. The rule is not symmetric because the failure modes are not.

---

## 2. English first

Two independent claims. Neither alone would decide the order; the conjunction does.

### 2.1 English is the only language with an incumbent baseline

**[FACT]** The recognition baseline: `ml/evaluation/stt/results/2026-08-05-intelliai-stt-en.json`,
identity `2026-08-05-intelliai-stt-en-whisper-small-cpu-v1` — `intelliai-stt` / `en` /
`whisper-small@v1` / `cpu-int8` / `stt-runtime` / `stt-eval-seed@v2`, coverage 4 clips /
2 natural / 2 probes / 44 reference words, `is_quality_claim: true`, `judge: null`,
WER 0.000, mean RTF 0.150.

**[FACT]** The production baseline: `ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-docker.json`
— four ladder levels, gateway overhead block, `prd_verdict: PASS`.

**[FACT]** Hindi's committed record (`2026-08-05-intelliai-stt-hi.json`) has coverage
2 clips / **0** natural / 2 probes / **0** reference words, `is_quality_claim: false`,
`overall_wer: null`. It is an honest record of a hallucination probe under a Hindi
declaration, and the M5 documents label it exactly that.

**[FACT]** Arabic has **no record, no corpus, and zero clips of any kind** — not even a probe.
`stt-eval-seed@v2` contains 8 clips: en 4, hi 2, zxx 2, ar 0.

### 2.2 English is the only language with a corpus — and the honest size of it

**[FACT]** `stt-eval-seed@v2`'s English slice is 4 clips, of which 2 are natural speech:
`jfk-flac` and `jfk-wav` — **the same utterance in two containers**, one speaker, ~11 s,
22 reference words per clip, 44 in the slice.

**[INFERENCE]** By the tier definitions in [STT_BENCHMARK_CORPORA §1](STT_BENCHMARK_CORPORA.md)
this is *below* C1 (10–20 clips), and a C1 result "may support **no quality claim**" in any
case. So "English has a corpus" must be read precisely: English has a **corpus lineage** —
a released, immutable, versioned manifest with a governance history and a committed result
citing it. Hindi has a manifest slice with no natural speech; Arabic has nothing. That is the
distinction that matters for ordering, and it is a distinction of *kind*, not of size.

### 2.3 Why the conjunction decides it: a switching test without an incumbent is not a test

Not a metaphor — a mechanical fact about the code that computes the verdict.

**[FACT]** `switching_test(incumbent: EvalRun, candidate: EvalRun)` in
[promotion.py](../../ml/evaluation/src/intelliai_evaluation/promotion.py) is a binary
function typed to two runs. With no incumbent record for a language there is no first
argument: the question cannot be *asked*, let alone answered.

**[FACT]** `_comparability` blocks the comparison outright on `identity_missing`,
`different_language`, or `different_corpus_version`. It returns `Verdict.BLOCKED` with
`comparable=False` — and the module's own docstring explains why that matters: *"'the
candidate lost' and 'we cannot tell' are different answers and collapsing them is how bad
promotions happen."*

**[FACT]** The only other admissible verdict shape is the absolute one, `enablement_test`,
and in Hindi and Arabic it is blocked **twice**, before any number is read:

- `no_natural_speech_in_corpus` — the corpus precondition (ADR-0027 Amendment 3) fires on a
  corpus with no natural-speech clips in the run's language. Hindi and Arabic both trip it
  today (F-M5-8, F-M5-6).
- `no_absolute_bar` — F-M5-3 is unruled, so `max_word_error_rate` is `None` and the test
  refuses **every** language regardless of the numbers, by design.

**[INFERENCE]** Therefore in Hindi and Arabic there exists today **no verdict shape that can
return anything but BLOCKED or REFUSED**, independent of any candidate's actual behaviour. A
session that runs there produces records that no instrument can read. In English, at least
one instrument has both of its arguments.

### 2.4 Being first is not being ready

**[FACT]** A quality claim requires ≥100 cases in the language, and a switching claim
requires ≥100 cases plus the C2 second-judge spot-audit
([methodology §7.1](STT_BENCHMARK_METHODOLOGY.md)). English holds 2 natural clips of one
utterance.

**[INFERENCE]** So the first English session is a **C1 smoke-and-apparatus session that
supports no quality claim by tier definition**, and English's C2 (prerequisite 2.1) is a
COLLECT item exactly as Hindi's and Arabic's are. English is first because its chain is
*shortest*, not because it is *short*. Any reading of this document as "English is ready" is
a misreading, and §11.5 records it as a live tension.

### 2.5 What the English phase produces that every later phase depends on

This is the load-bearing half of "English first". If the phase produced only English numbers,
its position would be nearly arbitrary — numbers do not cross the language boundary by law
([methodology §4](STT_BENCHMARK_METHODOLOGY.md), seven mechanisms). What crosses is
**apparatus**, and all of it is produced here:

1. **The session skeleton, debugged against a known answer.** The startup-lifecycle block,
   the CPU cost block, the concurrency ladder, the gateway-overhead block, and the
   replicate + reversed-order audit are identical in shape for all twelve candidates and all
   three languages. **[INFERENCE]** English is the only place they can be debugged where a
   *known-good* answer already exists — so a surprising number is attributable to the harness
   rather than to a candidate. Everywhere else, harness defect and candidate behaviour are
   confounded and indistinguishable.

2. **The metric register, exercised against a prior value.** **[FACT]** `SPEECH_METRICS`
   registers 16 names today (`round_trip_wer`, `pronunciation_accuracy`, `clipping_ratio`,
   `silence_ratio`, `duration_plausibility`, `time_to_first_audio_ms`,
   `synthesis_latency_ms`, `rtf`, `peak_memory_mib`, `cpu_percent_max`, and six
   listening/human names). **Not one** of the new recognition names in
   [methodology §3](STT_BENCHMARK_METHODOLOGY.md) is registered, and `EvalRun` has no
   `metrics` field to record them into. **[INFERENCE]** English is the only language where a
   newly registered name can be validated against a committed prior number: `wer_ascii` must
   reproduce 0.000 on the JFK slice; `recognition_rtf` must land near the committed mean.
   *A metric that cannot reproduce the incumbent's committed value is a defective metric* —
   and English is the only place that test can be run at all.

3. **The ruler-transition record.** **[FACT]** [Methodology §4.1](STT_BENCHMARK_METHODOLOGY.md)
   makes `wer_unicode` the English primary with `wer_ascii` co-recorded *"in a single
   transition record so the existing baseline stays comparable."* That record is English by
   construction — it *is* the bridge from the 2026-08-03 ASCII ruler to methodology v1. Every
   later reading that traverses the ruler change, in any language, depends on that bridge
   existing and being citable.

4. **`NormalizationProfile` and its V-7 round-trip, first instantiated.** Prerequisite 1.4
   (`ascii_en@v1`, `unicode_generic@v1`) lands here, together with the acceptance check V-7
   machinery. **Stated honestly:** English proves the *mechanism*; it does **not** exercise
   the hazards. **[FACT]** The category-Mn trap (Arabic tashkeel and Devanagari matras are
   both Mn, so a category-M fold that de-diacritises Arabic destroys Hindi) and the
   category-Cf trap (`speech_normalize` maps non-L/M/N to a **space, not nothing**, so
   ZWJ/ZWNJ split words) are exercised only by `devanagari@v1` and `arabic_orthographic@v1`.
   Do not read English V-7 evidence as coverage of them.

5. **The environment record and the `hardware_class` label.** **[FACT]** `hardware_class`
   appears in `docs/` and in **no** Python file in the repository — "same hardware class" is
   a comparability condition stated in prose and unenforced in code, and the one machine we
   have measured on is already spelled three different ways across committed records. 3.1 is
   a founder DECIDE item; the English phase is the first session that must *consume* its
   answer, and every later record's comparability key depends on the same label being used
   from then on.

6. **Per-language production evidence, first made true of an artifact.** **[FACT]** The
   committed production baseline carries no identity, no language and no artifact field at
   all — its language is implicit in the filename of one clip (`clip: jfk-wav.wav`).
   **[FACT]** `bench` sends no language. Prerequisites 4.7 and 4.8 land in the English phase,
   which is where "a production record belongs to exactly one language" stops being a
   sentence in a document and becomes a property of a record.

7. **The declaration-cost control point.** **[FACT]** Declaring a language is itself a
   first-order cost variable. **[CORRECTED 2026-08-05 — the claim originally made here was
   wrong.]** The standing figure is **~9.4×**: `hi` 13698.1 ms against `en` 1462.4 ms
   (RTF 2.740 vs 0.292), **committed** at
   [`2026-08-05-multilingual-baselines.md` §2a](../../ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md)
   as a **median of three runs per declaration**. The 17859/1391 ms pair (12.8×) is a
   *single-sample* comparison and is the weaker measurement. Arabic is indistinguishable from
   English (1389.4 ms). See the ledger correction C-1. **[INFERENCE]** English is where `language_mode` (`explicit` | `auto`) gets
   its first *paired* measurement on a language whose behaviour is otherwise known. That
   pairing is the instrument through which every Hindi and Arabic ladder is subsequently
   read; without it, a Hindi ladder number confounds the candidate with the declaration.

8. **A demonstrated band-establishing procedure.** **[FACT]** [Methodology §6.3](STT_BENCHMARK_METHODOLOGY.md)
   rejects any "non-zero delta is real" rule and returns `no_band_established` until a
   same-identity replicate exists. The English phase produces the first recognition-side
   replicate pair. **What transfers is the procedure, not the band** — a band is a property of
   (metric, language, corpus version, hardware class) and does not cross any of those
   boundaries.

**[INFERENCE]** Summary: English first because it is the only place where the *instrument*
can be calibrated against a known reading. Everywhere else we would be calibrating an
instrument and measuring an unknown at the same time, which is not a measurement.

---

## 3. Hindi second, Arabic third

### 3.1 The reason is a subset relation, not a judgement

**[FACT]** From the [prerequisite register](2026-08-05-stt-gate3-prerequisites.md), the two
chains, with the shared part factored out:

| | Hindi | Arabic |
|---|---|---|
| **Shared** | 1.3 empty-reference guard · 2.4 convention sheet · 2.5 double transcription + reconciliation · 2.7 speaker roster · 2.8 consent/licensing/PII · 2.9 probe set · 4.6 `EvalClip` local-path source · 4.1 `cer_unicode` (both primaries) | *(identical)* |
| **Ruler (Layer 1)** | 1.1 `devanagari@v1` | 1.2 `arabic_orthographic@v1` — **strictly larger**: must de-diacritise **without** naming a Unicode category (a category-M fold destroys Hindi), and must additionally enumerate alef/hamza forms and ta marbuta as codepoint folds |
| **Corpus (Layer 2)** | 2.2 C1/C2/C3 | 2.3 C1/C2/C3 — **strictly larger spec**: MSA and dialect as *separately declared slices*, diacritised and undiacritised references as *distinct cases*, AR-EN code-switching as its own slice |
| **Human prerequisite** | fluent Hindi transcribers (2.5, shared shape) | 2.6 **an Arabic dialect verifier competent in the dialects covered** — named explicitly, *"recorded as a named prerequisite, not assumed"* |
| **Starting holdings** | a released manifest slice (2 probe clips, 0 natural), a committed record, one observed error (लगता → लकता) | **zero clips of any kind**, no record, no observed behaviour |
| **Candidate set** | four claimants in three architecturally distinct shapes | one purpose-built, one incidental, one unverified, plus the incumbent's unevaluated Arabic |

**[INFERENCE]** Arabic's chain **contains** Hindi's chain and adds to it at three separate
layers, one of which (2.6) is a *person*, whose availability no engineering effort can
shorten. That is what "deeper" means, and it is a statement about our own register, not about
either language or about any candidate that serves them.

**[FACT] A trap that makes Hindi look readier than it is, worth recording because we already
fell into it once:** the M5 design assumed Hindi had a corpus because the M2.5 *synthesis*
corpus contains Hindi **text**. Transcription needs Hindi **audio** with committed
references, which is a different asset and does not exist — this is F-M5-8, raised at M5
Step 4. Hindi's advantage over Arabic is real but narrow: it is one ruler and one human
prerequisite, not a corpus.

### 3.2 This is explicitly not a product priority ordering

**[FACT]** The founder's living research priorities
([framework §16](RESEARCH_FRAMEWORK.md), founder-set 2026-08-04) run: #1 English STT,
#2 Hindi STT, #3 Arabic STT, then #4–#6 the TTS languages, #7 Translation, #8
Speech-to-Speech, #9 Voice Cloning, #10 IntelliAI-native models.

**The two orders coincide for STT. The coincidence is not the justification and must never be
cited as one.**

**[INFERENCE]** The orders are structurally independent and will diverge. Concretely: if
prerequisite 1.2 landed and an Arabic C2 were delivered while Hindi's C2 was still
uncollected, this document would order **Arabic before Hindi** with §16 completely unchanged
— and that would be correct, because §16 orders *attention* and explicitly "never skips gates
or lowers the evidence bar", while this document orders *the sequence in which valid records
can exist*. Two different questions with two different owners.

The practical guard: whenever this order and §16 agree, the agreement must be stated as an
observation and the derivation must stand on the register alone. A future reader who finds
them disagreeing should trust the register-based derivation and raise the disagreement to the
founder — not silently re-order to match the priorities.

### 3.3 The counter-pressure that runs the other way, recorded not suppressed

**[FACT]** Arabic STT is publicly `available` today. ADR-0027 Amendment 1 makes `available`
the entry rung, requiring **no** evidence; ARCHITECTURE §"Language policy state (M5)" records
STT as `en` supported, `hi`/`ar` available. **[FACT]** The M5 design's own words on F-M5-6:
Arabic STT being publicly `available` *"raises the urgency: we are serving it
honestly-labelled and unmeasured."*

**[INFERENCE]** By product-risk logic, Arabic has the strongest claim to going **first**: it
is the only one of the three languages where we serve customer traffic we have never measured
in any form. Depth-ordering places the highest-risk language last. That is a real, adverse
consequence of the rule, and it is accepted rather than hidden, for two reasons:

- The mitigation is already structural, not promissory. **[FACT]** ADR-0027 rejects a boolean
  per language precisely so that Arabic can be served honestly-labelled rather than either
  falsely promised or refused; the rung is `available`, the platform is making no claim it
  cannot support, and every refusal is recorded as demand evidence.
- Running Arabic early does not reduce the risk — it *converts* it. **[FACT]** Without 1.2
  and 1.3, an Arabic run does not measure Arabic badly; it commits `hallucinated_words = <the
  whole hypothesis>` into an append-only ledger (§1.2). The urgency argument is an argument
  for **funding 1.2/2.3/2.6 first**, which is a founder budget decision, not an argument for
  measuring first.

This tension is the single strongest founder-side reason to override the default order. §8.1
gives it a named trigger, so that the override is a *re-derivation* rather than an argument.

---

## 4. Streaming after the batch languages

### 4.1 The blocking fact is in the contract, not in the plan

**[FACT, verified at source]** `packages/runtime-contract/src/intelliai_runtime_contract/`
defines `TranscriptionRequest`, `TranscriptionSegment` and `TranscriptionResult`, and defines
**no streaming method**. A case-insensitive search for `stream` across the contract source
returns exactly one hit: the English word *"downstream"* in a docstring.

**[FACT]** The register carries this as 4.12, a **BUILD** item: *"the runtime contract has no
streaming method; every streaming metric is RESERVED until it exists."*

**[FACT]** In the metric register, `partial_revision_rate` is `RESERVED`, and under
arbitration A-7 `RESERVED` means *"a capability we do not have yet"* — registerable and
**unrecordable**. Acceptance condition **V-4** requires every metric name to be registered
**and `ACTIVE` at write time**. **[INFERENCE]** Therefore a streaming session today cannot
write a valid record. Not "would write a weak one" — cannot write a valid one.

### 4.2 The proxy that exists, and its limit

**[FACT]** `time_to_first_text_ms` is deliberately defined for **every** architecture: for
non-streaming candidates it equals end-to-end latency by construction, *"never N/A"*.

**[INFERENCE]** So latency-shaped streaming hypotheses have a measurable proxy in the batch
phases — but the proxy measures the candidate's **batch** latency, not its streaming
behaviour. It must never be cited as a streaming result, and a record produced this way must
carry a `Determination` (`state: not_supported`, `subject: streaming`, `producer: harness`)
rather than an absent field or a zero
([record schema §1.4](STT_BENCHMARK_RECORD.md), [methodology §3.4](STT_BENCHMARK_METHODOLOGY.md)).

**Wording reconciliation, carried forward:** one Gate-2 hypothesis is phrased in terms of
"time-to-first-token". **[FACT]** Arbitration A-1 **rejected** `time_to_first_token_ms` — a
token count is a property of one tokenizer and is not comparable across candidates. The
hypothesis must be read against `time_to_first_text_ms`. This is a reading correction, not a
new metric, and inventing one would breach the plan-only-what-Gate-3-defined rule.

### 4.3 Why this is M8 platform work and not research work

**[FACT]** Framework §1: research must never own production code or benchmark execution; the
causal chain is one-way — research → evidence → recommendation → founder decision →
engineering adoption. A streaming benchmark requires a **streaming method on the public
runtime contract**, which is a change to the platform's interface. **[FACT]** That work is
scheduled at M8 (`docs/CAPABILITIES.md`: *"streaming STT (M8)"*; the TTS streaming verdict is
already GO for v0.85/M8).

**[INFERENCE]** Research cannot order the platform to grow a method, and it should not
schedule a session whose validity depends on one. What it *can* do — and what the campaign
does — is record that until the method exists, streaming-first lineages are measurable **only
as batch candidates**, that their published streaming properties remain **[CLAIM]**, and that
the resulting records are structurally incomplete on exactly the axis their own hypotheses
name. §11.6 keeps that as an open tension rather than resolving it by wording.

### 4.4 The consequence for ordering

**[INFERENCE]** Streaming's deepest unmet prerequisite is Layer 4 (4.12), which sits below
Layer 2 (corpora) in the register's dependency ordering, but the streaming session **also**
needs everything a batch session in the same language needs — a corpus in that language and a
registered ruler for it. Its chain therefore *contains* the batch chain and adds 4.12 plus a
platform milestone. Streaming is after the batch languages by the same subset relation that
puts Arabic after Hindi.

---

## 5. Stress and robustness after quality

### 5.1 The definitional argument

**[FACT]** [Methodology §3.4](STT_BENCHMARK_METHODOLOGY.md): *"Robustness is **not** a
separate metric family. It is the *same* accuracy metrics computed over corpus slices carrying
the relevant `AudioCondition`."* And the reason it was designed that way: *"a robustness score
independent of accuracy would be a new ruler with no baseline."*

**[INFERENCE]** A robustness number is therefore literally the same metric name under a
different slice — and a metric value read against nothing is not a robustness finding, it is
an absolute number about an unknown. To read `wer_unicode` on a `NOISY` slice as evidence of
robustness, you must have `wer_unicode` on the `CLEAN` slice of the **same corpus version,
same ruler, same hardware class, same measurement route** — otherwise the §6.1 comparability
predicate is unsatisfied and there is nothing valid to difference against.

**Important scope note:** this is a **within-record**, within-session dependency, not a
cross-candidate one. Nothing here compares a candidate's noisy slice to another candidate's.
The clean-condition baseline a robustness number needs is the candidate's *own*. That is why
robustness can live inside a single session — but only a session whose clean pass came first,
in the same corpus version.

### 5.2 The tooling and corpus argument

**[FACT]** Prerequisite 4.9: no `snr` / `augment` / `babble` / `reverb` reference exists
anywhere in `ml/evaluation`. **[FACT]** C3 is a distinct corpus tier — 100+ clips,
condition-heavy — and no C3 exists for any language. **[INFERENCE]** Stress is deeper on both
axes at once: it needs the entire quality apparatus, *plus* a corpus tier that does not exist,
*plus* augmentation tooling that does not exist. Under criterion 1 it cannot come earlier.

### 5.3 A reading discipline this ordering buys

**[FACT]** `AudioCondition` is **tuple-valued** (A-3), because a real clip is telephony *and*
babble at once. The stated cost: *"`by_condition()` slicing is non-partitioning, which is
accepted and must be stated wherever such a slice is reported."*

**[INFERENCE]** A robustness table that implies a partition is therefore wrong by
construction. Running stress after quality gives the reader an anchor — the CLEAN slice —
against which overlapping condition slices can be read as *deltas from a known point* rather
than as shares of a whole that does not sum.

### 5.4 The exception: hallucination probes are not "stress" and are not deferred

**[FACT]** Empty-reference probes are mandatory *"in **every** tier, in every language"* — C1
included — and [corpora §4.2](STT_BENCHMARK_CORPORA.md) states plainly that they are how
hallucination is measured **and that they are cheap**.

**[INFERENCE]** So probe-shaped robustness rides along in *every* session from the first one,
and "stress last" must not be read as "hallucination last". Three facts govern how:

- **[FACT]** Our incumbent's zero-hallucination result was obtained **structurally** — the
  pipeline VAD short-circuits before the engine runs. A probe therefore measures the
  *pipeline*; an engine-level probe requires the research route, recorded via
  `MeasurementRoute = research_harness`, which is a comparability blocker and keeps the two
  kinds of result from being laundered into one another.
- **[FACT]** Probe clips carry `reference_text: ''`. The Layer-1 empty-reference hazard
  concerns **non-empty non-Latin** references. **[INFERENCE]** Probe-only sessions must
  therefore **not** be wrongly blocked behind 1.1/1.2 — over-blocking here would defer the
  cheapest and most architecture-general measurement in the entire campaign for no safety
  gain. The guard (1.3) must distinguish the two cases; if it cannot, that is a defect in the
  guard, not a reason to defer probes.
- **[FACT]** Probe results from two language corpora may be **read side by side, never
  differenced** — the comparability predicate blocks on both corpus identity and language. If
  a computed delta is ever wanted, the probes must live in a single probe-only corpus declared
  for all languages (2.9 is exactly that decision).

---

## 6. Regression last, by definition

### 6.1 The first argument does not exist yet

**[FACT]** [Record schema §3](STT_BENCHMARK_RECORD.md): a regression report compares a new
record against *"a **named prior baseline of the same artifact lineage**."*

**[FACT]** Eleven of the twelve PASS lineages have **no prior record of any kind** — we hold
exactly one CPU measurement in the entire candidate universe, our own whisper-small. For those
eleven, "regression" has no first argument, in the same mechanical sense as §2.3.

**[FACT]** For the incumbent lineage a prior record does exist — and under methodology v1 it
will be re-measured with a different **primary metric name** (`wer_unicode`), a different
**normalisation profile**, a different **corpus version**, and **per-language production
evidence** the committed record does not carry. **[INFERENCE]** Every one of those is a §6.1
comparability blocker in its own right. The prior record is therefore a historical reading of
the incumbent, not a v1 baseline.

**[INFERENCE]** So the first regression report of the campaign will be written against a
baseline **the campaign itself produced**. Regression is last not by scheduling convenience
but by definition: it is an operation *defined over the outputs of the earlier phases*. A rule
that placed it earlier would not be aggressive — it would be incoherent.

### 6.2 The comparator's own defects are prerequisites, not inventions

Two facts constrain what a regression phase can do even once it has both arguments:

- **[FACT]** `_comparability` emits `not_a_replacement` when
  `left.artifact == right.artifact and left.build == right.build`. A same-lineage version
  upgrade — `whisper-small@v1` → `@v2` on the same `cpu-int8` build — is exactly that shape,
  so the comparator **blocks the most common regression case there is**. Only `artifact` and
  `build` are compared; `artifact_version` is not.
- **[FACT]** STT records carry `judge: null` by law (A-0: the reference is a human
  transcript, not a model), so `different_judge` can **never** fire on the recognition path.
  The judge-host effect that moved `round_trip_wer` 0.5000 → 0.5042 across an identical judge
  artifact and version is real, but it lives on the generation path. Its recognition analogue
  is the **host** itself — which `_comparability` also cannot see, because **[FACT]** it emits
  no hardware finding at all.

**[INFERENCE]** Both are BUILD prerequisites in the register's spirit (Layer 3 hardware
capture, Layer 4 harness), not licences to invent a new comparator field. Recording them here
means the regression phase is planned against the comparator we will actually have.

### 6.3 What the regression phase's first output actually is

**[FACT]** [Methodology §6.3](STT_BENCHMARK_METHODOLOGY.md): a correctness delta is `real`
only when the metric is deterministic, the reference is the corpus's own text, and judge
deployment and host are identical; otherwise the reading is `no_band_established` *until a
same-identity replicate exists*, and **no threshold is invented**.

**[INFERENCE]** The first useful product of a regression phase is therefore a **band**, not a
verdict. A campaign that expects verdicts from its first regression report has misread the
methodology, and would manufacture a regression from a 0.0042 movement — which our own
committed replicate pair refutes directly.

---

## 7. The order, stated once

**[INFERENCE]** Applying §1 to the register dated 2026-08-05:

| # | Phase | Deepest unmet prerequisite | Why here | What it hands forward |
|---|---|---|---|---|
| 1 | **English quality + production** | Layer 2 (2.1 English C1/C2), with Layer 1 limited to 1.4 and Layer 4 items 4.1–4.4, 4.7–4.8 | Only language with both an incumbent baseline and a corpus lineage; only place a new metric can be validated against a committed prior value | Session skeleton · exercised metric register · ruler-transition record · `hardware_class` in use · per-language production record · declaration-cost control point · replicate procedure |
| 2 | **Hindi quality + production** | Layer 1 (1.1, 1.3) **then** Layer 2 (2.2) | Ruler build is smaller than Arabic's; a released manifest slice and a committed record already exist | `devanagari@v1` · `cer_unicode` in anger · the first non-Latin C2 collection protocol |
| 3 | **Arabic quality + production** | Layer 1 (1.2, 1.3) **then** Layer 2 (2.3, **2.6**) | Chain strictly contains Hindi's and adds a larger ruler, a larger corpus spec, and a human prerequisite | `arabic_orthographic@v1` · MSA/dialect slice discipline · the first corpus with a named external verifier |
| 4 | **Streaming** | Layer 4 (4.12) **plus** the batch chain in the target language **plus** M8 platform work | Contract has no streaming method; `partial_revision_rate` is RESERVED and V-4 refuses to write it | Streaming metrics become recordable; batch proxies become interpretable |
| 5 | **Stress / robustness (C3)** | Layer 2 (C3, all languages) **plus** Layer 4 (4.9) **plus** the clean reading of phase 1–3 | A robustness number is the same metric under a slice; unreadable without its own CLEAN anchor | Condition-sliced readings anchored to a clean baseline |
| 6 | **Regression** | The records produced by phases 1–5 | Defined over prior evidence of the same lineage; for eleven lineages that evidence does not exist yet | Bands, then eventually verdicts |

Precedence, as a partial order (`→` reads *"must not precede"*):

```
                        ┌──→  Hindi  ──┐
  English  ────────────►┤              ├──►  Streaming ──►  Stress  ──►  Regression
                        └──→  Arabic ──┘              (per language, after that language)

  probes (empty-reference)  ── ride along in every session from the first ──►
  bridging run (hardware succession)  ── preempts whatever phase is running ──►
```

Two clauses that are easy to lose in a diagram:

- **Hindi and Arabic do not depend on each other.** Their relative position comes from
  criterion 1 alone, so a change in either chain re-derives independently (§8).
- **Within a language phase, sessions are grouped by serving stack**, and groups are ordered
  by criterion 2 — number of sessions sharing the stack × setup cost. **[INFERENCE]** Group
  membership is recomputed per phase, because language coverage differs: the ONNX-Runtime
  group is large in English and a different set entirely in Hindi. **The incumbent's stack
  (CTranslate2) is already standing, so its setup cost is zero and it is first in every phase
  where it appears.** §9.4 addresses why that is not an advantage.

---

## 8. What would change the order

Each entry names the **event**, its **owner**, what it **reorders**, and — equally important
— what it does **not**.

### 8.1 A corpus arrives early
**Owner: founder** (commissioning under F-M5-6 / F-M5-8, or accepting a licensed third-party
corpus). **Reorders:** Arabic ahead of Hindi if the Arabic C2 is delivered first, or either
ahead of the other on the same basis. **Does not reorder:** a delivered corpus does **not**
shorten the ruler chain — Arabic still cannot precede `arabic_orthographic@v1` (1.2) and 1.3,
because running it through the current path commits silent corruption (§1.2). **Also note
[FACT]:** pinning a third-party dataset carries its licence into every future promotion in
that language, which is why F-M5-8 records the choice as a founder decision rather than an
engineering one. So this event is a decision, not a delivery.

### 8.2 The founder GPU decision (3.2)
**Owner: founder.** **Reorders:** *which candidates appear* in a language phase, and
therefore the stack-group composition under criterion 2 — a whole class of GPU-shaped
sessions becomes plannable or is closed. **Does not reorder:** the **language** sequence,
because languages are ordered on corpus and ruler depth, and both are hardware-independent.
**[INFERENCE]** If the decision is *"no GPU tier"*, the affected sessions are not deleted and
not moved — they narrow to a CPU-viability determination, which is still a valid record
(**failures are evidence**, framework §6.3).

### 8.3 Hardware succession (3.5) — the one event that preempts mid-phase
**Owner: founder / engineering.** **[FACT]**
[STT_BENCHMARK_HARDWARE §6](STT_BENCHMARK_HARDWARE.md): when reference hardware is replaced,
*"the **incumbent is re-measured on the new machine before any challenger is**"*, and
performance numbers cross a hardware-class boundary **only** through that bridging run.
**Reorders:** a bridging run inserts itself at the **front of whatever phase is running**.
This is the only legitimate mid-phase preemption in the whole scheme, and it is required by
criterion 3, not by criterion 1.

### 8.4 M8 lands (streaming method on the contract, plus 4.12)
**Owner: engineering, on the roadmap.** **Reorders:** streaming stops being blocked and
becomes orderable by its own prerequisite depth. **Does not reorder — and this is the
counter-intuitive part:** M8 landing early does **not** move streaming to the front, because a
streaming session still needs a corpus and a registered ruler in the language it streams. It
lands *after that language's batch phase*, not before it. What M8 actually changes is that
`partial_revision_rate` becomes recordable and `time_to_first_text_ms` starts meaning what a
streaming reader thinks it means.

### 8.5 The Layer-1 rulers land early (1.1 / 1.2 / 1.3)
**Owner: engineering.** **Reorders: nothing, by itself.** **[INFERENCE]** This is recorded
because it is the most likely misreading of *"rulers before data"*: a ruler with no corpus
measures nothing. Rulers are a **gate on** the corpus phase, not a substitute for it. The
register's own words — the Layer-1 ordering *"is not a preference; it is a safety
requirement."*

### 8.6 A candidate's eligibility changes
**Owner: research (Gate 1) or founder.** A BLOCKED lineage obtaining its clarification
re-enters at Gate 0/2 — it does **not** drop into a running phase. A PASS lineage whose licence
shifts goes *any status → Rejected* (framework §3) and leaves. **Reorders:** only *within*
stack groups — a lineage leaving can leave its group's setup cost unamortised, which under
criterion 2 can move that group later in its phase. **Never moves a language.**

### 8.7 The founder cuts the Layer-0 circularity (0.3)
**Owner: founder.** **[FACT]** The register states the circularity plainly: Gate 4 requires a
plan naming a corpus, metrics, hardware and baseline **that exist**; most do not; and the
register will not be funded without a plan. *"Something must be approved before it is fully
specified, or nothing starts."* **Reorders:** nothing — but it is the event that turns this
document from a description into a schedule. Until it happens, phase 1 has no start.

### 8.8 A corpus tier arrives out of order (a C3 before its C2)
**Owner: whoever collects.** **Does not reorder.** §5.1's argument is definitional, not
logistical: the CLEAN reading must exist in the **same corpus version** regardless of when the
adversarial clips were collected. Early C3 clips are stored; they are not measured earlier.

### 8.9 The meta-rule
**The order is re-derived, never edited.** A change event changes an *input* to §1; you re-run
§1 and record the new output with the event that caused it. A campaign that hand-edits its
sequence has quietly replaced a rule with a preference, and the next campaign inherits nothing
it can reason from. This mirrors the append-only law the evidence ledger already lives by:
corrections are new derivations, not overwrites.

---

## 9. Ordering confers no advantage or disadvantage on any candidate

The claim to be defended is specific: **being measured first, or last, cannot make a candidate
look better or worse.** An assertion would be worthless; below is the mechanism, device by
device, each one already in the Gate-3 design.

**9.1 Same corpus version — enforced, not intended.** **[FACT]** Within a language phase every
candidate is measured against one named corpus version that is *released, immutable and
hash-verified* (P-2, V-2), and a corpus version becomes immutable **the moment a result cites
it** (corpora §7). So the first candidate measured structurally cannot cause the corpus to
change for the second. And if it somehow did, **[FACT]** `_comparability` emits
`different_corpus_version` and **blocks** — the comparison is refused, not silently skewed.

**9.2 Same ruler, fixed before any candidate runs.** **[FACT]** [Methodology §4.1](STT_BENCHMARK_METHODOLOGY.md):
*"Primacy is fixed per (language, corpus version) — **never per candidate**."* The stated
reason is exactly this fairness property: a rule that selected the primary metric from a
candidate's emission granularity *"would give two candidates on the same corpus different
headline metrics, so the switching test would have no common ruler and the comparison would be
decided by ruler choice rather than by measurement."* **[FACT]** `emitted_unit` is recorded as
a condition a reader interprets; **it never selects the citation**. **[FACT]** Both WER and CER
are recorded on **every** run in **every** language, so no candidate's headline metric can be
chosen after its numbers are known. **[INFERENCE]** This is the single strongest
anti-advantage device in the design, and it is what makes ordering safe: the ruler is settled
before the first session of a phase opens.

**9.3 Same hardware profile, with the boundary instrumented.** **[FACT]** `hardware_class` is
recorded on every run and `_comparability` blocks on a class mismatch — *as designed*.
**[FACT] Stated honestly: this does not exist in code today** (`hardware_class` appears in
`docs/` only; `_comparability` emits no hardware finding), which is prerequisite 3.1/3.4 and a
precondition of the fairness claim, not a description of the present. Where hardware does
change mid-campaign, §8.3's bridging run re-measures the **incumbent** first, so the era
boundary is absorbed by a known artifact rather than by whichever candidate happened to be
next in the queue.

**9.4 The incumbent going first in every phase is a cost fact, not a favour.** **[INFERENCE]**
Criterion 2 puts the already-standing CTranslate2 stack first wherever it appears, which
*looks* like privileging the incumbent. Three things neutralise it: (i) the incumbent's run in
each phase **is the baseline run** — the thing challengers are read against — and the
methodology independently requires re-baselining the incumbent first on any judge, ruler or
hardware change; (ii) the corpus version, ruler and hardware class are all fixed **before** it
runs, so it cannot shape them; (iii) its record is subject to the identical validity
computation, and an incomplete incumbent record *may not be named a baseline* either.

**9.5 Order effects inside a session are caught deterministically.** **[FACT]** Procedure §4.1
chooses fixed manifest order plus a **reversed-order audit** (step 7) and drift probes at
opening and close, precisely because randomisation *"destroys diffability between runs"* while
the audit *"catches order and cache effects deterministically, which is what randomisation was
for."* **[FACT]** One known weakness is preserved deliberately: gateway overhead runs
immediately after the ladder on a warmed machine, bounded by our own record at about **+1.18%**
(ladder c=1 p50 1749.3 ms vs overhead direct p50 1770.0 ms). **[INFERENCE]** It is preserved
for continuity with the two existing baselines, and it applies identically to every candidate —
a constant, not a per-candidate advantage.

**9.6 Absence is recorded, never zeroed.** **[FACT]** A candidate that cannot process a
condition, emit a timestamp, or expose a counter produces a `Determination` — *"never as a
missing field and never as a zero"* — and an **incomplete** record is *"citable for what it
contains and may not be named a baseline."* **[INFERENCE]** So a harness gap cannot silently
convert into a worse-looking number for whoever was measured while the gap existed.

**9.7 Nothing crosses a phase boundary.** **[FACT]** Numbers do not cross the language boundary
(§4's seven mechanisms; **no roll-up field exists anywhere in the schema**), and probe results
from two language corpora may be *read side by side, never differenced*. **[INFERENCE]** A
candidate measured in the English phase therefore carries no credit, and no penalty, into the
Hindi phase.

**9.8 The comparison is not made here at all.** Cross-candidate reading happens **after** the
campaign, on records, under the §6.1 predicate — never by this document, never by a session,
and never by ordering or emphasis. **[FACT]** The structural backstops:
[record schema §6](STT_BENCHMARK_RECORD.md) — no field anywhere holds a shipping decision; no
roll-up field exists; `CostFactor` has no magnitude, weight or total; the promotion package
**cannot cite** the recommendation; direction of change is computed from `MetricSpec.direction`
rather than authored.

### 9.9 Where ordering *can* leak, and what actually contains it

An honest fairness claim states its residual. Three leaks are real:

- **Harness maturity drifts across the campaign.** Metrics land, `ClipResult.failure` lands,
  `store.ensure` gets timed. A candidate measured before `artifact_ensure_*` existed has a
  record without them. **Containment:** `platform_git_commit` and
  `evaluation_package_version` are on every record (`VersionIdentity`); the gap is recorded as
  `not_measured`, never zero; and such a record is `incomplete` and cannot be named a
  baseline. **[INFERENCE] The residual is not eliminated by ordering — it is eliminated by
  re-measuring**, which is the same standing remedy already required on judge change and
  hardware change: re-baseline, then compare.
- **Environmental drift across a long phase.** Contained by P-9 (the machine is *asserted*
  idle, not assumed), the same-identity replicate, and the reversed-order audit — none of
  which is an ordering device.
- **Operator learning.** A stack stood up for the fifth candidate is stood up better than for
  the first. **[INFERENCE]** This affects *engineering cost* legitimately; it affects the
  *measurement* only if it changes configuration. Since `thread_config`, `compute_type`,
  `decode_params` and pool configuration are all recorded, a configuration difference is
  visible — and the honest remedy is **re-running the earlier candidate at the better
  configuration**, not a footnote explaining the difference away.

**[INFERENCE]** The summary the campaign should be held to: *ordering decides when we learn
something; it never decides what is true.* Where that separation cannot be maintained, the
answer is another measurement, never a caveat.

---

## 10. What this order is not

- **Not a ranking.** No candidate is scored, compared, or preferred here, by statement or by
  position.
- **Not a priority list.** §16 of the framework orders attention; this orders dependency. §3.2
  records that they currently coincide and why that must not be cited as justification.
- **Not a schedule.** No dates, no effort estimates, no staffing. A partial order only.
- **Not executable.** **[FACT]** No candidate holds `Approved for Benchmark`; all twelve are
  `Researching` and none has passed a Promising review (framework Gate 3). Every session below
  is plannable; none is startable.
- **Not applicable to the four BLOCKED lineages**, which appear nowhere and remain frozen.

---

## 11. Open tensions this ordering does not resolve

Recorded so a reviewer sees them, not so this document can claim to have settled them.

**11.1 Arabic carries the most product risk and is measured last.** We serve `ar` today at the
`available` rung, unmeasured. Depth-ordering defers it. §3.3 argues the urgency is an argument
for *funding* 1.2/2.3/2.6 first, and §8.1 gives the override a named trigger — but the tension
is real and is a founder call.

**11.2 The two orders coincide, which is a trap.** §16 priorities and prerequisite depth
return the same STT sequence today. A future reader must not conclude the rule is a restatement
of the priorities; they are independent and will diverge (§3.2).

**11.3 The Layer-0 circularity is unresolved by construction.** Gate 4 needs a plan naming
things that exist; they mostly do not. Ordering cannot cut it; only a founder can (8.7).

**11.4 The gate numbering does not match the framework** (§0.2), with the two consequences
recorded there. The campaign documents should either adopt the framework numbering or record a
permanent mapping; this document does the latter as an interim.

**11.5 "English first" is not "English ready."** English's natural-speech holding is two
containers of one utterance. The first English session supports **no quality claim** by tier
definition, and English's C2 is a COLLECT item exactly as Hindi's and Arabic's are (§2.4). The
phrase "the only language with a corpus" is true of corpus *lineage*, not of corpus *size*.

**11.6 Streaming lineages will be measured on everything except the property that
distinguishes them.** Their records will be structurally incomplete on the axis their own
hypotheses name, carrying a `Determination` where a streaming metric would sit. Ordering does
not fix this; M8 does (§4.3).

**11.7 A number this document builds on is inconsistent in the source.**
[Procedure §1](STT_BENCHMARK_PROCEDURE.md) cites, as **[FACT]**, `hi` 13698 ms vs `en` 1462 ms
— a **9.4×** declaration effect. **[CORRECTED 2026-08-05]** The claim previously made here —
that this figure "was never committed" — is **false**. It *is* committed, at
[`2026-08-05-multilingual-baselines.md` §2a](../../ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md),
as a **median of three runs per declaration**, which makes it the *stronger* measurement; the
17859/1391 ms pair is single-sample. **Procedure §1 needs no correction.** Nothing in this
ordering depends on the magnitude — only on the fact that language declaration is a first-order
cost variable — but the discrepancy should be corrected in the procedure rather than silently
re-cited.

**11.8 The regression comparator has two defects that are themselves prerequisites** (§6.2):
it blocks same-artifact version upgrades via `not_a_replacement`, and `different_judge` can
never fire on the recognition path while the uncontrolled variable it stands in for — the host
— is invisible to it.

**11.9 A cadence wording ambiguity worth a founder read.** **[FACT]**
[Corpora §1](STT_BENCHMARK_CORPORA.md) gives C3 the cadence *"per campaign"*, which can be read
as *within* a campaign, while §5 here places stress after quality. **[INFERENCE]** The two are
compatible — cadence describes how often a corpus tier is refreshed, not where in a campaign it
is consumed — but the wording invites the opposite reading and should be tightened.

**11.10 A code-mixed convention must not be inherited from the generation side.** **[FACT]**
`mixed` is a live language value in the committed synthesis corpus, while
[methodology §4](STT_BENCHMARK_METHODOLOGY.md) forbids a `mixed` pseudo-language on the
recognition side: a Hinglish clip takes the **matrix** language, carries `CODE_MIXED`, and
records `embedded_languages`. The recognition corpora must not copy the generation
convention.

**11.11 Ordering assumes an English corpus can actually be referenced.** **[FACT]** `EvalClip`
has **no local-path source** (4.6), so audio we record ourselves is unreferenceable, and
**[FACT]** `corpus-inbox/` is not gitignored despite the recording protocol saying it is.
Until 4.6 lands, *every* collection item (2.1, 2.2, 2.3) is blocked simultaneously — which
means the phase-1/2/3 distinction buys nothing at all on the collection axis. Depth-ordering
still holds for the ruler and verifier chains, but this single schema gap flattens the corpus
axis across all three languages and is the highest-leverage item in the register on ordering
grounds.

---

*Change log: 0.1 (2026-08-05) — initial design (Gate 4 campaign ordering). Ordering rule,
per-phase derivation, reorder triggers, and the no-advantage mechanism. Executes nothing;
ranks nothing; names no winner.*
