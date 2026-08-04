# Milestone 4 Engineering Design Review — Usage Metering & Rate Limiting (v0.5)

**Approved:** 2026-08-04, with six founder refinements incorporated
(§8 identity continuity, §7.4 usage origin, §7.5 internal lineage,
§12.4 language analytics). This document is the reference every M4 step
is reviewed against; material deviations go through review, not through
the sprint. Related decisions:
[ADR-0021](../adr/0021-usage-ledger-append-only-gateway-authored.md)
(usage ledger),
[ADR-0022](../adr/0022-admission-control-separation.md)
(admission control),
[ADR-0023](../adr/0023-pricing-versioned-price-book-pure-rating.md)
(pricing and rating),
[ADR-0024](../adr/0024-idempotency-at-most-once-billing.md)
(idempotency).

## 1. What this milestone is

M2 and M3 built the **capability to serve**. M4 builds the **capability
to charge** — a different engineering discipline with a different failure
mode.

An inference bug produces a bad transcript. A metering bug produces a
wrong invoice, and a wrong invoice is a trust event, a support event, and
eventually a legal event. Inference failures are loud and
self-announcing. **Metering failures are silent.** A pipeline that stops
recording revenue looks exactly like a quiet Tuesday. That asymmetry
shapes every decision in this milestone.

The platform already emits accounting *signals*: `speech.completed` and
`transcription.completed` are structured log lines carrying organization,
public model, and measured quantity, emitted only by the gateway. They
were designed in M2 as the seam this milestone lands on.

But a log line is not a ledger. It has no uniqueness guarantee, no
transaction, no foreign key, no query surface, and no durability
contract. **M4's central act is promoting those signals from logs to
records.** Almost everything below follows from that one promotion.

**The platform keeps two permanent ledgers: what models did (evidence,
M2.5) and what customers consumed (usage, M4). Neither is ever edited.
Everything else — prices, plans, rollups, dashboards, invoices in draft —
is derived and rebuildable.**

## 2. The commercial request lifecycle

The ordering below is not cosmetic. It is a cost gradient: every stage is
cheaper than the one after it, so the cheapest rejection happens first
and expensive work is never performed for a request that will be refused.

| # | Stage | Knows | Owns | Fails as |
|---|---|---|---|---|
| 1 | Customer | public surface only | the credential | — |
| 2 | Transport edge | IP, size | TLS, size ceiling, **pre-auth IP guard** | 429, no detail |
| 3 | Request context | `request_id` | correlation identity | — |
| 4 | Authentication | credential → `AuthContext` | identity (M1) | 401 |
| 5 | Authorization | principal + act | policy stage (ADR-0013 pass-through) | 403 |
| 6 | Admission — identity | org, key | org rate limit, key rate limit, org concurrency | 429 + `Retry-After` |
| 7 | Parse & validate | body | size, format, `max_text_chars` | 400 / 413 |
| 8 | Registry resolution | public model → capability, service, artifact | routing (ADR-0017) | 404 |
| 9 | Admission — commercial | capability, model | capability limit, quota, spend limit | 429 / 402-class |
| 10 | Idempotency claim | `Idempotency-Key` | at-most-once billing | 409 / 422 |
| 11 | Runtime invocation | request params | inference; **measurement** | 5xx → translated |
| 12 | **Metering** | identity + measurement | **the usage event** | alarm, never customer-visible |
| 13 | Response | outcome | headers, `X-Request-ID` | — |
| 14 | Rating (async) | event + price book | money, derived | recompute |
| 15 | Aggregation | events | rollups, analytics | recompute |
| 16 | Invoice (post-v1.0) | rated period | **frozen document** | credit note |

Three stages deserve their reasoning stated:

**Stage 2 — IP is legitimate only before identity exists.** A flood of
invalid keys costs us an HMAC and an indexed lookup each. Without a
pre-auth guard an attacker makes us work for free. *After* authentication
IP becomes a bad dimension (NAT, cloud egress, shared proxies) and must
never be the primary limiter.

**Stage 3 — the request id becomes the customer's receipt number.** Every
unit ever billed must be traceable to an id the customer independently
possesses (already returned in `X-Request-ID`). Billing systems that
cannot do this lose every dispute regardless of who is right. This costs
nothing: the identifier already exists.

**Stage 9 cannot happen before Stage 8**, because quota and capability
limits need the capability, and the capability is only known after
registry resolution. That is why admission control is deliberately split
in two rather than being one middleware.

## 3. What usage is

> **Usage is the platform's own measurement of work it performed on an
> identified customer's behalf.**

Four load-bearing words. **The platform's own** — never the customer's
claim; a quantity the customer supplies is an input, never a measurement.
**Measurement** — an observed physical quantity, not a commercial one;
money is not usage. **Performed** — intent, attempt, and rejection are
not usage. **Identified** — usage without an attributable principal is
telemetry.

### 3.1 Before inference, after inference, or both

Both — but they are not the same thing, and conflating them is the most
common metering bug in the industry.

| | Admission estimate | Settled measurement |
|---|---|---|
| Source | the request itself (bytes, characters) | the runtime's envelope |
| Precision | upper bound | exact |
| Purpose | protect capacity, bound abuse | account and bill |
| Durability | ephemeral, may be lost | permanent |
| Ever billed? | **never** | always, if billable |

The estimate exists because a quota cannot be enforced against a cost not
yet known. It must never enter the ledger. The moment an estimate can
become a charge, the system bills for work it did not do.

### 3.2 When usage becomes billable

Two conditions, both required: the customer received value (a 2xx
response was produced), **and** the platform measured the quantity (the
runtime returned a `Usage` entry). Everything else follows from a failure
matrix that is a *product* policy encoded in engineering — far harder to
change later than to decide now.

| Outcome | Billable | Usage event | Rate limit | Quota |
|---|---|---|---|---|
| 200 success | yes | billable | consumed | consumed |
| 400 validation (pre-inference) | no | request event only | consumed | no |
| 401 / 403 | no | none | IP guard only | no |
| 413 payload too large | no | none | consumed | no |
| 429 | no | none | already spent | no |
| 500 our defect | no | non-billable event | **refunded** | no |
| 503 capacity refusal | no | non-billable event | **refunded** | no |
| 504 runtime timeout mid-work | no | non-billable event | **refunded** | no |
| Client disconnects after success | **yes** | billable | consumed | consumed |

