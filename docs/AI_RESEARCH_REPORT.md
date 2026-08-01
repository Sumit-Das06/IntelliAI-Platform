# IntelliAI — Consolidated AI Research Report

| | |
|---|---|
| **Status** | APPROVED 2026-07-31 (M1.5 D9) — synthesis snapshot; risk register (Part 7) reviewed at every milestone close; indexed at [STRATEGY.md](STRATEGY.md) |
| **Version** | 0.2 |
| **Research date** | 2026-07-31 (all license and model facts verified at source on this date; they decay from this date forward) |
| **Audience** | A future CTO. A first ML engineer. An investor in diligence. The founder, two years from now, wondering why things are the way they are. |
| **Role** | The synthesis. [AI_STRATEGY.md](AI_STRATEGY.md) is the constitution; [CAPABILITIES.md](CAPABILITIES.md) the map; [FOUNDATION_MODELS.md](FOUNDATION_MODELS.md) the bets; [MODEL_IDENTITY.md](MODEL_IDENTITY.md) and [REGISTRY_V2.md](REGISTRY_V2.md) the machinery; [FINE_TUNING_STRATEGY.md](FINE_TUNING_STRATEGY.md) the climb. This report connects them — cause to effect, decision to forced decision — and says where the whole thing is going. It repeats nothing it can reference. |

---

## Part 1 — Executive Summary

**Why this company exists.** IntelliAI is a developer-first AI platform —
one account, one key, one coherent API for speech, then language, vision,
and documents — being built by one person from an empty folder into a
commercial SaaS, and designed from its first database table to become
something rarer: a company that *owns the models it serves*. The market
gap is real and documented (PRD §5): speech specialists stop at speech,
generalists treat speech as a checkbox, and almost nobody offers coherent
multi-domain APIs with honest benchmarks, transparent pricing, and model
choice. The deeper opportunity is structural: the industry's value is
migrating from *having a model* (commoditized monthly by open releases)
to *owning distribution, evaluation, and data in a defensible segment* —
and a platform is the machine that acquires all three.

**Why serve before training.** Because training without distribution is a
research lab with a burn rate. Serving acquires the three assets no
amount of GPU spend can buy: customers whose traffic reveals what is
worth training; evaluation baselines that turn training from gambling
into engineering; and revenue that buys compute without selling the
company. Every admired reference point — Sarvam, OpenAI, ElevenLabs —
ran some version of this sequence: distribution first, then models, with
the platform funding and aiming the research. The sequence is forced,
not aesthetic (FINE_TUNING_STRATEGY Part 1).

**Why become a model company at all.** Margin and moat. A pure serving
platform earns distribution margin on commodity inputs forever, and its
COGS are set by upstream licensing weather. A platform that gradually
replaces upstream models with its own fine-tuned — eventually native —
lineages in a chosen wedge converts its usage into training data, its
serving bills into efficiency expertise, and its benchmarks into
marketing, none of which competitors can download. The wedge hypothesis
(Indic-language and domain-specific speech first) follows Sarvam's
validated pattern while targeting segments the global leaders
demonstrably neglect — the 2026 research found the top English ASR
models within one WER point of each other *and* almost uniformly devoid
of Indic coverage. Differentiation has moved to exactly where we aimed.

**Why the platform itself is moat.** Four compounding loops live inside
it: (1) the *identity loop* — engine-blind contracts and registry
routing mean every model improvement ships silently, so quality
compounds without customer churn; (2) the *data loop* — consent-clean
telemetry and opt-in corpora turn traffic into targeting and training
material; (3) the *trust loop* — the same gates (license, evaluation,
tenancy) that discipline our models become the enterprise pitch when
customers bring theirs; (4) the *economics loop* — CPU-first serving of
small, efficient models funds a generous free tier, which feeds
distribution, which feeds everything else. None of these is a feature; a
competitor cannot add them to an app in a quarter. They are the
architecture — and they were built in Milestones 0–1 before the first
model was ever served, which is why M1.5's strategy could be adopted
without refactoring anything.

**Where this goes.** Five years out (FINE_TUNING_STRATEGY Part 9): a
platform serving a dozen capabilities behind stable `intelliai-*` names;
the wedge majority-served by IntelliAI-lineage artifacts, including the
first native small speech models; a fine-tuning product where customers
own their artifacts under the same constitution we obey; and published,
reproducible wedge benchmarks as the marketing engine. The strategy's
defining property is that it *bends to measurement* — every stage gates
on evaluation verdicts, and the roadmap explicitly re-aims when the
numbers disagree with the plan.

