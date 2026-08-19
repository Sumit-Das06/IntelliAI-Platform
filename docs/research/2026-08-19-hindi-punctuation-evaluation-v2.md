# Hindi Punctuation Evaluation v2 + Word-Copy Decoder (M29B-DATA)

| | |
|---|---|
| **Status** | EVALUATION COMPLETE — classification **B: PROMISING — the smallest next step is a founder review, not more code**; NOTHING integrated, production unchanged |
| **Date** | 2026-08-19 |
| **Benchmark** | `hi-punct-eval@v2` — 148 rows (88 read-paragraph + 60 spontaneous), sha256 `edbddee8a1dd2a092955f6b21a7d38cf5d4b6c2a8eb13fe27350b8cacd753eff` |
| **Evidence** | `research/experiments/29b-hindi-punctuation-eval/` |
| **Follows** | [M28 architecture](2026-08-19-hindi-punctuation-restoration.md) · [M29A evaluation v1](2026-08-19-hindi-punctuation-evaluation-v1.md) |

Labels: **VERIFIED FROM REPO** · **MEASURED** · **WEB-RESEARCHED** ·
**ESTIMATED** · **UNKNOWN** · **PROPOSED**.

---

## 1. The M29A baseline (where this milestone started)

M29A ne classification B diya tha, do wajah se: (1) benchmark
single-sentence read speech tha — asli dictation jaisa nahi; (2) lead
model ki pipeline **words tod deti thi** (`M16 → <Unk>16`) — invariant
96.23%, jabki requirement 100% hai. Spontaneous Hindi punctuation
quality = UNKNOWN thi kyunki koi punctuated spontaneous reference
existed hi nahi.

## 2. V2 objective

Ek hi sawaal: **behtar product-shaped data + word-copy decoder ke saath,
kya lead model runtime integration ke laayak ho jaata hai?**

## 3. Benchmark composition — `hi-punct-eval@v2` (MEASURED)

Frozen manifest (`ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json`,
provenance sidecar in `ml/datasets/manifests/`), two domains reported
SEPARATELY, never blindly averaged:

| Component | Rows | Construction | Marks |
|---|---|---|---|
| **read-paragraph** | 88 | deterministic: consecutive v1 rows in groups of 3, dedup order — the M29A probe PROMOTED to a frozen component; every paragraph carries its member ids and is **reconstructible byte-for-byte** (test-pinned) from the pinned FLEURS revision | 6,606 words; 323 sentence boundaries; danda 81 / comma 266 / "." 240 |
| **spontaneous** | 60 | stt-hi-public-eval@v1 Extempore/Conversation clips (ascending id, first 60), reference transcripts hand-punctuated per the committed style guide; **builder refuses any annotation that changes words** (also test-pinned against the frozen ASR eval) | 1,087 words; 108 boundaries; danda 91 / comma 79 / **"?" 17** (v1 had 1) |

`hi-punct-eval@v1` remains the frozen single-sentence component —
complemented, not replaced. Probe sets (questions, edges) are committed
research probes, not benchmark rows. Audio is not vendored; every row
records its source audio identity.

## 4–5. Spontaneous annotation + style guide

- Written style guide BEFORE annotation:
  `annotation-style-guide-v1.md` (danda-only sentence enders for
  Devanagari, lexical-cue-only questions, sparing commas, filler/number/
  URL/truncation rules, uncertainty flagging). **The guide is part of the
  benchmark's provenance — there is no universal "correct" style.**
- **Annotator record (honest):** single annotator — the automated
  research assistant preparing this milestone (**AI, not a human native
  speaker**), TEXT-ONLY (no audio heard), prior exposure to model
  outputs disclosed. **PROVISIONAL until founder native-speaker
  review.** 24/60 rows carry explicit uncertainty flags with reasons.
- Data quality (**MEASURED**, `data-quality-review.json`): 17.2 marks
  per 100 words; mean sentence 10.1 words; 7.8 filler tokens per 100
  words; 4 fragment rows; only 2/60 rows contain Latin script (this
  slice barely exercises Hinglish — the probes do); 60 rows / 1,087
  words is SMALL — it bounds confidence, not a final verdict.

## 6. Question probes

30 authored questions (kya/kyon/kab/kahan/kaise/kaun/kitna, tags,
choice, Hinglish, declarative-form) + **12 statement controls** for
false-positive measurement. Committed as `question-probes.json`.

