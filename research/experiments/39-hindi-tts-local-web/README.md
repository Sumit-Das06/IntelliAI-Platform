# M39 — Kokoro Hindi TTS Local Web Implementation (evidence)

Verification evidence for the M39 implementation milestone. Report:
`docs/milestones/39-kokoro-hindi-tts-local-web.md`.

## Instruments

- `harness/m39_ttfa_bench.py` — the M36 TTFA instrument, voice-
  parameterized, fed the M38 Hindi ladder: stream vs whole-body TTFA/
  TTFB/total/RTF per length, plus the streamed concurrency ladder
  (c=1/2/4/8).
- REUSED as-is: `../32-tts-model-selection/harness/gateway_synth_bench.py`
  (production-path synthesis of the frozen M38 probe set, per voice),
  `roundtrip_judge.py` (E3 judge through the real gateway, frozen
  metrics), `../38-hindi-tts-selection/harness/m38_aggregate.py`
  (clean-slice/category aggregation), and
  `../35-kokoro-hardening/harness/m35_battery.py` (the English
  regression battery).

## Evidence

`evidence/` — JSON only; audio never enters git (scratchpad
`m39-audio/`). Same fixed M38 probe set (61 cases), same judge, same
solo-timing law as M38 — the before/after tables compare like with
like.
