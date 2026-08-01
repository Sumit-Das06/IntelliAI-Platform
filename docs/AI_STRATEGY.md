# IntelliAI AI Strategy — Strategy Principles & AI Constitution

| | |
|---|---|
| **Status** | IN FORCE — approved 2026-07-31 (M1.5 D1.5); **domain constitution** under [CONSTITUTION.md](CONSTITUTION.md) (§7 here is AI & data law) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Role of this document** | The constitution for AI-strategy decisions. [PRD.md](PRD.md) owns *what the product is*; [ARCHITECTURE.md](ARCHITECTURE.md) owns *how the system is shaped*; [adr/](adr/) owns *individual decisions*; this document owns *how IntelliAI relates to models and data over years*. Every future milestone — runtime, registry, fine-tuning, evaluation, deployment, billing, model management — is validated against §7 before it ships. Changes to §7 require the same discipline as ADR supersession: amend by recorded decision, never by silent edit. |

---

## 1. The IntelliAI Flywheel

IntelliAI's long-term plan is to evolve from *serving open foundation models
well* into *owning the models it serves*. That evolution is not a pivot; it is
a feedback loop that the platform is deliberately shaped to spin:

```
        ┌──────────────────────────────────────────────────────────┐
        │  (1) CUSTOMERS — integrate intelliai-* public models     │
        └───────┬───────────────────────────────────▲──────────────┘
                │ inference requests                │ (8) better quality,
                ▼                                   │     lower price,
        ┌──────────────────────────┐                │     published proof
        │ (2) RUNTIME              │        ┌───────┴──────────────┐
        │ gateway → contract →     │        │ (7) REGISTRY ROLLOUT │
        │ inference services       │        │ silent promotion,    │
        └───────┬──────────────────┘        │ canary, rollback     │
                │                           └───────▲──────────────┘
                │ content-free telemetry            │ passing candidates only
                ▼                                   │
        ┌──────────────────────────┐        ┌───────┴──────────────┐
        │ (3) TELEMETRY &          │        │ (6) EVALUATION GATE  │
        │ USAGE ANALYTICS          │        │ frozen eval sets,    │
        │ latency, volume, langs,  │        │ regression blocking  │
        │ error/retry patterns     │        └───────▲──────────────┘
        └───────┬──────────────────┘                │ candidate artifacts
                ▼                                   │
        ┌──────────────────────────┐        ┌───────┴──────────────┐
        │ (4) GAP ANALYSIS         │        │ (5b) TRAINING        │
        │ where do we lose? which  │───────►│ fine-tune, distill,  │
        │ languages, domains,      │        │ quantize, merge      │
        │ audio conditions?        │        └───────▲──────────────┘
        └───────┬──────────────────┘                │
                ▼                                   │
        ┌──────────────────────────────────────────┴───────────────┐
        │ (5a) DATA ACQUISITION — rights-clear only:               │
        │ commissioned, licensed, public-permissive, synthetic,    │
        │ explicitly-consented customer data (§2)                  │
        └──────────────────────────────────────────────────────────┘
```

### The stages, explained

1. **Customers** integrate against public model names (`intelliai-stt`, …)
   with a stability promise. Distribution is the flywheel's flywheel: every
   later stage is worthless without request volume.
2. **Runtime** serves requests through the capability contract. Because
   engines are invisible (ADR-0002/0003), every later model swap in stage 7
   is possible at all.
3. **Telemetry** — content-free metadata (durations, latencies, detected
   languages, error codes, retry patterns, model routing) — tells us *where
   the product is used and where it struggles*, without touching customer
   content. This is the compass for stage 4.
4. **Gap analysis** converts telemetry + evaluation results into training
   priorities: "Hindi telephony audio underperforms", "long-form audio
   times out", "medical vocabulary WER is 3× baseline". This is where
   product strategy (which gaps are worth money) meets ML reality (which
   gaps are trainable).
5. **Data acquisition and training.** Data is acquired deliberately
   (§2) — never harvested silently — and training produces *candidate
   artifacts* with full lineage (§4).
6. **The evaluation gate.** No candidate reaches production without beating
   (or consciously trading against) the incumbent on frozen, versioned
   evaluation sets. Regressions block by default.