## Part 2 — The 2026 landscape, as directionality

Seven movements matter more than any company list:

1. **Permissive licensing became the challenger's weapon — and the
   incumbent's discard.** Labs using open weights as distribution
   strategy (Alibaba, DeepSeek, Mistral, IBM, Zhipu) converged on
   Apache-2.0/MIT; Meta retreated toward closed; and a repeating
   pattern emerged of smaller labs *hardening* licenses after traction
   (Fish Audio, MiniMax, Kimi, Spark-TTS). Consequence: open models are
   abundant, but license *stability* is now a first-class selection
   criterion — which forced our per-artifact-verdict rule (Part 9.4).
2. **The frontier moved into small models.** 2026's best open ASR and
   OCR sit at 0.6–2B parameters; SOTA TTS at 82M–500M. Quality-per-
   parameter is collapsing downward — which vindicates CPU-first
   serving economics near-term and makes native speech models (Stage 5)
   startup-feasible.
3. **Everything is becoming an LLM.** ASR decoders, translation, OCR,
   and TTS are all migrating onto language-model backbones; dedicated
   architectures are being displaced modality by modality. Consequence:
   serving class K (token servers) will eventually gravitate most
   capabilities toward itself, and multi-capability artifacts (identity
   v0.2) will be the norm, not the exception.
4. **Leaderboards compressed; differentiation moved.** Top-10 English
   ASR spans <1 WER point. The competitive axes now are language/domain
   coverage, cost, latency, and trust — all axes where a wedge-focused
   platform can beat giants.
5. **Streaming went native.** Real-time-first architectures (in ASR and
   TTS both) stopped being exotic. Our contract-v2 streaming plan and
   serving class R have a maturing model ecosystem to land on.
6. **Sovereign AI arrived with funding.** IndiaAI-backed Sarvam released
   Apache Indic LLMs; the EU funds its own stacks. This validates the
   wedge and arms competitors in it simultaneously — a timer on our
   Stage-2 execution.
7. **Evaluation entered crisis.** Contamination, benchmark gaming, and
   leaderboard fitting are now openly documented. Private, rotating,
   customer-distribution evals — exactly what M9 builds — quietly became
   one of the few trustworthy quality signals an AI company can own.

## Part 3 — IntelliAI's position

Four categories, one honest placement:

| Category | Their moat | IntelliAI today | IntelliAI in five years |
|---|---|---|---|
| Application companies | UX on rented models | not us | not us |
| API providers | DX + serving economics | **us — deliberately** | still the revenue engine |
| Infrastructure platforms | serving other people's models at scale | partially (our own infra only) | not the destination — distribution business |
| Foundation-model companies | model IP + data + distribution | not yet | **us — in the wedge** |

The five-year position is **selectively full-stack**: a model company
where the wedge is (speech, Indic/domain segments — own lineages, own
data, published wins) and a best-of-open API provider everywhere else
(capability tiers, FINE_TUNING_STRATEGY Part 8). This asymmetry is the
strategy: full-stack everywhere is capital fantasy; full-stack nowhere
is a commodity distributor. The registry is what lets one platform be
both at once without customers seeing a seam.

## Part 4 — Capability roadmap, with reasons

Synthesis of CAPABILITIES.md §6 — the *why-then* column is the part that
matters here:

| Family | When (phase) | Business value | Difficulty | Why exactly there |
|---|---|---|---|---|
| **Speech** (STT→TTS→diarization→streaming) | P1–P2, now | wedge revenue; the flywheel's first fuel | moderate (serving class T exists after M2) | smallest models, clearest gap, deepest permissive-license arsenal, founder-feasible compute |
| **Language** (chat, embeddings, rerank, translation, moderation) | P3, yr 2–3 | the composite layer's engine; retrieval revenue | high — GPU economics arrive (class K) | can't come earlier (capital), can't come later (every composite depends on chat's gravity) |
| **Vision** (OCR, image understanding) | P4, yr 3–4 | document pipelines; enterprise pull | moderate — reuses T+K and media ingestion | infrastructure payoff phase: nothing new needs building |
| **Document intelligence** | P4, composites | highest enterprise willingness-to-pay | pipeline engineering, not new models | needs OCR *and* chat excellent first — composites ship after their primitives |
| **Agents** | P5, yr 4–5 | lock-in surface; every capability becomes a tool | high (state, safety, sessions) | the integration payoff — worthless until the tools it composes are excellent |
| **Realtime voice** | P5 | premium UX tier | high (class R at scale) | needs streaming STT+TTS+chat simultaneously mature |

