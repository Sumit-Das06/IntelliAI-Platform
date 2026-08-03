# ADR-0020: Binary audio responses as raw body plus operational envelope header

- **Status:** Accepted
- **Date:** 2026-08-03
- **Related:** ADR-0009, ADR-0016, ADR-0018;
  [M3 design review](../milestones/3-tts-design.md)

## Context

The runtime contract (ADR-0016) is transport-free; each binding decides
how envelopes travel. STT's binding was straightforward: the large
binary (audio) arrives as a multipart *request*, and the result (text)
is small and JSON-native. TTS inverts the asymmetry: the request is
small JSON, but the result is the large binary — a 30-second WAV is
roughly 1 MB. The envelope (usage, timing, runtime identity) and the
audio have opposite needs: structure versus throughput.

## Problem

How does a runtime return a large binary payload *and* its structured
envelope in one HTTP response without penalizing either — and without
creating a second error shape?

## Decision

We will bind binary-producing capabilities as: **raw audio bytes as the
response body, the runtime envelope JSON-serialized into the
`X-Runtime-Envelope` response header.** Errors are **always JSON** with
normal status codes — the platform's one error shape (ADR-0009) is never
binary, so a non-2xx response is always parseable.

Two invariants are part of the commitment:

1. **The envelope header carries operational metadata only** — usage
   counts, timing, runtime identity, contract version. Never
   transcripts, logs, diagnostics, debugging information, or any
   model-generated text. Operational metadata is bounded by
   construction; generated content is unbounded, and admitting one
   generated field makes header size a function of model output.
2. **The header size ceiling is intentional and pinned by test**, well
   under common proxy/server header limits (~8 KB total is a typical
   default), so future infrastructure never accidentally truncates it.

## Alternatives considered

- **Base64 audio inside the JSON envelope** — rejected: +33% payload,
  double-buffering on both ends, and clients must decode before
  playing; hostile to the streaming future.
- **Multipart response (JSON part + audio part)** — rejected: multipart
  *responses* have poor client-library support across browsers and
  SDKs; multipart is a request-side convention in practice.
- **Chunked/WebSocket streaming now** — rejected for v1 by the
  measured-first rule: the PRD targets TTFB < 1 s for short text, which
  the unstreamed path likely meets on CPU (production validation
  proves or refutes). Streaming's costs — session abstraction,
  partial-failure semantics, a second binding — are paid at M8
  platform-wide, or earlier only if measurement demands it. The chosen
  binding is chunk-ready: a raw body can become a chunked body with a
  trailer without changing the request shape.

## Trade-offs

- The envelope's size budget is a hard cap — anything that wants to be
  large must travel in the body or in logs. Accepted; that constraint
  *is* invariant 1.
- Success and error responses have different content types (audio vs
  JSON) — clients must branch on status code. Accepted: status-code
  branching is universal HTTP practice, and the OpenAI-compatible
  surface behaves identically.
- Header metadata is invisible to naive `curl -o out.wav` usage —
  accepted; the envelope is for the gateway, not end customers.

## Consequences

- The gateway reads the envelope from the header and streams the body
  through untouched — no re-encoding, no buffering penalty on the data
  path.
- The public `/v1/audio/speech` surface returns raw playable bytes,
  matching OpenAI's behavior.
- Every future binary-producing capability (image generation, document
  rendering) inherits this binding shape rather than redesigning it.

## Future review criteria

- **M8 streaming**: the trailer/chunk design supersedes or extends this
  binding via a new ADR when streaming becomes a product requirement.
- If the envelope legitimately needs to grow past the pinned ceiling,
  the documented fallback (envelope retrievable by request id from a
  separate endpoint) graduates from paper to plan — via review.
- A production proxy/limit incident involving the header reopens the
  ceiling value (not the invariant).
