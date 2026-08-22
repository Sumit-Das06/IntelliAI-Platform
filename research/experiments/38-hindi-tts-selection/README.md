# M38 — Hindi TTS Research & Model Selection (research instruments)

Research-only instruments and evidence for the M38 Hindi TTS model
selection. Nothing here ships; no production surface changes. Report:
`docs/research/2026-08-22-hindi-tts-model-selection.md`.

## Probe set

`probe-texts-hi-v1.json` — 61 fixed cases: the M32 hi/mixed probes
VERBATIM (cross-milestone comparability) + M38 additions (exclamation,
Devanagari numerals, percent, phone, time, slash-date, places,
org/product, abbreviations, technical, short, and a Hindi long-text
ladder ~120/300/700/1200/1900 chars, all under the 2000-char law).

## Harness

- `../32-tts-model-selection/harness/wsl_synth_bench.py` — REUSED
  as-is for candidate synthesis in disposable WSL venvs (identity,
  RTF, TTFA, RSS per probe; WAVs to a non-repo dir).
- `../32-tts-model-selection/harness/roundtrip_judge.py` — REUSED
  as-is: E3 judges hi/mixed through the real gateway, frozen
  normalization profiles, `intelliai_evaluation.accuracy`.
- `../32-tts-model-selection/harness/prosody_analyze.py` — REUSED for
  the ± punctuation pairs.
- `harness/m38_aggregate.py` — per-category WER/CER + clean-slice
  aggregation of a roundtrip output (clean-slice definition inside).
- `harness/m38_concurrency_probe.py` — research-only in-process thread
  ladder for Kokoro-hi (c=1/2/4/8; NOT production capacity).

## Evidence

`evidence/` — JSON only; audio never enters git (WSL `~/m38/audio`,
scratchpad mirrors). Solo-timing law: every timing run serialized —
no concurrent benches, no concurrent judging.

## Audition

`docs/research/audition/2026-08-22-hi-tts/README.md` — human-listening
pack + rubric (UNSCORED until someone listens).
