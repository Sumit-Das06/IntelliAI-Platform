# M44 — Qwen3-TTS English Baseline + Public-Data Fine-Tuning (research)

Research-only instruments and evidence for the M44 Qwen3-TTS track.
Nothing here ships; Kokoro remains production. Report:
`docs/research/2026-08-24-qwen3-tts-english-finetuning.md`.

## Identity

- Base: `Qwen/Qwen3-TTS-12Hz-0.6B-Base` @ `5d839924…` (Apache-2.0)
- Tokenizer: `Qwen/Qwen3-TTS-Tokenizer-12Hz` @ `7dd38ad4…` (Apache-2.0)
- Official finetuning scripts vendored at their 2026-08-24 state into
  the WSL workspace (`~/m44/finetuning`), SHA-256 recorded in the run
  log; the ONLY permitted local adaptation is memory-fit (documented
  in the report if used).

## Dataset

`qwen-en-public-train@v1` — LJSpeech-1.1 (public domain, single
English speaker), frozen by `harness/m44_dataset_freeze.py`: validated
rows only, seed-44 utterance splits (train 1000 / val 50 / test 100),
ONE pinned reference clip on every row (official recipe), manifest
with per-row SHA-256 in `evidence/qwen-en-public-train-v1.json`.
Audio never enters git.

## Instruments

- `harness/m44_qwen_bench.py` — Base (voice-clone with the pinned ref)
  or fine-tuned checkpoint (custom-voice) through one measurement core
  (M32/M33/M34 schema; GPU VRAM separated from CPU RSS; streaming API
  probed, never assumed).
- `harness/m44_dataset_freeze.py` — dataset governance (above).
- `probe-texts-m44-oov.json` — the Phase-12 OOV/proper-name probes,
  used with the frozen M33 25-probe trap set.
- REUSED: `../32-tts-model-selection/harness/roundtrip_judge.py`
  (whisper route judges EN through the real gateway, frozen metrics),
  `../33-english-tts-selection/probe-texts-en-v1.json` (the trap set
  every Kokoro/Qwen number since M33 is comparable on).

## Tracks

- **A** — Base benchmark: trap set + M44 OOV probes + LJ held-out
  test texts, GPU primary, CPU informative; vs Kokoro (hardened M35
  numbers + Kokoro re-run on the LJ texts through the gateway).
- **B** — official SFT: tiny overfit → pilot → full; checkpoint by
  frozen VAL evidence; evaluation on the SAME frozen sets; OOD
  retention gate = the trap set (non-LJ domain).

## Outcome (2026-08-25)

- **Track A**: Base with the calm LJ clone reference **beat Kokoro on
  clean text** (trap 0.0515 vs 0.0659; LJ 0.0478 vs 0.0535) — M34's
  0.2449 was the expressive speaker, not the model — but loses OOV
  (0.1724 vs 0.1085), has no streaming API, GPU RTF 1.4-1.6, CPU 2.85.
- **Track B**: **FAILED (verdict F)** — every full-run checkpoint
  shows text-conditioning collapse (fluent LJ voice, wrong content,
  runaway generation; no checkpoint selectable by frozen VAL); detail
  in `evidence/qwen-ft-full-collapse.json` + the three train logs.
- **M44 decision: D — Kokoro still wins** (UX-first: streamed TTFA
  0.4-1.6 s beats whole-shot RTF>1). Report:
  `docs/research/2026-08-24-qwen3-tts-english-finetuning.md`.