7. **Registry rollout.** Promotion is a registry binding change: the public
   model stays put, the artifact behind it moves — canary first, rollback
   one routing change away (§5).
8. **Better customer experience** — measurably better quality, lower serving
   cost (which becomes price room or margin), published benchmark proof
   (which becomes marketing). More customers. Return to stage 1.

### Who owns what

| Stage | Owner | Concretely |
|---|---|---|
| 1, 8 | **Product** | public model catalog, pricing, tiers, deprecation policy, published benchmark pages |
| 2, 3, 7 | **Platform engineering** | gateway, runtime contract, services, registry, metering, telemetry pipeline, rollout/rollback machinery |
| 4, 5a, 6 | **ML engineering** | dataset registry, evaluation harness, benchmark suites, lineage records, promotion pipeline |
| 5b + new architectures | **Research** | fine-tuning recipes, distillation, new model exploration — isolated in `research/`, never imported by production (existing rule) |

The boundary discipline matters: product decides *which* gaps are worth
closing, ML decides *whether* they are closable, platform makes the swap
*safe and invisible*, research stays free to fail without touching
production.

### Honest cold-start note

The flywheel does not spin at M2. Stages 3–6 run on public benchmarks and
deliberately commissioned data long before consented customer data reaches
useful mass. That is the Sarvam lesson: early differentiation comes from
*choosing a wedge and acquiring data for it on purpose*, not from waiting
for telemetry scale. The platform's job in year one is to make every stage
*exist* and be trustworthy, so that when volume arrives the loop is already
closed.

---

## 2. Data Strategy

**The prime directive: customer data is NOT automatically training data.**
The flywheel must spin without betraying the people spinning it.

### The data taxonomy

| # | Class | What it is | May train? | Conditions |
|---|---|---|---|---|
| 1 | **Inference data** | Customer request/response content (audio in, transcripts out, text to synthesize) | **Never by default** | Only under explicit, recorded, org-level opt-in (below). Default retention: processing window only, then deleted per PRD §9. |
| 2 | **Production telemetry** | Content-free metadata: durations, latencies, language IDs, error codes, model routing, usage quantities | N/A (contains no trainable content — by construction) | Used freely for ops, product analytics, gap analysis. The pipeline is *structurally* unable to carry payloads. |
| 3 | **Evaluation data** | Curated, labeled, held-out sets representing customer-relevant distributions | **Never** | Frozen and versioned; the moment an eval set leaks into training it is worthless and must be retired. |
| 4 | **Benchmark data** | Public standard sets (for external comparability) | **Never** (for our published claims) | Kept separate from internal eval sets; assume public sets contaminate foundation-model training, so internal evals are the real referee. |
| 5 | **Training data** | The aggregate corpus a model version is trained on | — | Assembled *only* from classes 6–9 plus opted-in class 1. Every source carries a recorded license/consent verdict. |
| 6 | **Synthetic data** | Generated data (e.g. TTS-synthesized audio for STT training, LLM-generated text pairs) | Yes, with license care | The *generator's* license/terms must permit training on outputs — many hosted-model ToS forbid it. Same gate as model licensing (ADR-0005 discipline applied to data). |
| 7 | **Human-labeled data** | Commissioned annotation/transcription with QA | Yes | Most expensive class; spend it on evaluation sets first, training second. |
| 8 | **Public datasets** | Open corpora | License-dependent | Per-dataset license audit; non-commercial licenses (CC-BY-NC etc.) are banned from commercial-model training exactly as NC models are banned from serving. |
| 9 | **Private datasets** | Purchased, licensed, or IntelliAI-commissioned corpora | Yes | The long-term moat; provenance and contract terms recorded per dataset version. |

### The consent architecture

- Training consent is an **organization-level flag, default OFF**, set only
  by explicit customer action under a distinct contractual clause — never
  bundled into general terms, never inferred from usage.
- Consent is **auditable**: who enabled it, when, under which policy
  version — recorded immutably, alongside the M1 identity model where the
  org already lives.
