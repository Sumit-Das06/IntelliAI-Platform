# ADR-0022: Admission control — four separate systems, split by loss tolerance

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0009, ADR-0010, ADR-0013, ADR-0018, ADR-0021

## Context

With two capabilities serving customers, the platform can be consumed
faster than it can serve and faster than a customer has agreed to pay
for. M3's measurements make the shape concrete: TTS plateaus at 0.64
requests per second with the worker pool capping at ten concurrent, and a
single long transcription occupies a worker for its whole duration
regardless of request rate.

Four different questions arrive at once, and the industry routinely
answers them with one mechanism: *are you going too fast right now*, *have
you used more than your plan allows this period*, *have you spent more
money than you authorized*, and *do we have capacity at all*. The fourth
is already answered — the runtime worker pool refuses with a fast 503
(ADR-0018).

## Problem

Which admission questions exist, where does each one's state live, in
what order are they asked, and what happens to each when its store is
unavailable?

## Decision

**We will implement rate limiting, quotas, and spend limits as three
separate systems, distinct from capacity backpressure, partitioned by
loss tolerance: protection state in Redis, entitlement state in
Postgres.**

1. **Rate limiting** answers *too fast right now*. Redis-backed, token
   bucket / GCRA evaluated atomically in a Lua script. Approximate,
   ephemeral, self-healing. Returns 429 with `Retry-After` and the
   `X-RateLimit-Limit` / `-Remaining` / `-Reset` headers, under the
   existing error contract code `rate_limit_exceeded`.
2. **Concurrency limiting** answers *too much at once*. A leased counter
   with TTL, per organization. For an inference platform this protects
   measured capacity more directly than request rate does; both
   dimensions are required, not one.
3. **Quotas** answer *too much this period*. Postgres-backed, derived
   from the usage ledger (ADR-0021), exact and durable. Measured in
   usage, not in requests. Returns 429 **without** `Retry-After` —
   retrying never helps, and saying otherwise builds clients that hammer.
4. **Spend limits** answer *past the money you authorized*. Postgres
   backed, derived from rated usage (ADR-0023). 402-class semantics.
5. **Capacity backpressure stays 503 and stays in the runtime.** 429 is
   *your allowance*; 503 is *our capacity*. They are never conflated.

**Hierarchy.** IP is a legitimate dimension **only before authentication**
(NAT and cloud egress make it unfair and evadable afterwards).
Organization is the load-bearing ceiling; per-key limits are subdivisions
that may never exceed it, because keys are unlimited in number and free
to create. Capability-scoped limits exist because measured capacity is
capability-scoped. Control-plane endpoints get their own cheap bucket.
Per-model and per-user limits are not implemented.

**Limits derive from the plan**, never hardcoded per organization: an
organization has a plan, a plan carries limits, an organization may carry
overrides — built with exactly one plan.

**Evaluation order is a cost gradient**: pre-auth IP guard →
authenticate → authorize → organization and key rate limits →
concurrency → parse/validate → registry resolution → capability limit →
quota → spend limit → inference. Identity-scoped checks run in a
dependency (no body parsing); capability and commercial checks run in the
service layer, where capability and model are known.

**Failure posture.** Redis-backed protection **fails open, loudly**, with
an alarm: a limiter outage becoming a platform outage is a worse failure
than minutes of unbounded traffic. Postgres-backed entitlement **shares
fate with authentication**: if Postgres is unavailable the platform
cannot authenticate anyway, so no independent failure mode exists.

**Quota overshoot is bounded, not eliminated.** A request's cost is
unknown until after inference, so the last admitted request may exceed
the allowance by at most `(concurrency limit) × (maximum single-request
cost)`. Maximum single-request cost is already bounded by the existing
input limits, which makes raising an input limit also a decision to raise
the overshoot bound.

## Alternatives considered

- **One unified limiter for all four questions** — rejected: they have
  different truth classes, stores, loss tolerances, retry semantics, and
  owners. A shared mechanism drags the exact system down to the
  approximate one's reliability.
- **Reserve-then-settle quota enforcement** — rejected for v0.5:
  distributed leases, expiry, and leak reconciliation to prevent an
  overshoot that is negligible at single-digit requests per second with
  2000-character inputs. The quota check is built as a named seam so the
  mechanism can land without restructuring.
- **Fixed-window rate limiting** — rejected: permits twice the limit
  across a window boundary.
- **Sliding-window log** — rejected: exact, but O(n) memory per principal
  for precision the use case does not need.
- **Read-then-write limiter in application code** — rejected: it races
  exactly under the concurrent load the limiter exists to control.
- **IP as a post-authentication dimension** — rejected: NAT and shared
  egress make it both unfair and trivially evaded.
- **Per-key limits without an organization ceiling** — rejected: defeated
  by creating more keys.
- **Per-organization hardcoded limits** — rejected: adding a plan tier
  would become a migration instead of a configuration change.
- **Failing closed when Redis is unavailable** — rejected: it converts a
  protection outage into a total outage.
- **Reusing 503 for allowance exhaustion** — rejected: the customer must
  be able to tell "slow down" from "they are broken".

## Trade-offs

- Redis becomes a serving-path dependency, mitigated by fail-open and by
  testing the outage rather than designing for it.
- Fail-open means a Redis outage is a window of unbounded traffic;
  accepted deliberately, alarmed loudly.
- Two limiting dimensions (rate and concurrency) mean two counters and
  two tuning surfaces.
- Bounded quota overshoot means a customer can end a period slightly over
  their allowance; accepted, bounded, and documented rather than hidden.
- Splitting admission across a dependency and the service layer makes the
  pipeline less visually linear than a single middleware would be.

## Consequences

- A limiter failure degrades protection, never correctness or revenue.
- Quota and spend enforcement read from the ledger, so entitlement and
  billing can never disagree about what was consumed.
- 429 and 503 remain diagnosable by customers without support contact.
- Adding a plan tier is configuration; adding a capability inherits
  capability-scoped limiting automatically.
- Raising an input limit is now explicitly a commercial decision as well
  as a safety one.
- Nothing in the inference plane changes; backpressure stays where
  ADR-0018 put it.

## Future review criteria

- A single request able to consume a meaningful fraction of a period
  quota (M5 batch jobs are the expected trigger) → implement
  reserve/settle at the named seam.
- Measured quota overshoot exceeding the predicted bound → the model is
  wrong; re-derive before adjusting limits.
- Redis outages frequent or long enough that fail-open traffic causes
  real harm → revisit with a degraded local limiter, not with fail-closed.
- Two models under one capability with materially different cost profiles
  → introduce per-model limits.
- Human principals acting through the console (M6) → per-user limits and
  the ADR-0013 authorization stage become relevant together.
