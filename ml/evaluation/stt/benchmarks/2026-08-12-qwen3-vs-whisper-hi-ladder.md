# Milestone 16 — Hindi Concurrency Ladders: Qwen3-ASR 0.6B vs Whisper-small (CPU)

Same clip (median frozen-eval Hindi utterance, 6.88 s), same runtime
pool (max_concurrency=2, max_queue=8), same machine (Intel64 F6M183,
24 threads, Windows 11), runtime-direct. Records:
[qwen3](2026-08-12-qwen3-asr-0.6b-cpu-ladder.json) ·
[whisper](2026-08-12-whisper-small-cpu-ladder.json). Method: the
standard bench harness — nearest-rank percentiles, `overloaded`
refusals counted as measurement, two warm probes excluded.

| | c=1 p50 | c=5 p50 | c=10 p50 | c=20 outcome | plateau rps | aggregate real-time |
|---|---|---|---|---|---|---|
| **qwen3-asr-0.6b (q8_0)** | 0.70 s | 2.07 s | 4.25 s | 50/100 clean 503s | **2.28–2.34** | **≈16×** |
| whisper-small (int8) | 1.56 s | 6.83 s | 14.80 s | 30/60 clean 503s | 0.65–0.68 | ≈4.6× |

Zero non-503 errors at every level on both engines. Sidecar peaks:
qwen3 llama-server RSS 1,538.5 MiB, machine CPU ~70% mean at
saturation; whisper python RSS 1,151.6 MiB, CPU ~23% mean. The c=20
shed happens exactly at the admission boundary (10 admitted = 2
executing + 8 queued) on both engines — the saturation point of this
deployment SHAPE is the pool configuration; the models saturate the
pool at very different throughputs.

Context for readers: these ladders measure the serving envelope, not
quality — quality lives in the EvalRun ledger (15E + the Milestone 16
switching records). Estimates derived from these numbers (sustainable
live-call concurrency ≈12 for qwen3, ≈3–4 for whisper on THIS box) are
labeled ESTIMATED in the milestone report and are not production
guarantees.
