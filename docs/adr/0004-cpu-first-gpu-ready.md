# ADR-0004: CPU-first serving; GPU adoption is deployment configuration only

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0002, ADR-0003

## Context

Phase 1 development happens on GPU-less machines, and the chosen engines
(faster-whisper int8, Piper ONNX) deliver acceptable quality and latency on
CPU. GPUs multiply cost and operational complexity, and cloud GPU pricing
punishes idle capacity — but production quality/latency targets will
eventually demand them for some workloads.

## Problem

How do we serve on cheap CPU hardware today without baking CPU assumptions
into code that GPU adoption would have to unwind?

## Decision

We will treat compute device as pure deployment configuration. Inference
services read `DEVICE` / `COMPUTE_TYPE` from environment; device resolution
happens in exactly one place per service (its config module); CUDA arrives
via a Docker base-image build argument plus a compose overlay adding device
reservations. Acceptance test: **moving a service to GPU changes nothing
under `services/*/src`.**

## Alternatives considered

- **GPU-first** — rejected: cost before revenue, dev-machine mismatch, and
  our chosen models don't need it for Phase 1 targets.
- **CPU-only permanently** — rejected: caps model quality (medium+ Whisper,
  streaming) and future throughput.
- **Scattered `torch.cuda.is_available()` branching** — rejected: device
  logic leaks everywhere and becomes untestable; this is the anti-pattern
  the single-resolution-point rule exists to prevent.

## Trade-offs

- Phase 1 latency envelope is CPU-bound: `small`-class STT models, capped
  sync audio duration, low per-worker concurrency.
- Two image variants (CPU/CUDA base) to build once GPU deploys begin.

## Consequences

- Development, CI, and small production tiers run on commodity hardware.
- The performance envelope is honest and documented (PRD §10).
- GPU adoption is a per-service, per-environment rollout decision.

## Future review criteria

- A latency/throughput SLO that `small`/int8-class models cannot meet, or a
  model tier (streaming STT, medium+ Whisper) whose CPU real-time factor is
  unacceptable → deploy that service's GPU variant via overlay.
- Sustained GPU utilization above ~50% on rented capacity → evaluate
  reserved/owned hardware.