- Consent is **revocable going forward**: revocation stops all future
  ingestion immediately. Honest caveat, stated now rather than discovered
  later: removing influence from *already-trained* weights is an unsolved
  problem (machine unlearning is research, not engineering). Therefore the
  contract language must promise "no future use + deletion from stored
  corpora at next dataset version", not magical retroactive removal — and
  the dataset versioning below is what makes that promise executable.
- Opted-in data still passes **filters before entering a corpus**: PII
  scrubbing, quality thresholds, dedup — consent makes data *eligible*,
  curation makes it *usable*.

### Dataset versioning

Datasets are **immutable, versioned artifacts** — the same discipline as
migrations and model weights:

- A dataset version = manifest (source list + consent/license verdicts +
  filter recipe + content hashes), stored durably (object storage buckets
  already reserved in the repo layout for exactly this).
- New data → new version; removals (revocations, takedowns) → new version
  with a recorded exclusion list. No in-place edits, ever.
- Every trained model records the exact dataset versions it consumed (§4);
  that is what makes "what did this model learn from?" answerable in one
  query — the question every enterprise customer, auditor, and regulator
  eventually asks.

### Evaluation data vs training data

They differ in every dimension that matters, which is why they are separate
classes and never share members:

| | Training sets | Evaluation sets |
|---|---|---|
| Size | as large as rights allow | small and surgical |
| Growth | continuously | frozen per version |
| Quality bar | noise-tolerant | gold-standard, double-checked |
| Composition | opportunistic | *stratified to the customer distribution* (languages, accents, audio conditions, domains) |
| Lifetime | superseded by bigger | retired only on contamination or drift |
| Contamination rule | must be dedup-checked **against** eval sets before every training run | never enters any training pipeline |

### How Sarvam-like companies improve models without violating trust

The pattern across credible full-stack model companies: differentiation
comes from **deliberate data acquisition in a chosen wedge** — commissioned
recordings, licensed corpora, partnerships, synthetic pipelines — not from
silently harvesting customer payloads. Customer trust is itself a data
strategy: enterprises with the most valuable domain data (call centers,
clinics, courts) will only ever opt in — or pay for dedicated fine-tunes on
*their* data for *their* use — with a vendor whose defaults are
demonstrably clean. Privacy-by-default is not a constraint on the flywheel;
it is the price of admission to its most valuable fuel. (It is also,
increasingly, law: GDPR and India's DPDP Act both point the same
direction — consent-based design is compliance done early.)

---

## 3. Public Model Philosophy

The five-layer identity chain, each layer owned by a different concern:

```
CAPABILITY        transcription                (platform concept — permanent)
    ↓
PUBLIC MODEL      intelliai-stt                (product SKU — years; the promise)
    ↓
FOUNDATION MODEL  <lineage chosen in D5>       (engineering input — swappable)
    ↓
RUNTIME ENGINE    <inference library/server>   (implementation detail — replaceable)
    ↓
DEPLOYMENT        cpu-int8 service / gpu pool  (operations attribute — configurable)
```

Each layer may change without permission from the layer above. A capability
survives every public model; a public model survives every foundation model;
a foundation model survives every engine; an engine survives every
deployment.

### One public model, many foundation models