Three rows are opinions, not physics:

- **Validation errors consume rate limit but not quota.** A malformed
  request still costs a handshake, a lookup, and a parse; if it were free
  the cheapest attack on us would be an infinite stream of invalid
  requests. It consumes no *commercial* allowance because no work of
  value was performed.
- **The rate-limit token is refunded on 5xx.** Punishing a customer's
  retry budget for our own failure is indefensible. Small code, large
  trust.
- **Client disconnect after successful inference is billable** — we
  consumed the compute; socket handling is not our cost centre. **Founder
  decision F1, ruled 2026-08-04**, with a permanent clarification that
  outlives this milestone: **successful generation, not socket
  completion, defines billability.** The rule must still hold after
  streaming lands (§8.3) — a stream that produced its output is billable
  even if the connection died before the last byte was acknowledged.

### 3.3 What is discarded

Raw usage events are **never** discarded — they are the ledger.

| Artifact | Retention |
|---|---|
| Usage events (billable facts) | permanent — at minimum the life of the invoices they support plus statutory retention |
| Request events (analytics/abuse) | 90 days, then aggregate-only |
| Rate-limit counters | seconds to minutes; lost on Redis restart by design |
| Admission estimates | discarded the instant the request settles |
| Rated rollups | cache — deletable and rebuildable at will |
| Invoices | permanent and immutable |

### 3.4 The two laws that make pricing evolvable

> **Billing rounds. Metering does not.**

The event stores the exact measured quantity as returned. Rounding,
minimum billable duration, tiering, free allowances, and per-plan
discounts are *pricing* decisions applied at rating time. A metering
layer that rounds to whole seconds has destroyed information it can never
recover and has hardcoded a 2026 pricing decision into a permanent
record.

> **Meter everything measured. Let pricing decide what is billable.**

TTS returns both characters and audio seconds. We bill characters. We
record both — because next year we may price by seconds, and because
audio seconds are how cost-to-serve margin is computed. Measurement is
cheap; a missing measurement is unrecoverable.

## 4. Eight systems, eight questions

Each answers a different question, at a different latency, over a
different truth class, with a different failure consequence. That — not
tidiness — is the argument for separation.

| System | Question | Truth class | Store | Loss tolerance | Change cadence | Failure |
|---|---|---|---|---|---|---|
| Authentication | Who is calling? | identity | Postgres | none | rare | 401 |
| Authorization | May they do this act? | policy | Postgres | none | rare | 403 |
| Rate limiting | May they act *right now*? | protection | Redis | **tolerant** | tuned often | 429 + `Retry-After` |
| Quota | Too much *this period*? | entitlement | Postgres | none | per plan change | 429, no retry |
| Spend limit | Past authorized *money*? | entitlement (derived) | Postgres | none | customer-set | 402-class |
| Metering | What actually happened? | **fact** | Postgres, append-only | **none, ever** | ~never | alarm, never customer-facing |
| Rating / pricing | What is that fact worth? | derived | code (V1) → DB | rebuildable | **frequent** | recompute |
| Accounting | What is the running position? | derived aggregate | Postgres rollup | rebuildable | continuous | recompute |
| Billing / invoicing | What is owed for a period? | **frozen document** | Postgres, immutable | none | monthly | credit note |

**They fail differently and must be allowed to.** Rate limiting is
*allowed* to be wrong — losing counters means brief over-admission, which
is harmless. Metering is never allowed to be wrong. Sharing a store drags
the sacred one down to the fragile one's reliability.

**They change at incompatible speeds.** Pricing will change many times
before the metering schema changes once. Coupling them puts the ledger at
risk on every price experiment.

**They have different blast radii.** A limiter outage degrades quality; a
metering outage destroys revenue; a billing bug creates legal exposure.
Systems with different blast radii should not share code paths, deploy
cycles, or on-call semantics.

**The anti-pattern this prevents:** a `usage` table with a `cost_cents`
column. It looks efficient. The day prices change you must choose between
rewriting history (destroying auditability) and leaving inconsistent rows
(destroying reconcilability). Both answers are wrong, so the design was.

> **Rate limits are measured in requests. Quotas are measured in usage.**
> That is why quota enforcement requires metering and rate limiting does
> not — and why they can never be one subsystem.

## 5. Where usage truth lives, and fraud

> **The runtime measures. The gateway is the sole author of truth.
> Postgres is the system of record. Redis is never truth.**

### 5.1 Why not the runtime

It is the only component that *can* measure — it decodes the audio, it
counts the synthesized characters. It is disqualified as the accounting
authority for three reasons:

1. **It has no identity context** and must not acquire one; that would
   breach the plane separation of ADR-0002, re-affirmed in M3.
2. **It is the most replaceable component in the system.** M3's ratified
   law: product capabilities are permanent, individual engines are
   temporary. **Truth cannot live in a thing designed to be thrown
   away.**
3. **It is horizontally scaled, restartable, and stateless**; anything
   durable it wrote would need its own reconciliation story.

The runtime is an instrument. Instruments report readings; they do not
keep the books.

### 5.2 Why not Redis

**If losing it costs money, it is not allowed in Redis.** That single
rule partitions the entire milestone: counters, leases, and buckets in
Redis; facts and entitlements in Postgres.

### 5.3 Why the gateway

It is the only scope in the architecture where these coexist:
authenticated organization, API key, request id, idempotency key, public
model name, capability, usage origin, and the runtime's measurement. The
usage event *is* that intersection; no other component can construct it.

**Architecture dividend already in place:** session-per-request with
commit-on-success means a usage INSERT in the service layer commits in
the same unit of work that served the request, before the response is
serialized — transactional metering with no new machinery. (§15 R2 raises
a connection-lifetime risk this creates, which must be measured.)

### 5.4 Fraud prevention — customer side

