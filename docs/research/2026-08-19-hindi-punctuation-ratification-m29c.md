# Hindi Punctuation — Founder Review Applied + Ratified Gate Assessment (M29C)

| | |
|---|---|
| **Status** | RATIFICATION APPLIED — benchmark updated to `hi-punct-eval@v3`, scoring re-run, gates assessed; NO runtime change |
| **Date** | 2026-08-19 |
| **Review input** | founder-supplied `spontaneous-annotations-reviewed` (text-only linguistic review per style-guide v1) |
| **Benchmark** | `hi-punct-eval@v3` — 148 rows, sha256 `e92d43c2cdef53cfb7110c1c977074cbd2fb0fb40ef51645d6adc53fe545fa45` |
| **Evidence** | `research/experiments/29b-hindi-punctuation-eval/` — `spontaneous-annotations-review.json`, `gate-assessment-v3.json`, `decision-matrix-v3.json`, `metrics-v3-*` |
| **Follows** | [M29B-DATA report](2026-08-19-hindi-punctuation-evaluation-v2.md) |

## 1. The review, applied (VERIFIED FROM REPO)

The founder-supplied review of the 60 spontaneous annotations:

| Verdict | Rows | Handling |
|---|---|---|
| APPROVE | 49 | text unchanged |
| REVISE | 2 | comma-only insertions applied (000472: comma after देखिए; 000918: commas around the coordinated chunks) |
| AUDIO_REVIEW_REQUIRED | 9 | text unchanged; ids recorded in provenance; **excluded from the gate-bearing slice** |

The review's own stated limit rides in provenance verbatim: *"Not a
native-speaker/audio review; intonation-dependent cases are flagged for
audio/native review."* So the ratified slice is **text-ratified**, and 9
rows plus final native/audio confirmation remain open.

Because released manifests are immutable, applying the review created
**`hi-punct-eval@v3`** (v2 stays frozen as the pre-review record). The
builder re-verified, and tests now pin: both revisions are comma-only
(word law intact against the frozen ASR eval references); paragraphs are
verbatim v2 copies; exactly 2 rows differ from v2; and the
punctuation-stripped restorer inputs are **byte-identical** to v2's —
therefore the committed M29B predictions remain valid and nothing was
re-predicted (fully deterministic re-score).

## 2. Ratified numbers (MEASURED, lead + word-copy decoder)

| Slice | rows | micro F1 | boundary F1 | boundary P | boundary R | comma F1 | invariant |
|---|---|---|---|---|---|---|---|
| read-paragraph | 88 | 0.2606 | 0.7441 | 0.6195 | 0.9313 | 0.3890 | **100%** |
| spontaneous ALL | 60 | 0.5698 | 0.7248 | 0.7182 | 0.7315 | 0.4361 | **100%** |
| **spontaneous TEXT-RATIFIED** | **51** | **0.5695** | **0.7363** | 0.7204 | 0.7528 | 0.4333 | **100%** |
| spontaneous audio-flagged (informational) | 9 | 0.5714 | 0.6667 | 0.7059 | 0.6316 | 0.4615 | 100% |

Notes: the all-60 micro F1 moved 0.5747 → 0.5698 because the two revised
references added commas the model did not predict — the review made the
target slightly stricter, honestly reflected. The audio-flagged 9 score
LOWER on boundaries (0.667) than the ratified 51 (0.736) — consistent
with the review's judgment that exactly those rows are the ambiguous
ones, and validating their exclusion from gate-bearing numbers.

## 3. Gate assessment on ratified references (MEASURED)

**M29A-proposed gates, as written:**

| Gate | Measured (paragraphs / ratified-51) | Verdict |
|---|---|---|
| Invariant 100% | 100% / 100% (+ edges 0/22) | **PASS** |
| Boundary F1 ≥ 0.75 | 0.7441 / 0.7363 | **FAIL** (by 0.006 / 0.014) |
| Boundary recall ≥ 0.85 | 0.9313 / 0.7528 | **FAIL** (spontaneous side) |
| Boundary precision ≥ 0.65 | 0.6195 / 0.7204 | **FAIL** (paragraph side) |
| Comma F1 ≥ 0.30 | 0.3890 / 0.4333 | **PASS** |
| Questions ≥ 80% overall | 70% | **FAIL** |
| Latency ≤ 10% STT p50 | ~1% (dev box) | **PASS** (deploy-box re-ladder pending) |
| RAM ≤ 700 MiB | 427.9 MiB | **PASS** |
| CER/WER byte-identical | no runtime stage exists yet | NOT APPLICABLE (M29B-runtime) |

**Revised gates (PROPOSED — REQUIRES APPROVAL, from the M29B report §16):**

| Gate | Measured | Verdict |
|---|---|---|
| Questions ≥ 85% on LEXICALLY-CUED + 0 statement false positives | 91.3% + 0 FP | **PASS** |
| Boundary F1 ≥ 0.70 AND ≥ rules + 0.25 absolute (multi-sentence) | 0.7441 vs rules 0.4216 (+0.32) | **PASS** |

## 4. What this means (simple Hinglish)

Safety ka sawaal poori tarah band hai: word-copy decoder ke saath
invariant har ratified surface par 100% hai, edge corruption zero.
Quality ratified references par bhi wahin hai jahan M29B ne dikhaya tha —
**M29A ke original bars se thoda neeche, revised bars ke upar.** Ye ab
engineering ka nahi, THRESHOLD ka decision hai, aur wo aapka hai:

- **Option 1 — revised gates approve karein** (§3 ki dusri table): dono
  PASS hain → **M29B-runtime unblocked** (M28 architecture, fail-open,
  hi-only, full test battery incl. byte-identical CER/WER proof).
- **Option 2 — original bars par kayam rahein**: to model ki boundary
  precision/recall ko upar lana hoga (post-filters — model probabilities
  expose nahi karta — ya better/bigger restorer), aur ye ek naya research
  cycle hai.
- Kisi bhi option mein: 9 audio-flagged rows ki audio/native review aur
  ek final native-speaker confirmation open items hain (review file khud
  ye limit declare karti hai).

## 5. Repo state

Added: `hi-punct-eval-v3.json` + provenance, the committed review record,
`build_v3.py` / `score_v3.py`, `metrics-v3-*`, `gate-assessment-v3.json`,
`decision-matrix-v3.json`, 5 new manifest-law tests (677 evaluation tests
green, mypy strict clean). v1/v2 untouched and still frozen. **No
runtime, API, client, routing, metering, or Speech Sample change** —
production still serves unpunctuated Hindi.
