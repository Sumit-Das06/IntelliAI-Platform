# ADR-0027: The Language Support Ladder and the three state machines

- **Status:** Accepted
- **Date:** 2026-08-04
- **Related:** ADR-0005, ADR-0017, ADR-0021, ADR-0025, ADR-0026

## Context

The Core Speech Language Policy promises English, Hindi, and Arabic as
first-class product languages. The platform has no vocabulary for what
"support" means: the incumbent STT model will transcribe Arabic today
with no corpus, no baseline, and no quality claim ever measured — and
nothing in the system knows it is happening. The Research Framework
defines the evidence bar (§7.1: corpus + quality baseline + production
benchmark per language) but the platform cannot represent the states
between "promised" and "refused."

Meanwhile three different kinds of status were at risk of collapsing
into one enum: whether an artifact is ready (MODEL_IDENTITY's ML
lifecycle), whether a binding carries traffic (Registry V2's planned
shadow/canary/production), and what we tell customers about a language.

## Problem

What may the platform truthfully say about a (public model, language)
pair, where is that said, and how does it stay distinct from artifact
readiness and traffic staging as both evolve?

## Decision

**We will give every (public model, language) pair an explicit status
from a three-rung ladder, held in the registry, and keep it strictly
orthogonal to the other two state machines.**

1. **The ladder.** `supported` — a product promise, requiring the
   evidence triple (corpus, committed quality baseline, production
   benchmark) for that (artifact, build, language), a license verdict
   covering the language-specific serving path, and a promotion record.
   `available` — served best-effort and honestly labeled, explicitly not
   promised; this is the customer-preview state **and the entry rung
   (Amendment 1)**. `unavailable` — refused with a clear error naming what is
   supported, and the refusal recorded as demand evidence; never
   silently served badly.
2. **Exhaustive by construction.** The ladder is a vocabulary of stances
   toward a customer, and exactly three stances exist: promise, honest
   no-promise, no service. Deliberately no fourth rung: "experimental"
   already has three homes — the MODEL_IDENTITY `experimental` purpose
   flag (never routable), the usage-origin taxonomy for internal traffic
   (metered, never rated), and the reserved `shadow` binding stage for
   unproven artifacts behind the real API. A ladder rung would be a
   fourth source of truth for the same fact.
3. **The three state machines**, orthogonal, with disjoint owners:
   artifact lifecycle (is the implementation ready — MODEL_IDENTITY);
   binding stage (how much traffic does this binding carry —
   `shadow`/`canary`/`production`, **reserved for Registry V2**, fixed
   at `production` in M5, living on the route binding); language promise
   (what we tell the customer — this ladder). A canary of a supported
   language and a production binding of a merely-available one must both
   be expressible; entangling the machines forecloses both.
4. **Transitions are promotions.** Ladder movements carry evidence per
   rung: enablement is an absolute bar (good enough to promise, F-M5-3);
   replacement behind a route is a relative bar (per-language switching
   test including code-mixed, plus the commercial continuity
   fingerprint); voice rebinding adds listening evidence. Composition
   refuses a `supported` status without its evidence references.
5. **Shadow billing is already decided.** When V2 activates stages, the
   M4 Request Identity Invariant answers the duplicated-inference
   question: one customer request, one billable event — the production
   binding's. Shadow and canary passes are our cost.

## Alternatives considered

- **A boolean per language** — rejected: `true` for Arabic claims a bar
  nobody measured; `false` refuses traffic the incumbent genuinely
  handles, destroying exactly the demand evidence the Language Policy
  needs.
- **An `experimental` rung** — rejected as a fourth home for a
  triply-homed fact (see Decision 2); divergent sources of truth for
  experiment status is the five-year failure mode.
- **Status inferred from engine model cards** — rejected: a card's
  language list is a claim, not evidence (Research Framework §2); the
  incumbent claims ~100 languages, the platform promises three.