| Vector | Control |
|---|---|
| Under-reporting usage | The customer never supplies a billable quantity. Only server-measured values enter the ledger. |
| Oversized inputs | Enforced pre-inference (`max_text_chars`, upload ceiling, transport limit) — these also bound quota overshoot (§10.4). |
| Replay to duplicate free work | Idempotency (§11) — protects the customer from double-billing, not us from double-compute. |
| Key sharing / resale | Abuse, not metering fraud: distinct-IP-per-key and usage-shape anomalies (§12.3). |
| Free-tier farming via many orgs | A signup-time concern (M7); flagged now so the org model does not make it easy. |
| Non-payment | Spend limits — the only control that works before payment integration. |

### 5.5 Fraud prevention — platform side, and measurement integrity

Every billed unit must be explicable: each usage event carries the
`request_id` the customer independently possesses.

Where the gateway can independently derive the quantity, it must — and
disagreement is an alarm, not a silent choice. The asymmetry is real:

- **TTS characters** — the gateway *can* derive this from the request
  text. It does, and asserts agreement with the runtime's report.
- **STT audio seconds** — the gateway *cannot*; decoding lives in the
  runtime by design (ADR-0018 sandboxing). Trust the instrument, bounded
  by a sanity envelope derived from input bytes and codec.

> **Where an independent derivation exists, record the runtime's
> measurement and assert agreement. Divergence is an incident, not a
> rounding difference.**

## 6. When inference succeeds and metering fails

| Option | Verdict |
|---|---|
| **A** — fail the request, roll back | **Rejected.** There is no rollback for compute; the work is already paid for. We would deliver nothing, invite an immediate retry, and pay twice — converting a bookkeeping fault into a service outage and punishing the customer for our defect. |
| **B** — serve and drop (today's implicit behavior) | **Rejected as the sole mechanism** — precisely the silent-failure class this milestone exists to eliminate. |
| **C** — serve, reconstruct from logs later | **Rejected.** Logs are lossy by design, retained shorter than billing needs, and carry no uniqueness constraint — reconstruction cannot distinguish a duplicated line from two real requests. |
| **D** — asynchronous broker (Kafka / Redis Streams) | **Rejected at this scale.** A second stateful system, exactly as ADR-0006 rejected for jobs, trading an exactly-once local INSERT for an at-most-once network hop. Graduation path is batched writes or a durable in-process spill — still not a broker. |
| **E** — durable-first, degrade loud | **Chosen.** |

**Option E in full:** inference succeeds → the usage event is written in
the request's existing transaction, before the response is serialized (a
sub-millisecond INSERT on a connection already held, on a request that
took hundreds of milliseconds) → **if that write fails, the customer
still receives 200**, the event goes to a durable fallback sink, and a
high-severity alarm fires.

> **Never charge the customer for our bookkeeping. Never let our
> bookkeeping charge the customer.**
>
> **Serving degrades open. Accounting degrades loud.**

A metering failure is a revenue incident and a paging event. It is never
a customer-visible error.

**The reconciliation invariant.** A fallback nobody checks does not
exist. M4 ships one daily query: *count of successful billable responses
(request events) must equal count of billable usage events, per
capability, per day.* Any nonzero delta is an alarm with a precise blast
radius. This is the difference between believing we bill correctly and
knowing it.

## 7. The event model

### 7.1 Two families, never merged

1. **Usage events** — billable facts. `transcription.completed`,
   `speech.completed`, later `ocr.completed`, `chat.completed`,
   `translation.completed`, `embedding.completed`. One per successful
   billable request. Permanent. Append-only.
2. **Request events** — every request including 4xx/5xx, with latency,
   status, model, capability. Higher volume, 90-day retention, not a
   ledger.

Merging them to "keep everything in one place" means the ledger's row
count is dominated by non-usage, and every revenue query starts with a
filter someone will forget to write.

Names carry forward unchanged from M2/M3, in **public product
vocabulary** on every customer-facing projection.

### 7.2 The schema principle

> **Adding a new capability must add zero columns.**

```
usage_event    : id · request_id (unique) · organization_id · api_key_id ·
                 idempotency_key · capability · public_model_id ·
                 origin · occurred_at · billable · outcome · lineage
usage_quantity : usage_event_id · unit · amount    (one row per quantity)
```

**Why not typed columns** (`audio_seconds`, `characters`): that design
dies the day OCR ships pages and chat ships tokens — every capability
becomes a migration and every revenue query grows a `COALESCE` chain.

**Why not a JSONB array**: revenue SQL must be boring, indexable, and
hard to get subtly wrong. `GROUP BY unit` beats JSON path operators when
the output is an invoice. The cost is one extra insert on an event that
already has two quantities.

This mirrors the runtime contract's `Usage(unit, amount)` tuple exactly —
the contract already anticipated multi-quantity billing, which is why M4
needs no contract change.

### 7.3 Immutability

**Events are never edited. Not once. Not ever.** Corrections are
**compensating events**: a reversal or adjustment referencing the
original event id. Ordinary double-entry discipline, for three reasons:

1. **Reproducibility** — an invoice must be regenerable from the ledger
   years later; editing history makes past invoices unreproducible.
2. **Trust** — a ledger that can be edited is a ledger whose numbers are
   opinions.
3. **Symmetry with the evaluation plane** — evidence is append-only for
   exactly these reasons. Two ledgers, one law, no special cases.

Enforced structurally: no UPDATE path in the repository, plus a
database-level restriction so a stray query cannot do what the code
refuses to.

### 7.4 Usage origin (founder refinement 3)

Not every metered request is a customer request, and the distinction is
**analytical, not permissional**. Every usage event carries an
**origin**, an append-only vocabulary:

| Origin | Meaning |
|---|---|
| `customer` | a paying or trialling customer's own traffic |
| `internal_qa` | manual verification, smoke tests, founder self-tests |
| `benchmark` | `bench-tts` / `bench-stt` production benchmark runs |
| `evaluation` | `speech-eval` and evidence-ledger runs |
| `research` | exploratory model or capability investigation |
| `fine_tuning` | data generation, validation, or training-adjacent inference |
| `demo` | sales, pitch, and public demonstration traffic |
| *(future)* | appended as new categories appear — never renamed, never removed |

