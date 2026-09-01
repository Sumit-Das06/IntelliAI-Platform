# Milestone 56 — Smart Transcript Correction: Research + Model Selection

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — decision **A. ENGLISH + HINDI CORRECTION MODEL FOUND** (Qwen3-4B-Instruct-2507, Apache-2.0, on our pinned llama.cpp GPU runtime; recorded Hindi edges below). NOTHING integrated: production, Playground, pipelines, billing all untouched. |
| **Date** | 2026-09-01 |
| **Evidence** | `research/experiments/56-smart-correction/` (49 files) · prototype `tools/research/smart_correction/` |

## 1-2. Problem + product goal

STT emits what was SAID — broken grammar, Roman-Hindi, spoken debris.
The product goal is a post-final **Smart Correction** layer:
`raw → punctuation → smart correction → user correction`, meaning
untouched, raw never destroyed. Realtime partials are never corrected
(display speed law); only finals are.

## 3-7. Benchmark (MEASURED foundation)

**`smart-correction-en-hi@v1` — FROZEN**: 300 rows (150 EN + 150 HI),
all AUTHORED in STT-noise style, sha256 `e2ea6f4d…` in the manifest.
Categories per the spec (grammar/tense/articles/SVA/capitalization/
fragments/repetitions/entities/numbers for EN; gender-number/tense/
Roman-Hindi/Hinglish/danda/entities for HI) plus three flag classes:
37 `already_correct` (over-correction control), 23 `meaning_trap`
(protected-meaning hard gate), 21 `ambiguous` (preservation
preferred). No public-corpus rows in v1; no private/boss audio; no
customer data.

## 8-9. Candidates + licenses (WEB-RESEARCHED, verified per card/API)

The decisive finding: **every usable out-of-box GEC specialist is
non-commercial** (grammarly/coedit CC-BY-NC-4.0; vennify/t5 CC-BY-NC-SA),
permissive specialists (mT5/IndicBART) need training we haven't done,
and inside the Qwen family **2.5-3B is research-licensed while 1.5B/7B
and ALL Qwen3 are Apache-2.0** — a classic license trap, caught.
Gemma-3: custom terms + gated (not measured; no merit case vs an
Apache winner). IndicXlit (MIT) = transliteration-only component.
MEASURED set: Qwen3-4B-Instruct-2507 Q4_K_M, Qwen3-1.7B Q8,
Qwen2.5-1.5B Q8 — all on the PINNED llama.cpp b10344 CUDA build
(research ports; the same binary identity as production, zero drift).

## 10-15. Results (MEASURED; full tables in evidence)

Prompt iteration was the real experiment (all three versions archived):
v1 combined → EN→HI translation flips on Indian names; v2 stronger
Hindi rules → fixed HI, BROKE EN (10.7% flips); **v3 = language-scoped
prompt pair (the pipeline knows the session language) → flips 0.0% both
sides — the single biggest lever.**

Qwen3-4B v3, full benchmark, vs baselines (identity WER 34.4% / rules
34.1%):

| gate | EN | HI |
|---|---:|---:|
| WER vs gold (one-valid-answer ruler) | **16.9%** | 21.2% |
| Exact match | 60.7% | 32.0% |
| Meaning-trap pass (HARD) | **100%** | **100%** |
| Entity violation (HARD) | **0.0%** | 2.3% (1 case: एक→१ date format, same date) |
| Language flips | **0.0%** | **0.0%** |
| Unchanged-correct | **100%** | 77.3% (recorded over-correction edge) |
| Addition proxy (EXPERIMENTAL) | 1.3% | 18% — inflated by Devanagari spelling variants; human read: **1 real hallucination in 50** |

Human read (AUTHOR EVALUATION, 25+25, 1-5, not MOS): EN means
4.80-4.96 across the rubric; HI 4.40-4.56 with four NAMED failure
classes: Roman homograph flips (der→डर), loanword mangling
(busy→बसी), one invented clause on an `ambiguous` fragment, occasional
tense breaks. Qwen3-1.7B: perfectly safe (0 violations, 100%/95%
unchanged) but a weak corrector; Qwen2.5-1.5B: rejected on Hindi.

## 16-20. Latency, memory, CPU/GPU, context, chunking (MEASURED)

Benchmark rows: EN p50 **201 ms**, HI p50 432 ms (GPU 4B). By length:
EN 0.3→2.6 s across 20→250 words; HI 0.9→9.2 s (Devanagari output is
token-heavy — generation dominates). **CPU verdict: EN marginal
(0.9-1.7 s short), Hindi FAILS (15-38 s) — this layer is
GPU-preferred, CPU-first is honestly not viable for Hindi.** VRAM ~3 GB
(Q4_K_M). Proposed targets read: EN ≤1 s PASS; HI passes only for
short utterances — long finals need async-apply UX or sentence-boundary
chunking, because **blind chunking measurably breaks coherence**
(verbatim tense/pronoun/boundary damage in `chunking.json`).

## 21-25. Pipeline, punctuation interaction, contracts

Measured: raw vs pre-punctuated input → 11/12 word-identical outputs —
the corrector is insensitive to pre-punctuation and punctuates on its
own. **Recommended arrangement: keep the existing punctuation stage as
the always-on guaranteed layer; correction runs AFTER it, flag-gated,
and MAY rewrite punctuation.** Two contracts now documented:
punctuation = words NEVER change (unchanged law); smart correction =
words MAY change, meaning NEVER (new law). Human override stays:
`raw → punctuated → AI-corrected → user-corrected`; AI is a suggestion
layer, never authoritative.

## 26. Data flywheel (PROPOSED only)

Consented raw↔user-corrected pairs are future fine-tuning data for
exactly this task; requires its own consent review. Nothing trained in
M56.

## Final decision + next milestone

**A. ENGLISH + HINDI CORRECTION MODEL FOUND** — primary
**Qwen3-4B-Instruct-2507** (Apache-2.0, Q4_K_M, pinned llama.cpp GPU,
language-scoped v3 prompts; fallback Qwen3-1.7B where VRAM is tight).
Recorded honestly against the proposed gates: meaning/entity/flip gates
pass; Hindi over-correction (23% of already-correct sentences touched),
homograph/loanword risk, and >50-word Hindi latency are the open edges.
**Next (ONE, founder-gated): Smart Correction Runtime (staging only)**
— flag-gated post-final stage with the provenance chain, ambiguity
review-flag UX, and the HI latency strategy. Production untouched;
existing suites green; no external APIs — every token stayed on this
machine.
