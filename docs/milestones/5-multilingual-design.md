# Milestone 5 Engineering Design Review — Multilingual Foundation (v0.6)

**Approved:** 2026-08-04, ratified after two founder refinement rounds
(v2: generalization and permanence; v3: the Route/Strategy Boundary).
This document is the reference every M5 step is reviewed against;
material deviations go through review, not through the sprint. Related
decisions: [ADR-0025](../adr/0025-serving-routes.md) (serving routes),
[ADR-0026](../adr/0026-multi-artifact-capability-deployments.md)
(capability deployments), [ADR-0027](../adr/0027-language-support-ladder.md)
(the Language Support Ladder). It builds on the strategy layer —
[MODEL_IDENTITY](../MODEL_IDENTITY.md), [REGISTRY_V2](../REGISTRY_V2.md),
[RESEARCH_FRAMEWORK](../research/RESEARCH_FRAMEWORK.md),
[FINE_TUNING_STRATEGY](../FINE_TUNING_STRATEGY.md) — and on the Core
Speech Language Policy v1 (PRD §6).

## 0. What this milestone is — and is not

M5 builds the **socket, not the bulb**. When a Hindi or Arabic engine
eventually passes the Research Framework's gates, it must plug into a
platform that already knows how to route to it, evaluate it per
language, promote it with evidence, meter it invisibly, and roll it
back — with zero redesign. Today none of that routing machinery exists:
`intelliai-stt` resolves to exactly one artifact, `intelliai-tts` to
exactly one, and "which languages does this public model support, at
what quality, served by what" is not representable anywhere.

Two boundary statements, so scope cannot creep:

**This milestone selects no model.** The Research Framework owns
candidate evaluation, license verdicts, and adoption decisions
(MODEL_LEDGER is their append-only record). M5 builds what those
decisions *land on*. The milestone is deliberately provable with what we
already own: the incumbent STT model is already multilingual (it serves
Hindi today, unrouted and unmeasured as a product), and the
deterministic reference engines can simulate any number of additional
engines in CI.

**This milestone changes no commercial semantics.** The M4 review §6
proved, mechanism by mechanism, that multilingual needs no commercial
redesign. M5 is held to that: the commercial continuity fingerprint is
the regression gate.

The load-bearing discovery the whole design rests on:

> **The routing seam already exists.** Every runtime request has carried
> an artifact id since M2 (`TranscriptionRequest.model`,
> `SpeechSynthesisRequest.model`), the gateway has always pinned it from
> registry resolution, and the runtime has always refused a mismatched
> artifact. M5 does not build a router. It teaches the *registry* to
> give a different answer to `resolve()` depending on language, and
> teaches the *runtime* to host more than one answer. Everything else is
> consequences.

## 1. The Two Vocabularies

Every law this platform has ratified turns out to be an instance of one
distinction, stated here once:

> **The platform speaks two vocabularies. The permanent vocabulary names
> promises and identities; the temporary vocabulary names
> implementations. Promises outlive every implementation that serves
> them.**