Two rules govern it:

> **Measurement always occurs. Pricing may later choose which origins are
> billable.**

Internal traffic is metered exactly like customer traffic — we *want*
that data; it is how cost-to-serve is computed and how benchmark load is
attributed. Rating decides what is charged. Suppressing measurement to
avoid a charge is the mistake this design forbids, because a suppressed
measurement is unrecoverable while an unbilled one is merely a filter.

This deliberately **replaces** a binary internal-vs-customer flag: the
binary form answers only "do we invoice this?", while origin also answers
"what did evaluation cost us this month?", "how much capacity do
benchmarks consume?", and "what share of load is demos?" — questions that
arrive later and cannot be answered retroactively from a boolean.

Origin is an attribute of the **organization or key classification**
resolved at authentication time, never a customer-supplied header.

### 7.5 Internal lineage metadata (founder refinement 4)

Usage events may carry internal lineage: artifact id, foundation model
identity, quantization or distillation variant, adapter or merge
identity, dataset version, fine-tune version, and runtime version. This
is a deliberate, guarded exception to the public-vocabulary habit,
because it buys two things nothing else can:

- **Cost-to-serve per artifact** — which engine is cheaper per audio
  second is a commercial question answerable only if usage joins to
  artifact.
- **A bridge between the two ledgers** — the same artifact identity
  appears in both the usage ledger and the evaluation evidence ledger, so
  *"the cheaper engine also scored worse on WER"* becomes a query rather
  than an argument.

> **Lineage is internal forever. It is stored, never projected.**

The control is the leak-guard test pattern already proven in M2 and M3,
extended to every usage projection and usage API. Lineage is never an
input to rating (§9) — pricing must remain unable to see engines.

## 8. Identity continuity — the law that survives every model change

### 8.0 The Commercial Identity Invariant

Ratified by the founder at Step 0 close, 2026-08-04:

> **Customers buy capabilities, not foundation models.**
>
> Usage, pricing, quotas, invoices, subscriptions, and analytics
> permanently attach to public capabilities (`intelliai-stt`,
> `intelliai-tts`). Foundation models, artifacts, routing decisions,
> quantization, fine-tunes, adapters, merged models, and future engine
> replacements are implementation details and must never alter commercial
> identity.

This is the commercial twin of the M3 engineering law — *product
capabilities are permanent; individual engines are temporary*. One
governs how the platform is built, the other governs how it is sold, and
together they say the same thing from both sides of the boundary:

| | Engineering invariant (M3) | Commercial invariant (M4) |
|---|---|---|
| Statement | Product capabilities are permanent; individual engines are temporary | Customers buy capabilities, not foundation models |
| Governs | runtimes, registry, contract, evaluation | ledger, pricing, quotas, invoices, analytics |
| Violated by | an engine name reaching a customer response | an engine choice reaching a customer's bill |
| Guarded by | leak-guard and engine-replacement tests | the Step 6 continuity proof (identical event shape, identical rated amount) |

Sections 8.1–8.3 are that invariant stated against three specific
futures. The operational form throughout:

> **Usage, metering, pricing, and billing always follow the public
> product capability — `intelliai-stt`, `intelliai-tts` — never the
> internally selected engine, artifact, or adapter.**

### 8.1 Multi-model routing (refinement 1)

Registry V2 may route a single public model to different foundation
models based on language, quality tier, latency target, customer policy,
cost, or future routing logic not yet imagined. **None of that may change
customer-facing usage semantics.** Concretely, across any routing
decision:

- the public model id on the usage event is unchanged;
- the billable unit is unchanged;
- the price applied is unchanged;
- the invoice line reads identically.

The internal choice is recorded as lineage (§7.5) for cost analysis, and
is invisible to the customer. If a routing decision would *require* a
different customer-visible price, that is not routing — it is a new
public product, and it goes through product review, not through the
router.

### 8.2 Fine-tuning, quantization, distillation, adapters (refinement 2)

Future fine-tuned models, quantized builds, distilled students, LoRA
adapters, and merged models **inherit the public capability identity of
the product they serve**. Metering continuity survives every internal
model replacement.

This is the metering-plane statement of the M3 law: *product capabilities
are permanent; individual engines are temporary*. It has a testable form
that M4 owes the platform — **replacing the artifact behind a public
model must produce a byte-identical usage event shape and an identical
rated amount** — the commercial analogue of the customer-invisible
engine-replacement test that already guards the API surface.

Where a fine-tuned model is genuinely a *different product* (a
customer-specific model with its own price), it becomes a new public
model record with its own identity. The distinction is commercial, not
technical: same promise to the customer, same public id; different
promise, different id.

### 8.3 Streaming (refinement 5)

Streaming synthesis is a GO for M8 on M3's measured evidence. Recorded
now so the ledger is not redesigned then:

> **One successful request produces exactly one completed usage event,
> streamed or not. Chunks are transport, not billable units.**

Consequences that follow, and that streaming must honor rather than
renegotiate:

- The usage event is written when the generation **completes
  successfully**, with the total measured quantity — not per chunk, and
  not conditional on the socket. Per F1, successful generation defines
  billability; a completed generation whose delivery was interrupted is
  billable with `outcome = disconnected`.
- A stream that fails mid-flight follows the 5xx row of §3.2: a
  non-billable event recording what was produced, for cost analysis.
- Partial delivery is a **product** decision about whether partial output
  has value, not a metering mechanism. Metering never invents a
  fractional billing unit to describe a broken connection.
- Time-to-first-byte remains a latency metric, never a usage quantity.

## 9. Pricing — evolution without touching runtimes

```
runtime         → measures     (unit, amount)          knows no money
gateway         → meters       writes the fact         knows no money
price book      → declares     (unit → rate, rules)    knows no engines
rating function → prices       pure(event, book) → money
rollup          → aggregates   derived, rebuildable
invoice         → freezes      immutable document
```