- **Ladder status in the runtime or in documentation alone** — rejected:
  runtimes are temporary and promises are permanent; a promise the code
  cannot check is a promise the code will break. The registry is the
  resolution authority for product identity.
- **One combined status enum across readiness, staging, and promise** —
  rejected: it cannot express the orthogonal combinations that real
  operations need, and every platform that builds it ends up unable to
  canary a supported language.

## Trade-offs

- The middle rung admits publicly that some languages are unpromised;
  accepted — honesty about quality is the brand position, and the
  alternative is silent unmeasured serving.
- Three machines are more concepts to hold than one enum; accepted,
  because the concepts are genuinely independent and the prose cost now
  prevents the redesign cost later.
- Refusing `unavailable` languages turns away servable traffic if the
  founder scopes the ladder tightly; mitigated by the `available` rung
  and by recording every refusal as demand evidence.

## Consequences

- "Which languages does `intelliai-stt` support, at what quality?"
  becomes a registry query with evidence behind every answer, and the
  public documentation's source of truth.
- Language enablement, engine replacement, and voice rebinding all
  become the same shape: evidence → reviewed diff → validation →
  continuity proof.
- The Language Policy becomes measurable: adoption analytics (M4) per
  rung, demand evidence from refusals, and the Arabic thread honestly
  represented as `available`-at-best until its corpus exists (F-M5-6).
- Registry V2 activates the reserved stage machine without touching the
  ladder or the artifact lifecycle.

## Amendments

**Amendment 1 — the ladder is a lifecycle (2026-08-04, founder decision
F-M5-1).** Amends Decision 1 and extends Decision 4; the ADR's core
decision — three rungs, three orthogonal machines — is unchanged, so
this is an amendment rather than a supersession.

> A new language always enters the platform as `available`. Promotion to
> `supported` requires a completed benchmark, evaluation evidence, a
> production baseline, and explicit founder approval. No language may
> skip this lifecycle.

Two consequences. First, `available` requires **no** evidence: the
original wording ("measured at least once") is withdrawn, because at
entry nothing has been measured yet and requiring evidence to begin
measuring is circular. Second, the prohibition on skipping needs no
state machine — a production baseline is unobtainable without having
served, so the top rung's bar structurally forbids the jump. Demotion
and withdrawal remain ungated: honesty may always be increased.

**Amendment 3 — the corpus precondition (2026-08-05, founder ruling
after M5 step 4).** Extends Decision 1's evidence requirement for
`supported` and Decision 4's promotion bar.

> A language cannot advance beyond `available` unless IntelliAI owns —
> or has formally adopted — a versioned evaluation dataset for that
> language. Evidence quality is bounded by dataset quality, so promotion
> requires both: benchmark evidence, and a versioned evaluation corpus.

Step 4 found the gap by walking into it: a benchmark can be run against
anything, and a technically valid evidence triple can be produced on a
slice containing no speech in the language being promoted — a number that
is real, reproducible, and about nothing. Ownership is recorded rather
than assumed, because an adopted third-party corpus carries its licence
into every promotion that ever cites it.

**Amendment 2 — the initial ladder (2026-08-04, founder decision
F-M5-2).** STT: English `supported`, Hindi `available`, Arabic
`available`. TTS: English `supported`, Hindi and Arabic `unavailable`.
The accompanying rule — *the ladder reflects measured product evidence,
not theoretical engine capability; a model claiming support does not
automatically promote the product* — restates Decision 1's rejection of
model-card inference as a standing policy rather than a one-time
alternative considered.

## Future review criteria

- A customer stance genuinely outside promise/no-promise/no-service —
  none is currently conceivable; any proposal must first show it is not
  artifact lifecycle or binding staging in disguise.
- Registry V2's stage activation → verify the shadow-billing rule
  (Decision 5) holds in implementation.
- The first `available` language generating significant revenue-bearing
  traffic → founder review of whether the rung's honesty labeling is
  sufficient, or promotion pressure should raise it to `supported`.
