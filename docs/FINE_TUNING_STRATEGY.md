# IntelliAI Fine-Tuning Strategy

| | |
|---|---|
| **Status** | IN FORCE — approved 2026-07-31 (M1.5 D8); **domain constitution** under [CONSTITUTION.md](CONSTITUTION.md) (Part 10 here is training law) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Role of this document** | The strategy for how IntelliAI evolves from serving open foundation models into owning progressively better `intelliai-*` models over 5–10 years. Sits with [AI_STRATEGY.md](AI_STRATEGY.md) (constitution) and [FOUNDATION_MODELS.md](FOUNDATION_MODELS.md) (current lineage choices); executes through [MODEL_IDENTITY.md](MODEL_IDENTITY.md) and [REGISTRY_V2.md](REGISTRY_V2.md). **Strategy and architecture only — no implementation, no APIs, no schemas.** |
| **Layer legend** | Sections are tagged by the kind of truth they state: **[BUS]** business strategy · **[ML]** ML strategy · **[PLAT]** platform architecture · **[PROD]** product philosophy · **[RES]** research philosophy. Keeping the layers distinct is itself a discipline: a business argument must never masquerade as an ML fact, and vice versa. |
| **Ecosystem-independence check** | Applied throughout: today's model names appear only as *current instantiations*, clearly marked. Every principle and framework in this document must survive the disappearance of every 2026 model leader. |

---

## Part 1 — Philosophy: why fine-tuning is the business, not a feature **[BUS]**

A feature is something customers use. Fine-tuning, for IntelliAI, is the
mechanism by which the company changes what it *is*: from a margin-taking
distributor of other people's models into an owner of differentiated
model IP served through its own distribution. Every structural decision
already made — engine-blind contracts, artifact lineage, the registry,
the consent architecture — exists to keep that transition cheap when its
time comes. This document decides how to spend it.

**Why serving comes first.** Serving is not the humble prelude to the
real work; it *is* the acquisition of the three assets training cannot
create: distribution (customers whose problems tell us what to train),
evaluation data (the measured gaps that make training targetable), and
revenue (which buys GPUs without selling the company). A model company
without distribution is a research lab with a burn rate (D1). The order
is forced, not chosen.

**Why evaluation precedes training.** Training without evaluation is
gambling with GPU bills. Evaluation converts training from "we hope this
helps" into "we predicted +2.1 on Hindi telephony and measured +1.8." It
is also the *cheaper* asset: an evaluation suite costs a fraction of one
training run and pays out on every run forever — including the runs it
prevents (a good eval kills bad ideas before they reach a cluster).
The evaluation harness is therefore the flywheel's ignition, deliberately
scheduled before any serious training.

**Why data becomes the moat.** Weights depreciate — every open release
devalues them, and the industry's release cadence guarantees it. What
appreciates: curated, rights-clean, wedge-specific data; frozen
evaluation suites that measure what customers actually experience; and
the accumulated recipe knowledge of what works on *our* distributions.
A competitor can download our base model's successor tomorrow; they
cannot download our data, our evals, or our lessons. Strategic corollary:
**models are derivatives of data — invest in the underlying, not the
derivative.**

**Why distribution matters before research.** Research chooses from an
infinite space of things to improve; distribution collapses it to the
few that pay. Usage telemetry (content-free, per AI_STRATEGY §2) tells us
which languages, domains, and audio conditions carry real traffic;
published benchmark wins in the wedge convert directly into acquisition
(the Sarvam and AssemblyAI lesson). Research directed by distribution
compounds; research directed by fashion evaporates.

**Why a platform makes better models over time.** The platform is a
standing experiment: every request is a data point about where models
fail; every serving-cost bill teaches efficiency; every customer
fine-tune (P6) reveals a domain we didn't know mattered. Companies that
only train lack this sensor array; companies that only serve lack the
means to act on it. Owning both loops is the whole design.