The public model is a **promise** ("the best transcription IntelliAI offers
at this tier"). Routing is **fulfillment**, and fulfillment may be plural:

```
public model: intelliai-stt        ← one name, one price, one quality promise
routing policy (registry-internal, invisible):
    language = en, es, fr …  →  artifact from lineage A (general multilingual)
    language = hi, ta, bn …  →  artifact from lineage B (Indic fine-tune — the wedge)
    audio > 60 min           →  artifact optimized for long-form
    default / fallback       →  artifact from lineage C
```

The same mechanism serves tiers (`intelliai-stt-lite` routes to a distilled
artifact; a future `-pro` routes to a larger one), canary rollouts (5% of
eligible traffic → candidate artifact), and regional deployments — all as
registry policy, none as API surface.

### Why customers must never know this routing exists

1. **Known routing is coupled routing.** The moment a customer knows "Hindi
   goes to Model B", some customer *depends* on Model B's quirks — and the
   routing table is frozen by exactly the mechanism that was supposed to
   keep it free. Routing changes weekly as evaluations move; knowledge
   would turn every improvement into a breaking change.
2. **It would recreate engine dependence one level up.** Customers who know
   the backing models will ask to pin them ("give me Model B directly") —
   and a pinned foundation model is precisely the wrapper trap this whole
   strategy exists to escape.
3. **The promise is measurable without it.** Customers get per-language
   quality claims backed by published benchmark runs on the *public model*
   ("intelliai-stt: Hindi WER x%"). That is a promise IntelliAI can keep
   through any number of backend swaps; "which weights served you" is not.
4. **Transparency ≠ programmatic dependence.** Documentation may honestly
   say IntelliAI builds on open foundations, and model cards may describe
   lineage in prose — trust-building is good. What must never exist is
   anything a customer's *code* can couple to: no engine names in
   requests, responses, parameters, error messages, or behavioral
   contracts.

---

## 4. Model Lineage

Every model artifact IntelliAI produces or adopts has an ancestry, and that
ancestry is recorded, queryable, and load-bearing:

```
foundation-model X (external, license L, weights hash H)
    ↓ fine-tune (dataset v3+v5, recipe R1)
intelliai-stt-v1
    ↓ fine-tune (dataset v7: +telephony)          ↓ distill (student S, recipe R4)
intelliai-stt-v2                              intelliai-stt-lite-v1
    ↓ quantize (int8)
intelliai-stt-v2-int8   ← a *build* of v2, same logical model, re-evaluated
```

### Derivation types (all first-class, all recorded)

- **Parent model(s)** — every artifact except a true foundation import has
  ≥1 parent. Lineage is a **DAG, not a chain**: merged models have multiple
  parents; a LoRA adapter has both a base and an adapter lineage.
- **Fine-tuned** — full-parameter or adapter-based (LoRA et al.); the
  adapter type is recorded because it changes deployment shape (an adapter
  can ship separately from its base).
- **Distilled** — teacher→student; the teacher is a parent even though no
  weights are shared, because quality claims inherit from it.
- **Quantized / pruned** — same logical model, different numeric build,
  and always **re-evaluated** — precision changes quality, and "the int8
  build regressed Hindi" must be visible, not assumed away. *(Refined by
  [MODEL_IDENTITY.md](MODEL_IDENTITY.md) §5, which is authoritative:
  post-training quantization is a **build**, not a derivation; only
  data-consuming transformations create artifacts. The re-evaluation
  requirement stands either way.)*
- **Merged** — multiple parents, one artifact; the riskiest derivation,
  which is exactly why the record must make it explicit.

### What every lineage record contains

`parents · derivation type · training recipe (config + code commit) ·
dataset versions consumed · base-weights hashes · evaluation history ·
license inheritance verdict · lifecycle state (§5)`

Three properties fall out of keeping this record honest:

- **Reproducibility:** any artifact is rebuildable from (parent hash +
  dataset versions + recipe + code commit). If it cannot be rebuilt, it
  cannot be promoted — irreproducible models are unpayable debt.
- **Rollback:** artifacts are immutable and retained; a public model points
  at an artifact, so rollback is repointing — minutes, not retraining (§5).
- **License inheritance:** a derivative's license obligations flow from its
  parents *and* its training data. The lineage DAG is what lets the
  registry compute "is this artifact commercially clean?" instead of
  hoping someone remembered.

### Lineage in Registry v2 (direction, not design — design is D7)

Registry v1 (M2) stores serving entries. Registry v2 grows the identity
model: model families, artifacts with self-referential parent links
(the DAG), training stage, adapter type, dataset-version references, and
attached evaluation runs. Deliverable 7 designs it; this section fixes what
it must be able to *say*.

---

## 5. Two Independent Lifecycles

Two state machines, attached to two different objects, owned by two
different concerns:

```
PLATFORM LIFECYCLE — attached to PUBLIC MODELS, owned by Product
(a customer-facing promise timeline; slow; loud)

   preview ──► available ──► deprecated ──► retired
   (no stability   (full promise,  (≥6-month sunset,  (404; name never
    promise yet)    license gate    Deprecation        reused)
                    passed)         headers)

ML LIFECYCLE — attached to MODEL ARTIFACTS, owned by ML engineering
(an engineering state machine; fast; silent)

   research ─► experimental ─► training ─► evaluation ─► candidate
                                                            │
                              archived ◄─ superseded ◄─ production
```

