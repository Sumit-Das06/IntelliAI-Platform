# M52 — Realtime STT feasibility experiments

Full report: [docs/research/2026-08-28-realtime-stt-feasibility.md](../../../docs/research/2026-08-28-realtime-stt-feasibility.md)

## Why the simulator (and why WSL)

Repo-verified: neither current engine consumes incremental audio —
faster-whisper (CT2) decodes one complete clip per call; Qwen3-ASR E3
(llama.cpp llama-server + mtmd) takes one WAV per completion request
and keeps no audio state between requests. A realtime session on the
CURRENT stack is therefore *re-decode the active window on a cadence*.
`sim_streaming.py` measures exactly that: it replays a WAV as if a
microphone produced it in fixed chunks on a virtual clock; decode
compute is REAL (measured wall time), only the arrival timeline is
virtual. A single decoder is assumed (production-shaped: one bounded
slot).

All CPU numbers come from **WSL2 Linux** with the same faster-whisper
pin as the repo (1.2.1): Windows-native CT2 measured ~3× slower per
decode on the same CPU (see `evidence/hardware.json`) and production
runs Linux containers, so Linux is the honest environment.

## Files

| file | what it measures |
|---|---|
| `sim_streaming.py` | the streaming simulator (chunk cadence, FPT, partial latency, finalization, stability, rolling-window commits, WER vs the offline decode) |
| `m52_qwen_ladder.py` | Qwen3-ASR E3 full-re-decode cost curve on real Hindi prefixes (staging container), + language-mix behavior n=1 |
| `gpu_whisper.py` | whisper-small on the RTX 5070 (WSL CUDA): decode-vs-window curve + one streaming sim |
| `la2_analysis.py` | LocalAgreement-2 display policy evaluated on captured partial sequences (monotonicity, lag, live coverage) |
| `prototype/ws_server.py` | ISOLATED WebSocket prototype (auth-gated, session ids, VAD-gated decodes, rolling window, bounded buffer, proposed event contract) |
| `prototype/ws_client.py` | streams a WAV like a microphone; measures FPT / cadence / finalization through the real transport; flood (backpressure) and restart (session isolation) modes |

## Evidence naming

- `chunk-<ms>ms-boss30.json` — chunk ladder, growing window, beam 5
- `greedy-…` / `base-…` — beam-1 partials / whisper-base variants
- `la2-*.partials.json` + `la2-metrics-*.json` — display-policy inputs/outputs
- `short-*.json`, `silence5.json`, `noise5.json` — edge probes
- `long-<n>-rolling.json` — 2/5/10 min rolling-window sessions
- `qwen-ladder.json`, `gpu-whisper.json`, `ws-*.json` — as named

Audio inputs live in the session scratchpad only (boss clip sha
`117cba69…af635`; synthetic clips from Windows SAPI + the staging TTS)
— **no audio enters git**.