**Lessons extracted (not copied) from the field.** *Sarvam*: wedge-first
works — pick underserved segments, commission data deliberately, publish
wedge benchmarks as marketing; platform preceded their own models.
*OpenAI*: brand accrues to the name customers type — product-owned model
names, deprecated freely, decoupled from research artifacts; also, the
API business funded the research, not the reverse. *ElevenLabs*: vertical
quality depth in one modality beats horizontal mediocrity, and
customer-created artifacts (their voices) are the strongest lock-in ever
shipped in audio. *AssemblyAI*: honest, reproducible benchmarks are a
speech specialist's entire marketing department. *DeepSeek*: efficiency
research is a differentiator in itself — doing more with less compute is
a moat when compute is the industry's scarcest input. The composite
lesson: **serve → measure → pick a wedge → own the data → publish the
wins → let customers build on you.** That is this document's spine.

---

## Part 2 — The Fine-Tuning Ladder **[ML] [BUS]**

The ladder is a maturity model **per capability, not per company** —
`transcription` may stand at Stage 3 while `ocr` stands at Stage 0, and
that unevenness is correct: rungs are climbed where the wedge is, not
everywhere (see Part 8's capability tiers). Investment is stated in
timeless units (GPU-time classes, person-weeks, data effort) — never
currency or vendor hardware.

### Stage 0 — Serve foundation models
- **Why it exists:** acquires distribution, telemetry, evaluation
  baselines, and serving competence — the preconditions of every later
  stage. Skipping it produces models nobody asked for.
- **Investment:** no training compute; engineering effort goes to the
  platform itself. **ROI:** revenue, gap maps, baseline evals.
- **Complexity:** engineering low (per capability), operational moderate
  (serving discipline).
- **Evaluation requirement:** baseline suites per wedge segment — the
  incumbent must be measured before it can be challenged.
- **Exit criteria:** evaluation harness live for the capability; wedge
  gaps identified *quantitatively*; traffic sufficient to justify a rung.

### Stage 1 — Parameter-efficient tuning (adapters)
- **Why:** the cheapest possible test of the core hypothesis — "targeted
  training on our data beats the stock model on our segments." Adapters
  (LoRA-class today; the *concept* — small trainable deltas on a frozen
  base — is architecture-independent) cost single-GPU-days and compose at
  serving time (identity §4).
- **Investment:** GPU-days per experiment; data effort dominates compute.
  **ROI:** fast wedge wins; recipe learning; the team's training muscles.
- **Complexity:** engineering low-moderate; operational low (adapter
  serving already designed).
- **Evaluation:** segment suites + no-regression on general suites.
- **Exit:** adapters *consistently* beat stock on wedge segments by
  margins customers can feel, and the promotion pipeline (Part 5) has
  carried at least one adapter to production — proving the machinery,
  not just the model.

### Stage 2 — Domain fine-tunes
- **Why:** adapters plateau where the gap is deep (new vocabularies,
  acoustic conditions, scripts). Full or heavy fine-tuning on curated
  domain corpora produces the first *named* lineage assets
  (`intelliai-stt-indic-v1`) and the first publishable benchmark wins.
- **Investment:** multi-GPU days-to-weeks per run; **data acquisition
  becomes the dominant cost** (commissioned recordings, licensed
  corpora). **ROI:** routing defaults in the wedge; published wedge
  benchmarks (marketing); margin (a tuned small model beating a stock
  large one is pure COGS win).
- **Complexity:** engineering moderate; operational moderate (more
  artifacts, more evals, portfolio reviews begin earning their keep).
- **Evaluation:** full segment matrix + regression + contamination checks
  now mandatory (Part 7).
- **Exit:** our fine-tune is the registry's routing default for its
  segment, and stayed there through at least one upstream base release
  (proving the switching test, Part 4).

### Stage 3 — Multi-domain consolidation
- **Why:** Stage 2 succeeds into sprawl — five domain tunes per
  capability multiply serving, evaluation, and maintenance cost.
  Consolidation trains single models covering multiple segments without
  regressing any (multi-task training on merged curricula).
- **Investment:** the largest fine-tuning runs yet; regression risk is
  the real cost. **ROI:** operational simplification; broad quality;
  fewer, stronger lineage assets.
- **Complexity:** engineering high (curriculum balance, forgetting);
  operational *reduced* on success — that is the point.
- **Evaluation:** the full matrix, with a hard no-regression gate: the
  consolidated model must match or beat every per-domain model it
  replaces, per segment.
- **Exit:** one model retires N specialists with the registry recording
  the supersession — sprawl reduced by decision, not accident.

### Stage 4 — Distillation and compression
- **Why:** once quality leads, cost leads become the growth lever:
  distilling our best models into smaller students creates the `-lite`
  tiers, fattens free-tier economics, and cuts serving cost at exactly
  the traffic levels where it matters. Distillation is also
  upstream-independence insurance: a student of *our* teacher is *ours*.
- **Investment:** teacher-student infrastructure + per-student runs;
  moderate compute, high engineering leverage. **ROI:** margin at scale;
  latency tiers; edge-viable builds.
- **Complexity:** engineering high (distillation is finicky); operational
  low (fewer, cheaper deployments).
- **Evaluation:** student-vs-teacher deltas per segment, priced: "within
  Y% of teacher at 1/Nth cost" is a product decision recorded with the
  artifact.
- **Exit:** a distilled student serves a public tier profitably — at
  which point Stage 4 becomes a *standing practice*, not a stage.

### Stage 5 — IntelliAI-native models
- **Why:** the ceiling of every earlier stage is the upstream
  architecture. Native models — pretrained (or continued-pretrained past
  the point of meaningful ancestry) on IntelliAI's data, for IntelliAI's
  segments — remove the ceiling and complete the identity: nothing above
  us in the lineage DAG.
- **The honest scoping [RES]:** feasibility is *modality-dependent*.
  Speech models are small (today's best serve at 10⁷–10⁹ parameters) —
  pretraining one is startup-feasible compute. Frontier language models
  are not, and this strategy does **not** assume IntelliAI ever pretrains
  one from scratch; the language path is continued-pretraining and deep
  post-training on open bases (Sarvam's proven route). Native-first
  candidates: STT and TTS in the wedge, where our data advantage is
  deepest and model scale smallest.
- **Investment:** cluster-scale compute for weeks + sustained research
  capacity + industrial data pipelines. This rung is gated on revenue
  and data maturity, never on ambition. **ROI:** full IP ownership,
  architecture freedom, permanent upstream independence in the wedge.
- **Complexity:** engineering and research high; operational unchanged —
  **by constitution, a native model is just another artifact**: same
  registry, same gates, same promotion pipeline. The platform must not
  be able to tell.
- **Evaluation:** must beat our own best derivative lineage (the hardest
  incumbent that exists) — native pride earns nothing.
- **Exit (into it, not out of it):** Stages 1–4 exhausted on the
  capability; wedge data moat sufficient to train from; evaluation
  predicts a win; unit economics of ownership beat continued derivation.
  All four, or the rung waits.

---

## Part 3 — Data Strategy: what IntelliAI builds **[ML] [BUS]**

AI_STRATEGY §2 fixed the taxonomy and the consent constitution; this
section decides **what we deliberately construct**. The classes below
map onto that taxonomy — nothing here amends it.

| Dataset class | What IntelliAI builds | Owner | Evolution |
|---|---|---|---|
| **Public** | Curated *subsets* of permissive corpora, filtered to wedge distributions (license-audited per source, contamination-checked) | curation is ours; sources retain theirs | re-cut per version as sources and filters improve |
| **Licensed** | Purchased/contracted corpora for segments where public data is thin (telephony audio, domain documents) | contractual — terms recorded per version | renewed/extended by explicit contract events |
| **Customer-consented** | Per-org opt-in pools (AI_STRATEGY §2 consent architecture) — scoped, revocable-forward, filtered before entry | the customer; IntelliAI holds a recorded license to train | grows with consenting traffic; shrinks at next version on revocation |
| **Synthetic** | Cross-capability bootstraps — TTS-read text for STT training, STT-transcribed audio for TTS alignment, LLM-generated domain text — *only from generators whose terms permit it* (the D3-verified rule) | IntelliAI | regenerated as generators improve; generator lineage recorded |
| **Human-labelled** | Commissioned recordings and annotations in the wedge: accents, code-mixed speech, scripts, domain vocabularies — the Sarvam lesson made concrete. The most expensive class; spent on evaluation first, training second | IntelliAI (work-for-hire, consent-clean) | grows by planned campaigns, not opportunistically |
| **Evaluation** | Frozen, stratified, gold-standard segment suites per capability — built *before* their training counterparts | IntelliAI; never shared with training | versioned; retired only on contamination or drift |
| **Benchmark** | Public-set harnesses for external comparability + published wedge benchmarks (our marketing surface) | public sets: theirs; wedge benchmarks: ours, published | tracked against community versions |

**Governance without storage design:** every dataset version is an
immutable manifest (sources, license/consent verdicts, filter recipe,
hashes — AI_STRATEGY §2); admission of a *new dataset* gets the same
ceremony as admission of a new model lineage (a recorded review against
the license and consent gates); the dataset registry (REGISTRY_V2 §10.2)
is the sibling system that will hold this; and **the provenance question
— "what did this model learn from?" — must always be answerable in one
query through the lineage DAG.** Until the dataset registry exists,
manifests live as reviewed documents; the discipline starts before the
tooling.

---

## Part 4 — Choosing what to fine-tune: the permanent framework **[ML] [BUS]**

The newest model is a hypothesis, not a decision. The framework:

**Step 1 — Is there a paying gap?** Evaluation and telemetry must show a
quantified quality gap on a segment that carries (or credibly will carry)
revenue. No gap, no training — regardless of what was released this week.

**Step 2 — Score the candidate base lineages** on the permanent factors
(instantiated for 2026 in FOUNDATION_MODELS §1; the factors outlive the
scores): license clarity and trajectory · fine-tuning recipes and tooling
maturity · ecosystem/community depth · serving cost per unit at our
scale · evaluation quality on *our* suites (never leaderboards) ·
benchmark stability across versions (a lineage that regresses on
re-release is a bad landlord) · long-term org viability · research
momentum · our accumulated expertise in the lineage.

**Step 3 — Apply the switching test.** This is the heart of the
framework: **a challenger lineage must beat *our tuned incumbent* — not
the stock incumbent — on our evaluations, by a margin exceeding the full
switching cost** (re-tuning capital, re-evaluation, serving-stack
changes, recipe knowledge reset, portfolio churn). Fine-tuning capital
*compounds within a lineage*: every recipe, dataset curriculum, and
failure lesson transfers to the next tune on the same base and mostly
evaporates across bases. Switching resets the compound interest.

**Why staying on an "old" lineage is often the stronger business:** an
18-month-old base carrying two years of our accumulated tunes routinely
beats a six-week-old base carrying none — and the old lineage's serving
stack is amortized, its failure modes are known, and its evals are
stable. Novelty is a cost center until proven otherwise. *(Current
instantiation, clearly marked: this is why D3 chose a frozen Whisper over
2026's leaderboard — the reasoning, not the choice, is what this section
makes permanent.)*

**The override triggers — when switching is forced regardless:** license
shift on the incumbent lineage (P4 gates it out); upstream death with a
decaying ecosystem; a demonstrated architectural ceiling on a wedge
requirement (e.g. the lineage cannot stream); or the portfolio review
(identity §1b) showing maintenance cost overtaking the compound value.
Then the challenger still passes the switching test — against reality,
with the test's cost side now including the cost of *staying*.

---

## Part 5 — The promotion pipeline, conceptually **[PLAT]**

The pipeline is the identity lifecycle (MODEL_IDENTITY §4, v0.2) plus the
registry's gates (REGISTRY_V2 §8) — restated here as what each transition
*proves*, and who approves it:

| Transition | What it proves | Approver |
|---|---|---|
| Foundation → Fine-tune (training run) | lineage, data rights, and reproducibility existed *before* compute was spent — a run that can't register its output didn't succeed | ML eng (routine) |
| Fine-tune → Evaluation | the artifact is complete: birth requirements attached, builds produced, suites selected | automatic (registration implies it) |
| Evaluation → Candidate | offline gates passed: beats incumbent on target segments, regresses nowhere, license verdict current, reproducibility complete | the gates themselves (structural); overrides are signed |
| Candidate → Shadow | live-traffic behavior matches offline promise: latency, stability, cost — with zero customer exposure (responses discarded) | platform eng |
| Shadow → Canary | real customers can experience it, bounded: the routing slice is small, watched, and reversible in one operation | ML + product jointly (first customer exposure is a product event) |
| Canary → Production | the binding flip: the promise of the public model is now fulfilled by this artifact; evidence recorded, replayable | product (loud, ceremonial for defaults; routine for segment routing) |
| Production → Superseded | a descendant won the same gates; the predecessor stays warm through the bake window, rollback-eligible forever | automatic on successor promotion |
| Superseded → Archived | retention policy: weights storage reclaimable, records eternal | ops (policy-driven) |

Two properties matter more than the stages: **every arrow is a recorded
registry operation carrying evidence** (auditable years later), and
**every arrow except the last is reversible by a cheaper operation than
the one that caused it** — promotion is expensive and careful, rollback
is cheap and instant. That asymmetry is what makes the pipeline safe to
run often.

---

## Part 6 — Customer fine-tuning philosophy **[PROD] [PLAT]**

The future product ("bring your data, own your model") is the flywheel
sold outward. Its philosophy, settled now:

- **Ownership:** a customer fine-tune is an **org-owned artifact** —
  full lineage, same identity machinery (identity §8). The customer owns
  the artifact's use and its fate; IntelliAI owns the base lineage it
  derives from; the lineage record makes the boundary precise and
  license inheritance computable.
- **Privacy:** their data trains *their* model, period. Never pooled,
  never leaked into platform models, never used to improve anything else
  — unless a *separate, explicit* consent (AI_STRATEGY §2) says
  otherwise. The default is total isolation; pooling is an opt-in
  product, not a default.
- **Isolation:** tenancy at every layer — their artifacts invisible
  outside their org (registry law 9), their traffic the only traffic
  routable to their models, adapter-composition serving isolated per
  org, dedicated deployments available where shared serving is
  unacceptable.
- **Evaluation:** their model passes through the *same pipeline* (Part
  5), with roles split: **quality floors are theirs to accept** (we
  report honestly; they decide if +1.2% is worth shipping), **safety
  floors are ours to enforce** (a customer artifact that fails platform
  safety gates does not deploy, regardless of their acceptance — our
  serving, our responsibility).
- **Billing:** three meterable moments, all citing registry identities —
  training (the job), hosting (the artifact/deployment), inference (a
  premium over the base public model's unit price). No architecture
  needed beyond what metering (M4) and the registry already define.
- **Consent:** the training-consent architecture applies doubly — their
  *own* data used for their *own* model still gets recorded consent
  (scope: this model), because "obviously they consented" is exactly the
  assumption the constitution forbids.
- **Lifecycle:** same ML lifecycle underneath; the customer sees a
  simplified projection (training → ready → live → retired). Their
  retirement requests follow data-rights flows: weights deletable,
  lineage records retained for audit (identity rule 9).
- **Why the same constitution:** a second, softer registry for customer
  models would fork identity, drift immediately, and betray the
  customers most likely to pay — enterprises choose vendors whose rigor
  provably applies to *their* assets too. The constitution applying
  uniformly *is* the enterprise pitch. And operationally: one pipeline
  serving both us and customers means every customer fine-tune
  stress-tests the machinery our own models depend on.

---

## Part 7 — Risk analysis **[ML] [BUS]**

| Risk | Nature | Mitigation (structural where possible) |
|---|---|---|
| **Catastrophic forgetting** | domain tunes destroy general competence | full-matrix regression suites; hard no-regression gate at promotion; replay/mixed curricula as standard recipe; Stage 3 consolidation exists partly for this |
| **Overfitting to the wedge** | wedge wins that collapse off-distribution | held-out diversity suites alongside segment suites; shadow stage catches distribution surprise before customers do |
| **License contamination** | one NC dataset/parent poisons a lineage | verdicts computed through the DAG at artifact birth (identity rule 6) — structural, already law; dataset admission ceremony (Part 3) |
| **Dataset contamination** | eval or benchmark data leaks into training | mandatory dedup/near-dup checks against all frozen eval sets before every run (P5); eval sets never touched by training pipelines — separate custody |
| **Evaluation leakage** | training pipelines "see" eval distributions indirectly (synthetic data generated from eval-adjacent sources) | generator lineage recorded on synthetic datasets; leakage review in dataset admission |
| **Benchmark gaming** | optimizing the number, not the quality (Goodhart) | internal suites are private and *rotating*; public claims cite public benchmarks; the two never mix (a private win is a hypothesis, a public win is a claim); suite versions retired on suspicion |
| **Research debt** | orphan checkpoints, unregistered experiments, irreproducible wins | `experimental`/`temporary` artifacts auto-expire; graduation is the only crossing (registry §6); reproducibility as birth requirement — the debt is refused, not managed |
| **GPU cost explosion** | training spend outrunning revenue | ladder gates each stage on the previous one's ROI; rented/spot compute until utilization justifies owned; efficiency-first culture (the DeepSeek lesson); distillation as standing cost-control |
| **Model sprawl** | dozens of half-maintained artifacts | portfolio reviews per family (identity §1b); Stage 3 consolidation; every production artifact carries an owner and a successor plan; archival policy enforced |
| **Upstream rug-pull** | license/direction shift on a base lineage | FOUNDATION_MODELS §14 protocol: pinned immutable imports, warm backups per capability, watch triggers reviewed at milestone closes |
| **Knowledge concentration** | (solo-founder reality) recipes living in one head | reproducibility records double as knowledge management — P7 means the *company* knows what its founder knows; recipes are artifacts of the process, not tribal memory |

---

## Part 8 — Build vs. buy: decade-stable principles **[BUS] [ML]**

First, the frame that prevents the question from being asked wrongly:
**capabilities are tiered, and the tier decides the default.**

- **Wedge capabilities** (where differentiation lives — currently speech
  in Indic/domain segments): climb the ladder aggressively; this is
  where tuning capital compounds into moat.
- **Strategic capabilities** (needed excellent, not needed *ours* —
  currently chat, embeddings): tune selectively where evals show paying
  gaps; otherwise ride the best upstream and spend the savings on the
  wedge.
- **Commodity capabilities** (needed present — currently e.g.
  moderation, rerank): serve upstream, monitor, do not tune. Tuning
  capital is the scarcest resource in the company; spending it on
  commodities is how model companies die of sprawl.

Tiers are reviewed, not permanent — today's commodity is tomorrow's
wedge if the market moves. Then, the decision rules:

- **Fine-tune** when evaluation shows a paying gap that upstream won't
  close, rights-clean data exists to close it, and the capability's tier
  justifies the spend.
- **Distill** when quality is already won and cost/latency is the
  binding constraint — or when upstream-independence insurance is worth
  the run.
- **Merge** rarely, and only evidence-heavy: merging is the least
  reproducible, least explainable derivation (identity flags it as the
  riskiest); it must beat both parents on the full matrix, not average
  them.
- **Replace** a lineage only through Part 4's switching test — beating
  our tuned incumbent by more than the switching cost — or on its
  override triggers.
- **Retire** when the portfolio review shows maintenance cost exceeding
  measured value; retirement is a decision with a date and a successor,
  never an entropy state.
- **Continue upstream** when the tier says commodity, when upstream's
  cadence is outrunning our gap (why tune what next quarter's base
  fixes free?), or when the data to tune with doesn't rightfully exist —
  the absence of rights-clean data is a full stop, not an obstacle.

---

## Part 9 — Five-year strategic evolution **[BUS]**

Growth described in capability terms, deliberately unmapped from
milestone numbers (milestones move; the sequence doesn't):

- **Year 1 — Measure.** Full serving across the speech wedge; evaluation
  harness live and trusted; baseline suites per segment; first adapter
  experiments proving the training loop end-to-end. Assets: eval suites,
  telemetry, first commissioned data campaign. Revenue: serving only.
- **Year 2 — Win the wedge.** Domain fine-tunes become routing defaults
  in wedge segments; first *published* wedge benchmarks; customer
  fine-tune pilots (design partners); data campaigns industrialize.
  Assets: named lineage artifacts customers can feel; the switching test
  survives its first upstream release cycle. Revenue: serving + early
  dedicated deployments.
- **Year 3 — Consolidate and compress.** Multi-domain speech models
  retire specialist sprawl; distilled `-lite` tiers ship the free-tier
  economics; language capabilities live on tuned open bases where evals
  justify; customer fine-tuning productizes. Assets: the portfolio has
  fewer, stronger models; recipes are a library. Revenue: serving +
  fine-tuning product + tier spread.
- **Year 4 — Go native where it pays.** First IntelliAI-native model in
  the modality where data moat is deepest and model scale smallest
  (speech, on current physics); document/vision tunes where P4-phase
  traffic justifies; continued-pretraining experiments in language.
  Assets: a lineage with nothing above it. Revenue: margin expansion
  from owned models.
- **Year 5 — Majority-owned wedge.** Most wedge traffic served by
  `intelliai-*` lineage artifacts; native small-model portfolio in
  speech; selective language ownership via continued-pretrain; the
  fine-tuning platform is a first-class revenue line and a data-moat
  engine (every customer model deepens the recipe library). The company
  the roadmap promised: distribution and models, each feeding the other.

The honest dependency: each year's plan assumes the previous year's
evaluation verdicts *supported* it. This roadmap bends to measurement —
that is not a caveat, it is the method.

---

## Part 10 — The Fine-Tuning Constitution **[ALL LAYERS]**

Timeless by construction; each survives the disappearance of every 2026
model, vendor, and architecture.

1. **Serve before you train; measure before you improve.** Distribution
   and evaluation are preconditions of training, never afterthoughts.
2. **No license clarity → no training.** Rights are verified before
   compute is spent — for bases, for datasets, for generators of
   synthetic data — and verdicts compute through lineage.
3. **No evaluation → no deployment; no regression → no promotion.**
4. **Customer data is never assumed to be training data.** Consent is
   explicit, scoped, recorded, and revocable-forward — even for the
   customer's own model.
5. **Training creates artifacts; evaluation creates trust; neither
   substitutes for the other.** Every run ends in a registered artifact
   or a recorded failure — orphan weights do not exist.
6. **Reproducibility is the product of the training system; weights are
   a byproduct.** What cannot be rebuilt cannot be promoted — and the
   record is also how the company outlives any single memory.
7. **Fine-tuning capital compounds within a lineage; spend it where the
   wedge is.** Tiers decide defaults; commodities ride upstream.
8. **Challengers beat the tuned incumbent or they wait.** Novelty pays
   the switching cost; the incumbent never pays a novelty tax.
9. **Models depreciate; data, evaluations, and recipes appreciate.
   Invest in the appreciating assets.**
10. **Efficiency before scale.** Distill, compress, and consolidate
    before buying more compute; sprawl is a decision, not an accident —
    every production model has an owner and a successor plan.
11. **Internal evaluations are private and rotating; public claims cite
    public benchmarks; the two never mix.**
12. **Customer models obey the same constitution as ours.** Same
    identity, same gates, same pipeline — rigor applied uniformly is
    both the safety property and the enterprise pitch.
13. **Research fails freely outside production; only graduation
    crosses.** The boundary protects both sides.
14. **Native models are ordinary artifacts.** When IntelliAI trains its
    own, the platform must not be able to tell — no shortcuts, no
    special lanes, no pride-driven gates.
15. **The ladder is climbed per capability, gated on measured ROI, and
    descended without shame.** Retreating from a rung that isn't paying
    is portfolio management, not failure.

---

## Self-review

**Weaknesses identified:**

1. **Capacity asymmetry.** The ladder assumes training capacity that a
   solo founder does not have; Years 1–2 are deliberately
   platform-heavy, but even Stage 1 competes with platform milestones
   for the same hands. The mitigation is honesty in sequencing (the
   ladder gates, Part 2), not optimism.
2. **The wedge is still a hypothesis.** Everything routes through "the
   Indic/domain speech wedge pays" — which telemetry and evals have not
   yet tested. Part 9's dependency note is the safety valve; the
   strategy bends to measurement, but a bent strategy still costs the
   time spent on the wrong wedge.
3. **Data acquisition costs are stated, not sized.** Commissioned
   recording campaigns are the dominant Stage-2 cost and this document
   deliberately avoids currency figures — meaning the first campaign
   will produce the platform's first real unit-economics shock. Plan for
   the shock, not against it.
4. **Stage 5's feasibility rests on speech models staying small.** If
   the modality's frontier moves to large unified audio-language models,
   the native rung's economics change class. The ecosystem-independence
   rule is honored (the *ladder* survives), but the Year-4 projection
   would slip.
5. **Two-hat governance.** Several pipeline approvals separate roles
   (product vs ML) that are currently one person. The separation is
   still worth recording — it is the org design the company grows into,
   and the ceremony keeps the two hats honest meanwhile.

**Assumptions registered:** wedge economics (above); open-weights
ecosystem continuing to produce permissive bases (FOUNDATION_MODELS
watch-triggers cover the erosion case); rented GPU compute remaining
available at startup-viable prices; evaluation harness (M9) landing
before any Stage-2 spend; consent-based data acquisition remaining a
competitive advantage rather than a universal norm (if everyone becomes
clean, the moat shifts to data *quality* — acceptable).

**Future review triggers:** first eval-harness results contradicting the
wedge hypothesis → re-tier capabilities; any base-lineage license shift →
Part 4 override path; GPU price regime change (either direction) →
re-gate Stages 2–5; a competitor publishing better wedge benchmarks →
accelerate or re-aim Stage 2; customer fine-tune pilot demand exceeding
plan → pull Part 6 productization forward; two consecutive portfolio
reviews showing sprawl growth → enforce Stage 3 before any new Stage 2.

**Layer check (required by the brief):** Parts 1, 9 are business
strategy; Parts 2, 3, 4, 7 are ML strategy with business gates; Part 5 is
platform architecture (by reference, not redesign); Part 6 is product
philosophy on platform rails; Stage-5 scoping and Part 8's research
notes are research philosophy. No layer smuggles conclusions into
another: every business claim cites a measurable gate, every ML claim
cites an evaluation, every platform claim cites an existing architecture
document.

---

*Change log:*
- *2026-07-31 — v0.1: initial fine-tuning strategy (M1.5 D8): philosophy,
  per-capability ladder (Stages 0–5), constructive data strategy,
  switching-test framework, promotion pipeline semantics, customer
  fine-tuning philosophy, risk register, capability tiers and build-vs-buy
  rules, five-year evolution, 15-principle constitution, self-review.
  Pending approval.*
