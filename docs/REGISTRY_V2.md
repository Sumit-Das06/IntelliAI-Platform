# IntelliAI Registry V2 — Control-Plane Architecture

| | |
|---|---|
| **Status** | IN FORCE — approved 2026-07-31 (M1.5 D5); **domain constitution** under [CONSTITUTION.md](CONSTITUTION.md) (§12 here is registry law) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Role of this document** | The architecture of the Registry: the control plane through which every model identity, gate, binding, promotion, rollback, and customer-owned artifact passes. Implements [MODEL_IDENTITY.md](MODEL_IDENTITY.md) (v0.2); governed by [AI_STRATEGY.md](AI_STRATEGY.md); inherits requirements from [FOUNDATION_MODELS.md](FOUNDATION_MODELS.md) §15. **Conceptual only — no schemas, no endpoints, no code.** Registry V1 (M2's code-declarative routing table) is this architecture's deliberately-small seed, already shaped to grow into it. |

---

## 1. What is a Registry?

Concept before architecture. Three old institutions, combined, describe it
exactly:

- **A land registry.** The authoritative record of what exists and who
  owns it. Possession (a weights file on a disk) is not ownership; the
  record is. If the registry doesn't know an artifact, that artifact does
  not exist in production — no matter what is sitting on a server.
- **DNS.** The resolution system between stable names and changing
  locations. Customers hold names (`intelliai-stt`); the registry resolves
  them — per request, fast, cached — to whatever deployment currently
  fulfills them. And like DNS, resolution keeps working even when the
  authority having a bad day; the *record* being briefly unavailable must
  never stop the *serving*.
- **A court record.** Append-only, attributed, and consulted when it
  matters most: Which weights served this customer on March 3rd? Under
  what license? Gated by which evaluation? Who promoted it, and when was
  it rolled back? Every one of those questions has a billing dispute, an
  audit, or an incident review attached to it eventually.

So: **the Registry is the platform's authoritative memory of model
identity, the enforcer of its admission gates, and the resolver of its
names — and it is none of the things around it**: not the model storage,
not the metrics system, not the billing engine, not the deployment
executor. It records, gates, and resolves. Everything else acts.

## 2. Why Registry V2 is the heart of IntelliAI

Every strategic promise this platform has made lands, mechanically, in the
registry:

| Promise (source) | The registry mechanism that keeps it |
|---|---|
| Engines swap invisibly (ADR-0003) | routing bindings — swap = binding change |
| No license verdict, no traffic (P4) | admission gate on artifacts, per version |
| No evaluation, no promotion (P5) | lifecycle transition gate |
| Rollback is a routing change (P8) | bindings + retained superseded artifacts |
| Product/ML lifecycles independent (P9) | the binding is their only join |
| Customers see one identity layer (identity rule 12) | resolution translates public names → engineering objects, one way |
| Fine-tuning as a product (P2/P5 roadmap) | org-owned artifacts with the same identity machinery |
| "What served you, exactly?" (auditability) | point-in-time record of bindings + deployments |

Without a registry these are policies in documents. With it they are
refusals in software. That is the difference between a platform that
*intends* its constitution and one that *enforces* it — and it is why
every runtime service, evaluation pipeline, deployment, promotion,
fine-tuning job, and future IntelliAI foundation model passes through it.

**Problems it solves, concretely:** name-to-model resolution at request
time; structural enforcement of license/evaluation/reproducibility gates;
lineage and audit answers in one query; safe promotion and boring
rollback; multi-tenant model catalogs (ours + each org's); preventing
identity drift between what product sells, what ML built, and what ops
runs.

## 3. The two planes — record and resolution

The registry has two faces with opposite engineering requirements, and
recognizing this early prevents the classic failure (one system trying to
be both a ledger and a hot path):

- **The Record Plane** — the authority. Slow-changing, transactional,
  validated, attributed, append-only in spirit. Every mutation is a
  **named operation** ("register artifact," "record evaluation verdict,"
  "propose promotion," "flip binding," "begin deprecation") that either
  passes all gates or is refused whole. Nothing edits records raw; the
  operation log *is* the audit trail.
- **The Resolution Plane** — the hot path. Read-only, cache-shaped,
  consulted on every inference request (public model + request attributes
  → deployment). It serves from validated **snapshots** of the record
  plane and keeps serving the last-known-good snapshot if the record
  plane is unavailable. Staleness is bounded and explicit — the same
  design honesty as M1's throttled `last_used_at`: we choose a small,
  stated lag over a hard runtime dependency.

**Intent vs. observation — the third distinction.** The registry stores
*intended* state: "this build should be deployed as prod-eu, canary at
5%." What is *actually* running is observed by operations (health checks,
the deployment executor). The two are reconciled continuously, and
**disagreement is an alarm, never a merge** — the registry does not
"update itself to match reality," because a record that follows reality
cannot be an authority over it.

## 4. What belongs in the Registry — and what does not

**The admission test.** A concept earns a place in the registry only if
it passes all three:

1. **Reference test** — other systems must durably reference it by
   identity (route to it, bill against it, audit it).
2. **Policy test** — it carries rules the platform must *enforce*
   (gates, tenancy, lifecycle), not merely display.
3. **Audit test** — its history must be reconstructible years later.

Every admission is recorded as an ADR. Failing the test is not exile —
it is placement:

| Explicitly NOT in the registry | Where it lives instead | Registry keeps only |
|---|---|---|
| Weights bytes | object storage | content hash + location reference |
| Live metrics, latencies, health | observability stack (M10) | nothing (intent only) |
| Request/usage logs | logging + usage events (M4) | identity fields those events cite |
| Prices, invoices, plans | billing catalog (M4+) | the public-model + usage-unit IDs billing references |
| Customer identity, keys, orgs | identity system (M1) | owner references (org IDs) |
| Training code, recipes | git | commit hashes in lineage records |
| Raw evaluation outputs | evaluation system (M9) | result summaries + verdicts by reference |
| Prompt/pipeline recipe contents | composite pipeline system (P3/P4, reserved) | recipe-version references, when they exist |
| Engine tuning knobs (beam size, worker counts) | service deployment config | nothing — configuration is not identity |
| Experiments, hypotheses, failed runs | experiment tracking (research side) | only what graduates: registered artifacts |

The registry that stores everything becomes the registry no one can
change safely. Refusing content is a feature.

## 5. The seven information classes

Everything inside the registry belongs to exactly one class, each with
its own mutability rule:

| Class | Examples | Mutability |
|---|---|---|
| **Identity** | artifact IDs, lineage DAG, public model names, capability bindings | Immutable, forever; append-only growth |
| **Metadata** | dossiers, family portfolio assessments, research notes | Freely editable knowledge — advisory, never behavioral |
| **Configuration** | routing policies, canary percentages, snapshot aliases | Versioned; every change is an operation; old versions retained |
| **Runtime state** | *none* — intent only (§3) | n/a — observed state lives in ops |
| **Deployment state** | declared deployments, their purpose/region/composition | Mutable through operations; disposable records |
| **Evaluation history** | verdict summaries per (artifact, build, suite version) | Append-only; never edited, never deleted |
| **Business ownership** | owner org per artifact, dedicated-deployment grants, consent evidence references | Changes only by recorded, consented operations (identity rule 10) |

The class determines the rule; arguments about "can we change X?" reduce
to "which class is X?" — which is the point.

## 6. Ownership and access

Who may write which registry domain, and who reads it (R = read,
O = owns/writes through operations):

| Registry domain | Product | Platform Eng | ML Eng | Research | Ops | Customer Org | Gateway | Runtime |
|---|---|---|---|---|---|---|---|---|
| Capabilities & contracts refs | R | **O** | R | R | R | — | R | R |
| Public models & lifecycle | **O** | R | R | — | R | R (catalog) | R | — |
| Routing policies & bindings | co-**O** (targets/tiers) | R | co-**O** (promotions) | — | R | R (own aliases) | R (hot path) | — |
| Foundation dossiers & families | R | R | **O** | R+propose | — | — | — | — |
| Artifacts & lineage | R | R | **O** (platform-owned) | propose→graduate | R | **O** (org-owned, via products) | R | R (own assignment) |
| Builds | R | **O** | R | — | R | — | R | R (own) |
| Deployments (declared) | R | **O** | propose | — | **O** (execute/reconcile) | R (dedicated) | R | R (own) |
| Evaluation verdicts | R | R | **O** (via eval system) | R | — | R (own artifacts) | — | — |
| Ownership & grants | R | R | R | — | — | **O** (own objects, consented ops) | — | — |

Three boundary rules the matrix encodes:

1. **The data plane never writes.** Gateway and runtimes are pure readers
   (the runtime reads only its own assignment and reports identity back
   through responses — reporting is not writing).
2. **Research proposes; graduation writes.** Nothing crosses from
   `research/` into the registry except through the artifact-registration
   operation with full birth requirements (identity rule 5).
3. **Customer orgs write only through products.** An org never touches
   registry operations directly; fine-tuning and voice-cloning products
   perform the operations on their behalf, inside their tenancy scope —
   and cross-tenant resolution is 404, exactly as in M1.

## 7. Interaction contracts

How each platform component relates to the registry — each contract
deliberately thin:

- **Runtime services** read their assignment (which artifact(s), build,
  deployment descriptor — including adapter compositions) at startup, and
  report that identity in every response envelope. They never resolve
  public models, never see routing, never write. (M2's `/info` endpoint
  is this contract's first half, already designed.)
- **The gateway** consults the resolution plane per request: (public
  model, request attributes: language, tier, region, org) → deployment.
  It writes nothing; attribution events it emits *cite* registry
  identities (§4 table).
- **Evaluation** reads what to test (evaluation candidates and their
  builds), runs outside the registry, and records verdict summaries
  through an operation. The registry *enforces the presence* of verdicts
  at gates; it never computes quality itself.
- **Training / fine-tuning jobs** (platform or product-triggered) read
  parent artifacts and dataset-version references, run in the jobs system
  (M5 machinery), and end — successfully — with exactly one registry
  effect: the artifact-registration operation, with lineage, computed
  license verdict, and reproducibility record attached at birth. A
  training run that cannot register its output did not succeed.
- **The deployment system** reads builds and intended deployments,
  materializes them in infrastructure, and reports observations for
  reconciliation. It executes intent; it does not define it.
- **Public models (Product)** are created, priced (by reference),
  tiered, deprecated, and retired through loud, human-approved
  operations — the platform lifecycle's ceremony lives here, including
  the ≥6-month deprecation clocks and snapshot-alias sunsets.
- **Customer-owned models** are org-owned artifacts (identity §8) — the
  registry gives them the same lineage, gates, and lifecycle as
  platform artifacts, plus tenancy: visible only in their org's catalog,
  routable only by their org's traffic, transferable only by consented
  operation.
- **Routing policies** are versioned configuration owned jointly:
  Product decides *what may be targeted* (tiers, snapshots, regions), ML
  decides *what wins* (promotions after gates), and every change
  produces a new policy version so "what routed where at time T" is
  always answerable.
- **Billing** never lives in the registry — but it cannot exist without
  it: the billing catalog prices public-model usage units, and every
  usage event cites registry identities (public model, artifact, build,
  deployment) so cost, margin, and disputes resolve against the same
  record. Registry → billing is a one-way reference.
- **Future fine-tuning products** are the composition of contracts
  already listed: a product front-end + jobs system + artifact
  registration under org ownership + optional dedicated deployments. The
  registry needs nothing new for them — which is the strongest sign the
  architecture is right.

## 8. The lifecycle of information

One narrative from idea to archive, entirely in registry terms:

```
RESEARCH            outside the registry (experiment tracking, research/)
   │ graduation: artifact-registration operation
   ▼
IMPORTED FOUNDATION artifact (derivation: imported) under a dossier —
   │                hash-pinned, license verdict verified at THIS version
   ▼ fine-tune / adapter / merge / distill (jobs system)
ARTIFACT            born with lineage + owner + verdict + reproducibility
   │ offline gates: evaluation vs incumbent · license · reproducibility
   ▼
EVALUATION          passed the offline gates; now trusted with LIVE
CANDIDATE           validation: shadow (duplicated traffic, discarded
   │                responses) then canary (small routed %) — both are
   │                deployments + routing weights, artifact stays candidate
   ▼ promotion operation: binding flip (the ONLY product↔ML join)
PRODUCTION          serving under one or more public models
   │ a descendant wins the same gates
   ▼
SUPERSEDED          no longer bound, still warm through the bake window,
   │                permanently eligible for rollback repointing
   ▼ retention policy
ARCHIVED            weights storage may be reclaimed; identity, lineage,
                    verdicts, and operation history are kept forever
```

**Promotion, conceptually:** a proposal operation names the candidate,
the target binding, and the evidence (verdict references). The registry
checks the gates — current license verdict, evaluation-vs-incumbent on
the current suite version, complete reproducibility record, owner and
tenancy validity — and either refuses or records the transition and the
new routing-policy version. Promotion is therefore *evidence-carrying and
replayable*: years later, the record shows exactly why this artifact was
trusted.

**Rollback, conceptually:** a repoint operation to the still-existing
predecessor binding — no rebuild, no re-provision, no gate re-run (the
predecessor's evidence is already on record). Rollback is cheap because
supersession never deletes; it is *boring* because it is the same
operation type as promotion, just pointing backward.

## 9. Immutable vs. evolving

| Immutable, forever | Evolving, freely (through operations) |
|---|---|
| Artifact identity, lineage, birth records | Lifecycle states (forward transitions, gated) |
| Public model names and their meaning-category | Routing policies (versioned), pricing references |
| License verdicts as recorded (superseded by new verdicts, never edited) | Dossiers, family portfolio assessments, notes |
| Evaluation verdicts as recorded | Which builds/deployments exist |
| The operation log itself | Snapshot aliases (bounded by sunset dates) |
| Retired names (never reused) | Reconciliation targets, canary percentages |

## 10. Reserved architectural space

Named now, designed later — so V2's shape leaves room instead of painting
over it. For each: its relationship to the registry, and where it lives.

1. **Evaluation Identity** (MODEL_IDENTITY §11): sibling system; registry
   holds verdict summaries + references. Designed at M9.
2. **Dataset Registry** (AI_STRATEGY §2): sibling with the same
   immutability discipline; artifacts cite dataset-version IDs; license
   verdicts compute through those citations. Designed at first serious
   training (P2).
3. **Experiment Tracking**: research-side, never registry content; the
   only crossing is graduation (§6 rule 2). Tooling choice is free
   (including off-the-shelf) precisely because it is outside.
4. **Feature Store**: far-future (no tabular-ML roadmap today); name
   reserved so that if structured-data capabilities ever pass the
   capability admission test, their data plumbing has a designated home
   outside the registry.
5. **Fine-tuning Jobs**: jobs system (M5) executes; registry sees only
   registered outputs. Product layer arrives P2/P5.
6. **Voice Cloning**: org-owned adapter artifacts + consent evidence
   references (identity §4/§8); the consent *ceremony* is a product flow,
   the consent *evidence reference* is registry business ownership.
7. **Customer-owned Artifacts**: fully designed in identity §8; V2 must
   implement tenancy scoping from its first version — bolting tenancy
   onto a registry later is the M1 lesson inverted.
8. **External Providers**: weights-less imported artifacts under provider
   dossiers (identity §10.3); deployments are adapter services; the
   registry treats them identically — indistinguishability is the point
   (ADR-0003).
9. **Model Marketplace** (future, if ever): would enter as recorded
   cross-org grants on artifacts — an extension of business ownership,
   not a new identity layer. Explicitly out of the five-year design;
   reserved so nobody invents a parallel sharing mechanism.

## 11. Rejected alternatives

- **Adopt an off-the-shelf model registry (MLflow, W&B, HF private
  hub).** Rejected as *the* registry: they model experiments and model
  files, not public-model contracts, routing, tenancy, license gates, or
  customer-owned artifacts — the parts that make this a *platform*
  control plane. They remain candidates for the experiment-tracking
  sibling, where their strengths actually lie.
- **Stay code-declarative forever (Registry V1 scaled up).** Rejected:
  code-as-registry cannot express org-owned artifacts written at product
  runtime, tenancy-scoped catalogs, or operation-level audit. V1 is
  correct *now* because every entry is platform-owned and
  reviewer-approvable; the moment customers own artifacts, the registry
  must be a running authority. (V1's lookup interface was designed for
  exactly this swap.)
- **Event-source everything as the storage model.** The *concept* —
  named operations forming an append-only log — is adopted (§3). Whether
  storage is an event log, versioned rows, or both is an implementation
  decision deliberately left open; concepts must not smuggle in storage
  tech.
- **Per-capability registries.** Rejected: fragmenting identity
  re-creates family-level trust assumptions, breaks cross-capability
  artifacts (multimodal, identity v0.2), and turns "single source of
  truth" into N sources with reconciliation debt.
- **Registry as an active orchestrator (calling deployers, triggering
  evals).** Rejected: an authority that acts develops opinions about
  execution and becomes unavailable when its dependencies are. The
  registry records intent and answers questions; actors act. (One
  deliberate consequence: something else watches for intent/observation
  drift — that something is ops tooling, not the registry.)

## 12. The Registry Constitution (permanent laws)

1. **If the registry doesn't know it, production doesn't serve it** — no
   side channels, no hardcoded model references, no temporary URLs.
2. **The registry records, gates, and resolves; it never executes.**
   Deployers deploy, evaluators evaluate, billers bill — citing the
   registry.
3. **Every write is a named, validated, attributed operation.** Raw
   edits do not exist; the operation log is the audit trail.
4. **Gates are refusals, not warnings** — license, evaluation, and
   reproducibility gates block transitions structurally; overrides are
   themselves recorded operations with named authors.
5. **Resolution survives the record plane.** Serving reads validated
   snapshots with bounded, stated staleness; a registry outage degrades
   freshness, never availability.
6. **The registry stores intent; operations observe reality;
   disagreement is an alarm, never a merge.**
7. **Identity content is append-only.** Archival reclaims weights
   storage, never records; names are never reused; verdicts are
   superseded, never edited.
8. **Product identity and engineering identity join only in routing
   bindings** — and every binding change produces a new, retained policy
   version.
9. **The registry is tenant-scoped from birth.** Org-owned entries are
   invisible outside their org; cross-tenant resolution is 404; customer
   writes happen only through products acting in-tenancy.
10. **The registry holds no opinions about quality.** It enforces the
    *presence and currency* of evaluation verdicts; it never computes
    them.
11. **Admission is by test and by ADR** (reference + policy + audit);
    what fails the test is placed elsewhere, explicitly.
12. **Advisory data has no behavioral role.** Families, dossiers, notes,
    and tags inform humans and portfolio reviews — never routing, gates,
    or verdicts.
13. **Every consumer goes through the registry's interfaces.** No other
    system reads its storage directly — the interface is the contract
    that lets storage evolve.
14. **Point-in-time answerability is a feature, not an accident:** "what
    served public model X at time T, under which policy version, with
    which verdicts" must always be reconstructible from the record.

## 13. Design principles

- **Declarative over imperative** — the registry says what should be;
  actors converge on it.
- **Boring availability** — the hot path is a cache of snapshots;
  everything clever lives on the slow path.
- **Ceremony proportional to blast radius** — artifact registration is
  routine; binding flips carry evidence; public-model lifecycle changes
  are loud and human-approved.
- **Policy as data, changes as code review** — routing policies are data,
  but their high-stakes transitions flow through the same
  approval discipline as code.
- **Small nouns, strong rules** — fewer object types with strict
  invariants beat rich schemas with soft ones.
- **Leave room, don't build rooms** — reserved spaces (§10) get names and
  boundaries now, design only when their milestone arrives.

## 14. Registry review checklist

Every future registry change answers these before merging:

1. Which of the seven information classes does this touch, and does it
   obey that class's mutability rule?
2. Does it pass the admission test, or does it belong in a sibling
   system? (Which one?)
3. Which constitution law is nearest to being bent? Why is it not?
4. Does it add a behavioral role to advisory data? (Automatic rejection.)
5. Can the hot path still serve from a stale snapshot during the change?
6. Is the change expressible as a named operation with an author and
   evidence?
7. Does it work identically for platform-owned and org-owned objects?
8. Would the answer to "what served traffic at time T" survive it?

## 15. Honest weaknesses

1. **A single point of coordination.** Everything passes through the
   registry — that is its value and its risk. Mitigations are laws 5 and
   2 (resolution survives; the registry never executes), but
   concentration of *change* remains: a bad operation design propagates
   platform-wide. The review checklist is the real defense.
2. **God-object gravity.** Every future feature will want "just one more
   field." The admission test and §4's placement table are the immune
   system; they only work if used every time.
3. **Bounded staleness is real staleness.** A revoked artifact or flipped
   binding takes seconds-to-minutes to reach all resolvers — the same
   trade M1 made for `last_used_at`, now with wider blast radius. The
   bound must be *stated, measured, and small*, and instant-kill (safety
   revocation) may need a priority invalidation path — flagged for
   implementation design.
4. **Reconciliation is delegated but essential.** The registry stores
   intent and refuses to watch reality (law 6, rejected orchestrator);
   if ops tooling doesn't actually reconcile, intent quietly rots. The
   dependency is architectural, not optional.
5. **Solo-operator ceremony cost.** Evidence-carrying operations and
   loud lifecycle ceremonies are designed for a team; today one person
   plays every role. The ceremony must be cheap enough to be real —
   otherwise it will be bypassed, and a bypassed constitution is worse
   than none. V2's implementation must make the right path the easy path.
6. **The composite-recipe gap** (identity §10.4) means early composites
   will version their pipelines outside the registry — an accepted,
   recorded inconsistency until the recipe-version concept lands.

## 16. Five-year scalability review

Scale the design must absorb: **thousands of artifacts × dozens of
capabilities × tens of builds each × org-owned long tail** (every
customer fine-tune and voice clone is an artifact).

- **Data volume is trivial** — even 10⁴ artifacts with full lineage is
  small data. The registry never stores weights, logs, or metrics (§4),
  so it never inherits their growth curves. The one genuinely growing
  table is evaluation verdicts — bounded by keeping raw outputs in the
  evaluation system and summaries here.
- **Read volume scales with request traffic**, not artifact count — and
  the resolution plane is a cache by design (law 5). Per-request
  resolution cost must stay O(policy lookup), independent of catalog
  size.
- **The real scaling risk is organizational**: operation review, gate
  maintenance, portfolio reviews across dozens of families. That is
  headcount and tooling, not architecture — and it is exactly what laws
  3, 11, and 12 keep manageable by keeping the object model small.
- **Tenancy scale** (thousands of orgs with private catalogs) rides on
  the M1 tenancy discipline already proven at the query layer.
- What would force redesign: real-time per-request *learned* routing
  (bandit-style model selection) — that would move routing from
  configuration to inference. If it ever comes, it enters as a *routing
  policy type* resolved by the same plane, not a new control plane.
  Recorded as the known frontier.

## 17. Definition of Done (for Registry V2, when implemented)

Registry V2 is done when — and only when — all of the following are true:

1. Every serving path resolves through it; the grep for hardcoded model
   references returns nothing (law 1, testable).
2. An artifact cannot be registered without owner, lineage, computed
   license verdict, and reproducibility record — enforced by refusal,
   proven by tests (identity rule 5).
3. A promotion without a current evaluation verdict is refused — proven
   by tests (law 4).
4. The gateway serves correctly with the record plane stopped (law 5 —
   demonstrated, not assumed).
5. "What served public model X at time T" is answerable by one recorded
   query path (law 14 — demonstrated on real history).
6. An org-owned artifact is invisible and unroutable outside its org —
   proven by the M1-style bidirectional tenancy tests (law 9).
7. Rollback of a production binding is performed live in under the
   stated bound, using only a repoint operation (P8 — rehearsed, timed).
8. Registry V1's consumers migrated without gateway code changes beyond
   the resolver swap (the V1 interface promise, kept).
9. Every concept implemented maps to this document or to a recorded
   admission ADR; nothing exists in the registry that this architecture
   cannot name.

---

*Change log:*
- *2026-07-31 — v0.1: initial control-plane architecture (M1.5 D5):
  record/resolution planes, intent-vs-observation, admission test and
  placement table, seven information classes, ownership matrix,
  interaction contracts, lifecycle with evaluation_candidate, reserved
  spaces, rejected alternatives, 14-law constitution, checklist,
  weaknesses, five-year review, definition of done. Pending approval.*
