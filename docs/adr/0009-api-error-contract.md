# ADR-0009: One OpenAI/Stripe-shaped error envelope for the entire API

- **Status:** Accepted
- **Date:** 2026-07-30
- **Related:** ADR-0008, ADR-0003

## Context

Client code can only handle failures it can predict. FastAPI ships three
default error shapes (string detail, validation array, bare 500). The PRD
commits to OpenAI compatibility where it is free, and error handling is the
single most-copied code path from that ecosystem. SDKs (M11) will map
errors mechanically to exception classes and retry policy.

## Problem

What is the single, permanent shape and semantics of every API error?

## Decision

We will render every failure as:

    {"error": {"type", "code", "message", "param", "request_id"}}

- `type`: closed set of nine (invalid_request_error, authentication_error,
  authorization_error, resource_not_found_error, conflict_error,
  rate_limit_error, quota_exceeded_error, internal_error,
  service_unavailable_error). Frozen; additions are SDK-breaking events.
- `code`: open, fine-grained machine condition; additive forever.
- `param`: offending field when identifiable. `message`: human-only, never
  parseable API.
- Retryable: rate_limit, service_unavailable (honor `Retry-After`), internal
  (once). All other 4xx: never.
- Validation errors render as 400 (not FastAPI's 422 shape). Unexpected
  exceptions render opaque `internal_error`; details never cross the API
  boundary. The envelope is rendered in exactly one place (the gateway);
  inference-service failures are translated, so every future domain (STT,
  TTS, LLM, vision, OCR) shares the surface with zero new shapes.
- Deliberate exception: `/health/*` keeps its probe-oriented report shape.

## Alternatives considered

- **Framework defaults** — rejected: three shapes, one of them (422) alien
  to the OpenAI-compatible ecosystem we target.
- **RFC 7807 `application/problem+json`** — rejected: the better *standard*,
  but the AI-SDK ecosystem speaks Stripe/OpenAI shape; compatibility is the
  stated product goal. Revisit only if the ecosystem moves.
- **Per-endpoint error schemas** — rejected: N parsers in every client.

## Trade-offs

- Divergence from the IETF standard.
- A frozen type set demands discipline: new failure modes must map into
  existing types plus new codes.

## Consequences

- SDK exception hierarchy and safe default retries become mechanical.
- Support flow standardizes on `request_id` (present in every error body).
- Tests pin the envelope key-set exactly; drift is a red build.

## Future review criteria

- A genuinely unmappable failure class → adding a type, coordinated as a
  major SDK version event.
- Ecosystem-wide migration to RFC 7807 by OpenAI/Stripe-class APIs.
