# Hindi Punctuation Restoration — Architecture Research (M28)

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — recommendation ready, decision required, NOTHING implemented |
| **Date** | 2026-08-19 |
| **Question** | Which punctuation-restoration architecture should IntelliAI use? |
| **Evidence** | `research/experiments/28-hindi-punctuation/` — `punctuation-baseline.json`, `punctuated-sources.json`, `tiny-benchmark.json` |

Labels used throughout: **VERIFIED FROM REPO** (read from our code/data),
**MEASURED** (an instrument ran and produced the number), **WEB-RESEARCHED**
(a model card or repository page — a claim, not our measurement),
**ESTIMATED** (a calculation from measured inputs), **UNKNOWN** (we do not
know yet and say so).

---

## 1. Problem statement

The promoted Hindi model (`qwen3-asr-0.6b-hi-ft-e3@v1`) transcribes Hindi
speech accurately but writes it **without any punctuation** — no danda (।),
no comma, no question mark. English output from the same stack IS
punctuated. The founder observed this in real product testing (Speech
Samples console, 2026-08-19).

For a dictation product this matters: a user who speaks two sentences gets
one unbroken line, and a spoken question does not end with "?". The words
are right; the writing is unfinished.

## 2. Verified current data findings

All numbers below are **MEASURED** by
`m28_punctuation_baseline.py` (evidence: `punctuation-baseline.json`).

