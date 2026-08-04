# Promotion — the procedure

Promotion is where every plane meets. The one-way causal chain becomes an
operating procedure here:

```
                    ┌──────────────────┐
                    │    EVALUATION    │   measures a slice against the
                    └────────┬─────────┘   artifact the registry resolved
                             │             → an immutable evidence record
                             ▼
                    ┌──────────────────┐
                    │  SWITCHING TEST  │   compares two records
                    └────────┬─────────┘   → BLOCKED | REFUSED | TRADE | PASSED
                             │
                             ▼
                    ┌──────────────────┐
                    │ PROMOTION VERDICT│   a computed opinion, with findings
                    └────────┬─────────┘   ── it changes NOTHING ──
                             │
                             ▼
                    ┌──────────────────┐
                    │   HUMAN REVIEW   │   reads the findings, weighs a trade,
                    └────────┬─────────┘   approves — or does not
                             │
                             ▼
                    ┌──────────────────┐
                    │  REGISTRY DIFF   │   one reviewed change, citing its
                    └────────┬─────────┘   evidence — the diff IS the record
                             │
                             ▼
                    ┌──────────────────┐
                    │ SERVING CHANGES  │   the next request resolves differently
                    └──────────────────┘
```

**Read the third box carefully. The switching test never promotes
anything.** It ends at a verdict; every arrow below it is a human act or
a consequence of one. There is no path from a passing verdict to a
serving change that does not go through a person and a diff — which is
also why there is no arrow pointing back up: an evaluation cannot cause
its own adoption, and serving state cannot alter the record of what was
measured.

Nothing in this document reverses that arrow. The evaluation plane
produces evidence and computes verdicts; a human decides; the decision
becomes a diff; the diff changes registry state; registry state changes
what serves. **The evaluation system never promotes anything**, and the
registry never consults an evaluation at request time.

## The three classes

They exist separately because they answer different questions, and a bar
that answers the wrong question is worse than no bar.

| Class | Question | Bar | Checked by |
|---|---|---|---|
| **Language enablement** — a ladder rung moves | Is this good enough to *promise*? | **Absolute** | `enablement_test()` |
| **Route replacement** — artifact A → B behind one route | Is B *at least as good as* A? | **Relative** | `switching_test()` |
| **Voice rebinding** — a voice's artifact changes | Does it still *sound like* the voice? | Relative **+ listening evidence** | `switching_test()` + the M2.5 listening protocol (F-M5-4) |

## The procedure (Registry V1.5)

1. **Measure.** Run the slice against the artifact the registry resolved
   for it. One run per (public model, language, artifact, build, corpus
   version) — the evaluation identity. Records are committed and never
   edited.
2. **Compute the verdict.** `switching_test` for a replacement,
   `enablement_test` for a rung. Both refuse to guess: a comparison
   across corpus versions, languages, judges, or clip sets is `BLOCKED`,
   not lost.
3. **Read the findings.** `PASSED` may proceed. `TRADE` means the
   aggregate held while something underneath moved — a human writes down
   why that is acceptable, in the diff. `REFUSED` and `BLOCKED` stop.
4. **Founder approval.** Absolute bars are a founder decision (F-M5-3);
   the enablement test refuses when no bar has been set, because a
   promise cannot be checked against a threshold nobody chose.
5. *[Reserved: shadow → canary. Registry V2 inserts here — the binding
   stage machine (ADR-0027) is fixed at `production` until then.]*
6. **One reviewed diff** to the catalog, citing its evidence by name.
   **The diff is the promotion record**; git is the audit trail.
7. **Composition validates.** A `supported` route without its citations
   fails the build; citations that do not resolve fail CI
   (`test_evidential_chain.py`).
8. **Continuity proof.** The commercial fingerprint must be identical per
   route — routing changes which artifact serves and nothing commercial.

## Preconditions that are not thresholds

- **The corpus precondition** (ADR-0027 Amendment 3). No language passes
  `available` without a versioned evaluation dataset IntelliAI owns or
  has formally adopted, containing natural speech in that language.
  Evidence quality is bounded by dataset quality; a corpus with no
  material in the promoted language cannot support a promise however
  good the numbers look. Checked before any threshold, and reported as
  `BLOCKED` rather than `REFUSED`, because it is not a close call.
- **The lifecycle** (F-M5-1). A language enters at `available` and
  reaches `supported` only through evidence that `available` service
  makes possible. Unskippable by construction: a production baseline is
  unobtainable without having served.
- **Comparability.** A switching test needs the same slice, the same
  corpus version, the same judge, and the same clips. Anything else is a
  category error with a plausible-looking delta.

## Rollback is a revert, not a promotion

Reverting a route needs **no new evidence and no new bar**. The
predecessor artifact still exists (immutable and retained,
MODEL_IDENTITY P8), its baseline still stands, and the evidence that
justified it never expired.

This is not a loophole — it is the payoff of routing-as-registry-state,
and it is why running the switching test *backwards* over a rollback is
meaningless: the demonstration in
[2026-08-05-promotion-rollback.md](../../docs/benchmarks/2026-08-05-promotion-rollback.md)
shows that direction returning `REFUSED`, which is correct and irrelevant.
A rollback restores a state that was already justified.

## What the evaluation plane may never do

- Promote, demote, or change any registry record.
- Decide a trade. It surfaces one; a human accepts it in writing.
- Fall back. An unrouted language or an unserved rung has nothing to
  evaluate, and substituting another artifact would be routing.
- Compare across corpus versions, judges, or languages.
