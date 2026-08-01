# IntelliAI Model Identity Architecture

| | |
|---|---|
| **Status** | IN FORCE — approved 2026-07-31 (M1.5 D4; v0.2 refinements approved); **domain constitution** under [CONSTITUTION.md](CONSTITUTION.md) (§9 here are the identity statutes) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Role of this document** | The answer to *"what exactly is a model inside IntelliAI?"* — the conceptual identity system that Registry V2 ([D5]) will implement. Governed by [AI_STRATEGY.md](AI_STRATEGY.md); capability definitions from [CAPABILITIES.md](CAPABILITIES.md); requirements inherited from [FOUNDATION_MODELS.md](FOUNDATION_MODELS.md) §15. **No tables, no APIs, no code — concepts and rules only.** |

---

## 1. The Model Identity Hierarchy

"Model" is the most overloaded word in this industry. IntelliAI resolves it
into **eight distinct objects on two axes** — a product axis owned by
Product, an engineering axis owned by ML/Platform engineering — joined at
exactly one point: **routing**. The join being singular is what makes the
two lifecycles of AI_STRATEGY §5 genuinely independent.

```
PRODUCT AXIS (customer-visible)          ENGINEERING AXIS (internal)

CAPABILITY        transcription          FOUNDATION MODEL   upstream dossier:
   │  permanent platform concept            │               "openai/whisper"
   ▼                                        ▼  import (snapshot + license verdict)
PUBLIC MODEL      intelliai-stt          ARTIFACT           immutable logical model
   │  product SKU, years                    │  the DAG: fine-tune / adapter /
   │                                        │  merge / distill → new artifacts
   │                                        ▼  deterministic conversion
   │                                     BUILD              executable form:
   │                                        │               int8-ct2, gguf-q4, fp16-vllm
   │                                        ▼  placement
   │                                     DEPLOYMENT         where a build runs:
   │                                        │               prod-eu-cpu, canary-1, dedicated-org_x
   │                                        ▼  process
   │                                     RUNTIME            the ephemeral serving instance
   │                                        ▲
   └────────── ROUTING POLICY ──────────────┘
        the registry-owned binding: which deployments
        fulfill which public model, under which rules
        (language, tier, canary %, region)

MODEL FAMILY (cross-cutting): the portfolio-management unit — groups
artifacts sharing a lineage ("whisper", "qwen3", "intelliai-stt-indic")
for research planning, succession, maintenance cost, and license-risk
tracking (§1b) — advisory only, never a routing or gating input.
```

### Layer summary — owner, lifecycle, stability

| Layer | What it is | Owner | Lifecycle | Stable | Changeable |
|---|---|---|---|---|---|
| **Capability** | The task; one runtime contract | Platform architecture | Permanent (admission-tested once) | identity, contract shape | contract *versions* (v1→v2, additive) |
| **Public Model** | Product SKU + promise | Product | Platform lifecycle: preview→available→deprecated→retired | name (never reused), capability, promise semantics | pricing, routing, quality (upward), tiers |
| **Model Family** | Lineage portfolio unit (§1b) | ML engineering | Portfolio lifecycle: evaluating→invested→maintained→replacing→exited | nothing contractual | everything — it is advisory |
| **Foundation Model** | Dossier on an external upstream | ML engineering | Knowledge lifecycle: evaluating→adopted/rejected→watch→dead | the historical record | current assessment, watch state |
| **Artifact** | Immutable logical model (weights identity + lineage + license + evals) | ML engineering (or customer org, §8) | ML lifecycle: research→…→production→superseded→archived | **everything** — artifacts never change | only lifecycle state and attached eval history grow |
| **Build** | Deterministic executable form of one artifact | Platform engineering | Derived: exists while its artifact is servable | source artifact, conversion recipe | which builds exist (add/remove freely) |
| **Deployment** | A build placed somewhere with a purpose | Platform ops | Disposable: requested→provisioning→active→draining→terminated | nothing — cattle | everything |
| **Runtime** | The running process | Infrastructure | Ephemeral (seconds–weeks) | reports identity truthfully | crashes, restarts, scales |

