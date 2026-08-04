# Milestone 4 Close-Out Review — Usage Metering & Rate Limiting (v0.5)

- **Closed:** 2026-08-04
- **Design reference:** [4-metering-design.md](4-metering-design.md)
- **Decisions:** [ADR-0021](../adr/0021-usage-ledger-append-only-gateway-authored.md),
  [ADR-0022](../adr/0022-admission-control-separation.md),
  [ADR-0023](../adr/0023-pricing-versioned-price-book-pure-rating.md),
  [ADR-0024](../adr/0024-idempotency-at-most-once-billing.md)
- **Baseline:** [commercial plane v1](../benchmarks/2026-08-04-commercial-plane-baseline.md)
- **Tests:** 430 → **576**
- **Contract version:** 1 (unchanged through a third milestone)

## 1. What shipped

| Step | Delivered | Commit |
|---|---|---|
| 0 Governance | Design review, ADR-0021/0022/0023/0024, founder decision ledger | `40db3a6` |
| 1 Ledger | `usage_events` + `usage_quantities`, append-only by trigger, origin, lineage | `7b86e5d` |
| 2 Metering | Log lines → permanent records; five failure semantics proven | `8247251` |
| 3 Admission | Redis token buckets, concurrency leases, plan-derived limits, circuit breaker | `eba3ada` |
| 4 Entitlements | Quota from the ledger, spend limits, day-one free tier, UTC periods | `2ded108` |
| 5 Pricing | Versioned price books, pure rating, rebuildable rollups | `7c9a52b` |
| 6 Continuity | `rating_algorithm_version`; eight internal realities, one fingerprint | `e0330a5` |
| 7 Production | Reconciliation, anomalies, language analytics, baseline | `ee187e7` |
| 8 Close | This review, PRD v0.8, ARCHITECTURE v0.5, version 0.5.0 | — |

**Ten architectural laws** were ratified during the milestone, all in the
design document: Commercial Identity (§8.0), Ledger Fact (§7.6), Request
Identity (§7.7), Ledger Completeness (§6.1), Commercial Completeness
(§7.8), Commercial Interpretation (§8.4), Rollup (§8.5), Rating
Reproducibility (§8.6), Historical Explainability (§8.7), Protection
Independence (§10.1a), Operational Honesty (§10.1b), and Operational
Measurement Independence (§10.1c).

## 2. Validated assumptions

Each of these was an assumption at design time and is now evidence.

**The M2 contract needed no changes to carry billing.** `Usage(unit,
amount)` was designed against two capabilities in M2 and turned out to
be exactly what a billing ledger needs. `CONTRACT_VERSION` stayed 1
through a third milestone, and `runtime-contract`, `runtime-core`,
`stt-runtime`, and `tts-runtime` ended M4 byte-identical to how they
started it.

**Session-per-request gave transactional metering for free.** The M1
unit-of-work meant a usage row commits with the response that produced
it, with no new machinery — a genuine dividend from a decision made
three milestones earlier.

**Quota can be read from the ledger rather than a counter.** Measured at
1.31 ms (100 events), 2.58 ms (1 000), 8.36 ms (5 000). One source of
truth, no drift, and cheap enough that the parallel counter was never
needed.

**The commercial plane is affordable.** ~18 ms p50 total, stable
regardless of inference duration; 2.1% of a served request at realistic
TTS latency.

**Capability-agnosticism holds under test, not just in argument.** Six
capabilities that do not exist (OCR, vision, chat, translation,
embeddings, speech-to-speech) record, rate, and are limited correctly
with zero schema and zero code changes.

**Engine replacement is commercially invisible.** Eight internal
realities — engine replacement, artifact swap, fine-tune, quantization,
LoRA, multilingual routing, registry promotion — produce one commercial
fingerprint across the customer API, ledger, quota, rollup, and rating.

**F8 was the right call.** Raising `pool_size` moved the concurrency
ceiling from 15 to 30 without touching transaction ownership, so §6's
durability argument never had to be re-earned. *Tune the cheap knob
before weakening a guarantee* is now a platform principle.

## 3. Invalidated assumptions

The ones worth more than the validated ones.

**"Failing open is enough."** It was not. With Redis unreachable, each
of a request's five limiter calls burned the full socket budget: **+1.2 s
per request**. A limiter outage was becoming a platform degradation by
another route — precisely what the fail-open posture exists to prevent.
A circuit breaker brought p50 at c=10 from 1891 ms to 575 ms,
indistinguishable from healthy. The law was amended to *fails open,
loudly — **and cheaply***.

**"A fail-fast timeout is a self-contained decision."** It interacts
with hostname resolution. A dual-stack name in front of an IPv4-only
Redis spends the whole budget on failover, and **the platform then runs
unlimited while looking perfectly healthy**. The alarm fires — that is
the point of failing loudly — but the cause is configuration, not Redis.

