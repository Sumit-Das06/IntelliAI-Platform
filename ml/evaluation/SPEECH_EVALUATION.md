# Speech Evaluation — Philosophy & Methodology

**Status:** IN FORCE (M2.5 D1) · lives beside the code that implements it
· changes follow the same law as metrics: *a changed methodology is a new
version, never an edit that silently moves old numbers.*

This document governs how IntelliAI evaluates **speech generation** — TTS
today; voice cloning, speech translation, and IntelliAI's own speech
models tomorrow. It is engine-agnostic by construction: nothing below
assumes Kokoro, or any engine. The test of every rule here: *will this
still be correct when IntelliAI owns its speech models?*

The companion for speech **recognition** is the existing STT seed (WER,
hallucination probes); both share one discipline: **the ruler exists
before the model, and the ruler never moves.**

---

## 1. What speech quality means

A generated utterance is good to the degree that:

1. **It says the right words** — a listener recovers exactly the input
   text (*intelligibility*), including the hard parts: numbers, names,
   technical terms, conjuncts (*pronunciation*).
2. **It is a sound signal a product can ship** — sane duration, no
   clipping, no dead air, no artifacts (*signal integrity*).
3. **It sounds like a person** — prosody, rhythm, pleasantness
   (*naturalness*).
4. **It is who it claims to be** — a chosen voice stays consistent across
   utterances and sessions; a cloned voice resembles its reference
   (*identity* — future capabilities).
5. **It is fast and cheap enough to serve** (*performance*).

These five properties have very different measurability — which is the
whole reason this document exists.

Conceptually they split into two questions, and evaluation discussions
should always know which one they are asking:

- **Correctness** — *"Did the model produce the requested speech?"*
  Intelligibility, pronunciation, signal integrity. Objectively checkable.
- **Quality** — *"Did it sound like high-quality speech?"* Naturalness,
  prosody, pleasantness. Human territory (today).

A model must be *correct* to ship at all; it must be *good* to win.

**Language independence (architectural statement):** this framework is
intentionally language-agnostic — every metric, record shape, and
protocol applies unchanged to any language the platform serves.
Language-specific *content* lives in corpus categories (Hindi conjuncts,
code-mixed text), and future language-specific metrics may be appended as
new specs — the philosophy itself never forks per language. This is the
evaluation half of IntelliAI's multilingual strategy.

## 2. The three-way split: measured, judged, deferred

### Objectively measurable today (automated, CI-able)

- **Round-trip intelligibility** — synthesize the text, transcribe the
  audio with our own STT runtime, score WER against the input text. The
  platform's ears grade its mouth. This is the *primary automated quality
  proxy*.
- **Pronunciation accuracy** — the same round trip, scored only on
  designated trap words (numbers, names, technical terms, Devanagari
  conjuncts): did each trap word survive?
- **Signal sanity** — from the WAV itself, stdlib-only: duration
  plausibility vs text length, leading/trailing/internal silence ratio,
  clipping ratio, digital-silence detection.
- **Performance** — time to first audio, total latency, real-time factor,
  peak memory, CPU (the M2 bench harness pattern, extended per capability).

### Requires human judgment (structured, honest about scale)

- **Naturalness, prosody, pleasantness** — no honest automated substitute
  exists in-house today. Measured by the **structured listening
  protocol**: anchored A/B comparisons, randomized presentation order, a
  fixed scoring sheet, scores recorded into the results ledger. With one
  listener the label is **"founder listening score (n=1)"** — never
  "MOS". Small-n honestly labeled beats large-sounding numbers we cannot
  defend.

### Intentionally deferred (architecture reserved, not implemented)

- **Model-based naturalness predictors** (UTMOS/NISQA class) — they are
  *models*: weights, licenses, verification; adopting one follows the full
  model-adoption protocol. Adopt when: a licensing-clear predictor exists
  AND listening-protocol volume becomes the bottleneck for promotion
  decisions.
- **Speaker similarity** (cloning) — embedding-based; arrives with the
  cloning capability, not before.
- **Voice consistency** across utterances/sessions; **emotion/style
  preservation** (S2ST, expressive TTS) — reserved layers.
- **Robustness** — a reserved *dimension* (not a single metric): how
  correctness holds up under hostile input — punctuation extremes,
  long-form text, mixed-language switching mid-sentence, noisy or
  malformed input, abbreviation expansion. Future robustness metrics
  join as specs under the correctness layer with their own corpus
  categories; nothing is implemented today.

**Where automation ends** — stated plainly: automation can prove speech
is *correct, clean, and fast*. Only humans (today) can prove it is
*pleasant*. A model may score perfectly on every automated metric and
still lose the listening comparison; the promotion methodology (§6)
therefore requires both.

## 3. The metric hierarchy

Every metric declares its **layer**, **direction**, **confidence**, and
**judge dependencies** at definition time. Dashboards and promotion gates
never infer direction — or how trustworthy a number is.

Confidence classes: **high** (objective, deterministic), **medium**
(objective but approximate — heuristic thresholds, sampling lag, or
judge-dependence), **human** (structured subjective judgment),
**reserved** (future capability, not yet implemented).