## Part 5 — The model bets, and why

FOUNDATION_MODELS.md holds the scores; this is the reasoning layer:

- **Whisper (STT primary)** — chosen *against* the 2026 leaderboard,
  because the top five English models sit within a point of each other
  while Whisper alone offers MIT + 99 languages + the largest
  fine-tuning ecosystem in ASR history. We are buying a lineage to
  compound tuning capital in, not a checkpoint (the switching test,
  FINE_TUNING Part 4, was born from this decision).
- **Kokoro (TTS serving)** — the forced move: Piper's archival and GPL
  fork ended the original M3 plan; Kokoro is Apache, Hindi-capable,
  CPU-real-time, and better. **Chatterbox (TTS ownership)** — because
  Kokoro cannot be trained or cloned, the serving pick and the ownership
  lineage split: MIT, zero-shot cloning (the P2 product), corporate
  cadence. **IndicF5** — the wedge lineage with consent-clean data, a
  property our own data constitution rewards.
- **The Qwen ecosystem (chat, VLM, embedding, rerank, moderation
  primary)** — one Apache family with a full size ladder, top-tier
  quality, the largest fine-tune ecosystem, and real Indic strength.
  Concentration is embraced *with a protocol* (warm non-Qwen backups in
  the registry, watch triggers, pinned imports) rather than avoided —
  for a solo founder, one serving stack and one toolchain is the
  difference between shipping and drowning.
- **PaddleOCR-VL (OCR)** — the only verified-permissive model combining
  SOTA-tier document parsing with 109-language coverage including Indic
  scripts; **Qwen3-VL (vision)** — Apache at every size and the substrate
  the OCR-specialist ecosystem itself fine-tunes on.
- **pyannote / Sortformer-streaming / Silero** (diarization/VAD),
  **IndicTrans2 + LLM-MT routing** (translation), **Qwen3Guard +
  Granite Guardian** (moderation) — each chosen where license + wedge +
  serving class aligned.
- **The intentional rejections are the strategy's proof.** Nine
  category-leading models were rejected — the best English ASR
  (English-only+GPU), the #1 embedder and rerankers and diarizer and MT
  model (all non-commercial), the WMT25 winner (unverifiable license),
  the best handwriting OCR (revenue-capped) — because a benchmark
  summary optimizes for a demo, and this document optimizes for a
  company. "No license verdict, no traffic" was applied *before* the
  first inference, which is exactly when it is cheap.

## Part 6 — The flywheel, and why every stage compounds

```
customers → platform → telemetry → evaluation → datasets →
fine-tuning → registry → deployment → better product → more customers
```

The loop is AI_STRATEGY §1; what synthesis adds is *where the compounding
actually lives*: each stage's output is a **durable asset that makes the
next revolution cheaper**, not just a handoff. Customers compound
distribution (integration is sticky). Telemetry compounds targeting
(every request refines the gap map at zero marginal cost). Evaluation
compounds trust (suites pay out on every future run, including runs they
prevent). Datasets compound moat (rights-clean data appreciates while
weights depreciate). Fine-tuning compounds recipes (lineage knowledge
transfers within a family — the switching test exists to protect this).
The registry compounds *safety* (every promotion makes the next one more
routine: evidence templates, rehearsed rollbacks). Deployment compounds
economics (every cost lesson feeds tiers and the free tier feeds
distribution). The wheel's designed property: **no stage requires heroics
once built — every stage is a recorded, gated, repeatable operation** —
which is what lets one person, then a small team, spin something this
large.

## Part 7 — Strategic risk register (consolidated)

