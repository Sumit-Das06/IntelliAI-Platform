# IntelliAI STT Benchmark Corpus Specification

| | |
|---|---|
| **Status** | PROPOSED (Gate 3 design, 2026-08-05) |
| **Version** | 0.1 |
| **Role** | What each benchmark corpus must **contain**. Nine corpora: three tiers × three product languages. Companion to [STT_BENCHMARK_METHODOLOGY.md](STT_BENCHMARK_METHODOLOGY.md). |
| **Scope** | **No data is collected, created, or specified as a schedule here.** This document defines requirements only. |
| **Permanence** | Corpora are permanent company assets. Models depreciate; corpora accumulate. A corpus version becomes immutable the moment a result cites it. |

---

## 1. Tiers — what evidence each supports

Tiers describe **the strength of claim a result can support**. They confer no authority over
a candidate: a tier does not grant permission, gate spending, or trigger a rejection. Only
the framework's gates and the founder do that.

| Tier | Purpose | Size | Cadence | A result measured here… |
|---|---|---|---|---|
| **C1** | Smoke and liveness | 10–20 clips | every run, every CI-eligible change | …may support **no quality claim**. It shows the system ran and produced plausible output. |
| **C2** | Quality evidence | **≥100 clips** | per benchmark session | …may support a per-language quality claim, a baseline, and a switching comparison. |
| **C3** | Adversarial and robustness | 100+ clips, condition-heavy | per campaign | …may support robustness findings and may be cited by a rejection criterion as evidence. |

**C2 is the tier the standing ≥100-case condition refers to.** A quality claim below that
size is not made.

**C1 is not a subset of C2.** C1 is deliberately cheap and stable so that it can run
constantly; C2 is deliberately broad. Overlap is permitted; identity is not.

---

## 2. What every corpus records

Reusing `CorpusProvenance` and adding recognition-specific fields:

```
name, version, capability, description
author, created, rationale, source, languages, license      # existing provenance
audio_conditions_present   tuple[AudioCondition, ...]
duration_bands_version     str = "duration_bands@v1"
speaker_count              int
speaker_roster             tuple[SpeakerProfile, ...]        # pseudonymous
consent_basis              str
pii_status                 str
publication_status         str    # private | public | derived
contamination_risk         str    # none_known | possible | known_overlap | undeterminable
```

**`publication_status` and `contamination_risk` are mandatory.** A corpus we built ourselves
and never published is the only structurally clean position — and **[FACT]** contamination
is an observed hazard, not a hypothetical: one lineage in the current research universe
publicly states it was RL-fine-tuned on a public leaderboard's training splits.

---

## 3. Content axes

Two orthogonal axes, deliberately kept separate:

- **Content** — reuses `TextCategory` **unchanged** (see methodology A-2: appending breaks a
  committed golden test against the immutable generation corpus).
- **Acoustic** — a new recognition-owned `AudioCondition`, **tuple-valued** (a real clip is
  telephony *and* babble at once).

Recognition-only content axes that have no `TextCategory` member live on recognition-owned
enums, never by appending to the shared one.

---

## 4. Composition requirements

### 4.1 Mandatory in every C2 corpus, every language

| Requirement | Minimum |
|---|---|
| Conversational / spontaneous speech | present, substantial |
| Read speech | present |
| Short utterances (<5 s) | present as its own duration band |
| Long-form (>60 s) | present |
| Numbers, dates, currency | present |
| Proper nouns and named entities | present |
| Disfluencies (repairs, fillers) | present |
| Telephony / narrowband | present |
| Background noise | present |
| Accent and dialect variation | present |
| **Empty-reference probes** (silence, tone, music) | **≥3, in every tier** |
| Speakers | ≥10, gender-balanced |
| Timed sub-slice (for timestamp scoring) | ≥20 clips |

**Proportions are not fixed by this document.** They are declared per corpus version, with a
sourced rationale, and recorded in provenance. A composition chosen from an unsourced
assumption about where models fail produces numbers that measure the assumption.

**Entity distribution is justified by declared target markets** — a founder-recorded
commercial fact — never by a claim about where any class of model concentrates its errors.

### 4.2 Empty-reference probes

Present in **every tier**, in every language. These are how hallucination is measured, and
they are cheap. **[FACT]** Our incumbent's zero-hallucination result was obtained
structurally — the VAD short-circuits before the engine runs — so a probe measures the
*pipeline*, and an engine-level probe requires the research route (recorded via
`MeasurementRoute`).

Byte-identical probe clips **may** be carried across language corpora, but a probe result
from `stt-en-c1` and one from `stt-hi-c1` are two records that may be **read side by side,
never differenced** — the comparability predicate blocks on both corpus identity and
language. If a computed delta is wanted, the probes must live in a single probe-only corpus
declared for all languages.

