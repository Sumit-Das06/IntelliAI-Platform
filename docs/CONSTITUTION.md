# The IntelliAI Constitution

| | |
|---|---|
| **Status** | In force — adopted at Milestone 1.5 close (2026-07-31) |
| **Authority** | The highest-level document in this repository. Every strategy document, architecture decision, milestone, and line of code answers to it. Where any other document conflicts with this one, this one wins — or is formally amended. |
| **Amendment discipline** | Principles are superseded by recorded decision, never edited in place and never silently ignored. An amendment states what changed, why, and what evidence forced it — the same discipline as ADRs. A principle that is being routinely bypassed must be either enforced or amended; a bypassed constitution is worse than none. |
| **Durability requirement** | Every principle here is technology-, model-, hardware-, and framework-independent. Nothing below names a vendor, a model, an engine, or a format. A reader in 2040 should still agree — or amend, on the record. |

## Hierarchy of law

```
CONSTITUTION (this document)            — the charter
 ├─ AI_STRATEGY.md §7                   — AI & data law (flywheel, consent, lifecycle)
 ├─ MODEL_IDENTITY.md §9                — identity statutes (what a model IS)
 ├─ REGISTRY_V2.md §12                  — registry law (the control plane)
 ├─ FINE_TUNING_STRATEGY.md Part 10     — training law (the ladder)
 └─ engineering handbooks & ADRs        — working law (how code is built)
```

Domain constitutions elaborate; they may never contradict. New domain law
is admitted the way everything here was: written, reviewed, adopted on the
record.

## The Twenty Principles

### Identity & promises

**1. The contract is the product.** Everything behind a promise is
replaceable — models, engines, hardware, providers; the promise is not.
Customers integrate names and behaviors we own; nothing they can couple
to may belong to anyone else.

**2. Customers see promises; engineering sees truth; exactly one bridge
connects them.** Product identity and engineering identity meet at a
single, owned, recorded join — routing — and nowhere else. This is what
keeps improvement silent and change safe.

**3. One name, one meaning, forever.** Names given to customers are
never reused and never change meaning. Retirement reserves a name
permanently.

**4. Improvements ship silently; degradations ship loudly; rollback is
boring.** Quality moves up without ceremony, down only with warning and
consent, and backward by a cheap, rehearsed, unremarkable act. If
rollback is frightening, the system is wrong.

### Rights & trust

**5. No rights, no use.** No license clarity → no serving. No consent →
no data. No provenance → no training. Rights are verified before use,
recorded with evidence, and computed through derivation — never assumed
at the family, vendor, or reputation level.

**6. Customer data is customer data.** Never assumed to be training
data; consent is explicit, scoped, recorded, and revocable-forward —
even for a customer's own model. Defaults protect the customer even when
inconvenient.

**7. Trust is architecture.** Whatever the company claims about privacy,
isolation, honesty, or safety must be enforced by structure — a gate, a
boundary, a refusal in software — not by policy documents. What cannot
be enforced may not be claimed.

**8. The platform must not be able to tell whose model it serves.** Its
own, a customer's, an upstream's: same identity machinery, same gates,
same rigor, same record. Uniform treatment is both the safety property
and the product.

### Evidence & quality

**9. Talk to customers, then serve, then measure, then train — in that
order, forever.** Distribution and evaluation precede training;
conversation precedes conviction. Nothing is improved that has not been
measured; nothing is measured that no one needs.

**10. No evaluation, no promotion; no regression, no release.** Every
promotion cites current evidence against the incumbent. "Passed our
tests" and "trusted with customer traffic" are separate, separately
auditable facts.

**11. Honest benchmarks or none.** Internal evaluations are private and
rotating; public claims are reproducible; the two never mix. Quality
claims are published measurements, not adjectives.

**12. Strategy bends to measurement; principles do not bend to
convenience.** When evidence contradicts the plan, the plan moves. When
convenience contradicts a principle, the principle holds — or is amended
on the record. Knowing which is which is leadership's entire job.

### Assets & records

**13. Records are immutable; infrastructure is disposable.** What
happened — lineage, verdicts, decisions, operations — is append-only and
kept forever; what runs is cattle, reconstructible from the record.
Change is birth, not mutation.

**14. Everything of value is reproducible from its record.** A model, a
build, a dataset, a decision: if it cannot be reconstructed from what
was written down, it does not get relied upon. The record is how the
company outlives any single memory.

**15. Models depreciate; data, evaluations, recipes, and trust
appreciate.** Investment follows the appreciating assets. Own names,
evidence, and data; rent everything else gladly.

### Capital & focus

**16. Capital compounds in lineages and wedges.** Investment
concentrates where accumulated work multiplies future work; novelty pays
the switching cost against the *invested* incumbent, never against a
strawman.

**17. Commodities ride upstream; the wedge gets the compounding.** Not
everything the platform serves deserves the company's scarce improvement
capital. Tiers are explicit decisions, reviewed — never accidents of
enthusiasm.

**18. Efficiency before scale; consolidation before expansion.** Make it
cheaper and simpler before making it bigger; sprawl — of models,
features, documents, or infrastructure — is a decision someone must
sign, not an entropy state.

### Conduct of the company

**19. Ceremony proportional to blast radius — and the right path must be
the easy path.** High-stakes acts carry evidence and approval;
routine acts stay cheap. Discipline that is harder than the shortcut
will lose to the shortcut; build the discipline into the easy path.

**20. Refuse well, decide on the record, and let research fail freely.**
What the company will not build is guarded as carefully as what it will.
Every consequential decision is written down with its alternatives and
superseded rather than erased. And research is free to fail outside
production — only graduation, with full rights and records, crosses the
boundary.

---

*Adopted 2026-07-31 at the close of Milestone 1.5, distilled from
[FOUNDING_STRATEGY.md](FOUNDING_STRATEGY.md) Part 11 and the domain
constitutions beneath it. Navigation for the full strategy stack:
[STRATEGY.md](STRATEGY.md).*
