# M54 — Realtime STT staging hardening + promotion readiness

Evidence for `docs/milestones/54-realtime-stt-hardening.md`.

## Method

Everything runs through the REAL gateway WebSocket
(`ws://127.0.0.1:8000/v1/audio/realtime`) on the local production-shaped
stack, same clips as M53 (boss30 + m51long EN, real IndicVoices HI).
`baseline-*` = the UNCHANGED M53 runtime, measured the same day on the
same machine (never against memory). `hardened-*` = after the M54
changes, identical clips and order.

## Tools

| file | purpose |
|---|---|
| `rt54_client.py` | battery client: p50/p95/max partial gaps, finalization + completion latency, full event traces (`evidence/traces/`) |
| `run_baseline.sh` / `run_hardened.sh` | the two batteries (identical bodies) |
| `run_drills.sh` | flood 8x, silence, short-speech drills |
| `rt54_concurrent.py` | c=N mixed EN+HI sessions, optional "loud" 10-min neighbor |
| `rt54_lifecycle.py` | stop/start-again/abrupt-disconnect drills |
| `anomaly_matrix.py` | the M52H Hindi service anomaly: cpu service vs contended vs GPU direct |
| `m54_quality.py` | finals vs ground truth (HI) / batch text (EN), frozen rulers |
| `m54_browser_e2e.py` | fake-microphone Chromium E2E (the M53 harness) |
| `gpu_sample.py` | VRAM/util sampling during runs |

Audio never enters git; clips live in the session scratchpad and are
referenced by name (shas recorded in earlier milestones).
