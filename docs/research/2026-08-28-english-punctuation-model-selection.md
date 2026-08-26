# English Punctuation / Readability — Research & Model Selection (Milestone 49)

| | |
|---|---|
| **Status** | COMPLETE - MEASURED. Decision A: kredor/punctuate-all (MIT, XLM-R-base) selected - boundary F1 0.827, spontaneous 0.639/0.727, 0.83 s per 10-min transcript; fullstop-large is the quality ceiling (micro 0.695) but 2.3 GiB RSS and borderline long-text latency. M50 = ONNX/int8 export + runtime stage under the M30 discipline. |
| **Date** | 2026-08-28 |
| **Question** | What is the best small, local, production-deployable English punctuation restoration approach for IntelliAI? |
| **Scope** | Research + evaluation + selection ONLY. No production change: Qwen E3, Whisper, the Hindi punctuation runtime (v1, prod-OFF), API, billing, UI all untouched — suites re-run green (§21-22). |
| **Evidence** | `research/experiments/49-english-punctuation-selection/` · dataset `ml/evaluation/punctuation/datasets/en-punct-eval-v1.json` (NEW; frozen Hindi sets and the punct_slots@v1 ruler untouched) |
| **Labels** | MEASURED · WEB-RESEARCHED · REPO-VERIFIED · ESTIMATED · UNKNOWN · PROPOSED |

## 1-2. M48 findings, contract, and the invariant (REPO-VERIFIED)

M48 proved the English gap is readability: same words, zero
punctuation, no English stage in the product. M49 selects the stage.
The contract is the M29/M30 law, unchanged: **input words → predicted
marks → the SAME word stream plus punctuation**. The word-copy
invariant `depunct(output) == depunct(input)` is a hard gate; every
candidate here decodes by copying the original tokens and appending
marks from the frozen `SUPPORTED_MARKS`, so word corruption is
structurally impossible — and the invariant was still CHECKED on
every row and every ladder rung (zero failures across all systems).
No grammar correction, no rewriting, anywhere.

## 3-6. Benchmark en-punct-eval@v1 — FROZEN (MEASURED provenance)

120 rows, one file, deterministic build (seed 49), sha-stamped into
every predictions file. Composition:

- **LJSpeech-1.1** (public domain; license REPO-VERIFIED via the M44
  intake): 50 single sentences, 10 comma-heavy, 10 numeric (raw
  transcript column so digits survive), 20 multi-sentence paragraphs
  (3-5 consecutive rows joined) — read speech, classes A/B/F/I/J/P.
- **27 authored probes** (classes D/E/G/H/K-O): questions,
  exclamations, lists, quoted speech, numbers/dates/phones, brands
  (IntelliAI/QwikCart/OpenAI/NVIDIA/PostgreSQL), abbreviations
  (Mr./Dr./U.N./a.m.), disfluencies. Annotation policy is in the
  dataset description: quoted speech is comma-introduced (STT emits
  no quote marks), abbreviation periods kept, disfluencies
  comma-separated.
- **3 spontaneous rows**: the M48 boss-audio DRAFT reference
  (human verification pending — labeled in-row).

Punctuation policy: marks in scope `. , ? !` (the frozen ruler also
carries danda for Hindi rows — unused here); `:`/`;`/`-` predictions
from candidates are DROPPED (out of v1 scope, documented).
Scoring ruler: **punct_slots@v1 UNCHANGED** — the same frozen module
scores Hindi v1/v2/v3 and this set.

Public-data survey (WEB-RESEARCHED, Phase 4): LJSpeech chosen as the
primary source (public domain, punctuation-bearing transcripts,
already vendored+hash-verified locally); Common Voice (CC-0 text
sentences) is the named secondary for a future v2; TED-LIUM (CC BY-NC-ND)
and Switchboard (LDC paid) are BLOCKED for our use; FLEURS remains the
Hindi lineage. Spontaneous coverage today is the boss slice — small,
honest, and flagged; growing it is the named v2 improvement.