### Why every layer exists (the collapse test)

Each layer earns its place because merging it with a neighbor breaks a
real requirement:

- Merge **public model into artifact** → every model improvement is a
  breaking customer event (kills the flywheel's silent-promotion stage).
- Merge **artifact into build** → "the int8 build regressed Hindi" becomes
  unsayable; quality accounting loses its subject.
- Merge **build into deployment** → every placement re-derives the
  executable; no two regions provably run the same bytes.
- Merge **deployment into runtime** → rollback requires rebuilding instead
  of re-pointing; canary/shadow become special snowflakes.
- Merge **foundation model into artifact** → upstream *knowledge* (license
  history, watch triggers, research trajectory) has nowhere to live when
  we hold three snapshots of the same upstream.
- Delete **model family** → succession planning ("what replaces the
  whisper lineage?") and concentration-risk tracking (FOUNDATION_MODELS
  §14) lose their unit of analysis.
- Delete **routing policy** as its own object → product identity and
  engineering identity fuse at N points instead of one, and the two
  lifecycles re-couple.

### 1a. Ecosystem independence (standing statement)

This identity system is deliberately independent of today's model
ecosystem. Nothing in it assumes HuggingFace, transformer architectures,
weights-as-files, or the 2026 open-model landscape. It must remain valid
— without redesign — whether IntelliAI serves open-source models,
IntelliAI-trained foundation models, customer-owned fine-tunes, external
API providers (weights-less imported artifacts, §10.3), or model
architectures that do not yet exist. The test for any future change:
if a proposal only makes sense for one ecosystem era, it belongs in a
build recipe or a dossier note, not in identity.

### 1b. Model families as portfolio management

A family is more than taxonomy: it is the unit at which IntelliAI manages
its model *portfolio* — the level where these questions live, none of
which any single artifact can answer:

- **Research planning:** where does the next quarter of fine-tuning
  capital go, and which lineage receives it?
- **Succession planning:** what replaces this lineage when it ages out,
  and how warm is the successor (FOUNDATION_MODELS §14 backup protocol)?
- **Maintenance cost:** how many builds, serving stacks, and toolchains
  does keeping this lineage alive actually cost?
- **License risk:** family-level license *trajectory* and watch triggers
  (verdicts remain strictly per-artifact — the family view aggregates
  risk, never grants trust).
- **Replacement strategy & long-term lineage management:** planned
  exit/migration paths, and the accumulated `intelliai-*` lineage built
  on top that must survive the base family's retirement.

The hard boundary stands: family data informs humans and portfolio
reviews. It is never an input to routing, gating, or license verdicts.

---

## 2. Public Models

A public model is **a named promise, priced** — the only model-shaped
object a customer ever sees, and the unit in which quality, price, and
stability are contracted.

- **Identity.** An IntelliAI-owned name (`intelliai-stt`,
  `intelliai-chat`, `intelliai-ocr`, …) bound to exactly one capability,
  permanent once shipped: **a public model name is never reused and never
  changes meaning-category** (a name that meant transcription can never
  mean synthesis). Tiers are separate public models (`intelliai-stt-lite`),
  not modes of one.
- **Pricing** attaches here and only here — per usage unit of the
  capability. Serving-cost improvements (better routing, cheaper builds)
  change margin, never the customer-visible price without a product
  decision. Nothing below this layer may carry a price.
- **Quality promise.** Defined by published, versioned evaluation results
  *on the public model* per segment (language, domain, audio condition) —
  "intelliai-stt: Hindi WER x% on benchmark v3" — a promise keepable
  across any number of backend swaps. Quality moves only upward within an
  `available` model, or the change ships as a new tier/snapshot.
- **SLA** (post-1.0): availability and latency classes attach to the
  public model per deployment class, because that is the name in the
  customer's contract.
- **Versioning.** Public model names are **versionless by default** —
  `intelliai-stt` simply gets better. For customers who need bit-stable
  behavior (regulated evaluation pipelines), **dated snapshot aliases**
  (`intelliai-stt-2026-06`) pin routing to specific artifacts — each
  snapshot carrying its own sunset date so pinning never becomes a
  perpetual museum obligation. Snapshots are aliases *into routing*, not
  new identity.
- **Deprecation.** Platform lifecycle with the PRD's ≥6-month sunset:
  `deprecated` serves with `Deprecation` headers and a date; `retired`
  returns `model_not_found`; the name stays reserved forever.
- **Routing.** A public model owns a routing policy (resolved by the
  registry, §7 of AI_STRATEGY): segment rules → deployments. The policy is
  invisible, changes freely, and is the entire mechanism of canary,
  regional, and tiered fulfillment.
- **Customer contract** = API contract (frozen per capability) + quality
  promise (published evals) + lifecycle promise (deprecation policy) +
  price. Nothing else — explicitly *not* the backing weights, provider,
  precision, or hardware.

**Why public models outlive every foundation model:** the customer
integrates the name; the name carries the promise; the promise is
fulfilled by whatever artifacts currently win our evaluations. Foundation
models have ~18-month relevance half-lives; customer integrations live
for many years; binding customers to the short-lived object would convert
every model succession into a migration project — and would permanently
foreclose the `intelliai-*` transition that is the whole strategy
(D1, Q2).

---

## 3. Foundation Models

A foundation model record is a **dossier about an external upstream** —
knowledge, not weights. The weights we actually pull become an *imported
artifact* (§4). One dossier ↔ many imported artifacts over time
(whisper large-v3, large-v3-turbo are snapshots under one dossier).

**The dossier holds (mutable, versioned knowledge):**

- **Origin & organization** — who makes it, where it lives, org's open-
  weights posture and trajectory (Meta's retreat vs Alibaba's cadence —
  FOUNDATION_MODELS evidence).
- **License intelligence** — the family's license *history* and current
  direction, watch triggers (e.g. "Qwen3.7 went proprietary"), known
  per-size/per-version traps. This is *intelligence*; the binding
  **verdict** lives on each imported artifact (§4), because licenses
  change between versions — the per-artifact rule this research proved.
- **Research status & trajectory** — papers, successor announcements,
  cadence health; **training-data transparency tier** (fully-open /
  documented / opaque).
- **Fine-tuning support** — recipes, frameworks, LoRA maturity, community
  precedent; this is what makes a lineage an *ownership candidate*.
- **Architecture facts** — tokenizer, architecture class, context length,
  capability fit, hardware envelope per size, supported languages (with
  our own Indic assessment, not the vendor's claim).
- **Adoption status** — `evaluating → adopted | rejected (reason recorded)
  | watch | dead`. A rejected dossier with its reason is as valuable as an
  adopted one: it prevents re-litigating NLLB every year.
- **Research notes** — our accumulated experience: quirks, hallucination
  behavior, fine-tuning lessons.

**What belongs to the dossier vs. the artifact:** the dossier answers
"what do we know and believe about this upstream?" and may be edited as
knowledge improves. The imported artifact answers "what exactly did we
take, when, under what verified terms?" and may never be edited. Weights
hash, snapshot date, license verdict with verification evidence, and the
frozen license text belong to the artifact. Assessments, trajectories, and
watchlists belong to the dossier. Confusing the two either freezes
knowledge or un-freezes evidence — both are failures.

---

## 4. Artifacts

The artifact is **the central object of the entire identity system**: an
immutable logical model. Everything above routes to artifacts; everything
below materializes them.

### The taxonomy — four orthogonal dimensions, not one enum

The long list of "artifact types" collapses cleanly once we notice it
mixes four independent questions:

**(a) Derivation — how it came to exist** (exactly one):

| Derivation | Parents | Notes |
|---|---|---|
| `imported` | none (upstream origin ref) | a foundation snapshot, hash-pinned |
| `fine_tuned` | 1 | full-parameter training on data |
| `adapter` | 1 base (+ produces composable weights) | LoRA-class; deployable composed with its base; the cheapest ownership unit — and the shape of voice clones |
| `merged` | ≥2 | riskiest derivation; explicitly multi-parent |
| `distilled` | ≥1 teacher (+ optional student init) | teacher is a parent for quality-claim inheritance even with zero shared weights |

**(b) Training stage — where in the recipe it sits** (metadata on
fine-tuned/adapter artifacts): `continued_pretrain | sft | preference |
domain`. "Instruction-tuned model" and "domain model" are stages, not
types.

**(c) Purpose flags** (zero or more): `experimental` (research/, never
routable), `evaluation_only` (baselines we measure against but will never
serve — e.g. Sarvam's models, NC-licensed references), `temporary`
(auto-expiring; ceremony/test artifacts).

**(d) Ownership** (§8): IntelliAI-owned or organization-owned. "Customer
model" and "voice clone" are not types — a voice clone **is** an
org-owned `adapter` (or small `fine_tuned`) artifact on a TTS lineage
with consent evidence attached. The identity system needs no special
case; the *product* around it (consent ceremony, pricing) lives above.

"Retired" is not a type either — it is the terminal lifecycle state
(`archived`).

### What every artifact carries, from birth

- **Capabilities exposed (one or more)**: an artifact declares which
  capability contracts it can fulfill. Most declare one; multimodal
  foundation models (omni-style speech+text, VLMs doing both OCR and
  image understanding) declare several — each exposed capability is
  independently evaluated, independently routable, and independently
  gated. Public models still bind to exactly one capability; a
  multi-capability artifact simply appears in more than one routing
  pool. No redesign is needed when natively-multimodal lineages arrive.
- **Lineage**: parents + derivation + the full reproducibility record —
  recipe (config + code commit), dataset versions consumed, parent weights
  hashes. The lineage graph is a **DAG** (merges, distillation,
  adapter-on-base), never a chain.
- **Owner** (§8) and **license verdict**: computed from parents ∪ dataset
  licenses ∪ own terms, with verification evidence and date — the
  per-artifact-version rule (FOUNDATION_MODELS §15.1). An artifact whose
  verdict cannot be computed cannot exist.
- **Evaluation history**: append-only, accumulated over life, attached to
  (artifact, build) pairs (§5).
- **ML lifecycle state**: research → experimental → training → evaluation
  → **evaluation_candidate** → production → superseded → archived
  (refines AI_STRATEGY §5's "candidate"). `evaluation_candidate` is the
  explicit stage between passed-evaluations and production: the artifact
  has cleared the offline gates (evaluation, license, reproducibility)
  and is now eligible for *live* validation — shadow and canary
  deployments run **while the artifact is an evaluation candidate**, and
  only surviving live validation promotes it to `production` (the routing
  binding flip). This makes "passed our benchmarks" and "trusted with
  customer traffic" two different, auditable facts.

### Behavior

- **Promotion** = lifecycle transition gated by evaluation (P5) — never
  edits the artifact; **rollback** = routing repoint to the still-existing
  predecessor (P8) — possible *because* artifacts are immutable and
  retained.
- **Children** never modify parents; a "new version of our Hindi STT
  model" is a new artifact whose parent is the old one.
- **Reproducibility**: an artifact is a *claim* that
  f(parents, datasets, recipe, code) = these weights; the record must be
  sufficient to re-run f. Irreproducible → unpromotable (P7).
- **License inheritance** flows through the DAG automatically: a
  derivative of an NC parent or an NC dataset is NC regardless of what
  anyone intends — computed, not asserted.

---

## 5. Builds

A build is a **deterministic transformation of one artifact into an
executable form**: precision (fp32/fp16/bf16/int8/int4), format (safetensors,
GGUF, ONNX, CTranslate2, TensorRT engine), target (CPU build, GPU build,
edge build later).

**The bright-line rule that separates artifact from build:**

> **If creating it consumed data, it is an artifact. If it is a
> deterministic transformation of existing weights, it is a build.**

Post-training int8 quantization: build. Quantization-*aware training*:
artifact (data was consumed). Distillation: artifact. Format conversion
to GGUF: build. This rule refines AI_STRATEGY §4 (which loosely listed
"quantized" under derivations) — the identity system supersedes that
phrasing, and the safeguard it wanted is preserved differently:
**every build is separately evaluated**, because precision does change
quality ("the int8 build regressed Hindi" must have a subject — that
subject is the (artifact, build) pair).

**Builds never become model identity because:**

1. Customers would couple to precision — freezing exactly the
   cost-optimization freedom (int8 today, fp8 on GPUs tomorrow) that
   funds the free tier.
2. Quality claims would fragment — N builds × M artifacts as independent
   identities destroys comparable evaluation history.
3. It would double-count: a build is *reconstructible* from artifact +
   conversion recipe; identity belongs to things that cannot be
   regenerated (the trained weights), not to things that can.

A build's own record is small: source artifact, conversion recipe +
toolchain versions (reproducibility of the mechanical kind), output hash,
target envelope, and its evaluation results.

---

## 6. Deployments

A deployment is **a build, placed, with a purpose**: environment
(prod/staging), purpose (`production | canary | shadow | benchmark |
internal | customer_dedicated`, later `edge`), region, hardware class,
scaling parameters, and — for adapter-composed serving — the list of
composed artifacts (base + adapters) it hosts.

- **Lifecycle**: requested → provisioning → active → draining →
  terminated. Nothing mourns a deployment; anything it "was" is
  reconstructible from (build, deployment descriptor). Deployments are
  cattle by construction — they hold no state and no identity.
- **Rollout**: promotion never flips traffic atomically. The sequence is:
  new deployment goes active → **shadow** (receives duplicated traffic,
  responses discarded, metrics compared) or **canary** (routing sends a
  small percentage of matching traffic) → percentage widens on evaluation
  → old deployment drains but stays warm through a bake window.
- **Rollback**: routing repoint to the still-warm predecessor —
  minutes, no rebuild, no re-provision (P8). The bake window is what
  makes rollback boring; boring rollback is what makes promotion brave.
- **Multi-region**: region is a deployment attribute plus a routing rule
  — `intelliai-stt` in the EU can resolve to an EU deployment of the
  *same build* with zero identity implications. Data-residency
  guarantees (post-1.0) become routing constraints, not new model
  objects.
- **Customer-dedicated deployments** (§8): the same machinery pointed at
  one org — a private placement of a build, possibly of the customer's
  own artifact. No new concepts required; that is the point of the
  layering.

---

## 7. Runtime Identity

A runtime service instance knows exactly four things about itself:
**capability** (which contract it speaks), **artifact** (which logical
model), **build** (which executable form), **deployment** (which placement
it belongs to). It reports all four truthfully — in `/info` and in the
envelope's `model` block on every response (the M2 contract already
reserves this) — and that report is the *only* contribution runtime makes
to identity: **the runtime reports identity; it never defines it.**

A runtime must never know: pricing, billing, customer contracts, org
identities, public model names, or routing policy. Because:

1. **Plane separation is a security boundary** (ADR-0002): a compromised
   inference service — the component most exposed to hostile input —
   yields weights-adjacent process access but zero business data, zero
   customer identity, zero pricing intelligence.
2. **Swap freedom**: a runtime that knows it serves `intelliai-stt`
   invites logic conditioned on product identity — the exact coupling
   that makes backends unswappable. Runtimes are interchangeable
   *because* they are ignorant.
3. **Attribution correctness**: the gateway joins (request, org, public
   model) with the runtime's reported (artifact, build, deployment) at
   response time — each side asserting only what it authoritatively
   knows. That joined record is the usage event; neither side alone could
   produce it honestly.

---

## 8. Ownership

Five levels, from most public to most private — each object in the
identity system lives at exactly one:

| Level | What lives here |
|---|---|
| **Open foundation** (external) | Foundation dossiers' subjects — upstreams we don't own and can't mutate; our *dossiers about* them are IntelliAI-owned knowledge |
| **IntelliAI** (platform) | Capabilities, public models, routing policies, all platform artifacts/builds/deployments, evaluation suites, the registry itself |
| **Organization** (customer) | **Customer-owned artifacts**: their fine-tunes, their voice clones (adapter artifacts + consent evidence), their dedicated deployments, their private routing aliases |
| **Project** (future) | Reserved: sub-organization grouping (team/app scoping of keys, artifacts, budgets). No object lives here yet; the level exists in the model so Registry V2 reserves room and M6+ needn't remodel identity |
| **User** | **Deliberately: no model objects.** Membership and credentials are user-level (M1); artifacts are never user-owned — org-first tenancy (ADR-0010) applies to models exactly as to keys. A departing employee must never orphan a production model |

**Customer-owned artifacts** are first-class artifacts with an org owner:
full lineage (their parent is typically an IntelliAI or imported artifact
— license inheritance computes through), full evaluation history, same
immutability, same lifecycle. Differences are policy, not identity: only
their org's traffic can route to them; they appear only in their org's
catalog; deletion requests follow data-rights flows (the *lineage record*
survives archival for audit; the weights need not).

**Shared artifacts:** IntelliAI-owned artifacts are implicitly shared with
everyone *through public models* — customers never reference artifacts
directly. Cross-org artifact sharing (marketplace, partner models) is
explicitly out of the 5-year identity model; if it ever arrives it enters
as recorded grants, not as a new ownership level.

**Private deployments:** `customer_dedicated` placements — our artifact or
theirs, their traffic only, optionally their region. Identity unchanged;
only routing and billing know the difference.

---

## 9. Identity Rules (immutable)

1. **One name, one meaning, forever.** Public model names and artifact
   identifiers are never reused and never change meaning — retirement
   reserves a name permanently.
2. **Identity flows downward only.** Capability → public model →
   (routing) → artifact → build → deployment → runtime. No lower layer
   may define, alter, or leak into the identity of a layer above it.
3. **Artifacts are immutable; change is birth.** Anything that alters
   weights creates a new artifact; anything that alters format creates a
   build; anything that alters placement creates a deployment.
4. **Data makes artifacts; determinism makes builds.** If producing it
   consumed data, it is an artifact with lineage; if it is a mechanical
   transformation, it is a build with a recipe.
5. **No artifact exists without owner, lineage, license verdict, and
   reproducible origin — at creation.** These are birth requirements,
   not documentation debt.
6. **License verdicts attach to artifact versions and are computed
   through the DAG** — from parents, datasets, and own terms; never
   asserted at family level; verification evidence recorded.
7. **Evaluation attaches to (artifact, build) pairs**, is append-only,
   and gates every lifecycle promotion. What you serve is what you
   measured.
8. **Routing is the only bridge** between product identity and
   engineering identity, and the registry owns it exclusively — no
   hardcoded artifact references anywhere above or below.
9. **Deployments are disposable; artifacts are permanent records.**
   Anything a deployment knows is reconstructible; nothing an artifact
   records is ever deleted — archival may reclaim weights storage, never
   the lineage record.
10. **Ownership changes are recorded, consented events** — never implicit,
    never a side effect; customer artifacts are org-owned, never
    user-owned.
11. **The runtime reports identity; it never defines it** — and it never
    learns product names, prices, or customers.
12. **Customers see exactly one identity layer.** Public models (and
    their dated snapshots) are the only model-shaped names in any
    customer-visible surface — logs, errors, docs, and usage records
    included.

---

## 10. Architectural Review — weaknesses, ambiguities, verdict

An honest audit of this identity model before it hardens into Registry V2:

**Known weaknesses and their resolutions:**

1. **Adapter composition strains single-artifact attribution.** A
   deployment may serve base + N adapters (multi-tenant voice clones on
   one TTS base). Resolution, decided now: the deployment descriptor
   lists all composed artifacts, and the envelope's `model` block reports
   the *set* — attribution is to a composition, and the usage event
   records every member. Registry V2 must model "served composition,"
   not assume one-artifact-per-request.
2. **Model family is the softest concept** — useful taxonomy, but if it
   ever leaks into routing or license logic it becomes a backdoor
   family-level trust assumption (exactly what rule 6 forbids). Guard:
   family is *display-and-analysis metadata only*; Registry V2 must give
   it no behavioral role.
3. **External-provider models stretch the artifact abstraction.** A
   future Deepgram adapter has no weights, no build. Resolution: an
   `imported` artifact whose reproducibility record pins provider +
   API version, with builds being not-applicable and the deployment being
   the adapter service. Accepted stretch — the alternative (a parallel
   identity system for external models) violates "providers are
   indistinguishable" (ADR-0003) far more expensively.
4. **Composites have versioned recipes that are not artifacts.** Document-
   intelligence pipelines, prompt templates, and routing-policy versions
   all change behavior without changing any artifact. This identity model
   deliberately does not cover them; they will need a lightweight
   "pipeline/recipe version" concept when composites ship (P3/P4).
   Recorded now so Registry V2 leaves room rather than painting over it.
5. **Dataset identity is referenced, not defined.** Artifacts point at
   dataset versions; the dataset registry (AI_STRATEGY §2, designed in
   D8/M9) is a sibling identity system with the same immutability
   discipline. The boundary is clean but the sibling must actually get
   built before heavy training begins.
6. **Snapshot aliases could recreate pinning.** Bounded by rule: every
   snapshot carries a sunset date at creation; no unbounded pins.

**Five-year test against the roadmap (CAPABILITIES §6):** P1 speech
(artifacts+builds+deployments for two capabilities — trivially covered);
P2 fine-tunes + voice cloning (adapter artifacts, org ownership, consent
evidence — covered by §4/§8); P3 language + GPU tier (builds/deployments
express the hardware shift with zero identity change — P10 holds); P4
documents/vision (same objects, more capabilities; composite-recipe gap
flagged above is the one addition); P5 agents + customer fine-tuning GA
(org-owned artifacts and dedicated deployments are already first-class;
project level reserved). **No phase requires a new identity layer; one
phase (P3/P4) requires the recorded pipeline-version addition.** The
model holds.

---

## 11. Reserved: Evaluation Identity

Evaluation will eventually need first-class identity of its own — today's
"evaluation history attached to (artifact, build)" is a reference to a
sibling system whose objects are reserved now so Registry V2 leaves room:

- **Evaluation suite** — a versioned, frozen collection of test sets +
  metrics + pass criteria for one capability segment (the thing quality
  promises cite: "Hindi WER on benchmark v3").
- **Evaluator** — the versioned harness/judge that produced a result
  (metric code version, judge model artifact if LLM-judged — itself an
  artifact reference, closing the loop).
- **Dataset bundle** — the eval-side dataset-version grouping, distinct
  from training datasets by constitution (AI_STRATEGY §2).
- **Evaluation result** — immutable: (artifact, build, suite version,
  evaluator version) → scores + verdict, timestamped.

Registry V2 stores result *summaries and verdicts by reference*; the
evaluation system owns the objects. Reserved, not designed — design lands
with the evaluation harness milestone (M9).

---

*Change log:*
- *2026-07-31 — v0.2: five approved refinements — ecosystem-independence
  statement (§1a); model family reframed as portfolio management (§1b);
  artifacts expose one-or-more capabilities; explicit
  `evaluation_candidate` lifecycle stage (shadow/canary happen there);
  Evaluation Identity reserved (§11).*
- *2026-07-31 — v0.1: initial identity architecture (M1.5 D4): two-axis
  hierarchy, eight objects + routing, artifact-centric design with
  four-dimension taxonomy, data-vs-determinism bright line, ownership
  levels, 12 identity rules, self-review. Pending approval.*
