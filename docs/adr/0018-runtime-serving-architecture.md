# ADR-0018: Runtime serving architecture — managed lifecycle, bounded admission, weights as verified cache

- **Status:** Accepted
- **Date:** 2026-08-03
- **Related:** ADR-0002, ADR-0015, ADR-0016, ADR-0017; evidence:
  [STT baseline v1](../../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md),
  [WER baseline](../../ml/evaluation/stt/results/2026-08-02-whisper-small.json)

## Context

M2 built the first inference runtime. Its internal architecture emerged
across steps 3–7 as a set of approved refinements; this ADR records those
decisions as one permanent commitment, now that production measurement has
converted each from design intent into evidence. Every future runtime
(TTS at M3, and beyond) inherits this shape.

## Problem

What is the permanent internal architecture of an IntelliAI inference
runtime — who owns model lifecycle, how is concurrency bounded, and how do
model weights reach a deployment?

## Decision

Every IntelliAI runtime is built from four separated responsibilities:

1. **HTTP binding** (`api/`) — the only transport-aware layer; realizes
   the runtime contract on the wire and maps `RuntimeServiceError` to
   internal statuses. Nothing below it knows HTTP.
2. **Model lifecycle** (`manager/`) — the ModelManager is the artifact
   manager: per slot, startup is a measured `ensure → load → warm-up →
   serve` sequence. Artifact files are SHA-256-pinned in code, downloaded
   into a **volume-mounted cache, never baked into images**, and re-hashed
   on every startup; a checksum mismatch refuses to serve (`internal`,
   never the customer's fault). Engines are constructed once at startup,
   reused by every request, closed once at shutdown; warm-up runs one
   engine-agnostic inference so no customer pays first-inference cost.
3. **Inference execution** (`engines/` + the worker pool) — engines are
   thin adapters around one foundation model, stateless beyond the loaded
   model, behind the `TranscriptionEngine`-style Protocol; engine
   libraries are **optional extras** imported only inside `engines/`
   (AST-enforced in CI). Blocking inference runs on a fixed thread pool
   with bounded admission (`concurrency + queue`); beyond capacity the
   runtime answers `overloaded` immediately — a fast honest no, with
   retry policy left to the gateway.
4. **Media pipeline** (`pipeline/`) — permanent, engine-independent
   ingestion (ADR-0016's ownership made concrete): validate → detect →
   decode → normalize → VAD → handoff, every stage timed; engines receive
   only canonical audio; no-speech short-circuits to an empty result
   without invoking an engine.

## Alternatives considered

- **Weights baked into images** — rejected: 500 MB+ images per artifact
  version, an image rebuild per model update, and registry/artifact
  changes coupled to image pipelines. The verified-cache volume gives
  2.4 s warm restarts and image-free artifact updates; the 46 s cold
  download is a first-boot-only cost covered by readiness probes.
- **Per-request or lazy model loading** — rejected: measured load+warm is
  ~2.1 s; charging it to requests (or the first request) violates the
  latency promise. Startup loading + readiness gating costs deploys, not
  customers (first request measured at parity with steady state).
- **Process pool instead of threads** — rejected by measurement: threads
  share the one ~800 MB loaded model (flat memory across c=1..20) and
  CTranslate2 releases the GIL (~9 cores saturated at c≥5). Processes
  would multiply memory per worker for no observed throughput gain.
- **Queue-until-timeout instead of bounded admission** — rejected: at
  2× capacity the measured behavior is 35 fast refusals with accepted-p95
  bounded (16.9 s vs 16.5 s at capacity); unbounded queues convert
  overload into universal timeouts and hide capacity truth from the
  gateway.
- **Model libraries as base dependencies** — rejected: CI must never need
  model wheels, and non-engine code must not be able to import them; the
  extras + isolation-test mechanism keeps the base service provider-free.

## Trade-offs

- First boot on a fresh node is slow (measured 46 s, dominated by a
  40.9 s download) — accepted; orchestration handles it via the readiness
  start period, and the cache amortizes it to 0.26 s verification.
- Bounded admission surfaces 503s under burst instead of absorbing them —
  accepted deliberately; smoothing bursts is the gateway/queueing layer's
  future concern (M4 rate limits, M5 batch), not the runtime's.
- Thread-based execution assumes GIL-releasing engines; an engine that
  holds the GIL would serialize. Revisit per engine at adoption (part of
  the switching test).

## Consequences

- M3's TTS runtime is a template instantiation: same four
  responsibilities, same store, same pool, a `SpeechSynthesisEngine`
  Protocol, different capability schemas.
- Capacity planning starts from measured constants: ~800 MB per loaded
  whisper-small runtime, ~6.3× real-time audio throughput per ~9 CPU
  cores, plateau at pool capacity.
- The evaluation harness measures the same envelope stages the
  architecture exposes — optimization work has per-stage evidence
  built in.

## Future review criteria

- **An engine that cannot release the GIL** (or needs GPU batching)
  reopens threads-vs-processes for that runtime.
- **M8 streaming** stresses the one-shot pipeline/pool shape; incremental
  decode may need a session abstraction beside (not instead of) this one.
- If artifact sizes grow past ~5 GB (LLM-class), revisit cold-start
  strategy (pre-warmed volumes, layer caching, P2P distribution).
- If measured queue depth is persistently at cap in production, admission
  limits become dynamic/config-managed rather than static env defaults.