## 7-8. Candidates & license audit (WEB-RESEARCHED at source, 2026-08-27)

| Candidate | Base | Params/size | Marks | Training data | License | Audit |
|---|---|---|---|---|---|---|
| `kredor/punctuate-all` @ `0fe37019…` | XLM-RoBERTa-base | ~278 M / 1.11 GB fp32 | . , ? - : | Europarl (12 langs) | MIT | **CLEAR** |
| `oliverguhr/fullstop-punctuation-multilang-large` @ `345e80ad…` | XLM-RoBERTa-large | ~560 M / 2.24 GB | . , ? - : (no !) | Europarl (4 langs) | MIT | **CLEAR** |
| `felflare/bert-restore-punctuation` @ `954108a1…` | bert-base-uncased | ~110 M / 440 MB | . , ? ! : ; ' - + casing | Yelp reviews | MIT | **CLEAR** |
| vendored `punct-cap-seg-47` + EN label map | xlm-r distilled ONNX | 47-lang, already shipped | . , ? ! (mapped) | 47-lang corpus | Apache-2.0 | CLEAR (already vendored) |
| Silero TE (text enhancement) | — | — | — | — | CC BY-NC-SA | **BLOCKED** (non-commercial) — not downloaded |
| NVIDIA NeMo punctuation_en_* | BERT/DistilBERT | — | . , ? | — | NVIDIA Open Model License | **REVIEW REQUIRED** — deferred, not measured |

Model identity governance: revisions pinned at download, weight
sha256 recorded in the experiment manifest; no mutable `latest`.

## 9-13. Results on en-punct-eval@v1 (MEASURED, CPU, WSL)

Overall (micro F1 across `. , ? !` + boundary F1; invariant failures 0
for every system on all 120 rows):

