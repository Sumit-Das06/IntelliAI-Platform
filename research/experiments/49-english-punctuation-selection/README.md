# M49 — English Punctuation Model Selection (research only)

Report: `docs/research/2026-08-28-english-punctuation-model-selection.md`.
Nothing ships here; the Hindi punctuation runtime (v1, prod-OFF) and
all production planes are untouched (STT 205 + evaluation 677 tests
re-run green).

## Benchmark

`ml/evaluation/punctuation/datasets/en-punct-eval-v1.json` — NEW
frozen set (120 rows: 90 LJSpeech read-speech incl. paragraphs, 27
authored probes, 3 spontaneous boss-DRAFT rows), scored with the
FROZEN `punct_slots@v1` ruler. Built by `m49_build_dataset.py`
(deterministic, seed 49).

## Instruments

- `m49_predict.py` — word-copy decoding harness (original tokens +
  predicted marks via the frozen `apply_marks`; window 180/overlap 20)
  for no-op, rules, felflare-bert, kredor/punctuate-all,
  fullstop-punctuation-multilang-large; per-candidate latency ladder +
  peak RSS.
- `m49_vendored47.py` — the shipped 47-lang model with the
  EXPERIMENTAL English label map (research process only).
- `m49_score.py` — M29A-style scorer (frozen `score_pair`), overall +
  per-class (single/paragraph/probe/spontaneous), per-mark F1.

## Headline (all MEASURED, CPU)

| System | Micro F1 | Boundary F1 | Comma | Spont. | 1412-word p50 | Peak RSS |
|---|---|---|---|---|---|---|
| **kredor/punctuate-all (SELECTED)** | 0.674 | **0.827** | 0.557 | 0.639/0.727 | **0.83 s** | 1489 MiB fp32 |
| fullstop-xlmr-large (quality ceiling) | **0.695** | 0.811 | **0.601** | 0.732/0.733 | 5.37 s | 2327 MiB |
| vendored47-en-map | 0.541 | 0.685 | 0.388 | 0.444/0.467 | — | ~437 MiB (M30 ONNX) |
| felflare-bert | 0.420 | 0.422 | 0.417 | 0.222/0.286 | 0.73 s | 1156 MiB |
| rules / no-op | 0.391 / 0 | 0.729 / 0 | 0 / 0 | — | — | — |

Word-copy invariant: **0 failures, every system, every row and rung.**
Boss raw transcript + kredor reads like a normal paragraph
(`evidence/boss-kredor.txt`; readability sheet UNSCORED).

**Decision A** — kredor/punctuate-all (MIT, rev `0fe37019…`, weights
`9aec7aa5…`). **M50 defined (not implemented):** int8 ONNX export with
conversion provenance, artifact spec pinning, the shipped word-copy
wrapper with en-route gating beside hi, flag default OFF, gates re-run
through the shipped stage, founder listening before any flip.