**Rating is a pure function.** Same event plus same price book version
yields the same money forever. That property alone gives retroactive
price correction, "what would this month have cost on the new plan"
analysis, invoice reproduction, and confident refactoring.

**The price book is versioned** with `effective_from` / `effective_to`. A
price row is `(capability or public model, unit, rate, minimum_billable,
rounding_rule, tier)`. **Prices are never mutated — a change publishes a
new version.** Every rollup and invoice records which version produced
it.

**Code-declarative in V1**, mirroring Registry V1 (ADR-0017): prices
change rarely, deserve a diff and a second look, and git supplies the
audit trail for free. **Graduation criterion:** the first customer
specific negotiated price moves the book into the database, because
per-customer pricing cannot be a deploy.

**The price book does not belong in the registry.** The registry answers
*what serves this name*; the price book answers *what does this cost*.
Merging them means an engine swap touches pricing and a price change
touches routing. The only relationship is a shared vocabulary — the
public model id — never a shared table.

**Adding a new billing unit later** (OCR billed in pages): append
`UsageUnit.PAGES` to the contract enum (already append-only by law,
contract version unchanged), the OCR runtime reports it, one price row is
added. Gateway metering, rating, rollups, and invoicing change by zero
lines. That is the test of whether this design is right.

**Money representation.** `NUMERIC` in Postgres, `Decimal` in Python,
never float. A currency code on every monetary amount from day one, even
while single-currency. Rounding happens exactly once, at the invoice
line — never at measurement, never twice.

## 10. Admission control

### 10.1 Two dimensions, not one

> **Rate (requests per window) protects against velocity. Concurrency
> (in-flight) protects against occupancy. Inference platforms need both,
> and concurrency is the one that actually protects capacity.**

M3's own numbers force this: TTS plateaus at 0.64 rps with the pool
capping at 10 concurrent, and a single long transcription occupies a
worker for its whole duration regardless of request rate. Concurrency
limiting is a leased counter with a TTL — cheap, and the only thing that
stops one organization consuming the measured pool.

### 10.2 The hierarchy

| Level | Dimension | Purpose | Verdict |
|---|---|---|---|
| 0 | **IP** (pre-auth only) | protect the unauthenticated surface | required, and *only* pre-auth |
| 1 | **Organization** | the commercial ceiling | **required — load-bearing** |
| 2 | **API key** | isolate a runaway service | subdivision; may never exceed org |
| 3 | **Capability** | protect measured, capability-specific capacity | required |
| 4 | **Endpoint** | control-plane abuse (key enumeration) | separate cheap bucket |
| 5 | **Model** | — | rejected: redundant with capability today |
| 6 | **User** | — | rejected: no human principals until M6 |

**The organization limit must exist before key limits mean anything.**
Keys are unlimited in number and free to create; without an org ceiling a
customer defeats per-key limits by creating twenty keys.

**429 is not 503.** 429 is *your allowance* — a property of the caller,
carrying `Retry-After`. 503 is *our capacity* — already implemented as
fast refusals by the runtime worker pool. Conflating them leaves the
customer unable to tell whether to slow down or whether we are broken.

**Limits come from the plan, never hardcoded per organization.** An org
has a plan, a plan carries limits, an org may carry overrides — built
with exactly one plan, so adding a tier is a config change rather than a
migration.

Headers: `X-RateLimit-Limit`, `-Remaining`, `-Reset`, plus `Retry-After`
on 429, matching the convention our OpenAI-shaped API implies. Error code
`rate_limit_exceeded` in the existing ADR-0009 envelope. Additive; breaks
nothing.

### 10.3 Algorithm and failure posture

| Algorithm | Verdict |
|---|---|
| Fixed window | rejected — boundary bursts allow 2× the limit |
| Sliding window log | rejected — exact but O(n) memory for precision we do not need |
| **Token bucket / GCRA in a Redis Lua script** | **chosen** — atomic, O(1), controlled burst, one round trip |

Atomicity is not academic: a read-then-write from Python is a race that
fails precisely under the concurrent load the limiter exists to handle.

> **Redis-backed protection fails open, loudly. Postgres-backed
> entitlement shares fate with authentication.**

A limiter outage becoming a platform outage is a worse failure than a few
minutes of unbounded traffic. If Postgres is down we cannot authenticate
anyway, so quota and spend checks have no independent failure mode. The
whole fail-open/fail-closed debate is resolved by having chosen the
stores by loss tolerance in the first place — and it must be *tested* by
actually killing Redis, not merely designed.

### 10.4 Quotas versus rate limits

| | Rate limit | Quota |
|---|---|---|
| Question | too fast *right now*? | too much *this period*? |
| Purpose | protect the platform | enforce entitlement |
| Measured in | **requests / concurrency** | **usage** |
| Time | rolling seconds or minutes | absolute billing period |
| Truth | approximate, ephemeral, self-healing | exact, durable |
| Store | Redis | Postgres, derived from the ledger |
| On loss | brief over-admission, harmless | entitlement error |
| Retry | **retrying later succeeds** | **retrying never helps** |
| Response | 429 + `Retry-After` | 429 / 402-class, no `Retry-After` |
| Owner | engineering (capacity) | product (commercial) |

The retry asymmetry is why they must not share an error code: a client
treating quota exhaustion as a rate limit retry-loops against a wall and
opens a support ticket blaming us.

**The uncomfortable truth:** a quota cannot be enforced exactly at
admission, because a request's cost is unknown until after inference. The
honest response is to bound the overshoot rather than pretend:

> maximum overshoot = (in-flight concurrency limit) × (maximum
> single-request cost)

and maximum single-request cost is already bounded by the input limits
built for safety (`max_text_chars = 2000`, upload ceiling). Those limits
turn out to be what makes quota enforcement tractable — so **nobody may
raise an input limit without also raising the quota overshoot bound.**

**Reservations are deliberately rejected for M4.** Reserve-then-settle is
correct in general and wrong for this milestone: it introduces
distributed leases, expiry, and leak reconciliation to prevent an
overshoot that is negligible at single-digit rps with 2000-character
inputs. Complexity that buys nothing measurable is complexity that will
contain the bugs. **But the quota check must be built as a named seam**,
because M5 breaks the assumption immediately — an hour-long batch
transcription is one request that can consume a meaningful fraction of a
period. Design the simple thing now; design the *place* where the complex
thing will go.