## 7. Edge probes

22 authored corruption probes (`edge-probes.json`): every M29A
corruption class (M16, pH, GMT, Apple, CEP, TogiNet, URLs, emails) plus
decimals, dates, spoken numbers, Hinglish, emoji, mixed script, PNR.
Rule: **any lexical corruption = FAIL.**

## 8. The word-copy decoder (the key engineering result)

**VERIFIED FROM REPO** (punctuators source + model config.yaml): the
ONNX graph returns argmaxed label ids for 4 heads; the upstream pipeline
then RECONSTRUCTS text from sentencepiece ids — that reconstruction is
where words died. Two further findings: the sentencepiece model is
lowercase-trained but the upstream pipeline never lowercases (uppercase
→ `<unk>` pieces), and the label set has **no "!" at all** — this model
can never predict exclamation (v1's `! F1 = 0` was partly structural).

The research decoder (`wordcopy_decoder.py`, scratch-venv only):

```
input words ──(casefolded pieces, per-word alignment)──▶ ONNX ──▶ mark per word
output = apply_marks(input text, marks)   ← ORIGINAL words, VERBATIM
```

- `apply_marks` lives in the evaluation plane
  (`intelliai_evaluation/punctuation.py`) — pure, dependency-free, and
  the contract is structural: tokens are copies; only supported marks
  attach at token boundaries; slot-count and mark-vocabulary violations
  are refused (`MarkApplicationError`). Foreign label variants normalize
  per a committed map (？→?, ،→, …); semicolon/Ethiopic labels drop.
- Windows: ≤126 pieces, word-aligned, 8-word overlap, core-region
  predictions. Deterministic.

## 9. Invariant by construction — MEASURED, not assumed

| Surface | old pipeline | **word-copy** |
|---|---|---|
| v1 (265 rows) | 96.23% | **100%** |
| read-paragraph (88) | 88.64% | **100%** |
| spontaneous (60) | 100% | **100%** |
| edge probes (22) | **13/22 CORRUPTED — FAIL** | **0/22 — PASS** |
| perf tiers (5–600 s) | — | 100% |

Zero `<unk>`, zero word changes, anywhere. M16, pH, GMT, Apple,
support@example.com, dates, decimals, emoji, PNR — all verbatim.

## 10. M29A benchmark re-run (v1, 265 rows) — C vs D

| System | micro F1 | boundary F1 | comma F1 | invariant |
|---|---|---|---|---|
| No-op | 0.0 | 0.0 | 0.0 | 100% |
| Rules | 0.1706 | 0.8942 | 0.0 | 100% |
| Lead + OLD reconstruction | 0.2421 | 0.7497 | 0.3467 | 96.23% |
| **Lead + word-copy** | 0.2420 | 0.7497 | 0.3481 | **100%** |

**The decoder costs nothing in quality and buys total word safety** —
plus it is ~10× faster in batch (2.99 s vs 30.99 s for 265 rows) and
lighter (RSS peak 428 vs 616 MiB).

## 11. Multi-sentence result (read-paragraph, 88 rows) — MEASURED

| System | micro F1 | boundary P | boundary R | boundary F1 | comma F1 | invariant |
|---|---|---|---|---|---|---|
| Rules | 0.0739 | 0.9773 | 0.2687 | 0.4216 | 0.0 | 100% |
| Lead + old | 0.2589 | 0.6496 | 0.9435 | 0.7695 | 0.3678 | 88.64% |
| **Lead + word-copy** | 0.2606 | 0.6195 | 0.9313 | 0.7441 | 0.3890 | **100%** |

Mid-text boundaries: model finds **93%**, rules find 27%. The model's
cost is precision 0.62 (over-segmentation). Note: the argmaxed ONNX
outputs expose no probabilities — precision tuning means post-filters,
not thresholds.

## 12. Spontaneous result — the first meaningful number (MEASURED)

Against the PROVISIONAL annotated references:

| System | micro F1 | boundary P | boundary R | boundary F1 | comma F1 | question F1 | invariant |
|---|---|---|---|---|---|---|---|
| No-op | 0.0 | 0 | 0 | 0.0 | 0.0 | 0.0 | 100% |
| Rules | 0.4211 | 1.0 | 0.5556 | 0.7143 | 0.0 | 0.1053 | 100% |
| **Lead + word-copy** | **0.5747** | 0.7182 | 0.7315 | **0.7248** | **0.4462** | 0.50 | **100%** |

Spontaneous Hindi par model READ speech se BEHTAR dikha (F1 0.57 vs
0.24-0.26) — kyunki yahan style confound nahi hai (references danda-only
hain, FLEURS ki tarah ।/. mix nahi). Failure pattern (worst rows,
`spontaneous-examples.json`, never hidden): the model joins spoken-flow
clauses with "," where the reference cuts with "।", and misses "?" on
tag questions — style disagreements more than word-placement failures;
plus one real error (a price statement ending "…बोरी का" got "?").
Rules' boundary 0.71 here is again the short-clip artifact: recall 0.56
and zero commas; clips average 18 words.

**Caveat that cannot be skipped: these references are single-annotator
AI annotations, PENDING founder review. This number is the first
evidence, not the final word.**

## 13. Question result

Lead + word-copy: **21/30 (70%)** correct, **0/12 false positives** on
statement controls, detection F1 0.8235. Rules: 5/30 (16.7%).

The 9 misses, inspected: 6 are tag/declarative questions (…है ना,
तुमने खाना खा लिया) — **intonation questions that NO text-only system
(or text-only human) can recover**, exactly the class the style guide
flags; 3 are lexically-cued misses (choice "…या कल", embedded किसने,
Hinglish declarative). On **lexically-cued questions: 21/23 = 91.3%**.
The M29A-proposed ≥80% gate was written before this distinction existed
— a revised framing is PROPOSED in §16, not silently promoted.

## 14. Edge-case result

Word-copy: **22/22 clean** — no `<unk>`, no token corruption, no
punctuation inserted inside URLs/emails (the model may still place a
mark AFTER such tokens; nothing lexical changes). Old pipeline on the
same probes: 13/22 corrupted. Examples in `edge-results.json`.

## 15. Performance (development machine — NOT a production SLA)

**MEASURED** (`perf-tiers-v2.json`, best of 3, 16 logical cores):

| Tier | model | decoder | total |
|---|---|---|---|
| 5 s | 0.015 s | 0.00004 s | **0.015 s** |
| 30 s | 0.027 s | 0.00006 s | 0.027 s |
| 120 s | 0.081 s | 0.00011 s | 0.081 s |
| 300 s | 0.236 s | 0.00025 s | 0.236 s |
| 600 s | 0.451 s | 0.00058 s | **0.451 s** |

Cold load incl. download 36.3 s (once, M28); warm disk load **0.88 s**;
RSS peak **427.9 MiB** (old pipeline: 616). The decoder itself is
negligible (<0.15% of total). Against the M28 target (≤10% of STT p50):
~1% at the 30 s dictation tier. Deploy-box numbers stay **UNKNOWN**
until the implementation milestone re-ladders there.

## 16. Revised gate assessment (M29A-proposed bars, as MEASURED)

| Gate (M29A PROPOSED) | Measured (lead + word-copy) | Verdict |
|---|---|---|
| Invariant 100% | 100% everywhere; edges 0/22 | **PASS** |
| Boundary F1 ≥ 0.75 (multi-sentence) | 0.7441 paragraphs / 0.7248 spontaneous | **FAIL** (by 0.006 / 0.025) |
| Boundary recall ≥ 0.85 | 0.9313 paragraphs / 0.7315 spontaneous | PASS / **FAIL** |
| Boundary precision ≥ 0.65 | 0.6195 paragraphs / 0.7182 spontaneous | **FAIL** / PASS |
| Comma F1 ≥ 0.30 | 0.389 / 0.4462 | **PASS** |
| Questions ≥ 80% | 70% overall; 91.3% lexically-cued; 0 FP | **FAIL** as written |
| Latency p95 ≤ 10% of STT p50 | ~1% (dev box) | **PASS** (dev) |
| RAM ≤ 700 MiB | 427.9 MiB peak | **PASS** |
| ASR CER/WER byte-identical | no runtime stage exists in this milestone | **NOT APPLICABLE** (moves to M29B-runtime) |

**Revised framing — PROPOSED, REQUIRES APPROVAL (thresholds NOT changed
silently):**
1. Split the question gate: ≥85% on LEXICALLY-CUED questions (measured
   91.3%) + 0 false positives on statements (measured 0) — intonation
   questions are text-unrecoverable and belong to a future
   audio-features idea, not this gate.
2. Boundary gates should be ratified against FOUNDER-REVIEWED
   spontaneous references: on provisional references the shortfalls
   (0.006–0.12) are within annotation-style noise for "," vs "।" joins
   — the review may move the measured number in either direction.
3. Keep invariant 100%, comma ≥0.30, latency, RAM as proposed
   (all currently PASS).

## 17. Domain gaps that remain

- Spontaneous references are PROVISIONAL (single AI annotator) — the
  single most important open item, and the cheapest (one founder
  session over 60 short rows, 24 already flagged).
- Long spontaneous dictation (multi-minute monologue) still has no
  punctuated references — paragraphs are read-speech surrogates.
- Hinglish quality is probe-level evidence only (2/60 spontaneous rows
  carry Latin script).
- Exclamation is structurally impossible for this model (no "!" label).

## 18. Decision matrix

| Candidate | Domain | micro F1 | Boundary F1 | Boundary R | Comma F1 | Question | Invariant | Latency 600s | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| No-op | all | 0.0 | 0.0 | 0.0 | 0.0 | — | 100% | 0 | today's floor |
| Rules | fleurs-single | 0.1706 | 0.8942 | 0.8162 | 0.0 | 16.7% | 100% | ~0 | benchmark artifact |
| Rules | read-paragraph | 0.0739 | 0.4216 | 0.2687 | 0.0 | — | 100% | ~0 | blind inside text |
| Rules | spontaneous | 0.4211 | 0.7143 | 0.5556 | 0.0 | — | 100% | ~0 | final-ender only |
| Lead+old | read-paragraph | 0.2589 | 0.7695 | 0.9435 | 0.3678 | 70% | **88.6%** | 0.31 s | word-destroyer — rejected |
| **Lead+word-copy** | fleurs-single | 0.2420 | 0.7497 | 0.9657 | 0.3481 | — | **100%** | — | style-confounded floor |
| **Lead+word-copy** | read-paragraph | 0.2606 | 0.7441 | 0.9313 | 0.3890 | — | **100%** | — | product-shaped read |
| **Lead+word-copy** | **spontaneous** | **0.5747** | **0.7248** | 0.7315 | **0.4462** | 70% (91.3% cued) | **100%** | **0.451 s** | the real signal |
| Cadence-Fast | — | — | — | — | — | — | — | — | still LICENSE BLOCKED |

## 19. Recommendation

**Classification: B — PROMISING.** A is not claimable: three
M29A-proposed bars (boundary F1, spontaneous boundary recall, question
%) read FAIL as written, and the spontaneous references that decide two
of them are PROVISIONAL. But the exact gap is now tiny and precisely
named — and it is a **decision gap, not a data-volume or code gap**:

1. **Founder review session** (~30–60 min): ratify/amend the 60
   spontaneous annotations (24 flagged) + the style guide v1.
2. **Founder gate ratification**: accept or amend the §16 revised
   framing.
3. Re-score (seconds, everything is committed and deterministic).

If the ratified gates pass on the reviewed references →
**M29B-runtime** is unblocked. The decoder side is DONE and proven:
invariant 100% by construction, zero corruption, negligible cost.

## 20. Exact next milestone

**M29C-ratify (founder-gated, small):** review annotations → re-score →
gate verdict. Then, if GO: **M29B-runtime** — the M28 architecture
(runtime post-merge stage, fail-open, hi-only, raw+punctuated contract,
§14-C sample semantics) with the production decoder implemented on the
word-copy contract (`apply_marks` is already in the evaluation plane;
the runtime needs its own vendored ONNX wrapper + artifact pinning) and
the full M28 §24 gate battery, including the byte-identical CER/WER
proof that was NOT APPLICABLE here.

---

Production behavior after M29B-DATA: **completely unchanged** — repo
additions are the v2 benchmark + provenance, the style guide +
annotations, probes, the `apply_marks` contract + tests in the
evaluation plane, research instruments + evidence, the ledger append,
and this document. No runtime, API, client, routing, metering, or
Speech Sample change. Hindi still serves unpunctuated.
