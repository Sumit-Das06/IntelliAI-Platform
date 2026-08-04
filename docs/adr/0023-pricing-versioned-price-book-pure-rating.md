# ADR-0023: Pricing — versioned price book outside the runtimes, rating as a pure function

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0005, ADR-0016, ADR-0017, ADR-0021, ADR-0022

## Context

The usage ledger records measurements and no money (ADR-0021). Money has
to come from somewhere, and every decision about where it comes from is
effectively permanent: an invoice issued in 2026 must still be
reproducible in 2031, and prices will change many times in between.

The platform already serves two capabilities billing in different units
(audio seconds, characters) and expects more: pages for document
capabilities, tokens for language models, images for vision. Registry V2
will additionally route one public model to different foundation models
by language, quality, latency, or customer policy, and future artifacts
will be fine-tuned, quantized, distilled, adapter-based, or merged.

## Problem

Where does price live, when is money computed, and how do prices change
without changing runtimes, invalidating history, or leaking engine
identity into billing?

## Decision

**We will keep price in a versioned price book outside the inference
plane, and compute money as a pure function of (usage event, price book
version), evaluated after the fact and never stored on the measurement.**

1. **Layering.** Runtimes measure. The gateway meters. The price book
   declares. Rating prices. Rollups aggregate. Invoices freeze. **Money
   never travels downward**: no runtime, and nothing in `runtime-core` or
   the runtime contract, may know a price exists.
2. **Rating is pure.** `rate(usage_event, price_book_version) → money`.
   The same inputs yield the same output forever, which is what makes
   retroactive correction, plan-comparison analysis, invoice
   reproduction, and confident refactoring possible.
3. **The price book is versioned and immutable.** Rows are
   `(capability or public model, unit, rate, minimum_billable,
   rounding_rule, tier)` with `effective_from` / `effective_to`. A price
   change publishes a new version; a published row is never mutated.
   Every rollup and every invoice records the version that produced it.
4. **Code-declarative in V1**, mirroring Registry V1 (ADR-0017): prices
   change rarely, deserve review, and git supplies the audit trail
   without an admin surface to build and secure.
5. **Price follows the public product capability**, never the internally
   selected engine. Multi-model routing, fine-tuning, quantization,
   distillation, adapters, and merges leave the customer-facing price
   unchanged. Internal lineage is recorded on the event but is **never an
   input to rating**. If a routing decision would require a different
   customer-visible price, it is a new public product, decided by product
   review, not by the router.
6. **Rounding happens once**, at the invoice line. Measurements are never
   rounded; minimums, tiers, free allowances, and discounts are price
   book rules applied at rating time.
7. **Origin decides billability, measurement never does.** Non-customer
   origins (benchmark, evaluation, internal QA, research, fine-tuning,
   demo) are metered exactly like customer traffic and excluded by
   rating.
8. **Money representation:** `NUMERIC` in Postgres, `Decimal` in Python,
   never float; a currency code on every monetary amount from day one.
9. **Rollups are cache.** Rated aggregates power spend limits and
   dashboards and may be rebuilt from events plus price book at any time.
   Only the invoice is frozen.

## Alternatives considered

- **Cost computed inline and stored on the usage event** — rejected: it
  freezes a price into a permanent fact, so a price change forces a
  choice between rewriting history and inconsistent rows. This is the
  single most common commercial-schema mistake and the reason ADR-0021
  keeps the ledger money-free.
- **Price book inside the registry** — rejected: the registry answers
  *what serves this name*, the price book answers *what does this cost*.
  Merging them means an engine swap touches pricing and a price change
  touches routing.
- **Price attached to the artifact** — rejected outright: it would make
  billing a function of the foundation model, breaking identity
  continuity the first time routing or a fine-tune changed what serves a
  request.
- **Database-backed price book in V1** — rejected for now: no
  customer-specific pricing exists, and a mutable price surface without
  review is a way to change revenue by accident. It becomes right the day
  a negotiated enterprise price exists.
- **Mutable price rows with an audit table** — rejected: versioning is
  the audit trail; a parallel audit table is a second source of truth
  that can drift.
- **Rating at request time for real-time spend accuracy** — rejected as
  the primary mechanism: it re-introduces money into the serving path and
  into the fact. Near-real-time spend is served by the rebuildable rollup
  instead.
- **Floating-point money** — rejected: sub-cent drift per request becomes
  a real number at volume and an embarrassing one in an audit.
- **Single-currency amounts without a currency code** — rejected: adding
  currency later touches every row and every query.

## Trade-offs

- Rated totals are eventually consistent with usage, so spend limits act
  on a slightly stale balance; bounded by rollup frequency.
- A price change requires a deploy in V1 — deliberate friction, and a
  real constraint once pricing experiments become frequent.
- Storing measurement plus version instead of a computed amount costs a
  join and a recomputation on every revenue query.
- Keeping money out of the serving path means the API cannot return a
  per-request cost today; a customer-visible cost surface is a console
  feature, not a response field.

## Consequences

- Invoices are reproducible from immutable inputs for the life of the
  business.
- Prices can change, and can be corrected retroactively, without touching
  the ledger, the gateway, `runtime-core`, the runtime contract, or any
  runtime.
- A new billing unit costs one appended `UsageUnit` member (the contract
  enum is already append-only) plus one price row — zero changes to
  metering, rating, rollups, or invoicing.
- Cost-to-serve margin becomes computable by joining rated revenue to
  lineage and measured infrastructure cost, making engine-replacement
  decisions quantitative on quality, cost, and revenue simultaneously.
- Internal traffic is fully measured and never billed, so evaluation and
  benchmarking consume capacity visibly without polluting revenue.

## Future review criteria

- The first customer-specific negotiated price, committed-use discount,
  or enterprise contract → move the price book into the database with a
  reviewed administrative surface.
- Pricing experiments frequent enough that deploy friction shapes
  commercial decisions → same trigger.
- A capability whose price genuinely cannot be expressed as a function of
  `(capability, unit, amount)` → reopen the rating model rather than
  special-case it.
- Multi-currency selling or a tax obligation (GST/VAT) → extend the money
  and invoice models; the currency code exists from day one so that
  extension is additive.
