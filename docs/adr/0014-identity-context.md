# ADR-0014: AuthContext — one immutable identity object for the platform

- **Status:** Accepted
- **Date:** 2026-07-31
- **Related:** ADR-0010, ADR-0012, ADR-0013 (planned)

## Context

Every layer below the router needs to know who a request runs as: services
for rules, repositories (via parameters) for scoping, logging for
attribution, metering (M4) for billing. Passing raw values — an org ID
here, a key row there — multiplies signatures and, worse, makes tenant
identity forgeable: a bare integer can come from anywhere, including a
client payload.

## Problem

What is the canonical representation of an authenticated caller, and how
does it evolve without churning every function signature?

## Decision

A frozen dataclass, ``AuthContext``, constructed in exactly one place (the
authentication dependency after full verification) and passed down as one
object. Initial fields: ``organization`` (loaded model), ``api_key``
(loaded model), ``request_id``, ``authenticated_at``; convenience
properties expose internal ids (for repositories) and public ids (for
logging). Endpoints and services never see the raw API key string.

- **Immutable**: identity is a fact about the request, not a variable.
  Mutation anywhere would be spooky action at a distance in the layer
  where bugs become breaches.
- **Constructed only by authentication**: holding an ``AuthContext`` IS
  proof that verification happened — the type system replaces trust.
- **Extension policy**: future capabilities (user principal in M6, scopes
  in M4+, billing context, trace ids) are new fields with defaults —
  signatures never change.

## Alternatives considered

- **Pass raw organization_id ints** — rejected: forgeable, multiplies
  parameters, loses key/audit attribution.
- **Pass the ApiKey model around** — rejected: leaks persistence concerns
  upward and invites services to read fields (hash!) they must not.
- **Read identity from request state / contextvars in services** —
  rejected: hidden dependency, breaks non-HTTP entrypoints (CLI, workers),
  and a missing global silently means "no tenant filter" — the worst
  failure mode.
- **A richer "principal" class hierarchy now** — rejected: one caller type
  exists (org-via-key); hierarchy when the second type arrives (M6 users).

## Trade-offs

- One more concept for newcomers to learn (mitigated: it appears in every
  endpoint signature, so it teaches itself).
- Convenience properties must be kept honest (internal vs public ids named
  explicitly) to avoid accidental id leakage into responses.

## Consequences

- Adding org-wide capability data is additive, never a refactor.
- Logging/metering attribution comes from one authoritative object.
- Services are testable by constructing an ``AuthContext`` directly — no
  HTTP machinery required.

## Future review criteria

- Second principal type (human console sessions, M6) → revisit whether
  ``AuthContext`` generalizes or splits into a small union.
- If scopes (M4+) grow policy logic, authorization moves to its own
  component consuming ``AuthContext`` (ADR-0013's territory), not into it.