**"A per-key limit is a meaningful subdivision."** Only if it is
namespaced by surface. A shared key bucket silently re-opened the hole
the control-plane bucket exists to close: credential enumeration
consuming the inference allowance a customer paid for. Caught by a
failing test, not by review.

**"Cold and drifted are both 'the rollup is wrong'."** They are not.
Reconciliation initially reported a never-built cache as drift.
"Never built" and "disagrees with the ledger" have different causes and
different urgencies, and conflating them is how alerts get ignored.

**"The spend limit can wait for the pricing step."** It could not: a
spend limit is a limit on *money*, and money does not exist until usage
is rated. Step 4 had to bring forward the minimum of ADR-0023 —
versioned books and pure rating — which is why Step 5 became completion
rather than construction.

**"Infrastructure absence is obvious."** Twice this milestone, missing
infrastructure produced *silently passing* tests: CI had no Redis, so
the limiter correctly failed open and every limit test passed while
proving nothing; and the dev database's residue made platform-wide
reconciliation tests order-dependent. Both are the same lesson: **a test
whose subject is a guarantee must fail, not skip quietly, when the thing
that provides the guarantee is absent.**

## 4. Architectural lessons

**Laws earn their keep when they are executable.** Every invariant in
this milestone has a test that fails if it is violated — the AST check
that `limits/` cannot see an engine, the fingerprint that collapses eight
realities to one, the assertion that the ledger has no column a discount
could occupy. A law with no failing case is a preference.

**The negative control is the load-bearing test.** A proof that "nothing
ever changes" is worthless unless the same machinery detects a change
that *should* happen. Step 6's pricing-policy change is what makes the
silence everywhere else meaningful.

**Separate what fails differently.** ADR-0022's split between Redis
protection and Postgres entitlement produced the single best production
result of the milestone: with Redis stopped, the platform kept serving,
published nothing it had not measured, and **still enforced idempotency**
— because that guarantee lives in a database constraint, not in a cache.

**Two mechanisms for one guarantee, when the guarantee is revenue.** The
ledger is append-only by database trigger *and* by an AST test that
refuses to let a mutating statement be written. One stops a mutation at
runtime; the other stops it from being written at all.

**State limitations rather than implying them.** The baseline names five,
including that the gateway → ledger link is only partially reconciled.
A limitation that is written down is debt; one that is not is a surprise.

**Measure the thing you are about to defend.** Every "this is cheap
enough" in this milestone has a number, and two of them changed the
design after the measurement.

## 5. Debt and future work

| Item | Why it exists | Trigger |
|---|---|---|
| **Persist request events** | Completes the gateway → ledger reconciliation leg; today only proves nothing was *rejected*, not that nothing was *missed* | before real revenue depends on the audit |
| **Invoice document** | Closes the Historical Explainability Invariant (§8.7); assembly, not design — every field already exists on `RatedLine` | post-v1.0 |
| **TTS language capture** | Language analytics are complete for STT, blank for TTS: the public synthesis API has no `language` parameter | M5 — a product decision |
| **Reserve/settle quota** | Removes bounded overshoot; the seam is named and unbuilt | when one request can consume a meaningful fraction of a period (long batch jobs) |
| **Rollup-backed quota** | Ledger aggregate is 1–3 ms today | ~25 000 events in one tenant's month (~40 ms) |
| **Response replay for binary idempotency** | Would give at-most-once *compute*, not just billing | if duplicate synthesis becomes a measurable cost |
| **Postgres role hardening** | `REVOKE UPDATE, DELETE` on ledger tables, beside the triggers | deployment hardening |
| **Batched usage writes** | Graduation from per-request INSERT | measured Postgres pressure, not anticipation |
| **Published pricing** | F3 keeps prices internal in v0.5 | customer evidence |

Two operational notes: the dev database permanently holds measurement
rows from this milestone (the ledger is append-only, so `make clean` is
the only reset), and those runs should have used `origin=benchmark` —
a small validation of why usage origin exists.

## 6. M4 → M5: multilingual engines without commercial redesign

M5 is the **multilingual foundation** milestone. The question this
review must answer is precise: *what does adopting Hindi and Arabic
engines cost the commercial plane?*

**The answer is nothing, and here is why, mechanism by mechanism.**

