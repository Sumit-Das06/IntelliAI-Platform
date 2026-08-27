# M53 — Realtime STT web implementation (staging battery)

Full report: [docs/milestones/53-realtime-stt-web.md](../../../docs/milestones/53-realtime-stt-web.md)

Everything here ran through the REAL product path on the staging
stack: browser/python client → Caddy/gateway `/v1/audio/realtime`
(authenticated) → host realtime runtime (whisper CUDA in-process, E3
via the pinned CUDA llama-server) → LA2 display → existing punctuation
→ collection/Correction.

| file | what |
|---|---|
| `rt_client.py` | mic-shaped WS session client (realtime / flood / nopace pacing), event timing |
| `run_battery.sh` | the EN+HI matrix: 30s/2min/5min/10min, shorts, silence, flood |
| `m53_browser_e2e.py` | Chromium with a FAKE MICROPHONE fed by real clips — the full user loop incl. Share/Correction, plus the flag-off drill |
| `m53_quality.py` | Hindi finals vs IndicVoices ground truth (+M52H baselines); English final vs the batch pipeline; scorecard |
| `evidence/en-*.json`, `hi-*.json` | per-session battery records (events, FPT, cadence, finalization, sample id) |
| `evidence/browser-*.json`, `screenshots/` | real-browser records: partials, final, Share=final, correction saved, mobile/tablet |
| `evidence/english-latency.json`, `hindi-latency.json`, `*-quality.json`, `scorecard.json` | summaries |
| `evidence/architecture/session-contract/auth/audio-format/chunking/vad/stability/long-session/backpressure/security/privacy/rollback/batch-regression/concurrency/gpu-resource` | the Phase-45 set |

Findings caught BY this battery (each fixed and re-proven):
1. **LA2 display could shrink** when a rewritten partial was shorter
   than the shown prefix → display now advances only (monotonic by
   construction), verified in-browser both languages.
2. **The mic kept streaming after Stop** → mic now stops at Stop
   (privacy + protocol hygiene).
3. **`session.completed` could be lost on the wire**: the runtime
   closed immediately after sending it and the transport flush raced —
   ordered shutdown now lets the client close after receiving
   completed; the gateway ends the bridge only after relaying it.
4. **A qwen generation loop** inflated one 2-min Hindi session by ~180
   repeated words → duration-scaled `max_tokens` cap + loud
   repetition observability; deeper retry/trim guard named for
   promotion hardening.

Audio inputs live in the session scratchpad only (real IndicVoices
clips + the boss clip sha `117cba69…af635`); no audio enters git.
