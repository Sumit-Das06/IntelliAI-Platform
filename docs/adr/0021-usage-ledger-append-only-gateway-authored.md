# ADR-0021: Usage ledger — append-only, gateway-authored, money-free facts

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0002, ADR-0008, ADR-0016, ADR-0017, ADR-0022, ADR-0023, ADR-0024

## Context

Two capabilities now serve customers, and both already emit accounting
signals: `transcription.completed` and `speech.completed` are structured
log lines carrying organization, public model, and the measured quantity
from the runtime envelope. They are emitted only by the gateway, in
public vocabulary, by deliberate M2 design.

A log line is not a ledger. It has no uniqueness guarantee, no
transaction, no foreign key, no query surface, and no durability
contract. Revenue cannot rest on it.

Three architectural facts constrain the answer. The runtime is the only
component that can *measure* (it decodes the audio, it counts the
synthesized characters) but it holds no tenant identity and is the most
replaceable component in the platform. The gateway is the only scope
where identity and measurement coexist. And the evaluation plane already
runs an append-only evidence ledger, so the platform has a precedent for
immutable measured facts.

## Problem

What is a usage fact, who is permitted to author it, where does it live,
and may it ever change?

## Decision

**We will record usage as an append-only ledger in Postgres, authored
exclusively by the gateway, containing measurements and never money.**

Mechanics that are part of the commitment:

1. **Authorship.** The runtime measures; the gateway meters. A usage
   event is written only by the gateway, only after a successful
   response, only from server-measured quantities. No customer-supplied
   quantity ever enters the ledger.
2. **Immutability.** Events are never updated or deleted. Corrections are
   compensating events referencing the original event id. Enforced
   structurally (no UPDATE path in the repository, plus a database-level
   restriction), not by convention.
3. **Money-free.** The event stores the exact measured quantity as
   returned — never rounded, never priced. Rounding, minimums, tiers, and
   discounts are pricing decisions (ADR-0023).
4. **Capability-agnostic shape.** Quantities are `(unit, amount)` rows,
   mirroring the runtime contract's `Usage` tuple. Adding a capability
   adds zero columns.
5. **Meter everything measured; let pricing decide what is billable.**
   All measured quantities are recorded even when only one is billed.
6. **Usage origin.** Every event carries an origin from an append-only
   vocabulary (`customer`, `internal_qa`, `benchmark`, `evaluation`,
   `research`, `fine_tuning`, `demo`, future members). Origin is resolved
   from organization/key classification at authentication, never
   supplied by a caller. Measurement always occurs; rating decides which
   origins are billable.
7. **Internal lineage.** Events may carry artifact id, foundation model,
   quantization/distillation variant, adapter or merge identity, dataset
   and fine-tune version, and runtime version — stored for cost-to-serve
   analysis and to join the usage ledger to the evaluation evidence
   ledger. **Internal forever: stored, never projected**, guarded by the
   existing leak-guard test pattern, and never an input to rating.
8. **Identity continuity.** Usage follows the public product capability
   (`intelliai-stt`, `intelliai-tts`), never the internally selected
   engine. Multi-model routing, fine-tuned, quantized, distilled,
   adapter-based, and merged models inherit the public capability
   identity; the usage event shape and the rated amount are unchanged by
   any internal replacement.
9. **Traceability.** Every event carries the `request_id` already
   returned to the customer in `X-Request-ID`, so every billed unit is
   explicable to the party paying for it.
10. **One request, one event.** Exactly one completed usage event per
    successful request, streamed or not. Chunks are transport, not
    billable units.
11. **Durable-first, degrade loud.** The event is written before the
    response is serialized. If the write fails the customer still
    receives their response; the event goes to a durable fallback sink
    and a high-severity alarm fires. A daily reconciliation invariant
    (successful billable responses = billable usage events, per
    capability) makes silent loss impossible to miss.

Usage events are a separate family from request events (every request,
including 4xx/5xx, for analytics and abuse detection, 90-day retention).
The two are never merged.

## Alternatives considered

- **Logs as the ledger** — rejected: lossy by design, retained shorter
  than billing requires, and carrying no uniqueness constraint, so
  reconstruction cannot distinguish a duplicated line from two real
  requests.
- **Runtime-authored usage** — rejected: the runtime has no tenant
  identity and must not acquire one (ADR-0002), and truth cannot live in
  the component the platform is explicitly designed to replace.
- **Redis-authored counters as the record** — rejected: if losing it
  costs money, it does not belong in Redis. Redis holds protection state
  only (ADR-0022).
- **Cost stored on the event** — rejected: freezes a price into a
  permanent fact, so a price change forces a choice between rewriting
  history (destroying auditability) and inconsistent rows (destroying
  reconcilability).
- **Typed quantity columns** (`audio_seconds`, `characters`) — rejected:
  every new capability becomes a migration and every revenue query grows
  a `COALESCE` chain.
- **JSONB quantity array** — rejected: revenue SQL must be boring and
  indexable; `GROUP BY unit` beats JSON path operators when the output is
  an invoice.
- **Editable events** — rejected: a ledger that can be edited is a ledger
  whose numbers are opinions, and past invoices become unreproducible.
- **A binary internal-vs-customer flag** — rejected in favour of usage
  origin: the boolean answers only "do we invoice this?" and cannot
  retroactively answer what evaluation, benchmarking, or demos cost.
- **Asynchronous broker delivery** (Kafka, Redis Streams) — rejected at
  this scale for the same reasons ADR-0006 rejected a broker for jobs: a
  second stateful system, trading an exactly-once local INSERT for
  at-most-once network delivery.
- **Failing the request when metering fails** — rejected: there is no
  rollback for compute; it delivers nothing, invites a retry, and
  charges us twice for our own defect.

## Trade-offs

- A synchronous INSERT on the serving path. Small against inference
  latency, but real, and it must be measured rather than assumed.
- Compensating events make corrections more verbose than an UPDATE, and
  every consumer must understand netting.
- Storing all measured quantities and full lineage costs storage that a
  minimal billing schema would not spend.
- Origin as an append-only vocabulary means a miscategorised organization
  produces permanently miscategorised history; classification is a
  reviewed decision, not a toggle.
- Two event families mean two retention policies and two write paths
  instead of one table.

## Consequences

- Invoices become reproducible from the ledger years later, because
  history is immutable and money is derived.
- Adding a capability (OCR, vision, chat, translation, embeddings)
  requires no metering change: a new `UsageUnit` member and a price row.
- Engine replacement, fine-tuning, and multi-model routing become
  commercially invisible by construction, and that invisibility is
  testable.
- The platform now keeps two permanent ledgers — evaluation evidence and
  customer usage — under one immutability law, joinable through lineage.
- Silent revenue loss requires the simultaneous failure of a write, an
  alarm, a fallback sink, and a daily invariant.
- Nothing in the inference plane changes: no runtime, no `runtime-core`,
  no runtime contract.

## Future review criteria

- Sustained INSERT pressure visibly degrading serving latency → batched
  writes or a durable in-process buffer (still not a broker).
- Ledger volume making period aggregation slow enough to affect the
  console → partitioning by period, or a dedicated analytics store.
- A regulatory or contractual requirement to physically delete usage
  history → revisit immutability with a documented redaction protocol
  that preserves aggregate integrity.
- A capability whose billable quantity genuinely cannot be expressed as
  `(unit, amount)` → reopen the quantity model before special-casing it.