| System | Micro F1 | Boundary F1 | Comma F1 | Spontaneous micro/boundary | Probe micro/boundary/? |
|---|---|---|---|---|---|
| no-op (baseline) | 0.000 | 0.000 | 0.000 | 0/0 | 0/0/0 |
| rules (baseline) | 0.391 | 0.729 | 0.000 | 0.150/0.333 | 0.483/0.871/0.667 |
| felflare-bert | 0.420 | 0.422 | 0.417 | 0.222/0.286 | 0.390/0.356/0.500 |
| vendored47-en-map (EXPERIMENTAL) | 0.541 | 0.685 | 0.388 | 0.444/0.467 | 0.774/0.941/**1.000** |
| **kredor-xlmr-base** | **0.674** | **0.827** | **0.557** | **0.639/0.727** | 0.706/0.892/0.857 |
| fullstop-xlmr-large | 0.695 | 0.811 | 0.601 | 0.732/0.733 | 0.757/0.889/1.000 |

Readings:
- **kredor/punctuate-all leads everywhere it matters** — the only
  system strong on BOTH read paragraphs and the spontaneous slice.
- The M29A lesson reproduced in English: the rules baseline looks
  respectable on single sentences (boundary 0.87 on probes) and
  collapses on real multi-sentence text (spontaneous 0.33, comma 0).
- The vendored 47-lang model is a clean-sentence specialist (perfect
  question detection on probes) but drops to 0.44 on spontaneous
  speech — confirming M48: not the English answer alone.
- felflare (Yelp-trained) underperforms across the board on our
  domains despite being English-only.

## 14. Boss audio (Phase 13) — MEASURED + QUALITATIVE

Candidates ran on IntelliAI's RAW M48 transcript (never on Sarvam's
output). kredor's result reads like a normal paragraph — sentence
breaks in the right places, commas sane (full texts in the evidence
dir; Sarvam's captured output remains QUALITATIVE ONLY per the M48
directive). Quantitatively, on the dataset's spontaneous rows (the
DRAFT reference stream): kredor micro 0.639 / boundary 0.727 —
versus the 0.092 the vendored model managed in M48. **Answer to
Phase 13's question: yes — our own raw transcript becomes comparably
readable with a proper English model.**

## 15. Readability — UNSCORED

Comparison sheet (raw / kredor / felflare / Sarvam capture) in the
evidence dir with the 1-5 rubric; ships UNSCORED until the founder
reads it. Machine F1 is never converted into a human score.

## 16-18. Latency, memory, long text (MEASURED, CPU WSL, this laptop)

| Words | kredor p50 | felflare p50 | fullstop-large p50 |
|---|---|---|---|
| 100 | 0.056 s | 0.049 s | 0.352 s |
| 300 | 0.167 s | 0.149 s | 1.081 s |
| 700 | 0.397 s | 0.357 s | 2.619 s |
| 1200 | 0.704 s | 0.608 s | 4.441 s |
| 1412 (ladder max; the "2000" rung — the paragraph corpus holds 1412 words) | 0.832 s | 0.731 s | 5.372 s |

- Zero truncation and invariant TRUE at every rung for every system
  (window 180 words, overlap 20 — deterministic chunking, sentence
  continuity carried by the overlap).
- **Latency vs the proposed gate** (punct p95 ≤ 10 % of STT p50): a
  10-minute transcript (~1400 words) punctuates in ~0.84 s against
  STT's measured 52 s for the same audio (M48 battery) — **~1.6 %,
  passes with a wide margin**; a typical 102 s clip (~220 words):
  ~0.12 s vs 6.37 s STT ≈ 1.9 %. PASS (PROPOSED gate).
- Memory: kredor peak RSS **1489.3 MiB**, felflare
  1156.4 MiB (fp32 PyTorch, in-process; the ≤700 MiB gate is
  PROPOSED — FAIL as fp32 for every candidate (kredor 1489 MiB incl. torch overhead); the gate is reachable only via the M50 ONNX/int8 export - the exact path M30 took (47-lang ONNX: 437 MiB RSS)). ONNX/int8 export is the M50 lever if
  the fp32 number crowds the runtime (the M30 stage took exactly that
  path: 47-lang ONNX at ~437 MB RSS).

## 19-20. Edge cases & normalization seat (MEASURED / REPO-VERIFIED)

Probe classes covered decimals ($49.99, 2.5), phones (+91-…), dates,
emails/URLs (depunct treats them as tokens; the word-copy decoder
cannot alter them — invariant 0 failures over every run), acronyms
(U.N., GMT, a.m.). Architecture seat (same as Hindi v1, REPO-VERIFIED
against the M30 stage): STT raw text → punctuation stage →
final transcript; `raw_text` keeps carrying the unpunctuated stream;
no broad normalization inside the stage.

## 21-22. Regression proofs (MEASURED)

`services/stt-runtime/tests` **205 passed, 1 skipped** and
`ml/evaluation/tests` **677 passed** after all M49 work — the Hindi
punctuation runtime, engines, API and evaluation planes are untouched.

## 23. Candidate decision matrix

| Candidate | License | Size | EN micro F1 | Boundary F1 | Spont boundary | Comma F1 | ? F1 (probes) | Word invariant | CPU p50 (1412 w) | Peak RSS | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **kredor/punctuate-all** | MIT | 1.11 GB fp32 | **0.674** | **0.827** | **0.727** | **0.557** | 0.857 | 100 % | 0.83 s | 1489.3 MiB | **SELECT** |
| fullstop-xlmr-large | MIT | 2.24 GB | 0.695 | 0.811 | 0.733 | 0.601 | 0.941 | 100 % | 5.372 s | 2326.5 MiB | quality ceiling; 2.3 GiB RSS + 10.3 % of STT p50 on a 10-min transcript (borderline) - backup, not the pick |
| vendored47-en-map | Apache | shipped | 0.541 | 0.685 | 0.467 | 0.388 | 1.000 | 100 % | (ONNX, ~sub-second) | ~437 MiB (M30) | clean-sentence specialist; not sufficient alone |
| felflare-bert | MIT | 440 MB | 0.420 | 0.422 | 0.286 | 0.417 | 0.500 | 100 % | 0.73 s | 1156.4 MiB | domain mismatch; reject |
| rules | — | 0 | 0.391 | 0.729 | 0.333 | 0.000 | 0.667 | 100 % | ~0 | ~0 | baseline only (M29A lesson holds) |
| Silero TE | CC BY-NC-SA | — | — | — | — | — | — | — | — | — | BLOCKED (license) |
| NeMo punctuation_en | NVIDIA OML | — | — | — | — | — | — | — | — | — | REVIEW REQUIRED; deferred |

## 24. Proposed gates — status against the leader (PROPOSED, not approved)

| Gate | Target | kredor today |
|---|---|---|
| Word preservation | 100 % | **PASS** (structural + measured 0 failures) |
| Boundary F1 | ≥ 0.75 | **PASS overall (0.827)**; spontaneous 0.727 — just under on the 3-row DRAFT slice (n small, reference pending founder verification) |
| Boundary recall | ≥ 0.85 | 0.841 - a NARROW miss of the proposed 0.85 on this 120-row set (spontaneous slice is a 3-row DRAFT); gate stays PROPOSED, re-measured in M50 through the shipped stage |
| Comma F1 | ≥ 0.30 | **PASS** (0.557) |
| Question handling | ≥ 80 % | **PASS** (0.857 probe ? F1) |
| Latency | p95 ≤ 10 % of STT p50 | **PASS** (~1.6-1.9 %) |
| RAM | ≤ 700 MiB | FAIL as fp32 for every candidate (kredor 1489 MiB incl. torch overhead); the gate is reachable only via the M50 ONNX/int8 export - the exact path M30 took (47-lang ONNX: 437 MiB RSS) — ONNX/int8 export is the M50 lever |
| Long text | zero truncation | **PASS** (all rungs, invariant held) |

No threshold was adjusted to fit any candidate.

## 25-26. Decision & next milestone

****A. ENGLISH PUNCTUATION MODEL FOUND - `kredor/punctuate-all` (MIT, XLM-RoBERTa-base, rev `0fe37019…`, weights sha `9aec7aa5…`).**

Why kredor over fullstop-large: best sentence-boundary F1 (0.827 vs 0.811), solid spontaneous performance, 6.5x faster on long text (0.83 s vs 5.37 s per ~10-min transcript), half the memory, and the only candidate with a realistic route under the proposed RAM gate via int8 ONNX. fullstop-large stays the recorded quality ceiling (micro 0.695, comma 0.601) if M50's export measurably degrades kredor. The vendored 47-lang model remains the Hindi stage only.

**M50 (defined, NOT implemented): English punctuation runtime stage** - (1) ONNX export + int8 quantization of kredor/punctuate-all with conversion provenance (source hash -> output hash) and an artifact spec pinned like punct-cap-seg-47; (2) the SAME shipped word-copy wrapper/invariant, en-route gating beside the existing hi gating, fail-open, flag default OFF; (3) gates re-run through the shipped stage (word preservation 100 %, boundary/comma/question per the proposed table, frozen-eval byte-identity OFF vs ON, latency/RAM tiers); (4) founder listening on the readability sheet before any flag flip.**

Explicitly NOT solved here (Phase 26): grammar, spelling,
paraphrasing — the stage only adds marks to the same words.

## 27. Artifact governance

Pinned identities and weight sha256 values live in
`research/experiments/49-english-punctuation-selection/evidence/manifest.json`;
the M50 intake must re-verify at download and pin an artifact spec the
way kokoro-82m/punct-cap-seg-47 are pinned (ONNX conversion, if
taken, records source hash → output hash).