| Layer | Metric | Direction | Confidence | Notes |
|---|---|---|---|---|
| Correctness | `round_trip_wer` | **lower** is better | medium | judge: pinned STT artifact |
| Correctness | `pronunciation_accuracy` | **higher** is better | medium | trap-word hit rate, 0–1 |
| Correctness | `clipping_ratio` | **lower** is better | high | samples at full scale / total |
| Correctness | `silence_ratio` | **lower** is better | medium | energy-threshold heuristic |
| Correctness | `duration_plausibility` | **higher** is better | medium | 0–1 vs speaking-rate band |
| Performance | `time_to_first_audio_ms` | **lower** is better | high | serving-path measurement |
| Performance | `synthesis_latency_ms` | **lower** is better | high | total request wall time |
| Performance | `rtf` | **lower** is better | high | synthesis time / audio duration |
| Performance | `peak_memory_mib` | **lower** is better | high | container measurement |
| Performance | `cpu_percent_max` | **lower** is better | medium | `docker stats` sampling lag |
| Quality (human) | `listening_preference` | **higher** is better | human | anchored A/B win rate |
| Quality (human) | `listening_naturalness` | **higher** is better | human | 1–5 sheet, n recorded |
| *Future* | `predicted_mos` | higher | reserved | model-based naturalness |
| *Future* | `speaker_similarity` | higher | reserved | cloning |
| *Future* | `voice_consistency` | higher | reserved | cross-utterance identity |
| *Future* | `emotion_preservation` | higher | reserved | S2ST / expressive TTS |
| *Future* | robustness family | (per metric) | reserved | §2 reserved dimension |

Mechanically (D3/D4): every metric is registered as a
`MetricSpec(name, layer, direction, unit, confidence, judge)` and every
recorded value carries its spec's name — adding a future metric is
appending a spec, never reshaping results.

## 4. The judge discipline (what keeps round-trip honest)

Using our own STT as the judge is deliberate — it exists, it is measured
(WER 0.000 on its seed set), and it is the same ear our customers' voice
pipelines will often use. It has two known hazards, managed openly:

1. **The judge moves.** If the STT artifact changes, round-trip numbers
   change for reasons unrelated to TTS. Rule: **every result records the
   judge's artifact id and version**; comparisons are valid only within
   the same judge; a judge upgrade re-baselines every incumbent (one
   command, D5) before any new comparison.
2. **Shared blind spots.** A strong ASR can transcribe mildly degraded
   audio correctly, masking quality loss — and our own models could in
   principle share training-data biases. Round-trip WER is therefore an
   *intelligibility floor*, never a naturalness claim; naturalness stays
   with the listening protocol until a vetted predictor is adopted.

## 5. Corpus and results principles (governing D2 and D4)

- **Corpus:** a **permanent product asset** — models improve, corpora
  accumulate; a corpus is evaluation capital, never a temporary fixture.
  Versioned, immutable, text-first (the input *is* the reference — no
  recordings needed). Organized by **category within language** (general,
  numbers, dates, currency, URLs, technical terms; Hindi conjuncts,
  matras, proper names; code-mixed and API/programming text), because
  category-level scores localize failures ("numbers regressed") where a
  single average hides them. Every case declares a **difficulty**
  (easy/medium/hard — orthogonal to category), enabling overall/easy/hard
  report slices without corpus changes, and may carry maintenance
  **tags** (`expected_failure`, `known_limitation`,
  `regression_sensitive`) documenting why it exists — never scoring
  inputs. Every corpus version records **provenance** (author, date,
  rationale, source, languages, license) — reproducible and legally
  auditable even for in-house text. **Evolution rule: a version cited by
  any recorded result never changes; new coverage always creates the
  next version; old results stay reproducible forever.**
- **Results:** one append-only record per (corpus version, artifact
  evaluated, judge, hardware) carrying artifact lineage and runtime
  identity, an extensible metrics map keyed by registered metric names,
  and optional human-evaluation fields. Capability-generic: a cloning
  eval is the same record shape with more metrics and a reference-voice
  field, not a new schema.

## 6. Regression & promotion methodology

- Every serving TTS artifact has a **committed baseline** (D5: one
  command → full evaluation → permanent artifact).
- A candidate replaces an incumbent only by the **switching test**: same
  corpus version, same judge, same hardware class; the candidate must win
  or consciously trade (the trade written down) on the quality layer,
  hold the performance layer within stated bounds, and win or tie the
  listening comparison.
- Determinism: synthesis parameters pinned and recorded; judge pinned
  (§4); nearest-rank percentiles for performance (the M2 bench rule);
  category-level scores always reported alongside overall.
- **Reproducibility (extends the repository's reproducibility
  philosophy):** every published benchmark must be reproducible from its
  recorded metadata alone — corpus version, evaluated artifact version,
  judge version, runtime version, hardware class. If a result cannot be
  re-derived from what its record states, it is an anecdote, not a
  benchmark, and does not enter the ledger.

## 7. Extension recipe (how future capabilities join)

A new speech-generation capability adopts this framework by: (1) adding
its corpus categories (new corpus version), (2) registering any new
metric specs (append-only, direction declared), (3) reusing the runner
with its capability's synthesis call. Voice cloning adds
`speaker_similarity` + a reference-voice field; speech translation adds
translation-adequacy metrics judged by text comparison in the *target*
language + `emotion_preservation` when measurable. Nothing existing
changes shape.
