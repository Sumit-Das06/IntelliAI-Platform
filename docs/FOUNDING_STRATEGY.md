# IntelliAI — Founding Strategy Review

| | |
|---|---|
| **Status** | APPROVED 2026-07-31 (M1.5 D10) — Part 11 extracted to [CONSTITUTION.md](CONSTITUTION.md), which is canonical; indexed at [STRATEGY.md](STRATEGY.md) |
| **Version** | 0.2 |
| **Last updated** | 2026-07-31 |
| **Premise** | It is Day 0. IntelliAI does not exist. Everything learned in M1.5 is known; nothing built is sacred. One chance to found the company correctly. Previous documents are *evidence here, not authority* — this document is allowed to overturn any of them. |

---

## Part 1 — The Fundamental Question

**Would I build the same company? Yes. Would I build it the same way?
No — three things change, and naming them honestly is this document's
first duty.**

**What survives untouched:** the destination (a selectively full-stack
model company grown out of a serving platform), the wedge logic, the
engine-blind architecture, the constitution-based governance, and the
serve→measure→train sequence. M1.5's research validated these harder
than the original intuition deserved: the Piper collapse proved
research-before-building pays cash; the license minefield proved the
gates must be structural; the leaderboard compression proved the wedge
was aimed at the right axis. These were bets in July; they are evidence
now.

**Change 1 — Customer discovery runs from Day 0, as a parallel thread
with the same discipline as engineering.** The single largest defect in
the company as actually built: nine strategy documents, ninety-six
tests, zero customer conversations. The personas are fiction. The wedge
is a research conclusion, not a market observation. On Day 0, the
company runs two loops from the first week — the build loop (as
executed) and a discovery loop (ten conversations per milestone with
developers who ship speech features; a public waitlist landing page as a
demand instrument; pricing conversations *before* pricing decisions).
The architecture would not change — but its *confidence intervals*
would, and Stage-2 data spending would aim at observed, not inferred,
segments.

**Change 2 — Evaluation is seeded on Day 0, not scheduled for v0.9.**
The strategy leans everything on evaluation gates, and then the roadmap
places the harness at M9. The synthesis already caught this
(AI_RESEARCH_REPORT Rec. 3); Day 0 makes it constitutional: the first
capability ships with a fixed eval clip-set and a measured baseline, and
every release re-measures. An evaluation habit costs nearly nothing at
birth and is unaffordable to retrofit culturally.

**Change 3 — The documentation-to-demo ratio gets a governor.** The
strategy stack is genuinely load-bearing — but a solo founder producing
nine architecture documents before the first model serves is also
exhibiting a known founder failure mode: architecture as comfortable
procrastination. On Day 0 the rule is: **every strategy document must
name the milestone that consumes it**, and no two consecutive milestones
may both be paperwork. (M1.5 passes this test — barely — because M2
consumes the runtime contract, the registry design, and the model
selections directly. The *next* strategy milestone would not pass it,
and none is planned.)

Everything else — examined below without protection — stands.

## Part 2 — The Company

**One sentence:** IntelliAI turns the world's best open AI models — and
eventually its own — into boring, reliable, honestly-benchmarked
developer infrastructure, starting with speech for the languages and
domains the giants neglect.

- **Mission:** make production AI boringly easy to consume — stable
  contracts, transparent prices, honest documentation, model choice.
- **Vision:** the developer platform where model quality compounds
  silently behind names customers never have to migrate off — and where,
  in its wedge, the models behind those names are IntelliAI's own.
- **Long-term purpose:** own the trust layer between fast-moving model
  research and slow-moving production software. Research churns
  monthly; production contracts last years; the company that absorbs
  that impedance mismatch — safely, measurably, cheaply — earns rent on
  every model generation without betting the company on any one of them.