| Risk | Likelihood | Impact | Mitigation | Review trigger |
|---|---|---|---|---|
| Upstream license shifts | **High** (observed repeatedly in 2026) | Medium (capped: releases are irrevocable) | pinned imports; per-artifact verdicts; warm backups (FM §14) | any watched-family license event; every milestone close |
| Wedge hypothesis fails | Medium | **High** — the strategy's aim depends on it | eval-first sequencing; roadmap bends to measurement | first wedge eval results vs. hypothesis |
| GPU economics of P3 | Medium | High (delays Language phase) | CPU-first revenue base; small-model trend (Part 2.2); rented compute | class-K unit economics at P3 planning |
| Solo-capacity overrun | **High** | Medium-High (schedule, not direction) | per-capability ladder gates; tiering protects focus; hire triggers | any milestone slipping >2× estimate |
| Evaluation quality (our own) | Medium | High — every gate cites it | private rotating suites; contamination checks; eval before training spend | M9 build; first gaming suspicion |
| Wedge-data scarcity/cost | Medium | Medium | commissioned campaigns planned, consent pipeline, CC-BY Indic corpora exist (BhasaAnuvaad etc.) | first campaign's unit-economics |
| Competition in the wedge (Sarvam et al., funded) | Medium-High | Medium (validates market too) | speed on Stage 2; publish benchmarks early; segments they neglect | competitor wedge-benchmark publications |
| Platform complexity outruns builder | Medium | High | boring-availability designs; ceremony-cheapness (registry weakness 5); strategy docs as the second brain | registry V2 implementation friction |
| Model sprawl | Medium (success-conditional) | Medium | portfolio reviews; Stage-3 consolidation; successor plans | 2 consecutive reviews showing growth |
| Research debt / irreproducibility | Low (structurally refused) | Medium | birth requirements; graduation-only crossing | any unregistered production weight found |
| Vendor dependence (Qwen concentration) | Medium | Medium (capped by protocol) | §14 protocol; our fine-tunes shift dependency to our own lineage | Qwen license/cadence triggers |

## Part 8 — The load-bearing decisions of M1.5 (and before)

Eighteen decisions, each with the rejected road and the five-year test:

1. **Inference never in the gateway** (ADR-0002) — rejected in-process
   serving; still true in five years because workload physics don't
   change.
2. **Capability-shaped contracts, engine-blind** (ADR-0003, M2 design) —
   rejected per-engine integration; the precondition of every silent swap
   the next decade will perform.
3. **Provider independence as precondition of model ownership** (D1) —
   rejected "wrapper now, refactor later"; a leaked engine name forecloses
   the endgame permanently.
