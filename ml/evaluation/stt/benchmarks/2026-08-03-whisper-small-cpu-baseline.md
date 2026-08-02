# STT Production Baseline v1 — whisper-small, CPU, containerized

**This is the permanent baseline.** Every future transcription artifact
(Qwen3-ASR lineage, IntelliAI-STT fine-tunes) is measured with the same
harness, the same clip, the same ladder, and compared against these
numbers. Raw data: [2026-08-03-whisper-small-docker.json](2026-08-03-whisper-small-docker.json).

- **Date:** 2026-08-03 · **Artifact:** whisper-small v1 (int8 build) ·
  **Engine:** faster-whisper 1.2.1 · **Runtime:** stt-runtime 0.1.0
- **Topology:** full compose stack (gateway + runtime containers, Docker
  Desktop/WSL2) on Intel Core i7-14650HX, Windows 11
- **Clip:** jfk-wav (11.0 s, stt-eval-seed@v1, SHA-256-pinned)
- **Runtime config:** defaults — pool concurrency 2, queue 8

## Startup lifecycle (from structured container logs)

| Phase | Cold (empty volume) | Warm (verified cache) |
|---|---|---|
| ffmpeg verification | < 1 ms | < 1 ms |
| Artifact ensure (download + SHA-256) | 43.1 s (40.9 s = model.bin, ~94 Mbps) | 0.26 s (re-hash 483 MB) |
| Model load (int8) | 907 ms | 713 ms |
| Warm-up inference | 1426 ms | 1389 ms |
| **Container start → ready** | **≈ 46 s** | **≈ 2.4 s** |

First request after startup: **1416 ms** vs steady-state p50 **1749 ms** —
warm-up works; the first customer request pays no cold tax. (It is even
slightly faster than p50: the measured first request ran with an idle CPU.)

## Concurrency ladder (direct to runtime, 3 requests/worker, 11 s clip)

| c | ok | refused (503) | p50 | p95 | rps | mean RTF | pool peak | CPU max | mem max |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 1.75 s | 1.79 s | 0.35 | 0.155 | 1 | (see note) | 677 MiB |
| 5 | 15 | 0 | 6.30 s | 9.56 s | 0.56 | 0.286 | 5 | 899 % | 795 MiB |
| 10 | 30 | 0 | 15.2 s | 16.5 s | 0.57 | 0.301 | 10 | 909 % | 796 MiB |
| 20 | 25 | 35 | 15.6 s | 16.9 s | 0.58 | 0.298 | 10 (cap) | 904 % | 797 MiB |

Readings:

- **Throughput plateaus at ~0.57 req/s** (≈ 6.3× real-time audio
  throughput) from c=5 on: the box is CPU-bound (~9 cores saturated).
- **Admission control behaves exactly as designed:** at c=20 the pool
  caps at its capacity of 10 (2 executing + 8 queued); the other 35
  requests were refused *fast* with `overloaded` instead of queuing into
  timeout territory, and the latency of accepted requests stayed bounded
  (p95 16.9 s vs 16.5 s at c=10).
- **Memory is flat (~800 MiB)** across all load levels — one loaded model
  shared by threads, no per-request model cost. This is the number
  capacity planning starts from.
- c=1 CPU reads low because `docker stats` sampling lags short bursts;
  treat CPU columns as saturation indicators, not per-request cost.

## Gateway overhead (ADR-0002 validation; c=1, n=10 medians, same clip)

| Path | p50 |
|---|---|
| Customer → runtime (direct) | 1770.0 ms |
| Customer → gateway → runtime | 1784.7 ms |
| **Gateway + extra hop** | **+14.7 ms = 0.86 % of inference (1714.5 ms)** |

ADR-0002's bet — inference isolation costs a negligible fraction of
inference itself — is validated: **under 1 %**.

## PRD target

p95 latency < 1.5× audio duration → target **16.5 s** for the 11 s clip.
Measured customer-path p50 **1.78 s**, uncontended: **PASS with ~9×
headroom**. (At full saturation with a 10-deep admission pool, p95 grazes
the target — capacity planning, not model speed, is the lever.)

## Reproduction (deterministic methodology)

```bash
# 1. Cold start: docker volume rm intelliai_modelcache, then
docker compose up -d stt-runtime      # lifecycle from container logs
# 2. Full stack + a bench key (revoke it afterwards):
docker compose up -d
uv run --package intelliai-api python -m intelliai_api.cli bootstrap-org ...
# 3. The harness (nearest-rank percentiles; saturation counted, never hidden):
uv run --package intelliai-evaluation python -m intelliai_evaluation bench \
  --clip ml/evaluation/data/jfk-wav.wav --levels 1,5,10,20 --repetitions 3 \
  --api-key <bench key> --docker-container intelliai-stt-runtime-1 \
  --hardware "<machine>" --out ml/evaluation/stt/benchmarks/<date>-<artifact>.json
```

Quality companion: WER/hallucination baseline in
[../results/2026-08-02-whisper-small.json](../results/2026-08-02-whisper-small.json)
(overall WER 0.000, zero hallucinated words on stt-eval-seed@v1).
