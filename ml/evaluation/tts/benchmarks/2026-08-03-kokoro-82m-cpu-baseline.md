# TTS Production Baseline v1 — kokoro-82m, CPU, containerized

**This is the permanent baseline.** Every future synthesis artifact
(successor engines, IntelliAI-TTS fine-tunes, cloned-voice serving) is
measured with the same harness, the same pinned sentence, the same
ladder, and compared against these numbers. Raw data:
[2026-08-03-kokoro-82m-docker.json](2026-08-03-kokoro-82m-docker.json).

- **Date:** 2026-08-03 · **Artifact:** kokoro-82m v1 · **Engine:**
  kokoro 0.9.4 (CPU torch 2.13) · **Runtime:** tts-runtime 0.1.0
- **Topology:** full compose stack (gateway + runtime containers, Docker
  Desktop/WSL2) on Intel Core i7-14650HX, Windows 11
- **Image:** 2.03 GB, **GPL-free by construction** — the espeak wrapper
  chain (phonemizer-fork, espeakng-loader) is uninstalled at build and
  the build FAILS if either remains importable; verified again in the
  running container (`find_spec` → None). CPU-only torch via the pinned
  PyTorch CPU index (the PyPI default on Linux is the CUDA build —
  caught by this validation).
- **Text:** the pinned 122-char benchmark sentence (`bench_tts.BENCH_TEXT`,
  fixed in code) → ~8.5 s of audio
- **Runtime config:** defaults — pool concurrency 2, queue 8

## Startup lifecycle (from structured container logs)

| Phase | Cold (empty volume) | Warm (verified cache) |
|---|---|---|
| Artifact ensure (download + SHA-256) | 31.9 s (28.0 s = kokoro-v1_0.pth, ~94 Mbps; voice packs 3.5 s) | ~1.5 s (re-hash 330 MB) |
| Model load | 3563 ms | 3563 ms |
| Warm-up inference | 328 ms | 328 ms |
| **Container start → ready** | **≈ 38 s** | **7 s** (measured, restart → ready) |

Two production defects were caught (and fixed) by this validation —
which is why it exists: misaki's G2P silently **pip-installs a spaCy
model from the internet at first load** (invisible on dev machines;
fatal in the installer-free image) — now a hash-locked explicit
dependency, no runtime fetches ever; and the stt Dockerfile predated the
runtime-core extraction and could no longer rebuild — fixed.

## Concurrency ladder (direct to runtime, 3 requests/worker, ~8.5 s audio)

| c | ok | refused (503) | p50 | p95 | rps | mean RTF | pool peak | CPU max | mem max |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 2.16 s | 2.26 s | 0.28 | 0.253 | 1 | (see note) | 1969 MiB |
| 5 | 15 | 0 | 5.58 s | 8.42 s | 0.64 | 0.328 | 5 | 793 % | 2032 MiB |
| 10 | 30 | 0 | 13.3 s | 14.5 s | 0.64 | 0.348 | 10 | 796 % | 2046 MiB |
| 20 | 22 | 38 | 15.1 s | 16.0 s | 0.59 | 0.374 | 10 (cap) | 1028 % | 2037 MiB |

Readings:

- **Throughput plateaus at ~0.64 req/s** (≈ 5.4 s of audio produced per
  wall second) from c=5 on — CPU-bound, ~8–10 cores saturated.
- **Admission control behaves exactly as designed, second engine, second
  capability:** at c=20 the pool caps at its capacity of 10 (2 executing
  + 8 queued); 38 requests were refused *fast* with `overloaded`, and
  accepted-request latency stayed bounded (p95 16.0 s vs 14.5 s at c=10).
- **Memory is flat (~2.0 GiB)** across all load levels — one loaded
  model shared by threads (torch-resident; native-Windows measurement
  was 1.4 GiB — the delta is the WSL2/container allocator). This is the
  capacity-planning number.
- Containerized RTF (0.25–0.37) is slower than native (0.19–0.21) — the
  WSL2 tax, consistent with the STT baseline's experience.
- c=1 CPU reads low because `docker stats` sampling lags short bursts;
  treat CPU columns as saturation indicators.

## Gateway overhead (ADR-0002 validation; c=1, n=10 medians, same text)

| Path | p50 |
|---|---|
| Customer → runtime (direct) | 2194.7 ms |
| Customer → gateway → runtime | 2237.4 ms |
| **Gateway + extra hop** | **+42.6 ms = 2.0 % of inference (2103.3 ms)** |

Higher absolute overhead than STT's +14.7 ms — the ~375 KB WAV rides
back through the gateway — but still ~2 % of inference: ADR-0002's
isolation bet holds for binary responses.

## PRD target — the milestone's first honest FAIL, and what it decided

PRD: TTFB < 1 s. v1 is unstreamed, so TTFB = full response (conservative).

| Input | Audio | Gateway p50 | Verdict |
|---|---|---|---|
| 44 chars, ONE sentence | ~3 s | **814 ms** | PASS |
| 28 chars, TWO sentences | ~3 s | 1122 ms | FAIL (two model passes) |
| 122-char pinned sentence | ~8.5 s | **2237 ms** | **FAIL** |

Unstreamed TTFB scales with audio length — the pinned benchmark sentence
misses the target by 2.2×. Two levers, both now measured:

1. **Chunk merging** (runtime debt, registered at step 4): the 28-char
   case fails only because two short sentences cost two model passes
   (~500 ms fixed cost each); merging chunks under the phoneme limit
   would put every short utterance under the target.
2. **Streaming** (M8 decision): this table IS the go/no-go evidence the
   design review deferred to. Verdict: **go** — unstreamed synthesis
   cannot meet a 1 s TTFB for arbitrary-length text on this hardware;
   streaming (or chunked transfer of early audio) is the only general
   fix. Until then, the honest product statement is: TTFB < 1 s holds
   for single-sentence utterances (the conversational-agent case), not
   for long-form text.

## Reproduction (deterministic methodology)

```bash
# 1. Cold start: docker volume rm intelliai_modelcache, then
docker compose up -d tts-runtime      # lifecycle from container logs
# 2. Full stack + a bench key (revoke it afterwards):
docker compose up -d
docker compose exec api python -m intelliai_api.cli bootstrap-org ...
# 3. The harness (nearest-rank percentiles; saturation counted, never hidden;
#    the benchmark sentence is pinned in code):
uv run --package intelliai-evaluation python -m intelliai_evaluation bench-tts \
  --levels 1,5,10,20 --repetitions 3 --api-key <bench key> \
  --docker-container intelliai-tts-runtime-1 \
  --hardware "<machine>" --out ml/evaluation/tts/benchmarks/<date>-<artifact>.json
```

Quality companions: day-one baseline
[../results/2026-08-03-kokoro-82m.json](../results/2026-08-03-kokoro-82m.json)
(EN round-trip WER 0.072) and its live reproduction
[../results/2026-08-03-kokoro-82m-repro.json](../results/2026-08-03-kokoro-82m-repro.json).