**Training corpus `qwen-hi-public-train@v3`** (E3's data, 15,192 rows):

| Language | Rows | Rows with ANY punctuation | danda । | comma , | ? | ! | : | ; | . |
|---|---|---|---|---|---|---|---|---|---|
| Hindi | 14,224 | **0 (0.0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| English | 900 | **900 (100.0%)** | 0 | 960 | 5 | 2 | 6 | 3 | 1,039 |
| zxx (negatives) | 68 | 0 (0.0%) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Model outputs on the frozen eval `stt-hi-public-eval@v1`** (153 clips,
per-clip `hypothesis_text` from the official result files):

| Model | Clips with ANY punctuation | danda | comma | ? | . |
|---|---|---|---|---|---|
| E3 (M23 run) | **0 / 153 (0.0%)** | 0 | 0 | 0 | 0 |
| E3 (M23 replicate) | 0 / 153 (0.0%) | 0 | 0 | 0 | 0 |
| E2, E1 | 0 / 153 (0.0%) | 0 | 0 | 0 | 0 |
| **whisper-small (incumbent, M24 fresh run)** | **86 / 153 (56.2%)** | 24 | 189 | 9 | 50 |
| **Qwen3-ASR base (pre-fine-tune, M17)** | **21 / 153 (13.7%)** | 1 | 24 | 0 | 2 |

Two conclusions fall straight out of this table:

1. **The incumbent DID punctuate Hindi (partially).** Switching hi to E3
   removed punctuation the product used to have. This is a behavioral
   regression against whisper-small on a dimension no gate measured.
2. **Fine-tuning erased the base model's punctuation habit.** Base Qwen
   punctuated 13.7% of clips; after 30 hours of supervision in which every
   Hindi transcript was unpunctuated, E1/E2/E3 all emit exactly zero marks.

E3's **English** probe outputs are 100% punctuated (18/18 sweep probe
texts carry commas — **MEASURED** from `sweep-probes.json`), matching the
900 punctuated FLEURS English training rows. The model writes each
language exactly the way its training slice was written.

## 3. Why current E3 has no punctuation

- **VERIFIED FROM REPO**: our ingestion pipeline preserves punctuation
  verbatim — pinned by
  `ml/datasets/tests/test_validate.py::test_case_and_punctuation_survive`.
  So the zero-punctuation Hindi rows reflect the **sources**
  (IndicVoices and Kathbath transcribe spontaneous speech without
  punctuation marks), not our processing.
- **VERIFIED FROM REPO**: no gate could have caught it. The scoring
  ruler (`ml/evaluation/src/intelliai_evaluation/normalization.py`,
  `UNICODE_GENERIC_V2`) keeps only Unicode categories L/M/N — every
  punctuation character (category P) becomes a space and disappears at
  `.split()`. CER/WER are **punctuation-blind**: a model that punctuates
  perfectly and a model that never punctuates score identically.
- The frozen eval references themselves contain **zero** punctuation
  (**MEASURED**: 0/153 clips), so even a punctuation-aware metric run
  against this set would have nothing to compare with.

Not a bug — a data property, the mirror image of the E2 English lesson.
But it is a **product-quality gap**, and it is currently unmeasured.

## 4. Current punctuation baseline

Baseline of the SERVED Hindi path today (E3, no restoration layer):

| Measure | Value | Label |
|---|---|---|
| Word/text preservation | 100% (identity — nothing modifies the text; see §16–18) | VERIFIED FROM REPO |
| Punctuation precision | undefined (zero marks predicted) → 0 by convention | MEASURED |
| Punctuation recall | **0.0** | MEASURED |
| Punctuation F1 | **0.0** | MEASURED |
| Sentence-boundary F1 | **0.0** (no sentence enders ever emitted) | MEASURED |

The transcript path is byte-exact end to end (**VERIFIED FROM REPO**,
full trace in §16–18): engine → runtime → gateway → response → client
insertion, with only whitespace trims at three boundaries. Any
punctuation a user has ever seen was the model's own output.

## 5. Punctuation contract

The layer we eventually build must obey one law:

```
Input : raw transcript text (the ASR's words)
Output: the SAME words + punctuation (+ optional capitalization for Latin script)

Invariant:  depunct(output) == depunct(input)

where depunct(t) = NFC(t).casefold(), every Unicode category-P char → space,
                   whitespace collapsed to single spaces
```

The layer is **not** a grammar corrector, translator, paraphraser, or text
improver. If the invariant fails, the punctuated result is **rejected and
the raw transcript is served** — punctuation can never make a transcript
worse than having no punctuation.

This check is cheap (pure string transform), deterministic, and was
exercised in the tiny benchmark (§22): **PASS on every input tested**.
It must ship as a hard gate in any implementation.

**Supported punctuation set** — the smallest useful one:

| Mark | Include? | Why |
|---|---|---|
| । (danda) | YES | the Hindi sentence end — the single most visible gap |
| ? | YES | spoken questions are common in dictation; benchmark showed correct detection |
| , (comma) | YES | biggest readability gain inside long sentences |
| ! | LATER | rare; low training signal; harmless to add in v2 |
| . (Latin full stop) | English/Hinglish segments only | in Devanagari context danda is the sentence ender |
| : ; quotes () | NO for now | rare in speech, high subjectivity, expands the eval burden |

## 6. Evaluation dataset strategy

`stt-hi-public-eval@v1` stays frozen and untouched — and it cannot judge
punctuation anyway (its references carry none). We need a separate,
new frozen set:

**Hindi Punctuation Evaluation v1** — proposed composition:

- **Source: FLEURS `hi_in` test split** (google/fleurs, CC-BY-4.0 — the
  same source family M23 already approved for the English retention
  slice). **MEASURED** (`punctuated-sources.json`, text-only probe, no
  audio downloaded): 418 test rows, **99.8% punctuated** — 126 dandas,
  398 commas, 375 Latin full stops, 1 question mark. Train split: 2,120
  rows at 99.9%; dev: 239 rows at 98.7%.
- **Style caveat (MEASURED)**: FLEURS Hindi mixes sentence-final "।" and
  "." — reference curation must define a sentence-end policy (§7).
  Only `raw_transcription` is usable; the `transcription` column already
  drops most punctuation.
- **Limitation (honest)**: FLEURS is **read speech**. Spontaneous
  dictation (our real traffic) has different rhythm. v1 starts with
  FLEURS because it is licensed, punctuated, and audio-backed; a small
  human-punctuated spontaneous slice (e.g. IndicVoices clips punctuated
  by a human annotator) is the right **v2** upgrade and needs a
  cost/effort decision.
- Sources checked and unusable: Common Voice hi (CC0, gated download,
  punctuation **CLAIMED** not verified — datasets-server returned 404);
  Shrutilipi (gated, 401 — **UNKNOWN** punctuation style); IndicVoices/
  Kathbath (**MEASURED**: unpunctuated — that is the root cause).

Two evaluation modes, in order of importance:

1. **Text-level (primary)**: take the punctuated reference, strip its
   punctuation, feed the stripped text to the restorer, compare with the
   reference. Isolates punctuation quality from ASR word errors.
2. **End-to-end (secondary sanity)**: E3 audio → transcript → restorer,
   aligned against the reference. ASR word errors pollute this number;
   report it, don't gate on it alone.

## 7. Evaluation metrics

Plain-language definitions (no jargon without explanation):

- **Precision** — of the marks the layer inserted, how many were right?
- **Recall** — of the marks that should exist, how many did it insert?
- **F1** — the balance of the two (harmonic mean); high only when both are high.

Proposed metrics:

- **PRIMARY: micro-averaged punctuation F1** over the supported set
  (§5) — every inserted/expected mark counts equally, computed on
  position-aligned tokens.
- Secondary: **per-mark F1** (danda, comma, question mark separately —
  commas are subjective; danda and ? matter most to readers).
- Secondary: **sentence-boundary F1**, where danda, "?", "!" and "." all
  count as one "sentence end" class — this neutralizes the FLEURS
  "। vs ." style mix instead of penalizing it.
- **HARD GATE (not a metric): the §5 invariant** — 100% pass required.

## 8. Option A — rule-based restoration

What rules can honestly do (**no ML**): append one final danda when a
Hindi transcript ends without a sentence ender; maybe insert "?" when an
utterance starts with an interrogative (क्या/कौन/कब/कहाँ/क्यों/कैसे).

What they cannot do: find sentence boundaries **inside** a 600-second
transcript (that is the actual product need — a 100-word wall of text),
place commas, or distinguish "क्या" as question-starter from "क्या" as
mid-sentence filler ("बोले बनाइए क्या अच्छा बनाते हो"). Hindi word order
makes interrogatives position-free; boundary detection IS a sequence
problem.

**Verdict: not viable as the restorer.** But one slice of Option A
survives in the recommendation: the deterministic **invariant gate**
(§5) wrapped around whatever model runs.

## 9. Option B — small local punctuation-restoration model

Token-classification models read the whole text and predict, for each
word position, "which mark (or none) follows". They **cannot rewrite
words by construction** — the output is the input tokens plus label-driven
marks. The §5 contract is satisfied structurally, not by prompt-begging.

Candidates researched (full table in §22). The lead candidate,
`1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase`
(Apache-2.0, ONNX, 47 languages including Hindi, danda in its label set),
was benchmarked on **our real E3 outputs** (§22): danda/comma/? emitted
correctly, invariant PASS everywhere, 0.5 s for a 600-second transcript
on this CPU, ~0.6 GiB RAM.

**Verdict: viable, and the strongest option.** Risks: trained on news
text (register shift vs spontaneous speech — quantify with the §6 eval);
the `punctuators` wrapper package is prototype-grade (31 stars, 11
commits — **WEB-RESEARCHED**), so we would vendor a minimal
onnxruntime+sentencepiece wrapper (~100 lines; the model card documents
manual usage) instead of depending on it.

## 10. Option C — LLM-based restoration

A small local instruct LLM (e.g. a 0.6–1.7B GGUF under our existing
llama.cpp runtime) prompted to "add punctuation, change nothing else".

- **Latency (ESTIMATED** from our measured llama.cpp CPU behavior): an
  LLM must re-generate the entire text. A 600 s transcript ≈ 7,300 chars
  ≈ 2,400–3,600 output tokens; at a realistic 20–40 tok/s on our CPU
  class that is **60–180 seconds — punctuation would take longer than
  the STT decode itself** and would crush the 3× concurrency headroom
  proven in M24.
- **Word preservation is not structural.** LLMs paraphrase, "fix"
  grammar, normalize dialect ("रहे हैं" → "रहे हो" class of edits) — the
  exact failures the product requirement forbids. The invariant gate
  would catch them, but every rejection wastes the full generation cost
  and serves raw text anyway.
- Deterministic output requires temperature 0 and still shifts across
  quantizations/versions; prompt sensitivity is real.
- An **external** LLM API is rejected outright (§19): customer
  transcripts must not leave our infrastructure.

**Verdict: wrong tool.** Slow where the classifier is fast, unsafe where
the classifier is safe by construction.

## 11. Option D — fine-tune Qwen to punctuate (an E4)

Could we teach E3 itself? The data exists: FLEURS `hi_in` train is 2,120
punctuated rows (**MEASURED**, 99.9% punctuated, CC-BY-4.0, same source
family as our approved English slice).

- For: no serving change, zero added latency, one artifact.
- Against — and these are heavy:
  1. **Signal imbalance**: 2,120 punctuated read-speech rows against
     14,224 unpunctuated spontaneous rows teaches "FLEURS-style audio →
     punctuation, IndicVoices-style audio → none" — punctuation would
     appear inconsistently, keyed to acoustic register. Fixing that
     means punctuating the 14k spontaneous rows (no such source exists;
     human annotation or model-assisted labeling — a project in itself).
  2. **Risk to a promoted model**: E3 passed every gate (M23/M24); a new
     mix re-rolls those dice. The E2 English regression taught us
     composition changes have side effects.
  3. **Coverage**: fixes only the Qwen hi route. whisper-small's partial
     56% punctuation stays inconsistent; every future engine re-solves
     punctuation from scratch. A backend layer covers all of them
     uniformly.
  4. Iteration speed: retraining + full gate battery per tweak vs
     re-running a text-level eval in seconds.

**Verdict: not now.** Park as a possible later complement (an E4 could
*reduce reliance* on the layer), to be judged as its own experiment with
its own gates. DO NOT TRAIN was the M28 rule and nothing here needs it.

## 12. Option E — hybrid

The recommendation is a hybrid in one specific sense: **the Option B
model wrapped in the Option A deterministic gate** (invariant check,
fail-open to raw text). Not two restorers — one restorer, one guard.
This gives the best quality/latency tradeoff available: the classifier's
quality and speed, the rules' determinism as a safety boundary.

## 13. Long-audio implications

**Punctuate per chunk or after merge?**

- Per Qwen chunk (≤120 s windows): each chunk boundary is an arbitrary
  100-second cut, usually mid-sentence. The restorer would see sentence
  fragments at every seam and confidently end them with dandas —
  spurious sentence breaks at exactly the places our merge law
  (`merge_chunk_text`, overlap dedup) works hard to keep seamless. Also:
  punctuation marks inside chunk text would enter the overlap
  dedup path (they normalize away for matching but stay in output —
  VERIFIED `qwen3_asr.py` `normalize_for_merge`), adding a new
  interaction with a frozen, proven law.
- **After the final merge (RECOMMENDED)**: the restorer sees the whole
  utterance with full sentence context; the proven merge law is
  untouched; and it is affordable — **MEASURED 0.505 s** for a
  600-second-equivalent transcript, ~1% of that job's STT decode time.

Within the restorer, its own internal windowing (256-token subword
windows in the lead candidate) handles arbitrarily long text; window
seams there shift a boundary by a word, not a sentence — quantified by
the §6 eval.

## 14. Speech Sample implications

Today (**VERIFIED FROM REPO**): `original_transcript` = exactly the
served text (`collection.py:177`), `current_transcript` born equal to it
(`speech_samples.py:63-64`), original immutable
(`speech_sample.py:126`), events append-only.

The three choices in the M28 spec:

- (A) punctuate before storage → `original_transcript` becomes punctuated;
  raw ASR output is LOST; future ASR training data would carry another
  model's punctuation baked in — **provenance corruption. Rejected.**
- (B) punctuate after storage only → stored raw, served raw?? — the
  response is built after storage, so this degenerates to either A or C.
- **(C) retain both — RECOMMENDED**: `original_transcript` stays the RAW
  ASR output (training provenance, the flywheel's ground truth of what
  the machine heard); the punctuated text is what the API serves and
  what `current_transcript` starts from; a `punctuated` **event**
  (existing append-only mechanism) records that the layer ran, with the
  restorer's identity/version in `detail`.

Future training then distinguishes cleanly: **ASR output** =
`original_transcript`; **punctuation-restored** = the `punctuated` event
(+ current before any correction); **human correction** = `corrected`
events / `current_transcript`. One law changes and must be re-worded in
a reviewed diff: "current == original at birth" becomes "current = what
the user was shown at birth" — the schema itself needs no new column,
though adding `served_transcript` explicitly is a reviewable alternative.

## 15. Correction implications

If the layer adds "।" and the user edits to "…हूँ!", the existing
correction flow already handles it: the correction endpoint updates
`current_transcript` and appends a `corrected` event; `original_transcript`
is untouched (**VERIFIED FROM REPO** — correction sends text EXACTLY as
entered, `CorrectionActivity.kt:72`). With §14-C, provenance after a
correction reads: raw ASR → punctuated (event) → human correction
(event) — nothing lost. Human corrections of punctuation are, in the
long run, the best possible training data for a self-improved punctuation
model — the flywheel argument for storing all three forms.

## 16. Web implications

**VERIFIED FROM REPO**: the console assigns the response verbatim
(`studio.html:308` — `transcript.value = body.text`), displays samples
raw (`samples.html:313`). **Zero web changes needed** — the punctuated
text flows through like any text.

## 17. Android implications

**VERIFIED FROM REPO**: the client inserts the transcript verbatim; the
leading-space law (`EditorActions.kt:33-46`) prepends one space only when
the cursor sits after a non-space AND the transcript starts with a
letter/digit — "IntelliAI STT's own punctuation and casing are
preserved" is already a pinned test. **Zero Android changes needed.**

## 18. iOS implications

**VERIFIED FROM REPO**: verbatim insertion via `textDocumentProxy`
(`KeyboardViewController.swift:123-132`). Two pre-existing nits found
during this research (neither blocks anything, both are notes for the
next iOS session):

- iOS trims the transcript (`IntelliAIApiClient.swift:205-206`); Android
  does not. Harmless today (engines already strip).
- The iOS space rule checks only the preceding character, Android also
  requires the transcript to START with a letter/digit — a transcript
  starting with "।" would get a leading space on iOS but not Android.
  Restoration never produces mark-first text (marks attach after words),
  so this stays cosmetic.

**Zero iOS changes needed** for punctuation itself.

**Client-agnostic requirement satisfied**: one backend layer, all three
clients receive the SAME punctuated transcript. No per-platform
punctuation. Edge cases (numbers, URLs, emails, abbreviations, mixed
Hinglish, emoji) belong in the eval set design, not in client code: the
token classifier never splits or rewrites tokens, so a URL stays a URL —
whether a stray mark lands after it is exactly what per-mark precision
measures. The benchmark already shows spoken numbers handled cleanly
("दस नौ दो हज़ार तेईस को… है।" — MEASURED, gallery).

## 19. Privacy

The recommended layer is **fully local**: an ONNX model executing on our
CPU inside our runtime container, seeded and hash-verified like every
other artifact, offline after seeding. No transcript leaves the box.

External punctuation APIs (cloud LLMs) are **rejected**: they would send
every customer utterance to a third party — a privacy regression the
platform's laws do not permit — plus per-request cost, added latency,
a new failure dependency, and no determinism. No quality gap observed so
far justifies even documenting them further.

## 20. Licensing

| Component | License | Status |
|---|---|---|
| `1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase` | Apache-2.0 | **WEB-RESEARCHED** (model card), permissive, commercial-safe — fits the platform's permissive-only law |
| `punctuators` package | Apache-2.0 | fine, but we would vendor a minimal wrapper anyway (§9) |
| ai4bharat/Cadence & Cadence-Fast | card says **MIT** | **CLAIMED — with a flag**: base model is Gemma-3, and Google's Gemma Terms of Use assert flow-down conditions on derivatives. The MIT label may not be the whole story. Needs legal verification BEFORE any adoption. |
| zicsx/Hindi-Punk | Apache-2.0 | WEB-RESEARCHED; model itself under-documented |
| FLEURS (eval/data source) | CC-BY-4.0 | already an approved source family (M23) |

## 21. Latency / RAM

**MEASURED** (`tiny-benchmark.json`; lead candidate, ONNX on this dev
CPU, single request, transcript lengths derived from the frozen eval's
measured 12.18 chars/sec):

| Transcript tier | Input chars | Latency | Invariant | Marks added |
|---|---|---|---|---|
| 5 s | 260 | **0.125 s** | PASS | 5 danda |
| 30 s | 412 | **0.142 s** | PASS | 8 danda, 2 comma |
| 120 s | 1,467 | **0.194 s** | PASS | 25 danda, 13 comma |
| 300 s | 3,782 | **0.301 s** | PASS | 56 danda, 35 comma, 1 ? |
| 600 s | 7,340 | **0.505 s** | PASS | 113 danda, 76 comma, 3 ? |
| English control | 104 | 0.120 s | PASS | 2 full stops (danda correctly NOT used) |

- Model load: 36.3 s cold (download) / **2.2 s warm** — loaded once at
  service start, like every other model.
- RAM (**MEASURED**, Windows working set): **469 MiB** after load,
  **578 MiB** after a 600 s-tier inference, peak 592 MiB. For scale: the
  E3 llama-server sits at ~1,559 MiB.
- Concurrency impact (**ESTIMATED**): at ~0.5 s per 600 s job and
  ~0.13 s per dictation utterance, the layer adds ≈1% to the busiest
  path; a single shared ONNX session per runtime process suffices.
- Production-box numbers (Linux/Hostinger class): **UNKNOWN** until the
  implementation milestone re-ladders there — dev-box numbers here set
  the shape, not the SLA.

**Target met with room to spare: punctuation does not dominate STT
latency — it rounds to noise.**

## 22. Candidate model comparison

| Model | Params | Hindi | Punctuation | License | CPU | RAM | Format | Verdict |
|---|---|---|---|---|---|---|---|---|
| **1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase** | xlm-roberta base class (**UNKNOWN** exact; ~280M typical) | YES (47 langs), danda label VERIFIED in card; **MEASURED working on our E3 outputs** | । , ? . + truecase + sentence boundaries | Apache-2.0 | **MEASURED** ≤0.5 s @600s-tier | **MEASURED** ~0.6 GiB | **ONNX** (+ sentencepiece) | **LEAD** — card claims Hindi punct 99.11 micro-F1, danda P 96.92 / R 98.66 (their news test set — CLAIMED, not our distribution); our tiny benchmark confirms behavior on real E3 text |
| ai4bharat/Cadence-Fast | 270M (Gemma-3-270M) | YES (en + 22 Indic), danda explicit | full set incl. ।, script-aware | MIT on card — **Gemma flow-down UNRESOLVED** (§20) | UNKNOWN (no ONNX; PyTorch + custom `modeling_*.py`, trust_remote_code) | 1.07 GB fp32 weights | safetensors only | **QUALITY CHALLENGER** — 2025 model, purpose-built for Indic; blocked on license verification + needs our own benchmark |
| ai4bharat/Cadence | 1.0B (Gemma-3-1B) | YES | same | same flag | heavier | ~4 GB fp32 | safetensors | over-budget for a helper layer; Cadence-Fast keeps 93.8% of it (CLAIMED) |
| zicsx/Hindi-Punk | ~0.2B (MuRIL BERT) | Hindi-only | marks not documented | Apache-2.0 | UNKNOWN | ~1 GB | PyTorch | thin card, no eval numbers, no ONNX — backup only |
| AI4Bharat/indic-punct (lib) | NeMo-based | YES (11 Indic) | ।, comma shown | LICENSE present, terms UNVERIFIED | heavy NeMo dependency | UNKNOWN | NeMo | 2022-era, maintenance UNKNOWN, dependency weight wrong for us |
| felflare/bert-restore-punctuation | 110M BERT | **NO** (English) | . , ? ! etc. | MIT | fine | ~0.4 GB | PyTorch | English-only — irrelevant for the Hindi gap |

Tiny-benchmark quality snapshot on REAL E3 outputs (MEASURED, gallery in
`tiny-benchmark.json`): boundaries and "?" mostly right — including
"क्या मैं आपको नगत रुपये दे सकता हूँ**?**" (the ASR's own words,
untouched) — with occasional
over-segmentation ("क्वालिटी।" cut as its own sentence). Exactly what
the §6/§7 eval exists to quantify. A model-card claim is never treated
as IntelliAI performance; the eval set decides.

## 23. Recommended architecture

**Option B — a small local token-classification punctuation model —
running in the backend as a post-merge stage, wrapped in the §5
deterministic invariant gate (fail-open to raw text).**

Lead model `1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase`
(Apache-2.0, ONNX), vendored behind a minimal onnxruntime wrapper.
Cadence-Fast enters as challenger if and only if its license verifies.

```
Client (Web / Android / iOS)
      │  audio
      ▼
API gateway ── auth, metering (audio-seconds; unchanged)
      │
      ▼
STT runtime
   ├─ engine decode (E3 direct ≤120 s / chunk+merge 120–600 s)  [unchanged]
   ├─ PUNCTUATION STAGE (new): final merged text → ONNX classifier
   │     · hi route only at first; config-gated per language
   │     · invariant gate: depunct(out) == depunct(in) else raw
   │     · any error/timeout → raw text (fail-open, never blocks STT)
   └─ returns BOTH: raw text + punctuated text (contract extension)
      │
      ▼
API gateway
   ├─ stores sample: original_transcript = RAW  (provenance, §14-C)
   │                 + "punctuated" event; current starts punctuated
   └─ response "text" = punctuated
      │
      ▼
All clients insert/display the SAME punctuated transcript  [zero client changes]
```

Placement rationale: models live in the runtime tier (artifact store,
hash-verified seeding, pins, RAM budgeting — all existing law); the
gateway stays model-free; every engine and every client inherits the
layer uniformly.

## 24. Implementation plan (the NEXT milestone, on approval)

1. **Hindi Punctuation Evaluation v1** — freeze FLEURS `hi_in` test-based
   set with pins + provenance; curation policy per §5–7; scorer
   (per-mark F1, micro F1, boundary F1, invariant checker) in
   ml/evaluation as a NEW capability — the frozen CER/WER ruler is not
   touched.
2. **Vendored restorer** — minimal onnxruntime+sentencepiece wrapper in
   the runtime; model registered as a pinned, hash-verified artifact
   (same ArtifactSpec law as GGUFs); config flag default OFF.
3. **Baseline + candidate eval** — text-level F1 for: no-op (current
   state), rules-only floor, lead model; Cadence-Fast if license clears.
4. **Runtime stage + contract extension** (raw + punctuated fields),
   invariant gate, fail-open, hi-only gating; sample-storage change per
   §14-C with the reworded birth law as a reviewed diff.
5. **Gate battery + staging** — the exact tests required before
   production adoption:
   - punctuation micro-F1 / per-mark F1 / boundary-F1 on Hindi
     Punctuation Evaluation v1 meet targets set from the step-3 baselines
   - **invariant gate 100%** across the full eval + the frozen eval's
     153 E3 hypotheses + long-audio outputs
   - CER/WER on frozen `stt-hi-public-eval@v1` **byte-identical** with
     the stage on vs off (the ruler strips punctuation — any drift means
     words changed, an automatic FAIL)
   - silence/noise negatives still yield empty text (stage must pass
     empty through untouched)
   - 300 s and 600 s long-audio law re-proven with the stage on
     (space-join law, billing, cancel-clean)
   - latency budget: stage p95 ≤ 10% of the route's STT p50 at every tier
   - RAM ladder re-run on the serving box class with the ONNX session loaded
   - leak test: no internal model names in any error path the stage adds
   - metering unchanged (audio-seconds; text length never billed)
   - sample provenance: original raw, `punctuated` event recorded,
     correction flow regression-tested
   - M24-style rehearsal through the local production-shaped stack
     before any promotion proposal.

## 25. Risks

- **Register shift**: news-trained model on spontaneous speech — comma
  precision likely suffers first. Mitigation: the eval quantifies it;
  comma can be disabled independently (drop its labels) if it fails its
  per-mark gate while danda/? pass.
- **Over-segmentation** (seen once in the gallery): short emphatic
  fragments get their own danda. Boundary-F1 gate + threshold tuning.
- **Wrapper abandonment**: `punctuators` is a prototype — mitigated by
  vendoring; the ONNX file + sp model are the stable assets.
- **Hinglish**: xlm-roberta is multilingual and the English control
  behaved (danda correctly withheld, full stops used), but mixed-script
  utterances need eval rows before claims. UNKNOWN until measured.
- **Sample-law change**: the "current == original at birth" rewording
  touches the flywheel's most load-bearing invariant — small diff, big
  review care.
- **Production-box performance**: dev-Windows numbers only so far;
  re-ladder on the deploy box class in the implementation milestone.

## 26. Open questions

1. Cadence-Fast license: does the MIT label survive Gemma ToU flow-down
   review? (Blocks the challenger, not the lead.)
2. Should English (whisper route) also pass through the layer for
   consistency, given whisper already punctuates ~56% of Hindi but its
   English is fine? Initial answer: no — hi only; revisit with data.
3. Spontaneous punctuated Hindi references (eval v2): human annotation
   budget and process — who punctuates, what style guide?
4. Does the correction UI need a "punctuation looks wrong" affordance,
   or is free-text correction (existing) enough? Existing is enough for v1.
5. Truecasing for Hinglish Latin segments: enable or ignore in v1?
   Proposal: ignore (punctuation only), revisit with eval rows.

## 27. Decision required

Founder decision, one of:

- **GO**: approve the §23 architecture + §24 plan as the next
  implementation milestone (M29 candidate) — punctuation eval set +
  vendored restorer + gates, everything staged, nothing promoted without
  its own reviewed proposal.
- **GO, eval-first**: approve only steps 1–3 (eval set + baselines),
  decide on the runtime stage after seeing measured F1.
- **NO-GO**: accept unpunctuated Hindi for now; this document remains
  the recorded analysis.

Nothing has been implemented, trained, deployed, or routed in this
milestone. E3, production routing, all clients, the API, metering, and
the frozen eval are untouched. The only repository additions are this
document and the read-only research instruments + evidence under
`research/experiments/28-hindi-punctuation/`.