| M5 will do this | Commercial plane response |
|---|---|
| Adopt a Hindi engine as a new artifact | A registry record. The ledger records `public_model_id`, never an artifact (§8.0) |
| Promote `intelliai-tts` to route by language | Proven invisible in Step 6 — registry promotion is one of the eight realities |
| Serve Arabic from a different engine with different capacity | A *capacity* concern (the runtime's 503), never an admission one (§10.1a) |
| Run a Hindi engine on different hardware | Forbidden as a commercial input (§10.1c) — no cost-recovery pricing by placement |
| Fine-tune, quantize, or LoRA-adapt a language model | Inherits the public capability identity (§8.2) |
| Measure Hindi quality against the corpus | Evaluation plane; unchanged and independent |

**What is already in place for M5 on day one:**

- **Language is a ledger fact.** Every event records the observed
  language, and the analytics report adoption *by distinct organization*,
  separates policy languages from unserved demand, and treats regional
  tags (`hi-IN`, `ar-EG`) as their base language.
- **Quota is keyed by unit, not by language or capability.** A Hindi
  request of 500 characters consumes exactly what an English one does.
- **Pricing is keyed by the public capability's billing unit.** Adopting
  a language changes no price.
- **The continuity proof already covers it.** Step 6 ran multilingual
  routing across three languages, including an Arabic engine that does
  not exist, and produced one commercial fingerprint.

**The one thing M5 must decide, and it is a product decision:** the
public TTS API has no `language` parameter, so synthesis records
`language=None`. Does a customer *state* a language, or is it inferred
from the voice they chose? Either answer is fine for the commercial
plane — `language` is already a nullable ledger column and an analytics
dimension — but until the product decides, TTS language adoption cannot
be measured, and the Core Speech Language Policy is being tracked on
half the evidence.

**And the one thing M5 must not do:** make language a pricing or
admission dimension without a published price book version. If Arabic
ever costs more, that is a new price book version (visible, dated,
versioned) or a new public model — never a special case in metering
(§10.1c).

## 7. ADR review criteria — do the decisions still hold?

| ADR | Review criterion | Status at M4 close |
|---|---|---|
| **0021** ledger | Sustained INSERT pressure degrading serving latency | Not reached: metering costs ~11 ms; no batching needed |
| **0021** | A capability whose quantity is not `(unit, amount)` | Not reached: six fake capabilities fit |
| **0021** | Regulatory requirement to physically delete history | Not reached |
| **0022** admission | A single request consuming a meaningful fraction of a period → reserve/settle | Not reached; seam named |
| **0022** | Overshoot exceeding the predicted bound | Not reached: measured within bound |
| **0022** | Redis outages harmful enough to revisit fail-open | **Amended, not reversed**: the breaker made fail-open cheap; posture unchanged |
| **0022** | Two models under one capability with different cost profiles | Not reached — but M5 makes it plausible; watch it |
| **0023** pricing | First customer-specific negotiated price → price book to the database | Not reached |
| **0023** | Pricing experiments frequent enough that deploy friction shapes decisions | Not reached (prices internal, F3) |
| **0023** | Multi-currency or tax obligation | Not reached; currency code already carried |
| **0024** idempotency | Customers asking for at-most-once *compute* | Not reached |
| **0024** | A capability whose responses are neither small JSON nor replayable binaries | **Approaching**: streaming (M8) must declare its replay semantics before it ships |
| **0013** authorization | M4 metering wanting key-class distinctions → scopes | **Resolved without scopes**: usage origin is commercial, not permissional. The pass-through stage stays a pass-through |
| **0006** jobs | Job insert rate approaching ~1k/min | Not reached |
| **0018** serving | — | Untouched; capacity backpressure stayed in the runtime |

**All four M4 ADRs hold.** ADR-0022 was amended by measurement (the
breaker) rather than reversed. ADR-0013's open question is now closed.

## 8. Definition of Done

| # | Criterion | Status |
|---|---|---|
| 1 | Every request authenticated → authorized → metered → rate limited → served → accounted | ✅ |
| 2 | Usage is an append-only ledger, money-free, capability-agnostic | ✅ |
| 3 | Admission control structural, atomic, fail-open and cheap | ✅ |
| 4 | Entitlements: quota, spend limits, free tier from day one | ✅ |
| 5 | Pricing: versioned, pure, reproducible, historically correct | ✅ |
| 6 | Commercial identity survives every internal replacement | ✅ 8 realities, negative control |
| 7 | Production validated: reconciliation, anomalies, recovery, baseline | ✅ |
| 8 | `runtime-contract`, `runtime-core`, STT, TTS unchanged; public APIs preserved | ✅ zero diff |
| 9 | All founder decisions F1–F8 ruled and applied | ✅ |
| 10 | PRD v0.8, ARCHITECTURE v0.5, version 0.5.0 | ✅ |

## 9. Verdict

Milestone 4 delivered the commercial spine: a permanent ledger, admission
control that protects without lying, entitlements derived from facts, and
pricing that can be explained years later. It did so **without changing a
single line of the inference plane** — which was the milestone's real
thesis, and is now measured rather than asserted.

The platform can now charge for what it serves. It cannot yet *bill* —
invoices, payments, and credits remain deliberate non-goals — but every
input those need is recorded, immutable, and reproducible.

**The most valuable output is not the code.** It is twelve executable
laws about where commercial truth lives, each with a test that fails when
it is violated, and a milestone's worth of assumptions that measurement
corrected.