They meet at **exactly one point**: the registry binding
`public_model (available) → artifact (production)`. Nothing else connects
them.

### Why they must remain independent

1. **Cadence mismatch.** ML iterates in days-to-weeks; product promises
   span quarters-to-years. One state machine forces one cadence: either
   every training success becomes a customer-facing event (churn), or
   every model improvement waits for a product process (paralysis).
2. **Cardinality mismatch.** One production artifact may back several
   public models (stt and stt-lite could share a backend at launch); one
   public model routes to several artifacts (§3). Fused lifecycles cannot
   express many-to-many.
3. **Different failure semantics.** `superseded` is a compliment — the
   artifact was good enough to be replaced by its own descendant.
   `deprecated` is a warning to customers with a legal-ish sunset clock.
   Confusing them makes internal progress look like external instability.
4. **Rollback must be shame-free.** Demoting an artifact
   (production → superseded, predecessor restored) is a routine engineering
   action. If it were coupled to the platform lifecycle it would be a
   *product incident* with announcements. Independent lifecycles make
   rollback boring — and boring rollback is what makes aggressive
   promotion safe.

---

## 6. Hardware Philosophy

**Revisited assumption, per direction: "CPU-first" is hereby reframed from
a platform philosophy to a deployment posture.**

New formulation: **hardware-agnostic architecture, CPU-first deployment
(today).**

### What ADR-0004 already got right

