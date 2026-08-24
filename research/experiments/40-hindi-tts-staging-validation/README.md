# M40 — Hindi TTS Final Staging Validation (evidence)

Replicate validation + live drills for the M40 promotion-readiness
milestone. Report: `docs/milestones/40-hindi-tts-final-staging-validation.md`.

## Instruments (all REUSED — no new benchmark code in M40)

- `../32-tts-model-selection/harness/gateway_synth_bench.py` +
  `roundtrip_judge.py` + `../38-hindi-tts-selection/harness/
  m38_aggregate.py` — the frozen M38 quality battery, replicated.
- `../35-kokoro-hardening/harness/m35_battery.py` — English
  regression.
- `../39-hindi-tts-local-web/harness/m39_ttfa_bench.py` — streaming
  TTFA + concurrency, replicated.

## New evidence classes in M40

- `m40-billing-drill.json` — LIVE Postgres ledger rows from a fresh
  internal_qa drill org: speed/voice/transport invariance, the F1
  client-abort law, zero rows for refusals.
- `m40-normalization-internals.json` — original → speech-only internal
  text from the exact runtime function, idempotency + no-English laws.
- `m40-chunk-plan.json` — ladder chunk plans from the exact runtime
  splitter (no text lost, budgets respected).
- `m40-rollback-drill.json` — staging rollback drilled live
  (hindi_g2p off → voices shrink, gateway refuses → restore).
- `m40-web-e2e.json` — HTTPS-edge page/stream/round-trip checks.

Audio never enters git (scratchpad `m40-audio/`); solo-timing law for
every timing run.
