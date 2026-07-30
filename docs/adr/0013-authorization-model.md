# ADR-0013: Authorization — implicit full org access now, staged narrowing later

- **Status:** Accepted
- **Date:** 2026-07-31
- **Related:** ADR-0010, ADR-0012, ADR-0014

## Context

Authentication (who are you?) is complete: every request resolves to an
``AuthContext``. Authorization (what may you do?) needs a policy. Today the
platform has exactly one principal type (an organization acting through an
API key) and one capability surface (the org's own resources). M4 will add
reasons to narrow (metering-exempt keys? transcribe-only keys?), M6 adds
human actors with roles, M9 may add per-model access.

## Problem

What is the authorization policy now, and how does it narrow later without
restructuring the request pipeline?

## Decision

**M1 policy: possession of a valid, unrevoked, unexpired organization key
grants full access to that organization's resources — and nothing else.**
Tenant scoping (ADR-0010) is the only boundary, enforced by repository
signatures and ``AuthContext``.

Authorization nonetheless exists as a **named pipeline stage** between
authentication and business logic — currently a pass-through. Narrowing
lands in that stage, additively:

1. **Key scopes** (M4+): a ``scopes`` column on ``api_keys``; a dependency
   like ``require_scope("audio.write")`` consumed per-route. Absent scopes
   mean full access (backward compatible).
2. **Membership roles** (M6): ``memberships.role`` (already stored:
   owner/member) becomes enforceable when humans act through the console.
3. **Resource-level policy** (M9+, if needed): per-model/per-feature access
   from registry data.

403 (``authorization_error``) is reserved for these stages; nothing in M1
can produce one — cross-tenant reads return 404 by design (no existence
disclosure).

## Alternatives considered

- **RBAC now** — rejected: one role exists in practice; speculative role
  matrices are the classic source of permission systems nobody understands.
- **Scopes now** — rejected: no second capability to distinguish until M2
  ships inference; scopes designed before their first consumer would be
  guessed wrong.
- **External policy engine (OPA/Cedar)** — rejected at this scale: a
  service dependency and a policy language for a one-line policy.

## Trade-offs

- Any leaked key is currently a full-org key; expiry and instant revocation
  (ADR-0012) are the compensating controls until scopes land.
- The pass-through stage is invisible in code flow until it isn't — hence
  this ADR as the marker that it exists on purpose.

## Consequences

- M1 endpoints need no permission checks beyond ``CurrentAuth`` — simpler
  code, honest model.
- The 401/403/404 semantics are fixed now and never change: 401 = unknown
  caller, 403 = known caller/forbidden act (future), 404 = no such
  resource (including other tenants' resources).

## Future review criteria

- First customer request for restricted keys, or M4 metering wanting
  key-class distinctions → implement scopes.
- Console human actions (M6) → enforce roles.
- A second 403-producing policy appearing anywhere else in code → stop and
  consolidate into the authorization stage.