## 11. Idempotency

Network retries, client timeout retries, and load-balancer retries all
produce the same request twice. Two failure modes follow: the customer is
billed twice (a trust event) and we compute twice (a cost event).

> **Idempotency guarantees at-most-once *billing*. It does not guarantee
> at-most-once *compute*.**

A deliberately narrower promise than customers may assume, so it must be
documented plainly. It is the right scope: the expensive guarantee
requires storing and replaying every response body including multi-
megabyte WAVs; the valuable guarantee requires a unique constraint.

- Accept an `Idempotency-Key` header (the Stripe convention — familiar to
  every developer who will integrate with us).
- Uniqueness scoped to `(organization_id, endpoint, idempotency_key)`,
  24-hour window.
- Claimed **atomically before inference** via `INSERT … ON CONFLICT DO
  NOTHING`. Won the insert → we own the work. Lost it → this is a retry.
- Retry of a **completed** request replays the stored outcome. Retry of
  an **in-flight** request returns 409 `request_in_progress` — we do not
  block or queue; for sub-second inference an honest 409 beats a held
  connection.
- The request fingerprint (model, params, hash of input) is stored, so
  **the same key with different content is a 422**, never a silent wrong
  response. That is the failure mode that makes naive idempotency
  dangerous.
- **JSON responses** (STT) are small: store and replay verbatim. **Binary
  responses** (TTS) either live in the existing object store under a
  short TTL, or are re-synthesized with billing suppressed by reusing the
  original usage event. v0.5 takes the second: simpler, honors the stated
  guarantee exactly, and object storage can be added later.

**Content-hash idempotency is rejected.** For a generative API two
identical requests are legitimately two billable events — a customer
synthesizing the same sentence twice receives two files and must be
charged twice. Absent an explicit client-supplied key there is no
idempotency, and that is correct behavior, not a gap.

**The guarantee lives in the database**, not in application logic:
`UNIQUE (request_id)` on every usage event (our middleware mints it, so
retries inside our own stack can never duplicate) and `UNIQUE
(organization_id, idempotency_key)` where a key was supplied. Two
constraints, enforced under any concurrency — including concurrency we
did not anticipate.

## 12. Observability and analytics

Four audiences with genuinely different needs; conflating them produces
dashboards nobody opens.

### 12.1 Operational

Request rate; latency p50/p95/p99 **per capability** (an aggregate across
STT and TTS is meaningless when their cost profiles differ by an order of
magnitude); error rate split 4xx vs 5xx; 429 rate; 503 rate; pool
saturation; model load events; upstream timeouts. New in M4: **added
gateway overhead from metering and limiting**, a number this milestone
must defend (§15 R1).

### 12.2 Commercial

Usage by capability by organization over time; active organizations; top
consumers; rated revenue; and the metric a solo founder cannot operate
without:

> **Cost-to-serve versus price — gross margin per capability.**

Computable today from M3's measurements (0.64 rps sustained, ~2.0 GiB
resident, known instance cost), yielding cost per audio second and per
thousand characters — **a price floor derived from measurement rather
than from guessing what competitors charge.** This is the commercial
plane's echo of *knowledge compounds*: benchmarks are not only quality
evidence, they are how we learn what we can afford to charge.

### 12.3 Integrity and fraud

- **Metering write failures — must be exactly zero, alarmed
  immediately.**
- The daily reconciliation invariant (§6).
- Usage anomaly: an organization's hourly usage against **its own**
  7-day baseline — a global threshold is either useless for small
  customers or noisy for large ones.
- Distinct IPs and user-agents per key (sharing / leak signal).
- 401 flood rate per IP.
- Runtime-versus-gateway measurement divergence (§5.5).
- Quota overshoot magnitude — exceeding the predicted bound means the
  model is wrong.

### 12.4 Product, quality, and language adoption (founder refinement 6)

The Core Speech Language Policy makes English, Hindi, and Arabic
first-class **product** languages. Analytics must therefore report
**language-level usage and adoption alongside capability-level metrics**:

- requested vs served language per capability, over time;
- adoption trend per language per organization (are customers arriving
  for Hindi, or are we assuming?);
- failure and quality-complaint rate by language;
- out-of-vocabulary and pronunciation-fallback frequency by language —
  the **Pronunciation Manager's** lexicon priority queue, generated from
  real traffic instead of intuition;
- unmet demand: requests for languages not yet served, which is the
  evidence that should drive engine research for Arabic and the Hindi
  checkpoint.

> **Language analytics informs the multilingual roadmap. It never affects
> billing semantics.** Language is an attribute of a usage event, never a
> pricing dimension — until and unless a founder decision makes it a
> product distinction, which would create a new public model, not a new
> price on an existing one.

### 12.5 Implementation posture

**Do not build or buy an observability platform in M4.** We have
structured JSON logs (ADR-0008) and Postgres, and at this scale **the
usage tables are the analytics warehouse.** M4 ships the reconciliation
invariant, the silent-failure alarms, and the handful of SQL queries that
will actually be run. Full observability, load testing, and dashboards
are already scoped to v0.95.

> **Alert on silence, not only on errors.** Zero metering writes for an
> hour is not a quiet period; it is an outage that produces no error.

## 13. Architectural placement and constraint compliance

### 13.1 Where code lives

| Concern | Home | Plane |
|---|---|---|
| Usage event model, recorder, repository | `apps/api` — metering module | control |
| Rate limiting, concurrency, quota, spend | `apps/api` — limits module | control |
| Price book and rating (pure) | `apps/api` — pricing module | control |
| Measurement | already in the runtimes | inference |
| Everything else | untouched | — |

### 13.2 Pipeline seams

- **Middleware** runs before routing: it cannot know capability or model
  and cannot see the measured result. Correct home for **pre-auth IP
  limiting only**.