| Permanent vocabulary (identities & promises) | Temporary vocabulary (implementations) |
|---|---|
| capabilities (`transcription`, `speech_synthesis`) | engines and foundation models |
| public model identities (`intelliai-stt`, `intelliai-tts`) | artifacts *(in service — see nuance)* |
| voice identities | voice assets and engine tokens |
| languages and their ladder statuses | builds (precision, format, conversion) |
| units of measure (`audio_seconds`, `characters`) | deployments and slots |
| datasets and corpus versions (as cited assets) | route bindings *(mutable state)* |
| the ledgers (usage, evaluation evidence, MODEL_LEDGER) | pools, caches, infrastructure |
| price book versions, rating algorithm versions | serving topology |
| request ids (the customer's receipt) | |
| the laws themselves (ADRs, invariants) | |

**The admission test for any new noun:** *if we replaced or renamed
this, who breaks?* If customers, history, or reproducibility break — it
is permanent vocabulary: append-only, never renamed, never removed. If
nobody outside the implementation breaks — it is temporary vocabulary:
replaceable at will, behind a promotion.

**The placement rule** (each clause is an existing law, now derivable
from one test):

- Customer surfaces draw **only** from the permanent column (the
  leak-guard law, M2).
- Deployment and service names draw **only** from the permanent column
  (the naming law — why language-named deployments are safe and
  engine-named ones are forbidden).
- Ledger **facts** draw from the permanent column; the temporary column
  appears in ledgers only inside **lineage** — stored, never projected
  (the Ledger Fact Invariant, M4).
- Evidence and promotion records may *reference* the temporary column:
  their job is precisely to record which implementation carried which
  promise, when, with what proof.

**Three nuances, so the binary doesn't lie:**

- **Artifacts** are temporary *in service* and permanent *as records* —
  immutable and retained forever, because rollback (MODEL_IDENTITY P8)
  and lineage depend on retention. Temporary role, permanent existence.
- **Voices** are permanent identities realized by temporary assets:
  `reference-alto` is forever; the asset that renders it is rebindable —
  behind the promotion bar of §7.
- **Route bindings** are the one deliberately *mutable* thing in the
  registry — and the Evidential Chain (§9a) exists so that even mutable
  state is always explainable from permanent records.

The two prior slogans are this table's diagonal: *capabilities are
permanent, engines are temporary* (one row from each column); *models
depreciate, knowledge compounds* (the ledgers row versus the artifacts
column).

## 2. The Language Support Ladder

Before routing can be designed, a question the platform cannot currently
answer must become representable: **what does it mean for
`intelliai-stt` to "support" Hindi?** Today the incumbent will happily
transcribe Arabic — no baseline exists, no corpus exists, no quality
claim was ever measured, and nothing in the platform knows it is
happening. The Research Framework gave the criterion (§7.1: support =
corpus + quality baseline + production benchmark); the platform has no
vocabulary for the states in between. That gap is where quality
embarrassments come from.

**Every (public model, language) pair has an explicit status, held in
the registry, from a three-rung ladder:**

| Status | Meaning | Evidence required | Customer experience |
|---|---|---|---|
| **`supported`** | First-class product promise under the Language Policy | Corpus + committed quality baseline + production benchmark + license-clean serving path + promotion record | Served, documented, quality-guaranteed |
| **`available`** | Served best-effort — honestly, without a promise | **None** — this is the entry rung (F-M5-1); the requirement is honest labelling, and evidence is what *leaves* this rung | Served, documented as preview/best-effort, no quality claim |
| **`unavailable`** | Not served | — | Refused with a clear, honest error — never silently served badly |

**The ladder is a lifecycle, not three loose labels** (F-M5-1, ratified
2026-08-04):

> **A new language always enters the platform as `available`. Promotion
> to `supported` requires a completed benchmark, evaluation evidence, a
> production baseline, and explicit founder approval. No language may
> skip this lifecycle.**

The prohibition needs no state machine, because the bar itself forbids
the jump: a **production baseline is unobtainable without having
served**, and serving requires the middle rung. This is the same shape
as M4's quota — computed from the ledger rather than trusted to a
counter — and it is why the design's original "measured at least once"
wording for `available` was superseded: at entry, nothing has been
measured yet, and demanding evidence to *begin* measuring is circular.
Demotion (`supported` → `available`) and withdrawal are never gated:
honesty may always be increased.

**The corpus precondition** (ratified 2026-08-05, after Step 4):

> **A language cannot advance beyond `available` unless IntelliAI owns —
> or has formally adopted — a versioned evaluation dataset for that
> language. Evidence quality is bounded by dataset quality, so promotion
> requires both: benchmark evidence, and a versioned evaluation corpus.**

This closes the gap Step 4 found by walking into it. A benchmark can be
run against anything; what makes its number *mean* something is the
corpus behind it. Without this rule, a promotion could cite a technically
valid evidence triple produced on a slice with no speech in the language
being promoted — the number would be real, reproducible, and about
nothing. Ownership matters as much as existence: an adopted third-party
corpus carries its licence into every promotion that ever cites it, so
which of the two applies is recorded, not assumed.

Structurally: a `supported` route's evidence must declare its corpus as
`owned` or `adopted`, and the cited corpus version must actually contain
natural speech in the promoted language. Hindi therefore cannot be
promoted today, and will not be able to be until F-M5-8 is resolved —
which is the rule working, not the rule failing.

**Why a ladder and not a boolean.** A boolean forces one of two lies.
`supported=true` for Arabic claims a bar nobody measured.
`supported=false` refuses traffic the incumbent genuinely handles —
destroying exactly the demand evidence the Language Policy needs (M4's
language analytics exist to answer *"are customers actually asking for
Arabic?"*; refusing all Arabic requests guarantees the answer is
unmeasurable). The middle rung is where honest evidence-gathering lives.

**Why in the registry.** Language status is a promise about a product,
and the registry is the resolution authority for product identity
(ADR-0017). It cannot live in the runtime (runtimes are temporary;
promises are permanent) and cannot live in documentation alone (a
promise the code can't check is a promise the code will break).

**Why three states, and deliberately not four.** The refinement pass
evaluated an `experimental` rung and rejected it. The ladder is a
vocabulary of **stances toward a customer**, and toward a customer
exactly three stances exist: *we promise this*, *we serve this honestly
without promising it* (`available` **is** the customer-preview state),
and *we do not serve this*. That set is exhaustive by construction —
which is what makes the ladder stable for five years. "Internal
experimentation" is not a stance toward a customer and already has its
homes:

| The thing `experimental` would have meant | Where it already lives |
|---|---|
| An artifact under investigation | MODEL_IDENTITY purpose flag `experimental` — *never routable*, by that document's own law |
| Internal traffic exercising real serving paths | The usage-origin taxonomy (`research`, `evaluation`, `internal_qa`) — metered, never rated (F7) |
| An unproven artifact taking real traffic behind the public API | The **reserved `shadow`/`canary` binding stages** (§5b) — Registry V2's, by design |

A ladder rung named `experimental` would be a fourth representation of a
fact with three homes — and divergent sources of truth for experiment
status is precisely the five-year failure mode.

**Consequences:** language transitions become promotions (§11) with
evidence per rung; the ladder is the public documentation's source of
truth; `unavailable` refusals are recorded as demand evidence (a
request-event fact, no billable event). Rejected: inferring status from
engine model cards — a card's language list is a claim, not evidence
(Research Framework §2); status is assigned by us, from our evidence.

## 3. How multiple engines coexist behind one public product

Three candidate topologies:

**(a) One fat runtime process hosting every engine.** Rejected by
arithmetic before philosophy: the TTS incumbent alone is ~2.0 GiB
resident (M3 measured), the STT incumbent ~1.4 GiB; every added language
engine is another residency. On CPU-first deployment, one process
hosting EN+HI+AR engines for both capabilities is a memory wall and a
shared blast radius — one engine's crash-loop takes down languages that
were healthy.

**(b) One service per engine.** Rejected on law: services are named by
capability, never by engine (the M3 rename `tts-kokoro → tts-runtime`
exists precisely because of this). Engine-named services leak engine
identity into deployment topology, ops vocabulary, and eventually
support conversations.

**(c) Chosen: capability services with named deployments, each hosting
one-or-more artifacts via ModelManager slots.** The capability service
stays singular in *name* (`stt-runtime`, `tts-runtime`) and becomes
plural in *deployment*. Each deployment declares which artifacts it
hosts; the registry routes to (service, deployment). The mechanism
already exists, which makes (c) nearly free:

- `ModelManager` has been **multi-slot since M2** (`SlotSpec`,
  `DEFAULT_SLOT`, slot-name uniqueness validation). The runtimes simply
  configure one slot today. Multi-engine hosting is configuration of an
  existing capability — "lifecycle, never inference" (ADR-0019) is
  untouched.
- The runtime already validates the request's pinned artifact against
  what it has loaded and refuses mismatches. In a multi-slot runtime,
  that check becomes slot *selection* instead of mere validation.

**Deployment naming law (permanent):** deployment names may reference
**capabilities and languages** (`tts-runtime-indic`,
`stt-runtime-default`) — both permanent vocabulary — and may **never
reference engines**. Language-named deployments are safe because
languages are promises kept regardless of what serves them; engine-named
deployments would break exactly when nothing should have to change.

### Three identities that are never interchangeable

```
   ┌─────────────────┐
   │    ARTIFACT     │   a concrete set of trained weights — an IDENTITY
   └────────┬────────┘   permanent as a record, immutable, retained forever
            │            (whisper-small v1)
            │  is hosted by
            ▼
   ┌─────────────────┐
   │   DEPLOYMENT    │   a named place that hosts one or more artifacts
   └────────┬────────┘   a CONFIGURATION, part of the temporary vocabulary
            │            (stt-runtime-indic)
            │  is realized by
            ▼
   ┌─────────────────┐
   │ RUNTIME PROCESS │   one running instance of that configuration
   └─────────────────┘   ephemeral: restarted, scaled, replaced at will
```

> **Permanent law: a deployment hosts an artifact. A runtime process
> realizes a deployment. These identities are related but never
> interchangeable.**

Each relation is many-to-one downward and one-to-many upward, and every
confusion between the layers is a real failure mode. An *artifact* can be
hosted by several deployments at once, so "the artifact" is never a
place. A *deployment* can be realized by several processes — that is what
scaling out is — so a deployment is never a process, and a process
restart is never a change of what is hosted (§6: a slot's binding is
fixed for the life of the process; replacing an artifact is a deployment
operation). And a process holds no identity of its own: nothing may name
one, route to one, or record one as the thing that served, because it
will not exist tomorrow.

**Packing is a deployment decision, not an architectural one.** Whether
two artifacts share a process (two slots, one deployment) or split
(memory isolation, independent scaling) is decided per adoption by
measured residency — MODEL_IDENTITY separates deployments from artifacts
for exactly this reason.

> **Ruled (F-M5-5, 2026-08-05): one artifact per deployment is the CPU
> default.** The measured ~54 MiB interpreter overhead is accepted in
> exchange for simpler operations, independent scaling, a cleaner blast
> radius, cleaner rollback, and cleaner promotion. Packing remains
> supported by the architecture and is not the default posture.

**Gateway consequence:** `runtime_clients` today is keyed by service
(one URL each). It becomes keyed by **deployment name**, and
`Resolution` gains a deployment field defaulting to the service name —
fully backward compatible; today's topology is the degenerate case of
one deployment per capability.

## 4. Language routing and engine selection

### 4.1 Where routing lives

| Option | Verdict |
|---|---|
| Runtime chooses the engine (fallback chains, per-request heuristics) | ❌ **Rejected on the three-planes law.** The causal chain is one-way: serving → evidence → promotion → registry state → routing. A runtime that picks its own engine is the data plane making a control-plane decision — invisible to promotion, unattributable in evaluation, unauditable when quality shifts. |
| Gateway service code chooses (if/else on language) | ❌ Rejected: routing logic outside the registry is registry logic that escaped — untestable at composition time, invisible to the license gate, unreachable by promotion machinery. |
| **The registry resolves (public model, routing key) → artifact** | ✅ **Chosen.** Resolution is already the registry's one job (ADR-0017: resolution-only). Routing is resolution with one more input. Promotion becomes a registry state change, exactly as REGISTRY_V2 §3's record/resolution split intends. |

> **Routing is resolution. The registry is the only component that maps
> a customer's request to an artifact, and it does so from declarative,
> evaluation-gated state. Runtimes serve what they are told; gateways
> ask; nothing else decides.**

### 4.2 The routing key — and the STT auto-detect trap

The routing key is the **declared language**, normalized to base subtag
(`hi-IN` routes as `hi`; the full tag is preserved as the recorded fact —
matching M4's analytics behavior). For STT that is the request's
existing `language` parameter; absent a declaration, resolution takes
the **default route** — today a genuinely multilingual incumbent that
performs its own detection.

The trap worth naming: it is tempting to route on *detected* language —
sniff the audio, send Hindi to the Hindi specialist. **Rejected for
M5**, with the reasoning recorded because someone will propose it again:

- Detection requires inference, so detect-then-route is a **two-pass
  architecture**: a detection pass (which model? held where?) before the
  real pass — a new serving stage with its own latency, capacity, and
  failure modes, for a benefit the incumbent already provides by being
  multilingual.
- Routing on content makes the serving path **non-deterministic from
  the request**: identical request bytes could route differently as the
  detector changes, poisoning evaluation attribution and
  reproducibility.

The rule that survives: **routing happens on declared intent; detection
is a recorded fact, never a routing input.** A requested-vs-observed
mismatch is written to the ledger as evidence — precisely the data that
would one day justify a detection-routing stage, or prove it not worth
building. The seam is named; nothing forecloses it.

#### Three languages, and only one of them routes

The word "language" names three different things in one request. They
are produced at different moments by different parties, and confusing
any two of them is how content-dependent routing gets built by accident:

```
   ┌────────────────────┐
   │ REQUESTED LANGUAGE │   what the customer DECLARED  ("hi-IN")
   └─────────┬──────────┘   · an input, supplied by the caller
             │              · normalized to its base subtag FOR ROUTING ONLY
             │              · recorded in full as a ledger fact
             ▼
   ┌────────────────────┐
   │   RESOLVED ROUTE   │   what the REGISTRY chose   (hi → future-hi-v1
   └─────────┬──────────┘                              @ stt-runtime-indic)
             │              · a pure function of (request, registry state)
             │              · decided BEFORE any inference runs
             │              · the artifact the runtime is then told to use
             ▼
   ┌────────────────────┐
   │ OBSERVED LANGUAGE  │   what the ENGINE reported  ("en")
   └────────────────────┘   · an OUTPUT of serving, produced by inference
                            · recorded as a ledger fact
                            · feeds analytics and future evidence
                            · ────► never flows back upward ◄────
```

> **Permanent law: observed language is an output fact produced by
> serving. It is never routing input.**

The arrow only ever points down. The moment an observed language is
allowed to influence a route, resolution stops being a pure function of
(request, registry state): identical request bytes could route
differently as the detector changes, evaluation can no longer attribute
a result to an artifact, and a served response is no longer explicable
from records alone. A requested/observed mismatch is *evidence about*
routing rules — read by humans, weighed in a promotion — never an input
to them.

### 4.3 TTS: the voice *is* the routing key

TTS has no language parameter — M4 flagged this as the open product
question. The answer falls out of the M3 voice stack:

**A voice is intrinsically bound to the artifact that can render it.**
M3 defined the Voice Asset as "the engine-specific representation
required to reproduce a voice" — a voice's sound *is* an
artifact-specific asset. Therefore:

> **TTS routing: resolve(public model, voice) → the artifact bound to
> that voice. Language is a property of the voice, not a separate
> routing input.**

`PublicVoiceRecord` already carries `languages`; it gains an **artifact
binding**. A customer picks `intelliai-tts` plus a Hindi voice; the
registry resolves to the Hindi-capable artifact because that is where
the voice lives. No second routing dimension, no possibility of "Hindi
voice routed to an engine that lacks it."

This *refines* an M3 ownership line, stated honestly: M3 said "the
runtime owns voice→engine mapping" — correct with one engine. With
many: **the registry owns which artifact serves a voice** (routing —
control plane); **the runtime owns how that artifact renders it**
(engine tokens, assets — mechanics). Identity/mechanics, same law, one
level deeper.

Remaining case: a genuinely **multilingual voice** (one voice,
`languages=("hi","en")`, one artifact). The voice still routes
unambiguously, but the engine may need the effective language and the
ledger needs the fact.

**Correction, found at Step 3 implementation:** this design proposed
adding `SpeechSynthesisRequest.language` as an additive contract field.
It was already there — added in M3 (commit `2ccc346`) as a "BCP-47-ish
hint for multilingual voices", optional and defaulted to `None`, and
never populated by anything since. The contract therefore needs no
change at all, and the "one additive field" figure quoted throughout
this document was wrong from the start.

**F-M5-7 leaves it unpopulated** (§16.1): with no public language field,
nothing can put a value there that the voice does not already determine,
and no engine reads it. The gateway sends `None` and M4's ledger gap
closes from the other side — the recorded language is the **voice's**
declared language, a fact the gateway already holds. When a multilingual
voice and an engine that needs the hint both exist, populating the
existing field is a gateway change and nothing more.

## 5. Registry evolution — V1.5, on the road to V2

### 5.1 What V1 cannot represent

Three things: a public model served by **more than one artifact**;
**language** as a resolution input and a status dimension; a voice's
**serving artifact**. Everything else (license gate, capability guard,
leak-guard) carries forward unchanged.

### 5.2 The ServingRoute

The routing record enters as **`ServingRoute`** — generalized at the
founder's direction so that today's language routing never becomes
tomorrow's migration:

```
ServingRoute
  ├─ public_model_id
  ├─ selector        RouteSelector — typed, append-only fields; M5: language only
  ├─ status          the ladder rung this route serves
  ├─ artifact_id     the binding (+ deployment)
  └─ stage           reserved (§5b) — fixed at `production` in M5
```

`RouteSelector` is a typed record with **exactly one optional field
today** (`language`), evolving append-only — the same additive
discipline as contract models. `PublicModelRecord.artifact_id` remains
the **default route** (an empty selector); a model with only its default
route behaves exactly as v0.5.0 does today.

**Rejected selector shapes:** a generic match-dict
(`{"lang": "hi"}`) — a stringly-typed policy engine no composition-time
validation can defend, where every typo is a silent routing miss; a
per-dimension record family (`LanguageRoute`, `RegionRoute`, …) — the
migration this generalization exists to prevent.

**Two permanent rules, fixed now while there is one dimension and zero
ambiguity:**

> **The Selector Admission Test.** A selector dimension is admissible
> only if the customer could know its value from their own request or
> their own commercial agreement — declared intent (language, quality
> tier, latency class) or contracted policy (customer tier, region). A
> dimension knowable only from our operations (hardware class, load,
> placement, cost) is **inadmissible as a selector** and enters the
> system as deployment metadata instead. *(Protection Independence and
> Operational Measurement Independence, extended to the routing layer:
> what serves a customer may depend on what they asked for and what they
> bought — never on what our infrastructure was doing.)*

> **The Specificity Law.** Resolution selects the most specific matching
> selector; the default route matches everything; a tie between two
> equally-specific selectors is a **composition-time error**, never a
> runtime coin-flip. In M5, **exactly one binding exists per selector**;
> multiple bindings on one selector are not a tie to be resolved but a
> *strategy* (§5c), and only a Strategy mechanism — when it exists — may
> create that state.

Of the candidate future dimensions: quality tier, latency class,
customer tier, region, and deployment policy pass the admission test and
are **reserved, not designed**. Hardware class fails it and is
explicitly relocated to deployment records, per ADR-0015's
placement-is-never-identity rule.

Composition-time validation grows in the existing eager style
(misconfiguration aborts startup, never surfaces at request time): every
routed artifact exists, matches the capability, and passes the license
gate *including the language-specific serving path* — the Research
Framework's rule §7.4 made structural (Hindi TTS was gated on GPL
phonemization, not on the model; a route's verdict must cover the whole
path). Every voice's artifact must declare the voice's languages among
its routes. A `supported` status without its evidence references is a
composition error.

### 5b. Three state machines, and the reserved Registry V2 stages

M5 touches three kinds of state; the permanent clarification is naming
them as **orthogonal machines with disjoint owners** — because the
five-year failure mode is one entangled status enum that can express
neither "a canary of a supported language" nor "a production binding of
a merely-available one":

| Machine | Question | States | Owner | M5 |
|---|---|---|---|---|
| **Artifact lifecycle** | Is this implementation ready? | research → … → `evaluation_candidate` → `production` → superseded → archived | MODEL_IDENTITY §4 | consumed as-is |
| **Binding stage** | How much real traffic does this (route → artifact) binding carry? | **`shadow` → `canary` → `production`** | **Registry V2 — reserved here** | hard-fixed: `production` |
| **Language promise** | What do we tell the customer? | `supported` / `available` / `unavailable` | The Ladder (§2) | implemented |

**The reservation, precisely.** The `stage` field lives on the
**binding** — not on the artifact (MODEL_IDENTITY owns that machine) and
not on the ladder (a stance toward customers). M5 declares the field's
home and fixes its value; V2 makes it variable. The §11 promotion
classes are shaped so shadow/canary **insert between founder approval
and the binding flip** — the insertion point is named in the workflow.
Per-route stages compose naturally: a canary on the `hi` route never
touches `en`.

**Stages vs. strategies, reconciled.** A canary inherently involves
*two* bindings on one selector — the incumbent at `production`, the
candidate at `canary`. The `stage` field names the **role one binding
plays**; the future Strategy (§5c) owns **how bindings sharing a
selector cooperate** (the split, its adjustment, its promotion or
rollback). Neither concept absorbs the other: stages without strategies
are inert labels; strategies without stages have no vocabulary for
roles.

**One V2 design obligation is already discharged by M4.** Shadow serving
duplicates inference for a customer request — who is billed for the
shadow pass? The Request Identity Invariant (M4 §7.7) already answers:
one customer request produces exactly one immutable commercial fact —
the production binding's. Shadow and canary passes are our cost. V2
inherits the answer instead of designing it under pressure.

### 5c. The Route/Strategy Boundary

> **A `ServingRoute` binds one selector to one artifact. Coordination
> among multiple ServingRoutes — fallbacks, cascades, A/B splits, shadow
> routing, canary routing, ensembles, chained routing, regional
> failover, or any future routing strategy — belongs to future
> **Serving Strategy** mechanisms and never changes the semantics of an
> individual ServingRoute.**
>
> The route stays intentionally small; routing intelligence is additive
> and lives above it — exactly as `runtime-core` stayed intentionally
> small ("lifecycle, never inference") and engines grew around it. The
> route's law is the same shape: **binding, never coordination.**

When Serving Strategies are designed (Registry V2 territory), a Strategy
will be a named, versioned, evidence-gated object that *references*
routes. It coordinates evidenced bindings; it can never launder an
unevidenced artifact into traffic, because the Evidential Chain (§9a)
attaches at the binding, and a Strategy has no bindings of its own.

Why the boundary matters at five years: nobody designs a bloated route
record — it grows one "small" field at a time (`fallback_artifact_id`,
`traffic_percent`, `ensemble_weight`), each locally reasonable, until
resolution is no longer a pure function and no migration can untangle
binding from coordination. Drawing the boundary while the record has
five fields and one selector dimension costs a paragraph.

### 5.3 What Registry V2 inherits

V1.5 stays code-declarative: **a route change is a reviewed diff**,
which *is* the promotion record while promotions are rare (the same
reasoning as price books, ADR-0023). Rejected: jumping straight to V2
(database-backed, promotion state machine, per-customer policy) — that
designs the state machine before the first real promotion has run
through the simple version, the ADR-0013 mistake; and a generic policy
engine — exactly one selector has customer-visible meaning today.

V1.5 is deliberately V2's record-plane vocabulary in miniature: routes
are records; resolution is a pure function of records; promotion is a
record change; status is explicit state; stages have a reserved home;
strategies have a reserved boundary. V2 (M9) lifts these into its store,
makes stages variable, designs strategies, and absorbs voice resolution
(the M3 note). Nothing in V1.5 needs undoing; graduation is a re-homing.
The measurable V2 trigger: **when route records outgrow reviewable
diffs, the binding table — never the laws — moves to V2's store.**

## 6. Runtime evolution

Small by design, because the heavy lifting was done in M2/M3:

1. **From `default_engine` to a slot catalog.** `build_manager` grows
   from one `SlotSpec` to N, driven by deployment configuration.
   `ModelManager` needs nothing — multi-slot is its existing shape. Each
   slot keeps its capability-defined warm-up probe; `/health/ready`
   reflects all slots; `/info` lists every hosted artifact (the
   `speech-eval` CLI already reads `/info` and will see the catalog).
2. **Slot selection by the request's `model` field.** Today:
   validate-or-refuse. Tomorrow: select-or-refuse. Unknown artifact
   remains `INVALID_INPUT` — the M3 behavior, unchanged in meaning.

   > **A slot hosts exactly one artifact at a point in time.** The
   > binding is fixed for the life of the process: slots are created at
   > startup, loaded once, and released once. **Replacing the artifact
   > behind a slot is a deployment operation — a new process with a new
   > declaration — never a mutation of a running slot.** Nothing in the
   > runtime may rebind, hot-swap, or reload a slot in place.
   >
   > This is what keeps a served response attributable: for the whole
   > life of a process, `(slot → artifact)` is constant, so every
   > evaluation record, ledger lineage entry, and benchmark can name what
   > actually served it without a timestamp. An in-place swap would make
   > artifact identity a function of *when* you asked — and the
   > evaluation and commercial planes both assume it is not.

3. **Per-engine voice maps become per-slot voice maps** (TTS).
4. **Worker-pool posture per deployment.** Admission capacity is a
   deployment property; artifacts sharing a deployment share its pool —
   deliberate, since per-artifact pools inside one process would be
   premature partitioning of measured-scarce CPU.

**What does not change (the constraint the milestone is held to):**
`runtime-core` gains **zero** code; the runtime contract is **untouched**
— the field §4.3 planned to add has existed since M3, and F-M5-7 leaves
it unpopulated; the engine
`Protocol`s, license firewall, and isolation AST suites are untouched.
Every future engine still enters by the M3 permanent rule — satisfy the
Protocol before a single weight is downloaded.

## 7. Voice architecture evolution

The M3 voice laws hold; three extensions:

- **Voices carry their serving artifact** in the registry (§4.3).
- **Multilingual voices are representable** (`languages` is already a
  tuple) with the effective-language validation rule.
- **Voice rebinding is a promotion.** Rebinding a voice to a new
  artifact changes what the customer *hears* even though the id is
  permanent. M5 gives the M3 anticipation teeth: rebinding requires the
  replacement-promotion bar **plus listening evidence** (the M2.5 judge
  discipline; the reserved `speaker_similarity` metric is the eventual
  quantitative form). A silent timbre change on a voice customers
  scripted against is a product incident, not an engine detail. F-M5-4
  sets the bar.

New-language voices are new voice records bound to the new language's
artifact — naming remains a founder act (the M3 placeholder rule
stands; engineering never waits on branding).

## 8. Derived artifacts and lineage

The strategy layer answered the identity questions; M5 confirms the
plumbing treats every derivation identically — and names the one nuance
that isn't identity.

| Derivation (MODEL_IDENTITY §4) | Registry/routing treatment | Runtime treatment | Commercial treatment |
|---|---|---|---|
| **Fine-tuned** | New artifact, parent in lineage, own license verdict (computed through the DAG), routable like any other | A slot; `ArtifactStore` pins weights like any other | Invisible (M4 §8.2 — already *tested* as one of the eight realities) |
| **Adapter / LoRA** | New artifact whose lineage names (base, adapter); composition is load-time mechanics, not identity | One slot whose `ArtifactSpec` lists base + adapter files; the engine adapter composes at load (multi-file specs are existing `ArtifactStore` behavior) | Invisible (tested) |
| **Merged** | New artifact, multi-parent lineage (a DAG, not a chain) | A slot | Invisible (tested) |
| **Distilled** | New artifact; teacher is a lineage parent even with zero shared weights | A slot | Invisible (tested) |
| **Quantized** | **Not a new artifact — a build** (MODEL_IDENTITY §5; ADR-0015: precision is never identity) | Same slot, different build | Invisible by construction |

The nuance, recorded as law:

> **Quality evidence binds to (artifact, build), not artifact alone.** A
> quantized build is the same identity but not necessarily the same
> behavior; a build that can plausibly alter quality (quantization,
> major runtime conversion) requires revalidation against the same
> per-language baselines before it may serve a `supported` language.

**Lineage representation:** `ArtifactRecord.provenance` stays; M5 adds
the **structured minimum** beside it, additively: parents (artifact
ids), derivation (the MODEL_IDENTITY enum), dataset version references,
upstream origin for imports. Deliberately a *subset* of the full lineage
record — enough that the three ledgers join (registry lineage ↔
evaluation evidence ↔ commercial lineage, all keyed on artifact
identity, so "the cheaper Hindi fine-tune also scored worse on
code-mixed WER" is a query), while the full reproducibility record
(recipe, code commit, parent weight hashes) arrives with the Dataset
Registry and real training runs, as REGISTRY_V2 §10 reserves. Rejected:
full lineage now — structure for training runs that haven't happened,
against a dataset registry that doesn't exist.

## 9. Evaluation: per-language evidence

The M2.5 framework was built capability-independent; M5 extends its
*identity*, not its machinery.

**Baseline identity gains language and corpus version.** A baseline
becomes **(public capability, artifact, build, language, corpus
version)**. The existing baselines slot in as the `en` instances (STT
WER 0.000; TTS round-trip WER 0.072). Corpus version was already
*recorded* in every M2.5 evidence record (they are self-contained by
design); promoting it to **identity** means two baselines on different
corpus versions are different evidence — which makes comparisons honest
(a switching test is only valid within one corpus version) and the
chain below walkable forever.

**The evidence law that gates routing:**

> **No language route reaches `supported` without its evidence triple —
> corpus, committed quality baseline, production benchmark — for that
> (artifact, build, language).** (Research Framework §7.1, made
> structural: composition-time validation refuses the status without the
> references.)

**Code-mixed is a first-class slice.** Hindi-English mixing is the
realistic Indian traffic shape (the M2.5 corpus already encodes it). A
Hindi route's evidence includes the code-mixed slice; a specialist that
collapses on code-mixed input is a *worse* product than the multilingual
incumbent even at better pure-Hindi WER. This is the "multilingual model
vs. per-language specialists are competing hypotheses" test the Research
Framework demands (§7.3) — evaluation must privilege neither.

**The switching test evolves per-route:** M2.5's C3 gate becomes
per-language — replacing the artifact behind the `hi` route requires the
switching comparison on the Hindi corpus (including code-mixed) at ≥100
cases under the M2.5 judge discipline, with the C2 second-judge
spot-audit still owed at first promotion. Switching the **default
route** additionally requires the multilingual comparison across all
supported languages, because the default serves everything undeclared.

**Arabic has a prerequisite, and it is not an engine.** Arabic has
policy status, no corpus, no baseline, no candidate (Research Framework
§7.5). The corpus is the *first* Arabic artifact-of-work, belongs to the
evaluation/research track, and **no Arabic routing decision of any kind
is possible before it exists** (F-M5-6).

### 9a. The Evidential Chain

The Research Framework establishes datasets as permanent company assets;
this section makes the connection structural without implementing the
Dataset Registry.

```
ServingRoute (mutable registry state)
   ▲  no route above `unavailable` without its evidence triple
Promotion record (the reviewed diff)
   ▲  cites evidence record ids — never summaries
Evaluation evidence (immutable, M2.5)
   ▲  identity includes the corpus VERSION that produced it
Corpus / dataset versions (permanent assets, cited by version id)
   ▲  trained/derived artifacts cite consumed dataset versions in lineage (§8)
Artifact lineage (structured minimum)
```

> **The Dataset Thread (law):** no route without evidence; no evidence
> without a versioned corpus; no trained artifact without cited dataset
> versions. Every binding in the registry is thereby explainable, years
> later, from immutable records alone — the evaluation-plane sibling of
> the Historical Explainability Invariant.
>
> **And the corpus must be ours** (§2): no language above `available`
> without a versioned evaluation dataset IntelliAI owns or has formally
> adopted for that language. Evidence quality is bounded by dataset
> quality — a benchmark can be run against anything, and what makes its
> number mean something is the corpus behind it.

**Why this is where training pipelines attach.** A future fine-tuning
pipeline touches this chain at exactly two points and nowhere else: it
**consumes** dataset versions (cited in the artifact's lineage at birth)
and **produces** artifacts that enter the *same* promotion path as any
imported model — same evidence triple, same switching test, same
reviewed diff. The data flywheel (RESEARCH_FRAMEWORK §14) closes through
it: production ledger facts (observed languages, mismatch rates,
unserved demand) → dataset priorities → dataset versions → training →
evidence → routes → better facts. Dataset citations remain version-id
strings in M5; the Dataset Registry that resolves them stays reserved
exactly where REGISTRY_V2 §10.2 put it.

## 10. Promotion workflow

Promotion is where every plane meets, and the one-way causal chain
(serving → evidence → promotion → registry state → routing) becomes an
operating procedure. Three promotion classes, because they answer
different questions:

| Class | Question | Evidence bar |
|---|---|---|
| **Language enablement** (`unavailable` → `available` → `supported`) | Is this *good enough to promise*? — an **absolute** bar | The evidence triple (§9) at the founder-set bar; license verdict covering the language-specific path; ladder rung recorded |
| **Replacement within a route** (artifact A → B behind `hi`) | Is B *at least as good as* A? — a **relative** bar | Per-language switching test incl. code-mixed; production bench comparison; **commercial continuity fingerprint** (the M4 Step 6 test, per route) |
| **Voice rebinding** (§7) | Does it still *sound like* the voice? | Replacement bar + listening evidence |

**The chain, and where it does not run** (the operational form lives in
[PROMOTION.md](../../ml/evaluation/PROMOTION.md)):

```
  Evaluation ─► Switching Test ─► Promotion Verdict ─► Human Review ─► Registry Diff ─► Serving Changes
                                  └── changes nothing ──┘
```

The switching test **never performs promotion**. It ends at a verdict;
every arrow after it is a human act or a consequence of one, and no arrow
points back — an evaluation cannot cause its own adoption, and serving
state cannot alter the record of what was measured.

**The procedure** (V1.5, code-declarative): proposal cites evidence in
MODEL_LEDGER → founder approval → *[reserved insertion point: shadow →
canary, Registry V2]* → **one reviewed diff** changing route/status
records — the diff *is* the promotion record, git the audit trail —
→ composition-time validation enforces the evidence references →
continuity proof runs in CI → deploy. **Rollback is a revert**: the
predecessor artifact still exists (immutable, retained — MODEL_IDENTITY
P8), its baseline still stands, and the rollback diff needs no new
evidence because the old evidence never expired. Cheap rollback is the
payoff of routing-as-registry-state.

## 11. Failure modes

| Failure | Behavior | Why |
|---|---|---|
| Request for an `unavailable` language | Honest refusal (400-class, additive code `language_not_supported`, naming what *is* supported), **recorded** as demand evidence | Operational Honesty: never silently serve a language badly; never lose the demand signal |
| Declared language ∉ voice's languages (TTS) | 400, additive code, pre-inference | The voice is the routing truth; a contradiction is the caller's to resolve |
| Routed deployment down | **503 for that route — never a silent cross-language or cross-artifact fallback** | Fallback is a Serving Strategy that does not exist (§5c), so it *cannot* be an emergent behavior of routes; an automatic quality substitution is a promotion nobody approved. When fallback exists it will be explicit, evidenced registry state |
| Default route down, language routes up | Undeclared-language traffic gets 503; declared routes keep serving | Deployment isolation working as intended |
| Requested vs. observed language mismatch (STT) | Serve, record both facts, never re-route mid-request | §4.2's law; the mismatch rate is itself the signal that routing rules need attention |
| Artifact requested that this deployment doesn't host | `INVALID_INPUT` (exists today) | Registry/topology drift must be loud — an ops defect |
| Partial multilingual rollout | Fully representable: each language's rung is independent | The ladder *is* the partial-rollout model |
| Language spoken ∉ any route (auto-detect surprise) | Default route serves it; ledger records observed language | Today's behavior, now measured instead of invisible |

Commercial failure semantics are unchanged from M4 in every row —
refusals produce no billable events, 5xx produces non-billable capacity
records, and language never touches admission (Protection Independence)
or pricing (Operational Measurement Independence).

## 12. Deployment implications

- **Memory is the binding constraint** and the reason deployments exist:
  each resident engine is GiB-scale on CPU. Compose grows overlay
  services per deployment; the shared model cache serves any number.
- **Capacity is per-deployment**, surfaced as the runtime's own 503
  (ADR-0018 unchanged). Admission control remains capability-scoped and
  **must not** grow per-language limits: capacity differences between
  languages are handled by deployment sizing and 503, never by 429.
- **Cold-start multiplies per slot** (M3: ~38 s cold with download, 7 s
  warm); multi-slot warm-up ordering is a Step-measurement question.
- **The R2 lesson applies forward:** more deployments = more gateway
  HTTP clients, not more DB connections; no new interaction with the
  pool ceiling.
- **The gateway's static URL config** becomes a deployment-name → URL
  map. Compose stays the dev topology; the k8s mapping stays 1:1.

## 13. Constraint compliance

| Law | M5 posture |
|---|---|
| Runtime contract | **Untouched** — `SpeechSynthesisRequest.language` has existed since M3 and F-M5-7 leaves it unpopulated; `CONTRACT_VERSION` stays 1 |
| Runtime-core | **Zero changes** — multi-slot already exists |
| Public API stability | Routes and shapes unchanged; no TTS language field (F-M5-7); additions are additive only (new error codes; ladder documentation) |
| Engine invisibility / leak-guard | Deployment names and route records use permanent vocabulary only; leak-guard extends to `/info`-derived surfaces and error messages |
| Two Vocabularies placement rule | Customer surfaces, deployment names, and ledger facts draw from the permanent column only — enforced by the existing leak-guard and naming tests, now cited to one law |
| Route/Strategy Boundary | Routes accrete no coordination fields; asserted structurally (record shape tested; one binding per selector is a composition-time error) |
| Commercial Identity Invariant | Routing changes which artifact serves; the fingerprint (API, ledger, quota, rating) proven identical — the M4 Step 6 test becomes a per-route CI gate |
| Ledger Fact / language-is-a-fact | TTS finally records language; `hi-IN` recorded fully, routed as `hi` |
| Protection / Op. Measurement Independence | No per-language admission; no per-language pricing without a published price book; placement never a commercial input; the Selector Admission Test extends both laws to routing |
| Three planes / one-way causal chain | Routing = registry state; promotion = evidence-gated state change; runtimes never choose |
| Evaluation independence | Machinery unchanged; identity extended (language, corpus version); evidence immutable |
| Research Framework boundary | M5 names no candidates; MODEL_LEDGER remains the only home of adoption decisions |
| License law | Route-level verdicts must cover the language-specific serving path (the Hindi-GPL lesson, made structural) |
| Capabilities permanent / engines temporary | The whole milestone is this law's routing-layer instantiation, generalized in §1 |

## 14. Consolidated rejected designs

| Design | Why rejected |
|---|---|
| One fat multi-engine process | Memory wall on CPU; shared blast radius across languages |
| Engine-named services or deployments | Violates the naming law; breaks exactly when it matters |
| Runtime-side engine choice / fallback chains | Data plane making control-plane decisions — and an unauthored Serving Strategy (§5c) |
| Gateway if/else routing outside the registry | Registry logic escaped its authority; invisible to license gate and promotion |
| Detect-then-route STT | Two-pass architecture bought before its evidence exists; content-dependent routing poisons attribution. Mismatch facts are collected to justify it later, or not |
| Boolean language support | Forces a lie in one direction or destroys demand evidence in the other |
| `experimental` as a ladder rung | A fourth home for a fact with three (artifact purpose flag, origin taxonomy, reserved shadow stage); divergent sources of truth |
| Status inferred from model cards | Claims are not evidence |
| Registry V2 now | Designs the promotion state machine before the first promotion has run through the simple version |
| Generic routing policy engine / match-dict selector | One real selector exists; a stringly-typed engine is unvalidatable and every typo is a silent miss |
| Per-dimension route record family | The migration the ServingRoute generalization exists to prevent |
| `hardware_class` as a selector | Fails the Selector Admission Test; relocated to deployment metadata (ADR-0015) |
| Separate per-language public models (`intelliai-stt-hi`) | Breaks the Language Policy's core promise (three languages, *one* product); makes every customer integration language-aware |
| Quantization as a new artifact | Contradicts ADR-0015/MODEL_IDENTITY; identity carries no precision |
| Full lineage/reproducibility records now | Structure for training runs that haven't happened, against a registry that doesn't exist |
| Automatic cross-artifact fallback on deployment failure | An unauthored Strategy serving an unapproved promotion, silently |
| Per-language rate limits or prices | Forbidden by the M4 independence laws unless a published price book makes it policy |

## 15. Risks

- **R1 — Evaluation cost scales with (languages × artifacts × builds).**
  Every route needs its triple; every replacement a per-language
  switching test. Mitigation: only `supported` rungs pay the full bar;
  `available` is deliberately cheaper. If evidence production becomes
  the bottleneck, the pressure lands on evaluation tooling, never on
  lowering bars.
- **R2 — Memory economics may make languages look expensive.** GiB-scale
  residency per language per capability is real money. A deployment and
  cost-to-serve fact (lineage-joined analysis exists for this); it must
  never leak into per-language pricing without a published policy.
- **R3 — The default route hides demand.** Because the incumbent serves
  undeclared languages, customers may never declare. Mitigation:
  observed-language recording measures reality regardless of
  declaration.
- **R4 — Quality asymmetry across languages harms the brand.** The
  ladder plus honest documentation is the defense; the founder's
  absolute bars (F-M5-3) are the policy instrument.
- **R5 — Combinatorial routing tables.** 2 capabilities × 3 languages
  stays reviewable in code; 11 capabilities × N languages does not. That
  growth curve *is* the Registry V2 trigger, stated measurably: when
  route records outgrow reviewable diffs, the binding table — never the
  laws — moves to V2's store.
- **R6 — Voice rebinding without listening evidence.** The cheapest
  promotion to do carelessly and the most customer-visible; F-M5-4 makes
  the bar explicit before the first rebinding.
- **R7 — Scope creep into model adoption.** The moment a candidate looks
  promising, pressure to "just wire it in" will bypass Research
  Framework gates. The milestone's own DoD — provable with incumbents
  and reference engines only — is the structural defense.

## 16. Founder decisions

### 16.1 Ruled

**F-M5-1 — The language lifecycle** *(ratified 2026-08-04, before M5
Step 1)*. A new language always enters the platform as `available`.
Promotion from `available` to `supported` requires a completed
benchmark, evaluation evidence, a production baseline, and explicit
founder approval. **No language may skip this lifecycle.** Recorded as
law in §2; enforced structurally by `LanguageEvidence`, whose four
required references are the four requirements.

**F-M5-2 — The initial Core Speech Language Policy ladder** *(ratified
2026-08-04, before M5 Step 1)*:

| | English | Hindi | Arabic |
|---|---|---|---|
| **Speech-to-Text** | `supported` | `available` | `available` |
| **Text-to-Speech** | `supported` | `unavailable` | `unavailable` |

> **The ladder reflects measured product evidence, not theoretical
> engine capability. A model claiming support does not automatically
> promote the product.**

This ruling is *narrower* than the recommendation it answers: Hindi STT
was proposed as "supported pending its formal baseline commit" and was
ruled `available`, which F-M5-1 then makes the only lawful entry point.
Hindi STT's formal baseline (Step 4) becomes the evidence for a *future*
promotion, not a retroactive justification for a present one.

English's `supported` rung is not an exception to F-M5-1: the four
requirements were met before the law existed (M2.5 evaluation evidence,
the committed quality baselines, the M3 production benchmarks, and
F-M5-2 itself as the explicit approval), and the catalog cites all four.

**F-M5-5 — One artifact per deployment on CPU** *(ratified 2026-08-05,
after M5 Step 6)*. The measured ~54 MiB interpreter overhead is accepted
in exchange for simpler operations, independent scaling, a cleaner blast
radius, cleaner rollback, and cleaner promotion. **Packing remains
supported by the architecture but is not the default deployment
posture** — the mechanism stays, the habit does not. Recorded as law in
§3 beside the three-identity diagram, and as ADR-0026 Amendment 2.

**F-M5-7 — No TTS language field in M5** *(ratified 2026-08-05, before
M5 Step 3)*. The public API introduces **no** `language` field for
speech synthesis. Throughout M5, language is expressed through **voice
selection**; the field is reconsidered when Registry V2 owns voice
resolution and multilingual voice routing.

Two consequences for the design as ratified. First, the runtime contract
is **untouched in M5**. §4.3 planned to add
`SpeechSynthesisRequest.language`; implementation found it already
present since M3 (see the correction in §4.3), optional and never
populated. F-M5-7 leaves it that way — with no public source, nothing
can put a value there that the voice does not already determine, and no
engine reads it. `CONTRACT_VERSION` stays 1 for a fourth milestone with
no contract change at all. Second, M4's TTS-language ledger gap closes
anyway: the gateway derives the recorded language from the **voice's**
declared language, which is a fact it already holds.

One hazard worth naming: the public synthesis schema is a tolerant
reader by decision (SDKs send extras), so a client sending `language`
today has it silently ignored. If the field is ever introduced publicly,
that previously-inert key becomes live for those clients — so it lands
with an announcement, not quietly.

### 16.2 Open

Each is tagged with the step it gates and carries a recommendation so
engineering is never idle waiting.

| # | Decision | Recommendation | Gates |
|---|---|---|---|
| **F-M5-3** | Absolute quality bars for `supported`, per language | Set per language at promotion time from corpus evidence, recorded in the promotion diff — not guessed now. F-M5-1 fixed the *process*; this fixes the *numbers* | First language enablement |
| **F-M5-4** | Voice rebinding evidence bar | Listening protocol (M2.5 discipline) mandatory; `speaker_similarity` implementation before the *second* rebinding | First rebinding |
| **F-M5-6** | Arabic corpus commissioning — the prerequisite for *any* Arabic progress | Approve as an evaluation-track work item now; it gates all Arabic decisions and takes calendar time. Arabic STT is now publicly `available` (F-M5-2), which raises the urgency: we are serving it honestly-labelled and unmeasured | Research/evaluation track |
| **F-M5-8** | **Hindi speech corpus** — audio with committed reference transcripts. Found at Step 4: this design assumed Hindi had a corpus because the M2.5 *synthesis* corpus contains Hindi text. Transcription needs Hindi **audio**, which is a different asset and does not exist | Commission or select one, as an evaluation-track work item. Pinning a third-party dataset into the permanent evidence chain carries its licence into every future Hindi promotion, so the choice is a founder decision, not an engineering one. Until it exists, Hindi's honest rung is `available` — where F-M5-2 already put it — and no Hindi run can be a quality claim | Hindi promotion to `supported` |

## 17. Implementation roadmap — review-gated steps

Ordering principle: **representation → routing → serving → evidence →
promotion → proof.** Registry first because everything else consumes its
vocabulary; runtime multi-slot before gateway plumbing so there is
something to route to; evaluation identity before promotion because
promotions consume evidence.

| Step | Concept / Trade-off | DoD sketch |
|---|---|---|
| **0 Governance** | This document committed; ADR-0025/0026/0027; founder decisions recorded as open items with gates | Docs committed and indexed; CI green |
| **1 Registry V1.5 — serving routes** | `ServingRoute` + `RouteSelector`, ladder status, voice→artifact binding, `resolve(model, language/voice)`, composition-time validation incl. route-path license coverage — **behavior-frozen**: today's catalog expressed as default routes, zero resolution changes for existing traffic | Existing tests pass unedited; selector admission test, specificity law, and one-binding-per-selector asserted by composition-time tests; fake future languages prove capability-agnosticism |
| **2 Runtime multi-slot** | Slot catalogs from deployment config; slot selection by pinned artifact; per-slot voice maps; `/info` lists all slots — proven in CI with **two reference engines in one process** | Both runtimes serve two artifacts concurrently in CI; refusal semantics unchanged; isolation suites pass |
| **3 Gateway routing + language plumbing** | Resolution with language/voice inputs; deployment-keyed clients; ~~additive contract field~~ (withdrawn by F-M5-7 — the contract is untouched); TTS ledger language derived from the voice (closes the M4 gap); `language_not_supported` refusal + demand recording | E2E: one public model, two artifacts, language-routed, over real HTTP; leak-guard extended; continuity fingerprint green per route |
| **4 Evaluation identity** | Baselines gain (public model, language, artifact, build, deployment, **corpus version**, benchmark, judge); per-language slices; existing baselines re-recorded as `en` instances; the Hindi record formally committed — **and honest: no Hindi speech corpus exists (F-M5-8), so the Hindi slice measures hallucination under a Hindi declaration and is explicitly not a quality claim** | Baseline records committed; the runner verifies the resolved artifact against live `/info`; reproduction from records alone |
| **5 Promotion workflow + ladder enforcement** | The three promotion classes as procedure; evidence-reference validation at composition; per-route switching-test harness (C3 per-language); rollback-as-revert demonstrated | A full promotion and rollback executed end-to-end on reference artifacts, with the diff-as-record |
| **6 Deployment topology** | Compose overlays for multi-deployment; deployment→URL map; cold-start and residency measured per slot | Two deployments of one capability serving side by side; measurements recorded |
| **7 Production validation** | The whole path with **real incumbent Hindi STT routing** (same artifact, now a measured, promoted route) + reference-engine TTS second-language simulation; per-route continuity fingerprints; language analytics complete for both capabilities | Validation doc with evidence; reconciliation clean; PRD language table honest |
| **8 Close** | ADR ledger review, PRD v0.9 (ladder published), ARCHITECTURE v0.6 (routing invariants, Two Vocabularies), M5 review incl. the M5→research-track handoff contract, version 0.6.0 | Review committed; founder items re-asserted |

## 18. Non-goals of Milestone 5

Each is anticipated by the architecture; none is built. A request for
any of these during M5 is a scope change and goes through review.

- **Adopting any model** — Research Framework territory, always.
- **Candidate research or benchmarking** — same.
- **Serving Strategies** (fallback, cascade, A/B, ensembles, failover) —
  boundary reserved (§5c); Registry V2 designs them.
- **Shadow/canary traffic splitting** — binding stages reserved (§5b).
- **Detection-based routing** — seam named (§4.2); evidence first.
- **`speaker_similarity` implementation** — before the second rebinding,
  per F-M5-4.
- **The Arabic corpus** — evaluation-track work item (F-M5-6), not an
  M5 step.
- **Dataset Registry** — reserved (REGISTRY_V2 §10.2); citations are
  version ids.
- **Per-customer routing** — V2, behind the Selector Admission Test.
- **Any pricing or admission change** — the commercial plane is
  complete and closed for this milestone.