The architecture was never CPU-shaped: device and compute type are env
config, GPU adoption is a compose overlay, and the acceptance test ("moving
a service to GPU touches nothing in `services/*/src`") already treats
hardware as deployment. This section does not reverse ADR-0004; it
*sharpens* it and removes one place where the old phrasing quietly leaked
into strategy.

### What the reframing actually changes

1. **Model selection (the important one — this is why it must land before
   D3).** Under "CPU-first philosophy", GPU-native model lineages get
   vetoed at the door. Under the new phrasing, *no lineage is excluded by
   hardware*; serving cost and deployment complexity enter the D4 scoring
   as weighted criteria instead of acting as a hard filter. The best
   fine-tuning lineage for the next five years may well be GPU-native —
   that must be a priced trade-off, not a blind spot.
2. **The registry models hardware explicitly.** An artifact has
   *builds/deployments* (cpu-int8, gpu-fp16, a hosted-provider adapter,
   later edge builds), each with its own hardware envelope and its own
   evaluation results. "Where can this model run, at what quality, at what
   cost" becomes registry data, not tribal knowledge.
3. **The contract stays hardware-blind.** Nothing in the runtime contract,
   public API, or registry *identity* layers may assume a device — which is
   what lets the same logical model ship as a CPU build today and a GPU
   build next quarter with zero customer-visible change.
4. **Deployment targets are open-ended by construction:** CPU and GPU now;
   TPU/NPU via portable runtimes when justified; *hosted inference
   providers as a deployment class* (an adapter service is "a deployment
   of a capability" — already true in the M2 design); edge later (noting
   honestly: edge inverts the trust boundary — weights leave our
   infrastructure — so it arrives with licensing and IP homework, post-1.0).

### The trade-offs, stated honestly

- **Risk of hardware-agnosticism:** abstraction tax — lowest-common-
  denominator serving that is optimal nowhere. **Mitigation:** agnostic at
  the *contract and registry* layers only; each service remains ruthlessly
  concrete, optimized for its engine+hardware pair. Agnostic interfaces,
  specialized implementations — the same split the whole platform uses.
- **Risk of dropping "CPU-first" language:** losing the economic discipline
  that makes the generous free tier possible. **Mitigation:** CPU-first
  survives as the *default deployment posture* and a standing bias in unit
  economics — every model adoption still answers "what does this cost to
  serve per unit?" — it just no longer masquerades as architecture.
- **What it costs now:** almost nothing — one ADR amendment and a scoring-
  criteria change. **What it saves later:** not having to un-write a
  philosophy the first time evaluations show a GPU lineage is the right
  long-term bet.

**Action on approval:** record this as a new ADR superseding-with-refinement
ADR-0004 (per our supersede-don't-edit rule), at M1.5 close.

---

## 7. The IntelliAI AI Constitution

Ten principles. Each is written to still be checkable — by a test, a
registry rule, or a review question — five years from now. Every future
milestone review must answer: *which principles does this milestone touch,
and does it satisfy them?*

**1. Customers integrate with promises, not implementations.**
The only model names in public APIs are IntelliAI-owned names whose meaning
is defined by contract and published evaluation — never by the weights
behind them. *Forbidden:* any engine or foundation-model name, parameter,
or behavior a customer's code can couple to. *Checkable:* grep the public
schemas; audit new API fields against the portability test.

**2. Capabilities are permanent; engines are replaceable; artifacts are
disposable.**
Lifetimes are strictly ordered: capability > public model > foundation
lineage > engine > artifact > deployment. No layer may create a dependency
on a shorter-lived layer above this order. *Checkable:* every design review
names which layer a change lives in; anything engine-specific outside
`services/<name>/` fails review.

**3. The registry is the single source of model truth.**
If the registry does not know a model — its identity, license, lineage,
evaluation, routing — that model does not exist in production. No side
channels, no hardcoded model references, no "temporary" direct URLs.
*Checkable:* the gateway can reach an inference service only through
registry resolution.

**4. No license verdict, no traffic.**
Every model artifact and every dataset version carries a recorded
license/consent verdict *before* use, and derivatives inherit obligations
through the lineage DAG. The gate is structural (refuses to boot/promote),
not procedural (a checklist someone forgets). *Checkable:* the M2 registry
startup gate, extended to datasets and derivatives in later milestones.

**5. No evaluation, no promotion.**
Nothing serves production traffic without beating — or consciously,
recordedly trading against — the incumbent on frozen, versioned evaluation
sets. Regressions block by default; overrides are explicit and signed.
Evaluation sets never enter training pipelines. *Checkable:* promotion
tooling refuses artifacts without an attached eval run against the current
eval-set version.

**6. Customer content is not training data; consent is explicit, auditable,
and default-off.**
Telemetry (content-free by construction) informs decisions; customer
content enters training only through recorded org-level opt-in, and the
telemetry pipeline is physically incapable of carrying payloads.
*Checkable:* data-path review + the consent audit record.

**7. Every production model is reproducible from its lineage record.**
Parent hashes, dataset versions, recipe, code commit — sufficient to
rebuild. If it cannot be rebuilt, it cannot be promoted. *Checkable:*
lineage record completeness is a promotion precondition; periodically prove
it by actually rebuilding one.

**8. Rollback is a routing change, never a rebuild.**
Artifacts are immutable and retained through their support window; moving a
public model between artifacts — forward or backward — requires no
retraining, no client change, no data migration. *Checkable:* rollback
rehearsal is part of every promotion runbook, and it must be boring.

**9. Product lifecycle and ML lifecycle never share a state machine.**
Public models live on the platform lifecycle (loud, slow, promised);
artifacts live on the ML lifecycle (silent, fast, disposable); they meet
only at the registry binding. *Forbidden:* customer-visible events caused
by artifact-lifecycle transitions, and vice versa. *Checkable:* every
lifecycle field in the registry belongs to exactly one of the two machines.

**10. Hardware, precision, and placement are deployment attributes — never
architecture, never identity.**
The same logical model may ship as many builds (cpu-int8, gpu-fp16, hosted,
edge); contracts and registry identity are hardware-blind; each build is
separately evaluated and separately costed. *Checkable:* ADR-0004's
acceptance test, generalized — adopting a new hardware target touches
deployment config and (at most) adds a build, never the contract or the
public API.

---

*Change log:*
- *2026-07-31 — v0.1: initial draft (Milestone 1.5, Deliverable 1.5) —
  flywheel, data strategy, public-model philosophy, lineage, dual
  lifecycles, hardware reframing, ten-principle constitution. Pending
  approval.*