### 4.3 Code-mixed slices

Code-mixed clips are **mandatory and separately reported**. They take the **matrix** language
as their language, carry `CODE_MIXED`, and record `embedded_languages`.

**The code-mixed share does not enter the headline per-language aggregate at a proportion
chosen from a judgement about model families.** Monolingual and code-mixed are two
independently reported slices, each with a declared, sourced rationale, and every cited
number names the slice it came from. Choosing a large code-mixed proportion on the reasoning
that specialists handle it worse would encode the expected outcome into the instrument.

---

## 5. Per-language requirements

### 5.1 English

Primary ruler `wer_unicode`, with `wer_ascii` co-recorded in one transition record so the
existing 2026-08-03 baseline stays comparable.

Specific demands: accent breadth (this is where a nominally "solved" language actually
varies); long-form coherence; alphanumeric strings and entity-dense speech; disfluent
spontaneous speech.

### 5.2 Hindi

Primary ruler `cer_unicode`, co-primary `wer_unicode`.

Specific demands: **conjunct consonants** and **matra coverage** as explicit content
requirements (a matra error is invisible to a word-level ruler unless it changes the whole
word); Devanagari numerals **and** Arabic numerals as separate cases; transliteration
ambiguity (English loanwords written both ways); Hinglish code-mixing as its own slice;
regional accent variation across Hindi-speaking regions.

**[FACT]** The single Hindi error we have ever observed — लगता → लकता — is a matra-class
error. It is the reason CER is primary here, and it is one data point, not evidence.

### 5.3 Arabic

Primary ruler `cer_unicode`, co-primary `wer_unicode`.

Specific demands: **MSA and dialect as separately declared slices** (they are not
interchangeable, and a corpus that blends them measures neither); diacritised and
undiacritised references, recorded as distinct cases; clitic-heavy constructions;
orthographic variants (alef/hamza forms, ta marbuta) enumerated in the normalisation profile
rather than folded by category; Arabic-English code-switching as its own slice.

**[FACT] The trap that governs Arabic normalisation:** Arabic tashkeel and Devanagari matras
are both Unicode category **Mn**. A profile that strips category M to de-diacritise Arabic
**destroys Hindi**. Folds are therefore enumerated codepoint tables, and any profile naming
a Unicode category is rejected at registration.

---

## 6. References — the asymmetry that must be confronted

**[FACT]** Our existing corpora are **text-first**: for synthesis, the input *is* the
reference. Recognition is the opposite direction — it needs **real audio with human
references**, which is a different kind of asset with a different cost, different licensing,
and different consent obligations. None of the existing corpus tooling addresses that.

**Reference standard:**

- Produced by a fluent speaker of the language, not by a model.
- **No normalisation at creation.** References are stored verbatim; normalisation happens at
  scoring, by a declared, versioned profile. A reference normalised at creation has silently
  baked in one ruler forever.
- Ambiguity (unclear speech, overlapping talk) is resolved by a written convention sheet
  versioned with the corpus, not by transcriber preference.
- **Double transcription with reconciliation** for the C2 tier; disagreement rate is itself
  recorded, because it bounds the achievable error floor. A candidate cannot be meaningfully
  measured below the disagreement rate of its own references.
- Arabic dialect references require a verifier competent in that dialect — recorded as a
  named prerequisite, not assumed.

### 6.1 Speaker attribution: recorded now, consumed later

Every C2 timed clip and every `MULTI_SPEAKER` clip **carries per-segment speaker ids** from
the pseudonymous roster, even though nothing consumes them today.

**Why now:** corpora are immutable, so retrofitting attribution means re-buying the corpus —
a full re-baseline per served artifact per language. Recording alternates while a
transcriber is already in the clip is nearly free; reconstructing them years later is not.
The moment any candidate emits speaker-attributed output, un-attributed references are the
wrong shape.

This is the reserve-a-slot pattern used elsewhere in this design, applied where it is
cheapest and most expensive to get wrong.

---

## 7. Governance

- **Versioned and immutable once cited.** A correction is a new version.
- **Consent and licensing are gating properties**, not metadata. Recorded audio carries real
  consent and privacy obligations; consent-collected data is explicitly rewarded by our data
  constitution.
- **PII policy** applies at collection, not at publication.
- **Contamination controls:** prefer corpora we built and never published; where public data
  is used, record `contamination_risk` honestly, including `undeterminable`.
- A corpus is a **dataset-research asset** (framework §12) as much as a benchmark input, and
  inherits that lifecycle.

*Change log: 0.1 (2026-08-05) — initial design (Gate 3).*