- **Competitive advantage** (in order of durability): the wedge data and
  evaluation assets; customer-owned artifacts (the strongest lock-in in
  the stack — customers' own fine-tunes and voices live here); the
  identity/registry machinery that makes model succession free;
  CPU-efficient serving economics; OpenAI-compatible frictionless entry.
- **Why it deserves to exist:** because the alternative for its target
  customer is genuinely bad — speech specialists without platform
  breadth, generalists without speech depth, all with English-first
  quality cliffs, opaque model churn, and benchmarks nobody can
  reproduce. The gap is documented, the incumbents' incentives point
  away from it, and the timing (open-weights abundance, small-model
  frontier) makes a capital-light entry possible *now* in a way it was
  not three years ago and may not be three years hence.

## Part 3 — What We Will Never Build

Negative space, stated so future enthusiasm has something to collide
with:

1. **A consumer chatbot or general assistant** — consumer AI is a
   brand-and-capital war between giants; we sell to builders, not users.
2. **A frontier LLM** — pretraining at the frontier is a capital class
   this company will never occupy; the language strategy is derivation,
   permanently.
3. **A GPU cloud / compute reseller** — infrastructure resale is a
   margin knife-fight with hyperscalers; we buy compute, we do not sell
   it.
4. **An AI search engine** — different data, different moat, different
   war.
5. **Media generation (image/video/music)** — different market, serving
   physics, and moderation burden (CAPABILITIES §7); brand dilution for
   a developer-intelligence platform.
6. **Voice biometrics / identity claims** — regulatory and abuse surface
   disproportionate to value (CAPABILITIES §7); diarization yes,
   "who is this person" never.
7. **Surveillance and ad-tech applications** — incompatible with the
   consent constitution that the enterprise trust story depends on;
   trust is not segmentable.
8. **A custom-model consulting business** — services revenue is
   seductive at exactly the moments the platform needs focus; customer
   fine-tuning ships as *product* (self-serve, uniform constitution),
   never as bespoke engagements.
9. **White-label "AI features" agency work** — same trap, worse margins.
10. **A model marketplace** (unless the identity model's reserved grants
    mechanism is someday consciously activated) — hosting other people's
    commerce is a different company.
11. **Crypto/token anything** — no.

The pattern behind every refusal: each is either a *capital class we
cannot win*, a *trust posture we cannot mix*, or a *focus tax we cannot
afford*. The list is reviewed only at funding-stage changes — not at
every shiny opportunity.

## Part 4 — The Core Wedge

**The wedge: speech AI for Indic languages and underserved domain
segments (telephony, code-mixed speech, domain vocabularies) — served
globally, benchmarked publicly.**

Why this one: (a) the quality gap is measured, not imagined — 2026's
leaderboard leaders are within one WER point of each other in English
and nearly absent in Indic; (b) the model scale is founder-feasible —
speech models are small enough to fine-tune on rented single-digit GPUs
and eventually pretrain without frontier capital; (c) the permissive
data and model arsenal exists (MIT/CC-BY Indic corpora and lineages,
verified in D3); (d) the market is validated by a funded competitor
(Sarvam) whose success *proves demand* while their positioning
(sovereign, India-first, government-aligned) leaves room for a
developer-first, globally-served, honestly-benchmarked alternative;
(e) the founder's context (India-based, market-proximate) is an actual
edge — one of few a solo founder gets.

Why not the alternatives considered: *European languages* — crowded by
funded sovereign efforts and better-covered by incumbents; *enterprise
document AI first* — highest willingness-to-pay but demands trust and
sales capacity a Day-0 company lacks, and its primitives (OCR + chat)
arrive naturally in P3–P4 anyway; *realtime voice agents* — hot, but it
composes primitives we don't have yet; building the composite before the
primitives is building the roof first.

**Focus duration:** through Stage 2 of the ladder — until IntelliAI
fine-tunes are the routing defaults in wedge segments with published
benchmark wins and paying traffic — before any *wedge expansion* (new
language families, new domains). Estimated two years; governed by
measurement, not calendar. Capability breadth (P3–P5) is not wedge
expansion — the tiering rule (commodities ride upstream) exists
precisely so breadth never competes with the wedge for tuning capital.

## Part 5 — The Model Strategy, re-decided from zero

Re-examining each pillar as if unchosen, with M1.5's evidence on the
table:

- **Public model identity, provider independence, the registry, the
  ladder** — re-chosen without hesitation; these follow from the
  *company definition* (Part 2's impedance-mismatch purpose), not from
  any model-ecosystem fact, and would be chosen in any ecosystem era.
- **Whisper as STT primary** — re-chosen, with sharpened honesty: it is
  the right *first* lineage because its fine-tuning ecosystem and
  language breadth match the wedge, and the switching test now exists
  to unseat it the moment a challenger beats *our tuned* Whisper. Day-0
  difference: none in choice, one in posture — Qwen3-ASR is tracked as
  a named successor from the start, not discovered later.
- **Kokoro to serve / Chatterbox to own / IndicF5 for the wedge** —
  re-chosen; the serve/own split felt awkward when discovered and now
  reads as the honest shape of the TTS market (quality-per-cost and
  trainability currently live in different models). If one lineage
  later offers both, consolidation is one registry operation.
- **The Qwen concentration** — re-chosen *because of*, not despite, the
  Day-0 lens: a solo founder's scarcest resource is operational
  attention, and the concentration protocol (warm backups, watch
  triggers, pinned imports) prices the risk honestly. A funded 20-person
  company might diversify earlier; this one should not.
- **One genuine Day-0 sharpening:** the **evaluation-only baseline
  tier** gets founding-document status — Sarvam's open models, the NC
  quality leaders (F5, DiariZen, NLLB), and each capability's
  leaderboard head are enrolled as *measured baselines* from the first
  harness run. We legally cannot or strategically will not serve them —
  but the company's quality claims are only honest if it measures
  itself against the best that exists, not the best it ships.

## Part 6 — Business Strategy: how value actually accrues

**Revenue** stacks in maturity order: usage-metered API (the base, from
v0.5); tier spread (lite/standard/pro margins from distillation and
routing); dedicated deployments (enterprise, from P2–P3); the
fine-tuning product (training + hosting + inference premium — the
highest-margin line because the customer brings the data and takes the
lock-in).

**Margins** ride three curves that all bend the right way: small-model
frontier (quality-per-parameter falling), CPU/quantization efficiency,
and — later — owned models in the wedge removing upstream dependence
from the cost structure entirely.

**The moat, stated precisely.** Honesty first: this platform has **no
strong classic network effect** — customers don't benefit much from
other customers' presence. Claiming otherwise would be founder
self-deception. What it has instead: (1) **switching-cost asymmetry** —
free to enter (OpenAI-compatible), increasingly costly to leave
(accumulated evals, tuned models, owned voices); (2) **scale economies
in the flywheel** — data, evaluation, and recipe assets that compound
with traffic and are purchasable by no competitor; (3) **a trust
position** — consent-default-off, honest benchmarks, uniform
constitution — that is slow to build and *very* slow for a competitor
to copy credibly, because it must be true in the architecture, not the
marketing; (4) **customer-owned artifacts** — the closest thing to a
real network effect here: every customer model deepens the platform's
recipe library while binding that customer's differentiation to our
serving.

**How they interact:** distribution funds evaluation; evaluation aims
data; data trains models; models improve the product silently (identity
machinery); improvement widens distribution — while the trust position
gates the whole loop's *enterprise* tier, where the margins live. The
business is the flywheel with prices attached.

## Part 7 — Organizational Strategy

- **At 1 (now):** the documents are the org chart — constitutions play
  the role of the missing reviewers; ceremony must stay cheap enough to
  be real (REGISTRY_V2 weakness 5). The discipline that matters most:
  keeping the two-hat separations (product-vs-ML approvals) honest even
  when both hats share a head.
- **At 5:** the first ML engineer red-teams the strategy stack as
  onboarding (pre-committed in D9); roles begin matching the axes —
  someone owns the product axis, someone the engineering axis; the
  registry's operation log quietly becomes the team's shared memory;
  discovery loop gets a dedicated owner.
- **At 20:** teams align to the planes (control plane, data plane,
  ML/research) — and the architecture's boundaries become Conway's law
  run *forward*: the org chart follows the module boundaries instead of
  corrupting them. Registry ceremonies become real multi-party
  approvals without changing form — they were designed as if the team
  already existed.
- **At 100:** platform, product, research, and go-to-market orgs;
  regional deployments; compliance as a function. The constitutions are
  now the only thing preventing 100 people from re-litigating settled
  questions — their value has compounded a hundredfold from the day
  they governed one person.
- **What never changes:** the constitutions and their amendment
  discipline (supersede, never erase); org-first tenancy; the gates;
  the one-join rule between product and engineering identity.
- **Which decisions appreciate with headcount:** module boundaries and
  contracts (they become team interfaces); the registry's operations
  (they become the audit and coordination layer); ADR discipline (it
  becomes institutional memory); reproducibility records (they become
  onboarding). Almost everything built for discipline-at-one converts
  into coordination-at-many — that conversion is the best argument that
  the early architecture investment was purchase, not gold-plating.

## Part 8 — The biggest mistakes we could make

Twenty-two, each with its mechanism and its current defense (**bold**
where the defense is weak or absent — those are the honest ones):

1. **Capability sprawl** — enthusiasm adds a 12th, 15th primitive; the
   admission test + tiering defend; portfolio reviews enforce.
2. **Leaderboard chasing** — switching lineages for benchmark deltas;
   the switching test defends structurally.
3. **Premature GPU expansion** — buying class-K infrastructure before
   P3 economics clear; ladder gates + CPU-first posture defend.
4. **Premature native models** — pride-driven Stage 5; four-condition
   entry gate defends.
5. **Weak evaluation** — gates citing stale or gamed suites; rotating
   private suites + contamination checks defend; **the harness existing
   at all is currently the weak point (M9 — mitigated by the Day-0 eval
   seed only if actually practiced)**.
6. **License negligence** — one NC dataset poisoning a lineage;
   DAG-computed verdicts defend structurally.
7. **Silent data harvesting temptation** — "just this once" under
   competitive pressure; consent architecture + the fact that trust IS
   the enterprise product defend.
8. **Architecture drift** — hardcoded model references, engine names in
   contracts; grep-able invariants + review checklists defend.
9. **Product drift** — chasing a shiny adjacent market; Part 3's refusal
   list defends; **founder discipline is the only enforcement**.
10. **Documentation as procrastination** — more strategy instead of
    shipping; **the Part 1 governor is new and untested**.
11. **Over-ceremony at one person** — bypassed gates because the right
    path was the hard path; registry weakness 5 names it; **the
    implementation hasn't proven ceremony-cheapness yet**.
12. **Under-ceremony at twenty** — informal promotions surviving into a
    team era; operations-as-audit defends if adopted early.
13. **Hiring too late** — solo capacity as the binding constraint until
    burnout; **no defense exists in the architecture; only revenue and
    self-awareness**.
14. **Hiring wrong first** — a researcher before a platform engineer
    (or vice versa) misaligned with the ladder stage; Part 7's sequence
    is the guidance.
15. **Free-tier abuse economics** — generous tier meets bot farms;
    metering (M4) + limits defend; **abuse tooling is unplanned**.
16. **Building for imagined enterprises** — SOC2/SSO/marketplace before
    any enterprise asks; PRD's foreclose-nothing/build-nothing-early
    stance defends.
17. **Ignoring ops burden** — support, incidents, on-call as unpriced
    costs; **currently unmodeled anywhere; first real outage will
    price it**.
18. **Wedge abandonment at the first hard quarter** — pivot pressure
    when Stage 2 data costs bite; Part 4's measurement-governed
    commitment defends; **conviction is not architecture**.
19. **Competitor panic** — reactive repricing or feature-matching
    against funded players; published-benchmark positioning defends by
    changing the axis of competition.
20. **API contract breaks** — "just one breaking change"; append-only
    contract law + versioned packages defend structurally.
21. **Model supply-chain compromise** — malicious weights/pickles from
    upstream; **partially defended (hash-pinned imports) — format
    hygiene and scanning are unplanned; add to M2's import path**.
22. **Bus factor = 1** — everything above, concentrated in one person;
    reproducibility records and the document stack are the partial
    defense; **the full defense is called hiring, and it has a date
    only revenue can set**.

## Part 9 — If the repository disappeared tomorrow

Knowledge survives; code doesn't. The rebuild:

**Same architecture — rebuilt in a different order.** Week 1: the
constitutions (from memory — they fit in twenty minutes precisely
because they were written to be memorable), the discovery loop, and a
landing page. Weeks 1–6: the chassis (M0+M0.5+M1 compressed hard — the
*decisions* were the slow part and they're already made; the second
telling of a story is always shorter). M1.5 becomes a two-day refresh
(re-verify licenses against the current date; the *frameworks* need no
re-research). Then M2 as designed.

**What gets simplified:** the six engineering handbooks merge into two
(contributing + principles); the strategy stack rebuilds as *thin*
constitutional documents that grow sections only when a milestone
consumes them; ceremony implements the light version first.

**What gets added:** the discovery log as a first-class repo artifact;
the eval seed in the first capability milestone; weights-import security
hygiene (Part 8, mistake 21); a one-page pricing hypothesis subjected to
customer conversations before v0.5 rather than at it.

**What gets removed:** nothing architectural. The honest surprise of
this exercise: the *sequence* has fat; the *structure* does not. Every
layer earned its place through a failure it prevents, and the rebuild
would re-create each — faster, in the same shape.

## Part 10 — 2036

**The company that exists:** a profitable, mid-sized,
developer-infrastructure company — the default speech platform for its
language wedge worldwide, a credible multi-domain intelligence API
everywhere else, serving a mix of its own lineages (dominant in the
wedge, including native small speech models several generations deep),
tuned open derivatives, and pass-through frontier capacity — all behind
public model names whose oldest (`intelliai-stt`) has never once broken
a customer in ten years, through what will by then be dozens of
generations of invisible succession. Customer-owned artifacts number in
the thousands; the fine-tuning product is the margin engine; published,
reproducible benchmarks are still the marketing department.

**Products that don't exist, still:** everything in Part 3. The list
surviving ten years of temptation *is* the strategy having worked.

**What makes it different from every competitor:** it is the platform
whose claims can be checked — model lineage queryable, benchmarks
reproducible, consent auditable, deprecations honored. In a 2036 where
AI trust regulation has arrived in force (the safest prediction in this
document), the company that built evidence-architecture in 2026 is
selling compliance as a byproduct.

**What part of today's architecture still exists:** the contracts
(v1 endpoints still answering), the registry's record (the oldest
artifact lineages still queryable — the court record has outlived
several courthouses of serving infrastructure), the constitutions
(amended, never erased), and the identity hierarchy — while every
engine, format, serving framework, and probably every 2026 model named
in D3 is gone. Which is exactly what D3 predicted, and why it recorded
frameworks instead of only picks.

## Part 11 — The Founding Constitution

> **Extracted at M1.5 close into [CONSTITUTION.md](CONSTITUTION.md), which
> is the canonical, in-force version.** The text below is preserved as the
> original draft for historical record; amendments happen only in
> CONSTITUTION.md.

Twenty principles, written for a 2040 reader. The three domain
constitutions (AI_STRATEGY §7, REGISTRY_V2 §12, FINE_TUNING Part 10)
remain the detailed law; this is the charter above them.

1. **The contract is the product.** Everything behind a promise is
   replaceable; the promise is not.
2. **Talk to customers, then serve, then measure, then train — in that
   order, forever.**
3. **Own names, evidence, and data; rent everything else gladly.**
4. **No rights, no use:** no license clarity → no traffic; no consent →
   no data; no evaluation → no promotion.
5. **Customers see promises; engineering sees truth; exactly one bridge
   connects them, and the registry owns it.**
6. **Records are immutable; infrastructure is disposable; never confuse
   which is which.**
7. **Models depreciate. Data, evaluations, recipes, and trust
   appreciate. Invest accordingly.**
8. **Capital compounds in lineages and wedges; novelty pays the
   switching cost.**
9. **Commodities ride upstream. The wedge gets the compounding. Tiers
   are decisions, reviewed.**
10. **Improvements ship silently; degradations ship loudly; rollback is
    boring or the system is wrong.**
11. **The platform must not be able to tell whose model it serves** —
    ours, a customer's, or an upstream's: same gates, same rigor, same
    record.
12. **Trust is architecture.** Defaults protect the customer even when
    inconvenient; what marketing claims, code must enforce.
13. **Honest benchmarks or none.** Internal evals private and rotating;
    public claims reproducible; the two never mix.
14. **Efficiency before scale; consolidation before expansion; sprawl
    is a decision someone must sign.**
15. **Research fails freely outside production; only graduation
    crosses; the boundary protects both sides.**
16. **Ceremony proportional to blast radius — and the right path must
    be the easy path, or it will not be the taken path.**
17. **Write decisions down with their alternatives; supersede, never
    erase; the company must always know why it is the way it is.**
18. **A principle that cannot be checked is decoration.** Every law
    here must map to a test, a gate, or a review question.
19. **Strategy bends to measurement; principles do not bend to
    convenience.** Knowing which is which is the founder's job.
20. **Refuse well.** What the company will not build (Part 3) is
    guarded as carefully as what it will — focus is the scarcest asset
    and the only unpurchasable one.

## Part 12 — Final Self-Review: the case for rejecting this company

The experienced founder across the table, trying to kill it:

**"You have no customers."** Correct, and it is the strategy's deepest
current flaw — not a gap but a *sequencing error* partially repaired on
paper only (Part 1, Change 1). Every market claim in nine documents
rests on published pricing pages, competitor positioning, and one funded
competitor's existence. That is hypothesis-grade evidence. If discovery
contradicts the wedge, the roadmap bends — but months will have been
spent, and a Day-0 company would have known in weeks.

**"This is over-engineered for a zero-revenue project."** Partially
guilty. The defense — every layer converts to team coordination (Part
7), the Piper save paid for the research milestone, M2 consumes the
designs directly — is real. But the honest accounting says: the
platform could have served its first paying transcription with half of
M0.5 and a third of the strategy stack, and *learned from money* months
earlier. The counter-defense — that this is also an apprenticeship
project where the learning is the point, and that retrofitting
discipline is costlier than installing it — is true but must not become
a universal alibi. The governor (Part 1, Change 3) exists because the
next over-engineering temptation is already scheduled somewhere.

**"You are one person planning like an institution."** Yes. The
two-hat ceremonies, the approval matrices, the org-appreciating
architecture — all of it assumes a company that does not yet exist and
may never. The plan's own risk register rates solo-capacity overrun
HIGH. There is no architectural answer; there is only the discipline of
gates ("descend the ladder without shame") and the honesty of the
hiring trigger being revenue, which is circular: revenue needs
shipping, shipping needs capacity. This circle is where the company
most plausibly stalls — not dramatically, just slowly.

**"Your wedge has a funded incumbent with government backing."** The
sharpest external threat, understated in earlier documents' polite
"competitor and resource" framing. Sarvam has capital, data programs,
sovereign distribution, and now open Apache models. The counter-position
(developer-first, globally-served, honest-benchmark, multi-domain) is
real but narrow, and the window assumption — that Stage 2 lands before
the wedge closes — is the single most optimistic date in the plan.

**"Where is the go-to-market?"** Nowhere, yet. Developer marketing is
a discipline (content, community, DX, launch mechanics) with its own
failure rates, and this stack contains zero pages on it. OpenAI
compatibility lowers friction; it does not create demand. This is the
largest *missing document* in the repository — deliberately not written
by the architecture-minded author it would need to escape from.

**"Would you fund it?"** As a venture investor: not yet — solo
non-famous founder, zero revenue, incumbent-shadowed wedge, GTM
unwritten. As a bootstrapped company building toward default-alive on
serving revenue with a real technical moat compounding underneath:
yes, with the three Day-0 changes enforced and the first customer
conversation happening this month. The strategy's saving grace is that
it was built to bend to evidence — the fatal version of every risk
above is the version where measurement is ignored, and refusing to
ignore measurement is the one discipline this stack has practiced
nine deliverables in a row.

---

## Closing requirements (the six)

1. **Architectural review:** complete (Parts 8, 9, 12). The structure
   survives its own attack; the sequence and the missing GTM/discovery
   threads do not.
2. **Remaining strategic contradictions:** none new beyond D9's list
   (ADR-0004 supersession, PRD Piper row, ARCHITECTURE forward map —
   all queued). One *tension* elevated, not contradiction: FINE_TUNING's
   eval-at-M9 vs the eval-seed principle — resolved in favor of the
   seed (this document, Part 1, Change 2).
3. **Change before Milestone 2:** the close-out list (commits, ADR,
   PRD/ARCHITECTURE edits, Dependabot + dev-env rule); the eval-seed
   habit into M2's definition of done; weights-import security hygiene
   (Part 8, mistake 21) into M2's import path; and the first customer
   conversations scheduled *alongside* M2, not after it.
4. **Remove from the repository:** nothing. One reclassification:
   FOUNDATION_MODELS.md should carry a standing header note that its
   §2–§12 verdicts are dated evidence (decaying from 2026-07-31) while
   its frameworks (§1, §13–§15) are permanent — the document is two
   documents in one, and readers must know which half they are citing.
5. **Permanent constitutional documents:** Part 11 of this document
   should be extracted at M1.5 close into **docs/CONSTITUTION.md** —
   the single charter — with AI_STRATEGY §7, REGISTRY_V2 §12, and
   FINE_TUNING Part 10 remaining as domain law beneath it, and
   MODEL_IDENTITY §9 as the identity statutes. Amendment discipline:
   supersede, never erase, same as ADRs.
6. **Stopped for review.** Milestone 1.5 has no further deliverables;
   what remains is the close-out itself.

---

*Change log:*
- *2026-07-31 — v0.1: founding strategy review (M1.5 D10, final):
  re-founding verdict with three Day-0 changes (discovery from day
  zero, eval seed, documentation governor); company definition; refusal
  list; wedge commitment; model strategy re-decided; precise moat
  claims (no classic network effects); org scaling; 22 mistakes with
  defense audit; rebuild-from-knowledge; 2036 outlook; 20-principle
  founding constitution; adversarial self-review including the
  would-you-fund-it verdict. Pending approval.*