4. **Hardware-agnostic architecture, CPU-first deployment** (AI_STRATEGY
   §6, superseding ADR-0004's phrasing) — rejected CPU-first-as-identity;
   without it, D3 would have vetoed the GPU-native lineages the ladder
   later needs.
5. **Permissive-license gate, enforced structurally** (ADR-0005 → registry
   law 4) — rejected case-by-case judgment; 2026's license drift proved
   the gate must be code, not vigilance.
6. **Per-artifact-version license verdicts** (FM §15) — rejected
   family-level trust; born from observed mid-family license flips in
   *both* directions.
7. **Org-first tenancy extended to models** (ADR-0010 → identity §8) —
   rejected user-owned artifacts; a departing employee must never orphan a
   production model.
8. **Public models as versionless promises with sunset-bounded
   snapshots** (identity §2) — rejected checkpoint-named APIs; the naming
   layer is where brand accrues and swaps hide.
9. **Two lifecycles, one join** (AI_STRATEGY §5; registry law 8) —
   rejected a unified state machine; cadence mismatch would force churn or
   paralysis.
10. **Artifact immutability + lineage DAG** (identity §4) — rejected
    mutable model records; rollback, audit, and license computation all
    stand on this.
11. **The data/determinism bright line between artifact and build**
    (identity §5) — rejected quantization-as-derivation; keeps identity
    small while forcing per-build evaluation.
12. **Evaluation before deployment; evaluation_candidate as explicit
    stage** (P5; identity v0.2) — rejected trust-by-benchmark; "passed our
    suites" and "trusted with traffic" became separately auditable facts.
13. **Consent-default-off data constitution** (AI_STRATEGY §2) — rejected
    silent harvesting; it is simultaneously ethics, law (DPDP/GDPR), and
    the enterprise sales pitch.
14. **The registry as recording-gating-resolving control plane that never
    executes** (REGISTRY_V2) — rejected orchestrator-registry and
    off-the-shelf MLOps registries; authority and action separated so each
    can fail safely.
15. **The switching test / lineage compounding** (FINE_TUNING Part 4) —
    rejected newest-model-wins; tuning capital compounds within lineages,
    and the test prices novelty honestly.
16. **Capability tiers for tuning capital** (FINE_TUNING Part 8) —
    rejected tune-everything; commodity capabilities ride upstream so the
    wedge gets the compounding.
17. **Customer models under the same constitution** (FINE_TUNING Part 6)
    — rejected a softer second registry; uniform rigor is the enterprise
    product.
18. **Qwen concentration with protocol, not avoidance** (FM §14) —
    rejected both naive concentration and reflexive diversification;
    operational focus for a solo founder, hedged by warm backups and
    irrevocable Apache imports.

## Part 9 — What the research changed

| Original assumption | Research result | New conclusion | Roadmap impact |
|---|---|---|---|
| Piper is the M3 TTS engine (locked 2026-07-29) | archived Oct 2025; successor fork GPL-3.0, maintainerless | **Kokoro serves; Chatterbox owns; IndicF5 for the wedge** | M3 scope + PRD v0.4 table change at M1.5 close |
| Newest strong ASR would displace Whisper | top-10 within 1 WER pt; none match Whisper's license+languages+FT ecosystem | Whisper stays; Qwen3-ASR named successor-lineage | M2 unchanged — validated, not assumed |
| CPU-first as platform philosophy | GPU-native lineages among the best; small-model trend favors CPU anyway | hardware-agnostic architecture, CPU-first *deployment* | ADR supersession at close; D3 scoring unblocked |
| License checked once per family | licenses flip mid-family, both directions, repeatedly | per-artifact-version verdicts, verification evidence recorded | Registry V2 hard requirement |
| Registry = routing table (V1 vision) | customer-owned artifacts, lineage, gates, tenancy all converge on it | registry = control plane (record/resolution planes, operations, laws) | Registry V2 architecture (D5) |
| Speech translation needs a native model eventually soon | zero commercially-usable open native S2ST exists (all NC) | composite-first is the *only* clean path; clean datasets (CC-BY) exist to train our own later | validates D2's composite design |
| Reasoning/agents as capabilities | shape analysis: same contracts as chat / platform feature | demoted to chat-tier + platform runtime | capability list stays at 11 primitives |
| Moderation as a later add-on | every generative capability needs it internally; only two clean options exist (both verified) | promoted to primitive, dual-use from birth | P3 scope |
| Sarvam as distant reference | released Apache 30B/105B Indic LLMs (IndiaAI-funded), Feb 2026 | wedge validated *and* armed; their models = evaluation baselines to beat, not bases to build on | Stage-2 urgency; eval-baseline list |
| One model family per capability, chosen independently | one Apache family (Qwen) tops or seconds seven capabilities | concentration-with-protocol as explicit strategy | FM §14; serving-stack consolidation |

## Part 10 — Reading this in 2031

**Likely to have been right** (they encode physics or law, not fashion):
the engine-blind contract; the registry as control plane; artifact
immutability and lineage; consent-default-off; evaluation gating;
public-model naming; the two lifecycles; serving-before-training. If the
company exists in 2031, these are why swaps, audits, and pivots were
cheap.

**Most likely to have failed or bent:** every *specific model name* in
FOUNDATION_MODELS (by design — the bets are replaceable, the framework
is not); the assumption that speech models stay small (if unified
audio-language giants win the modality, Stage 5's economics change
class); the CPU-first cost edge beyond P3 (GPU/accelerator economics
move fast in both directions); the five-year *pace* (solo capacity is
the tightest constraint and the least modeled); possibly the Indic wedge
itself (the market may be won or transformed before Stage 2 lands —
the bend-to-measurement rule exists for exactly this).

**Technologies likely to be unrecognizable:** today's serving engines
and quantization formats (the *build* abstraction absorbs their
churn — that is why builds aren't identity); adapter mathematics
(LoRA-the-technique vs adapter-the-concept — identity deliberately
recorded the concept); separate-modality models (omni-consolidation is
visible now; multi-capability artifacts, identity v0.2, are the
prepared landing).

**Designed never to change:** the three constitutions (AI_STRATEGY §7,
REGISTRY_V2 §12, FINE_TUNING Part 10) — forty-odd laws written to be
checkable in any ecosystem era. The 2031 reader's fastest audit: pick
ten laws at random and grep the platform for their enforcement. Where
enforcement is missing, this report predicts the incident reports will
already exist.

## Part 11 — Recommendations

**Immediate (Milestone 2):**
1. Build M2 exactly as architecturally designed (runtime contract,
   registry V1, faster-whisper service, `/v1/models`) — the design
   survived D3 unchanged; *impact:* first revenue-capable capability;
   *depends on:* M1.5 close-out.
2. Close M1.5 properly: commit the seven strategy documents; ADR
   superseding ADR-0004; PRD updates (Piper→Kokoro, M1.5 in the version
   table); step-0 debts (Dependabot, dev-env rule — three milestones
   old); *impact:* the strategy becomes repo law, not chat history.
3. **Seed evaluation before M9** (new, from synthesis): the full
   harness lands at v0.9, but the wedge hypothesis and Stage-1 gates
   need baseline suites *years* earlier. Ship a minimal per-capability
   eval habit starting in M2 (fixed test clips, WER/RTF measured per
   release). *Impact:* the flywheel's ignition moves early at near-zero
   cost; *depends on:* nothing — that is the point.
4. Re-verify the flagged-license list (FM §15.3) before any adoption
   step; *impact:* closes the research's known decay points.
**Next year:**
5. First commissioned wedge-data campaign, sized deliberately small
   (unit-economics learning is the goal); *depends on:* eval baselines
   proving where data pays.
6. First adapter experiments (Stage 1) on wedge segments after eval
   baselines exist; *impact:* proves the training loop end-to-end
   through the promotion pipeline.
7. M3 with Kokoro; voice-cloning groundwork (consent ceremony design)
   on the Chatterbox lineage.
**2–3 years:**
8. Domain fine-tunes as routing defaults; first *published* wedge
   benchmarks; customer fine-tune design partners; GPU tier for class K
   when Language-phase economics clear; *depends on:* Stage-1 exits.
**5 years:**
9. Native speech model program, gated on all four Stage-5 entry
   criteria; fine-tuning platform GA; *depends on:* everything above,
   in order, with the gates honestly kept.

## Part 12 — Self-review: the case against this report

**Weak assumptions, named:** the wedge is unvalidated by any customer
evidence — PRD personas are hypotheses, and no discovery interviews
exist yet; the five-year pace assumes a hiring curve that is nowhere
modeled; data-campaign economics are deliberately unsized (FINE_TUNING
self-review) and the first real quote may reprice Stage 2.

**Research gaps:** TTS evaluation methodology (MOS-proxy design) is
undesigned while two TTS decisions already lean on "quality tiers";
serving-class K operational knowledge is zero (no vLLM-class experience
in-house yet — P3's risk is practical, not conceptual); legal review of
the Gemma-terms *class* of licenses (commercial-with-flow-down) is
recommended before any such model is adopted; regulatory mapping
(DPDP/EU-AI-Act obligations per capability) has a placeholder, not an
analysis; streaming contract v2 is a named intention with no design.

**Unknowns that resist mitigation:** whether open-weights abundance
persists past the current strategic fashion; whether the wedge's window
outlasts our Stage-2 timeline; where speech-model scale actually goes.

**Biases, honestly:** **single-author bias is the big one** — every
document in this stack, including this critique, comes from one
mind-pair (founder + one AI assistant) that has agreed with itself for
nine deliverables. The gates were real but the reviewers were not
independent. Mitigation, concrete: the first ML hire's onboarding task
should be a structured red-team of this stack; investor diligence should
be *welcomed* as free adversarial review. Also present: recency bias
(research verified on one date, decaying since), survivor bias in the
company comparisons (Part 1 cites winners; the graveyard of
platform-then-model companies is unexamined), and optimism bias endemic
to founder documents — the risk register (Part 7) is the antidote only
if its triggers are actually reviewed at every close.

**Contradictions found across the stack (and their resolutions):**
ADR-0004's "CPU-first" phrasing vs AI_STRATEGY §6 — resolved by the
pending supersession ADR (close-out item); AI_STRATEGY §4 listing
"quantized" as a derivation vs identity §5's bright line — identity
v0.2 supersedes, noted in both; PRD v0.4's roadmap table still names
Piper for v0.4-TTS — must change at close; ARCHITECTURE.md's forward
map predates M1.5 and needs its one-line update. No deeper
contradictions found — the stack was written in sequence against itself,
which is exactly why the independent-review recommendation above
matters.

**What should change before Milestone 2:** nothing architectural — M2's
design survived the entire strategy layer unchanged (the strongest
validation this process produced). Three process items: the eval-seed
habit (Rec. 3), the license re-verification pass (Rec. 4), and the
close-out documentation debt (Rec. 2). M2 is cleared for opening upon
M1.5 approval.

**Future review triggers for this report itself:** each milestone close
(risk-register sweep); any Part 9-class discovery (an assumption
invalidated by the world); the first ML hire (red-team); and a full
re-synthesis no later than the v1.0 launch review.

---

*Change log:*
- *2026-07-31 — v0.1: consolidated research report (M1.5 D9) —
  synthesis of the nine-document strategy stack: executive case, 2026
  directionality, position, roadmap reasoning, bet rationale, flywheel
  compounding, consolidated risk register, 18 load-bearing decisions,
  10 research-driven changes, 2031 outlook, staged recommendations,
  adversarial self-review. Pending approval.*