- **Dependency** runs after auth and knows the route, but reading the
  body there is awkward across multipart and JSON. Correct home for
  **identity-scoped limits that need no body** (stage 6).
- **Service layer** already resolves the registry and already emits the
  accounting event. Correct home for **capability/quota checks and
  metering** (stages 9 and 12).

The split is the cost gradient again: cheap floods die without body
parsing; precise decisions happen where precise facts exist.

### 13.3 Constraint compliance — the claim M4 is held to

| Constraint | Status |
|---|---|
| Existing APIs must not change | Additive response headers; 429 is new behavior, launched generous (§18 F4) |
| Runtime contract must not change | **Zero changes.** `Usage(unit, amount)` already carries everything. `CONTRACT_VERSION` stays 1 through a third milestone |
| `runtime-core` must not change | **Zero changes.** Metering is control plane by construction |
| Registry remains model ownership | Pricing keys off public model / capability by convention; no shared table |
| Evaluation remains independent | Untouched; the usage ledger is a third record set, not a merge |
| Inference never knows pricing | Enforceable by an AST boundary test, using the pattern proven for `runtime-core` |
| Pricing never knows engines | The price book addresses public model ids and capabilities only; lineage is never a rating input |
| Billing never knows foundation models | Rating consumes `(capability, unit, amount)` |
| Public APIs expose only `intelliai-stt` / `intelliai-tts` | Leak-guard tests extended to usage projections |

If a design in any step *requires* changing `runtime-core` or the
contract, that is a signal the commercial plane has leaked into the
inference plane, and it is rejected on those grounds rather than
accommodated.

### 13.4 M4 does not force API key scopes

ADR-0013 named M4 as a possible trigger for scopes. With the requirement
now visible, the answer is **no**. The real need — our own benchmark,
evaluation, and QA traffic must not pollute customer revenue analytics —
is satisfied by **usage origin** (§7.4), which is a commercial
classification, not a permission. Scopes would model it as *what may be
done*, which it is not. **ADR-0013's pass-through authorization stage
stays a pass-through**, which is the outcome that ADR predicted.

## 14. Rejected designs

| Design | Why rejected |
|---|---|
| Cost stored on the usage event | Freezes a price into a permanent fact; makes price changes retroactively destructive and past invoices unreproducible |
| Typed quantity columns | Every new capability becomes a migration; revenue queries grow `COALESCE` chains |
| Editable usage records | Destroys audit, reproducibility, and the ledger's authority |
| Rolling back the response when metering fails | No rollback exists for compute; punishes the customer for our defect and doubles our cost |
| Message broker for usage events | Second stateful system (ADR-0006); trades exactly-once local writes for at-most-once delivery |
| Logs as the ledger | Lossy, wrongly retained, no uniqueness constraint, unreconstructable |
| Reservations / leases in v0.5 | Correct in general, unjustified at this scale; overshoot is bounded by existing input limits. Revisit at M5 |
| Content-hash idempotency | Wrong for a generative API — two identical requests are two billable events |
| Fixed-window rate limiting | Permits 2× the limit across a boundary |
| Non-atomic (read-then-write) limiter | Races exactly under the load it exists to control |
| IP as a post-auth limiting dimension | NAT and cloud egress make it unfair and evadable |
| Price book inside the registry | Couples routing to money; engine swaps would touch pricing |
| Rate limits hardcoded per organization | Adding a tier becomes a migration instead of a config change |
| Per-key limits without an org ceiling | Trivially defeated by creating more keys |
| Binary internal-vs-customer flag | Answers only "do we invoice this?"; loses questions that arrive later and cannot be answered retroactively (§7.4) |
| Suppressing measurement for internal traffic | A suppressed measurement is unrecoverable; an unbilled one is a filter |
| Per-chunk usage events for streaming | Chunks are transport; billing units must not be a function of connection behavior |
| Dashboards and an observability stack now | No traffic to observe; v0.95 owns this |
| API key scopes to classify internal usage | The distinction is commercial, not permission-shaped |

## 15. Risks

- **R1 — Added latency on every request.** M3 measured gateway overhead
  at 42.6 ms (2.0%). M4 adds Redis round trips and an INSERT. **Ceiling
  to defend: metering plus limiting adds < 10 ms at p95, total gateway
  overhead stays under 5%** — measured on the existing harness, never
  asserted.
- **R2 — Database connection lifetime versus long inference calls.** The
  session opens for the whole request, so authentication checks out a
  pooled connection that is held across the runtime call. With
  `pool_size=5` and `pool_max_overflow=10`, effective concurrency may cap
  near 15 in-flight requests regardless of inference capacity; M3's
  benchmarks likely never surfaced it because the runtime pool refuses at
  10 concurrent first, and the two ceilings mask each other. M4 adds
  database work to this path. **Must be measured explicitly.** The likely
  fix — close the auth transaction before the runtime call, open a short
  transaction for the usage write — removes metering from the auth
  transaction, so §6's durability argument must be **re-verified rather
  than assumed**.
- **R3 — Silent revenue loss.** Mitigated by the write-failure alarm, the
  durable fallback sink, and the daily reconciliation invariant. Without
  all three, correct billing is a belief rather than a fact.
- **R4 — Double-billing a customer.** Worse than lost revenue: it costs
  trust rather than money. Mitigated by database uniqueness constraints,
  never by application logic alone.
- **R5 — Redis becomes a hard dependency.** Mitigated by the explicit
  fail-open posture, which must be tested by killing Redis.
- **R6 — Period boundaries and time zones.** Billing periods are
  UTC-anchored with explicit `period_start` / `period_end` on every
  rollup. **A usage event belongs to the period containing its completion
  time**, not its start time. Cheap now, expensive after the first
  invoice.
- **R7 — Concurrency correctness.** Limiter increments must be atomic
  (Lua); rollup updates must be atomic (`UPDATE … RETURNING`). These bugs
  appear only under load, which is when they cost most.
- **R8 — Scope creep into billing.** The strongest risk to the milestone
  itself. Every conversation about Stripe, invoices, plans UI, or credits
  during M4 is scope creep wearing a business case (§17).
