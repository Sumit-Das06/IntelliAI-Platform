# ADR-0003: Capability-shaped internal runtime contract for inference services

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0002, ADR-0005

## Context

Over time each capability will be served by several engines: STT by
faster-whisper today, possibly Parakeet or a fine-tuned custom model later;
TTS by Piper, later Kokoro; external providers (Deepgram, Azure) may join.
The public API contract must stay frozen while engines churn beneath it.

## Problem

How does the gateway talk to interchangeable inference engines without
engine-specific code paths?

## Decision

We will define one internal contract per *capability* (transcription, speech
synthesis, …), not per engine: Pydantic schemas and standard endpoints
(`/invoke`, `/info`, `/health`) in `packages/runtime-contract`. Every
inference service — ours or an adapter wrapping an external provider —
implements the contract for its capability. The gateway routes by model
registry entry and speaks only the contract.

## Alternatives considered

- **Per-engine integration in the gateway** — rejected: N engines × M
  capabilities of bespoke glue; every new model touches gateway code.
- **Existing serving standards (KServe V2, etc.)** — rejected for now:
  tensor-shaped rather than capability-shaped; heavy machinery for a
  two-service platform. Reconsider at scale.
- **gRPC instead of HTTP+JSON** — deferred: real performance benefits, but
  tooling/debugging cost is not justified before streaming workloads exist.

## Trade-offs

- Contract versioning discipline required from day one.
- Risk of lowest-common-denominator schemas; engine-specific extras must
  ride in explicitly-marked extension fields.

## Consequences

- Swapping a model is a registry row change, invisible to clients.
- External providers are indistinguishable from in-house services.
- Services are testable against fake engines — no model weights in CI.
- Per-model capability metadata (languages, formats) lives in the registry,
  not in gateway code.

## Future review criteria

- Streaming STT (M8) is the first stress test: if HTTP+JSON strains under
  real-time framing, evaluate gRPC/WebSocket for contract v2.
- If a third serving standard becomes industry-dominant and adapter-friendly,
  evaluate adopting it instead of growing ours.
