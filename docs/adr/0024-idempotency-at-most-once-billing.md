# ADR-0024: Idempotency — client-supplied keys guaranteeing at-most-once billing

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0009, ADR-0012, ADR-0021

## Context

Once requests are billed, retries acquire a cost. Network retries, client
timeout retries, and load-balancer retries all deliver the same request
twice, producing two distinct harms: the customer is billed twice (a
trust event) and the platform performs the work twice (a cost event).

The two capabilities return different response shapes: transcription
returns small JSON, synthesis returns a raw WAV body that can be
megabytes (ADR-0020). Any replay mechanism has to answer for both.

Our own middleware already mints a `request_id` per request and returns
it in `X-Request-ID`, and the usage ledger already carries it (ADR-0021).

## Problem

What guarantee does the platform make about duplicate requests, how is it
enforced, and what happens when a retry arrives while the original is
still running?

## Decision

**We will accept a client-supplied `Idempotency-Key` header and guarantee
at-most-once *billing* — explicitly not at-most-once *compute* — enforced
by database uniqueness rather than by application logic.**

1. **The guarantee is narrow and stated.** A retry carrying the same key
   never produces a second billable usage event. It may, for binary
   responses, produce a second inference; the customer is not charged for
   it.
2. **Scope and window.** Uniqueness is `(organization_id, endpoint,
   idempotency_key)` over a 24-hour window.
3. **Claimed before inference**, atomically, via `INSERT … ON CONFLICT DO
   NOTHING`. Winning the insert means we own the work; losing it means
   this is a retry.
4. **In-flight retries return 409 `request_in_progress`.** We do not
   block or queue: for sub-second inference an honest 409 beats a held
   connection.
5. **Key reuse with different content is 422**, never a silently wrong
   response. The stored request fingerprint (model, params, hash of
   input) makes this detectable.
6. **Replay policy by response shape.** JSON responses are stored and
   replayed verbatim. Binary responses are re-synthesized with billing
   suppressed by reusing the original usage event; object-storage-backed
   replay is registered as future work if customers ask for at-most-once
   compute.
7. **Absent a client key there is no idempotency**, and that is correct
   behavior rather than a gap.
8. **The guarantee lives in the database**: `UNIQUE (request_id)` on
   every usage event, and `UNIQUE (organization_id, idempotency_key)`
   where a key was supplied.

## Alternatives considered

- **Content-hash idempotency** (deriving the key from the request, no
  header needed) — rejected, and this is the important rejection: for a
  generative API two identical requests are legitimately two billable
  events. A customer synthesizing the same sentence twice receives two
  files and must be charged twice. Content-hash idempotency would
  silently under-bill us and silently surprise them.
- **At-most-once compute as the guarantee** — rejected for v0.5: it
  requires storing and replaying every response body, including
  multi-megabyte audio, to protect against a duplicate cost that is small
  at current volume. The valuable half of the guarantee costs a unique
  constraint; the expensive half costs an object-storage subsystem.
- **Blocking or queueing an in-flight duplicate** — rejected: it holds a
  connection for the duration of an inference and turns a client retry
  storm into a connection-pool problem.
- **Application-level duplicate detection** (check, then act) — rejected:
  it races precisely under the concurrent retries it exists to handle.
  Uniqueness must be enforced by the database.
- **Deduplicating on `request_id` alone** — rejected as the customer
  facing mechanism: we mint it, so it protects against duplication inside
  our stack but cannot recognise a client's retry, which arrives as a new
  request. Both constraints are needed for different threats.
- **A custom header name** — rejected: `Idempotency-Key` is the
  convention every developer integrating with a billing API already
  knows, and our error and API surfaces already follow that family
  (ADR-0009).
- **Indefinite key retention** — rejected: an unbounded table for a
  transient protection, when retries occur within minutes and 24 hours is
  already generous.

## Trade-offs

- A duplicate binary request can still cost us compute; accepted
  deliberately and revisited if measured.
- One extra write on the serving path before inference.
- Callers who never send the header get no protection, so the guarantee
  must be documented prominently rather than assumed.
- Storing request fingerprints means hashing the input payload on every
  keyed request.
- A 24-hour window means a retry after a day is a new billable request;
  correct, but a surprise worth documenting.

## Consequences

- Double-billing requires a database uniqueness violation, not merely a
  logic error.
- Retry storms become safe for the customer's invoice and diagnosable for
  us (a rising 409 rate is a client-integration signal, not an outage).
- The billing guarantee is independent of response shape, so future
  capabilities inherit it without re-deciding.
- The idempotency record joins directly to the usage event, so a disputed
  charge resolves to a single request id and a single key.

## Future review criteria

- Customers asking for at-most-once *compute*, or duplicate binary
  synthesis becoming a measurable cost → add object-storage-backed
  response replay.
- A capability whose responses are neither small JSON nor replayable
  binaries (streaming, long-running jobs) → decide its replay semantics
  before it ships; M5 batch jobs are the expected first case.
- Sustained 409 rates indicating clients treating in-flight duplicates as
  failures → revisit with a bounded wait before answering.
- Idempotency-record volume pressuring Postgres → shorten the window or
  move the claim to a durable store, never to a lossy one.