- **R9 — Tax and regulatory reality.** GST/VAT is out of scope, but the
  money type carries a currency code and the invoice model must be able
  to grow tax lines. Architecting them out is the mistake; building them
  now is the other mistake.

## 16. Implementation roadmap — review-gated steps

**Ordering: the fact before the enforcement before the price.** The
ledger is the only artifact whose shape is permanent, so it lands first
and everything else is written against a settled fact model. Admission
control precedes pricing because limits protect capacity from day one
while pricing has no customer waiting on it.

| Step | Concept / Trade-off | DoD sketch |
|---|---|---|
| **0 Governance** | Decisions before code: design review with founder refinements; ADR-0021/0022/0023/0024; founder decision ledger opened | This document committed; ADRs indexed; open decisions tagged with the step they gate |
| **1 Ledger** | Usage event + quantity schema, origin, lineage, immutability enforced structurally; repository with no UPDATE path | Migration + repository + tests; append-only proven by test, not convention; capability-agnostic schema proven by a fake third capability |
| **2 Metering** | Services write the event in the request's unit of work; failure degrades loud; reconciliation invariant query | `speech.completed` / `transcription.completed` become records; failure-path test asserts 200 + alarm; R2 measured |
| **3 Admission — protection** | Redis token bucket + org concurrency, plan-derived limits, 429 contract and headers; fail-open proven by killing Redis | Limits enforced at both seams; atomicity proven under concurrent load; Redis-down test serves traffic |
| **4 Admission — entitlement** | Quota and spend limit from the ledger; **free tier shipped from day one (F5)** so accrual, reset, and refusal all execute in production; overshoot bound asserted; reserve/settle seam named but unbuilt | Quota exhaustion returns the right code with the right retry semantics; period reset proven across a calendar-month boundary (F6); overshoot measured against the predicted bound |
| **5 Pricing** | Versioned code-declarative price book; rating as a pure function; rollups as rebuildable cache; units per F2, period per F6, billable origins per F7 | Rating reproducible from (event, version); rollup rebuild produces identical totals; **only `origin = customer` rated**, excluded by rating and never by measurement; prices remain internal (F3) |
| **6 Continuity proof** | The §8 law made testable: artifact swap and simulated multi-model routing produce identical usage events and identical rated amounts | Engine-replacement test extended to the commercial plane |
| **7 Production validation** | Overhead ladder vs the R1 ceiling; anomaly and language analytics queries; reconciliation run against real traffic | Benchmark doc published beside the STT and TTS baselines |
| **8 Close** | ADR review-criteria ledger, PRD v0.8, ARCHITECTURE v0.5 (identity-continuity invariant promoted), milestone review, version 0.5.0 | Review doc; founder decision ledger fully resolved |

## 17. Non-goals of Milestone 4

Each is anticipated by the architecture; none is built. A request for any
of these during M4 is a scope change and goes through review, not through
the sprint.

- **Payment processing** — cards, mandates, gateways.
- **Invoice generation or delivery** — the ledger makes it possible; the
  document is post-v1.0.
- **Tax computation** (GST/VAT) — the money type must not foreclose it;
  nothing more.
- **Prepaid credits and top-ups** — a signed-entry balance ledger, M7+.
- **Self-service plan selection or upgrade flows** — M7 console.
- **Developer console UI** — M7.
- **Per-customer negotiated pricing** — the trigger that moves the price
  book to the database, post-v1.0.
- **Async batch jobs** — M5; it is also what activates the reserve/settle
  seam.
- **Observability platform, dashboards, load testing** — v0.95.
- **API key scopes / RBAC** — not required (§13.4); adding them
  speculatively is the ADR-0013 mistake.
- **Any change to `runtime-contract`, `runtime-core`, or either runtime.**

## 18. Founder decision ledger — resolved 2026-08-04

All seven commercial decisions were ruled at Step 0 close. They are
recorded here as settled inputs, not open questions.

| # | Decision | Ruling | Gates |
|---|---|---|---|
| **F1** | Client disconnect after successful inference | **Billable.** The platform completed the work. **Successful generation, not socket completion, defines billability** — and this survives streaming | Step 2 |
| **F2** | Launch billing units | **STT → `audio_seconds`; TTS → `characters`** | Step 5 |
| **F3** | Published pricing in v0.5 | **Internal only.** Measure cost-to-serve and customer behavior before publishing | Step 5 |
| **F4** | Launch limit values | **Intentionally generous.** M4 validates the mechanism, not production numbers | Step 3 |
| **F5** | Free tier at launch | **Ship one from day one**, with generous default quotas — so quota logic, reset behavior, enforcement, analytics, and rating are exercised in production instead of lying dormant until the first customer | Step 4 |
| **F6** | Billing period anchor | **Calendar month, UTC** | Step 5 |
| **F7** | Billable origins | **Only `origin = customer`.** All other origins remain fully metered and are excluded during rating | Step 5 |

F5 is the ruling with the largest engineering consequence and it is worth
stating as a principle: **enforcement code that never runs is untested
code.** A free tier at launch means quota accrual, period reset, refusal
semantics, and rating exclusion all execute against real traffic from
day one rather than being exercised for the first time on the day a
paying customer hits a limit.

## 19. Registered platform work (from M4 design)

- **Reserve/settle quota enforcement** — named seam built in Step 4,
  implemented when M5's long-running batch jobs make single-request cost
  a meaningful fraction of a period quota.
- **Response replay for binary idempotency** — object-storage-backed
  replay of WAV responses, if customers ask for at-most-once *compute*
  rather than at-most-once billing.
- **Batched usage writes** — the graduation path from per-request INSERT,
  triggered by measured Postgres pressure, not by anticipation.
- **Language analytics surface** — §12.4 queries become a customer-facing
  and founder-facing view in the M7 console.
- **Cost-to-serve margin reporting** — usage joined to lineage joined to
  measured infrastructure cost; the commercial use of the benchmark
  asset, and the quantitative half of engine-replacement decisions.
- **Identity-continuity invariant** — §8 promoted into
  `ARCHITECTURE.md` at M4 close, beside the existing invariants.
