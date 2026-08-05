# Milestone 5 Close-Out Review — Multilingual Foundation (v0.6)

- **Closed:** 2026-08-05
- **Design reference:** [5-multilingual-design.md](5-multilingual-design.md)
- **Decisions:** [ADR-0025](../adr/0025-serving-routes.md) (serving routes),
  [ADR-0026](../adr/0026-multi-artifact-capability-deployments.md) (deployments),
  [ADR-0027](../adr/0027-language-support-ladder.md) (the ladder)
- **Measurements:** [multi-slot runtime](../benchmarks/2026-08-04-multi-slot-runtime.md) ·
  [language routing E2E](../benchmarks/2026-08-05-language-routing-e2e.md) ·
  [deployment topology](../benchmarks/2026-08-05-deployment-topology.md) ·
  [promotion & rollback](../benchmarks/2026-08-05-promotion-rollback.md) ·
  [production validation](../benchmarks/2026-08-05-multilingual-production-validation.md)
- **Evidence:** [first multilingual baselines](../../ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md)
- **Tests:** 576 → **823**
- **Contract version:** 1 (unchanged through a **fourth** milestone)

## 1. Goal, and what it was not

M5 built **the socket, not the bulb**. When a Hindi or Arabic engine
eventually passes the Research Framework's gates, it must plug into a
platform that already knows how to route to it, evaluate it per language,
promote it with evidence, meter it invisibly, and roll it back — with
zero redesign.

Two boundaries held for eight steps: **no model was selected,
benchmarked, or researched**, and **no commercial semantics changed**.
The milestone was deliberately provable with what the platform already
owned — the incumbent STT model is multilingual, and the deterministic
reference engines simulate any number of additional artifacts in CI.

## 2. What shipped

| Step | Delivered | Commit |
|---|---|---|
| 0 Governance | Design review, ADR-0025/0026/0027, founder decision ledger | `5f713c5` |
| 1 Registry V1.5 | `ServingRoute` + `RouteSelector`, the ladder, voice bindings, behaviour-frozen | `4da7616` |
| 2 Runtime multi-slot | Deployment slot catalogs, slot selection, per-slot voice catalogs | `b4e5352`, `92a3e49`, `019dc8c` |
| 3 Gateway routing | Language- and voice-resolved serving, deployment-keyed clients, honest refusals, TTS ledger language | `d17e6ce`, `d46af02` |
| 4 Evaluation identity | Nine-field record identity, the resolution manifest, slice coverage, first multilingual baselines | `d94d969` |
| 5 Promotion | Three bars, the Evidential Chain enforced both sides, promotion and rollback executed | `ba62c5e` |
| 6 Deployment topology | Deployment → URL map, the naming law enforced at startup, packing measured | `8d426ab` |
| 7 Production validation | Shipped catalog, both real engines; two defects found and fixed; ladder coverage | `9148628` |
| 8 Close | This review, PRD v0.9, ARCHITECTURE v0.6, version 0.6.0 | — |

**Eight architectural laws** were ratified during the milestone and are
now promoted to [ARCHITECTURE.md](../ARCHITECTURE.md) invariants 13–20:
the Two Vocabularies, the Language Support Ladder (with its lifecycle and
corpus precondition), Routing Is Resolution with the Selector Admission
Test and the Specificity Law, the Route/Strategy Boundary, the Three
Identities, the three-language distinction, the Evidential and promotion
chains, and language's independence from admission and price.

## 3. Architectural discoveries

Things that were *learned*, not designed.

**The routing seam already existed.** Every runtime request had carried a
pinned artifact id since M2; the gateway had always pinned it from
registry resolution; the runtime had always refused a mismatch. M5 did
not build a router — it taught the registry to give a different answer
and the runtime to host more than one. `lookup()` became slot *selection*
where it had been slot *validation*: same call, same refusal, more
answers available.

**`runtime-core` needed zero lines.** `ModelManager` had been multi-slot
since M2 (`SlotSpec`, `DEFAULT_SLOT`, uniqueness validation); the
runtimes simply configured one slot. The most load-bearing capability of
the milestone was a configuration change to machinery written three
milestones earlier.

**One constraint turned a law into structure.** `ModelManager` hands the
warm-up probe *only the engine* — no slot, no artifact — and runtime-core
was not changing. That forced the synthesis voice catalog to be keyed by
the **loaded engine instance**, which is the one key both callers hold.
The result is stronger than the design asked for: "voice lookup happens
after slot selection" stopped being a comment and became unbypassable,
because the selected engine *is* the key and no global map remains.

**A slice can be honest about being thin.** The Hindi evidence record
carries `natural_speech_clips: 0` and `is_quality_claim: false` as
*data*, not prose. A future reader cannot skim past it, and the
promotion bar reads the same field.

**The declaration is an experimental variable.** With no Hindi corpus,
declaring the *same* deterministic audio as `en` and as `hi` made the
effect of the declaration measurable with no third-party data at all.
That is what produced the milestone's most useful finding.

**Policy arrives after history.** A ladder-coverage check compares
present policy against past facts, and history predates policy. On the
dev database it fires on fixtures. The check is right; the fixtures are
wrong.

## 4. Rejected alternatives (the ones worth remembering)

| Rejected | Why |
|---|---|
| Runtime-side engine selection / fallback chains | The data plane making a control-plane decision — invisible to promotion, unattributable in evaluation, and an unauthored Serving Strategy |
| Gateway `if language == …` | Registry logic that escaped its authority: untestable at composition, invisible to the licence gate |
| Detect-then-route STT | A two-pass architecture bought before its evidence exists; content-dependent routing makes the serving path non-deterministic from the request |
| A generic match-dict selector | A stringly-typed policy engine no composition-time validation can defend; every typo a silent routing miss |
| An `experimental` ladder rung | A fourth home for a fact with three; divergent sources of truth for experiment status is the five-year failure mode |
| Separate per-language public models (`intelliai-stt-hi`) | Breaks the Language Policy's promise — three languages, *one* product — and makes every customer integration language-aware |
| One fat process hosting every engine | Memory wall on CPU and a shared blast radius across languages |
| Engine-named services or deployments | Breaks exactly when the engine changes — now refused at startup, not merely discouraged |
| Evaluation importing the registry | Reverses the dependency direction; the resolution manifest is the seam instead |
| Evaluation falling back from `hi` to the default route | A reader that falls back is routing — quietly, about a language the registry may have deliberately refused |
| A `promote()` function | Closes the one-way chain into a loop; the diff is the promotion record precisely because a human wrote it |
| Defaulting the quality bar | A promise checked against a threshold nobody chose is not a promise anyone made |
| Adding the planned contract field | It already existed (M3) and F-M5-7 leaves it unpopulated: nothing public can fill it and no engine reads it |

## 5. Production validation summary

The whole path on the **shipped catalog**, both real engines, over real
sockets. It found two defects — which is the point of doing it.

**A regional tag reached the engine and became a 500.** `hi-IN` routed
correctly to `hi`, then the gateway forwarded the *raw* tag; faster-whisper
accepts base subtags only. The normalization law was being applied at the
routing boundary and nowhere else. Fixed: the engine is told what routing
decided, never what the customer typed. A Step 3 test had **encoded** the
defect by asserting the opposite, and passed for two steps because a fake
runtime accepts anything.

**The adapter let a library exception escape.** Any unaccepted language
would have produced a 500 rather than a 400; the whisper adapter now
translates it to `INVALID_INPUT`.

After the fixes: all five transcription paths and all three synthesis
paths serve; the ledger carries language, artifact and deployment for
both capabilities; reconciliation is clean; ladder coverage shows zero
contradictions when properly scoped; and the **per-route commercial
fingerprint is identical across `en`, `hi` and `ar`**.

Two findings recorded without diagnosis, because the numbers stand
either way: **Hindi costs ~30 s where English costs 1.4 s** on the same
one-second clip, and **Arabic emits text on pure-tone input** where
English and Hindi emit nothing. Both are exactly what the `available`
rung exists to collect.

## 6. Measurements — and what they established

| Measurement | Result | Architectural conclusion |
|---|---|---|
| Multi-slot residency, 1→8 hosted artifacts | RSS flat (~1 MiB, noise); readiness and `/info` flat | Hosting more artifacts costs what the artifacts cost and **essentially nothing else**; residency is a property of the models, not the mechanism |
| Real deployment, second artifact added | +0.2 ms startup, no measurable memory | Multi-artifact hosting is free on top of a real engine |
| Packed vs isolated (whisper + one artifact) | 407.2 MiB vs 461.7 MiB | **Isolation costs one interpreter (~54 MiB)** — ~4 % of that engine's container residency. Cheap relative to models, which is why F-M5-5 chose isolation |
| Language-routed refusal | 19 ms vs ~95 ms served | The measurement of *"refused before crossing a plane"* — no runtime call, no inference, no ledger write |
| Deployment isolation under failure | `hi` → 503, `en` → 200 | Partial multilingual availability is honest by construction; a down deployment 503s its own routes only |
| English baseline, v2 corpus | WER **0.000**, identical to M2 | Adding a language did not reset the platform's history: v1's clips carried forward byte-identical |
| Hindi vs English declaration, same non-speech audio | 13 698 ms vs 1 462 ms (runtime); ~30 s vs 1.4 s (production) | **The Hindi route's latency profile is not the English route's**; capacity planning per language is a real concern |
| Commercial fingerprint per route | Identical across three languages | Routing changes which artifact serves and nothing commercial — the M4 invariant holds at the routing layer |

## 7. ADR review ledger — do the decisions still hold?

| ADR | Implemented as designed? | Amendments during implementation | Assumptions proven false | Review triggers | Wording |
|---|---|---|---|---|---|
| **0025** serving routes | **Yes**, all eight decision points | None | None | Unchanged: a second selector dimension, coordinated routes, sustained observed/declared mismatch, records outgrowing diffs — none reached | Clear as written |
| **0026** deployments | **Yes** | **Two, both additive.** *Amendment 1* (founder, Step 2 review): a slot hosts exactly one artifact at a point in time; replacing it is a deployment operation. *Amendment 2* (founder, F-M5-5): the three identities, and one artifact per deployment on CPU | None | Residency-headroom trigger **partially satisfied** — the interpreter cost is measured; per-hardware headroom still open. Service-discovery and GPU triggers unchanged | Amendment 2 supplies the vocabulary Decision 4 assumed |
| **0027** the ladder | **Yes**, all five decision points | **Three.** *Amendment 1* (F-M5-1): the ladder is a lifecycle; `available` requires **no** evidence — the original "measured at least once" was withdrawn as circular. *Amendment 2* (F-M5-2): the initial rungs. *Amendment 3* (founder, after Step 4): the corpus precondition | **One, and it mattered.** The design assumed Hindi had a corpus because the M2.5 *synthesis* corpus contains Hindi **text**. Transcription needs Hindi **audio** with committed transcripts, which does not exist — F-M5-8 | The `experimental`-rung reopening test held (never reopened). Shadow-billing trigger not reached. **New in practice:** the first `available` language generating revenue-bearing traffic — not reached | Amendment 1 corrected Decision 1's `available` clause in place, with the amendment cited |

**All three M5 ADRs hold.** Every amendment was additive or a founder
ruling; none reversed a decision. Two earlier ADRs were touched and both
survived: **ADR-0016** (contract) proved to already contain the field M5
planned to add, and **ADR-0022**'s watch item from M4 close — *"two
models under one capability with different cost profiles"* — is now
**live**: Hindi and English share `intelliai-stt` with an order-of-magnitude
latency difference. The M4 answer stands: capacity differences surface as
the runtime's honest 503, never as a 429 or a price.

## 8. Founder decisions

| # | Decision | Status |
|---|---|---|
| **F-M5-1** | A language always enters at `available`; promotion needs benchmark + evaluation evidence + production baseline + explicit approval; no skipping | ✅ Ruled 2026-08-04, enforced by the evidence bar |
| **F-M5-2** | Initial ladder: STT `en` supported / `hi`,`ar` available; TTS `en` supported / `hi`,`ar` unavailable | ✅ Ruled 2026-08-04, shipped |
| **F-M5-5** | One artifact per deployment on CPU; packing supported, not default | ✅ Ruled 2026-08-05 on measured evidence |
| **F-M5-7** | No public TTS language field in M5; language via voice selection | ✅ Ruled 2026-08-05; the contract field stays unpopulated |
| — | The corpus precondition: no language above `available` without an owned or adopted versioned corpus | ✅ Ruled 2026-08-05, ADR-0027 Amendment 3 |
| **F-M5-3** | Absolute per-language quality bars | ⏳ **Open** — `enablement_test` refuses every enablement until ruled, by design |
| **F-M5-4** | Voice rebinding evidence bar | ⏳ Open — gates the first rebinding |
| **F-M5-6** | Arabic corpus commissioning | ⏳ Open — blocks all Arabic progress; Arabic is publicly `available` and unmeasured |
| **F-M5-8** | **Hindi speech corpus** (raised at Step 4) | ⏳ Open — blocks Hindi promotion; the design assumed this asset existed |

## 9. Technical debt

| Item | Trigger |
|---|---|
| **Hindi/Arabic speech corpora** | F-M5-8 / F-M5-6 — blocking for any promotion above `available` |
| **Test fixtures write `origin=customer`** | Second consumer of the M4 residue lesson; makes unscoped analytics lie |
| **Persist request events** | Third consumer now — `language.refused` demand evidence and the requested-language fact both live in the log stream |
| **Whisper's Hindi latency** | Undiagnosed; capacity planning per language is blocked on understanding it |
| **STT quality baselines predate baseline naming** | Step 4 cites a christened name going forward; the M2 record is cited by path |
| **`available` rung publicly documented, not yet surfaced by API** | `/v1/models` does not yet project ladder rungs; the registry can answer |
| Carried from M4 | Invoice document, reserve/settle, rollup-backed quota, binary idempotency replay, Postgres role hardening, published pricing |

## 10. Lessons

**A fake that accepts everything cannot fail the way a real engine
does.** The `hi-IN` defect passed two steps of tests because the fake
runtime accepted any language — and one test had *encoded* the defect as
an assertion. Fakes prove wiring; only real engines prove behaviour.

**Apply a normalization law at every boundary it names, not the first
one.** Routing normalized; the engine call did not. The law was right and
its application was partial, which is indistinguishable from a bug.

**An adapter's job includes translating "no".** The whisper adapter
converted results faithfully and let the library's rejection escape as a
500. Contract-shaped in, contract-shaped out — *including* refusals.

**Scope every read of a shared database.** Third occurrence. This time an
unscoped read produced a confident *false alarm* rather than a false
pass, which is the same defect wearing the other face.

**The best structural laws come from constraints you refuse to relax.**
Keeping `runtime-core` frozen forced the engine-keyed voice catalog,
which is stronger than the design's own proposal.

**Write down what a record does not contain.** `is_quality_claim: false`
does more work than any paragraph of caveats, because the promotion bar
can read it.

## 11. M5 → Research Track handoff

The milestone's real output is a boundary. Everything below is now
decidable independently on each side.

```
   RESEARCH TRACK                          ENGINEERING
   (Research Framework, MODEL_LEDGER)      (this platform)

   candidate selection ─────────┐
   benchmarking                 │
   datasets & corpora           │  proposes
   fine-tuning                  │  (evidence + citations)
   promotion PROPOSALS ─────────┼──────────►  promotion EXECUTION
                                │             routing
                                │             serving
                                │             registry
                                │             deployment
                                └──────────    (verdicts, gates, diffs)
                                   informs
                                (production facts:
                                 observed languages,
                                 mismatch rates,
                                 unserved demand)
```

**Research owns** which model, measured how, on what data, and whether it
is worth proposing. **Engineering owns** what serves, where it runs, what
is promised, and how a proposal becomes production. Neither may do the
other's job: engineering may not adopt a model, and research may not
change registry state.

**The interface between them is three artifacts**, all of which now
exist:

1. **The resolution manifest** — registry state, exported, drift-guarded.
   Research reads what actually serves; it never asks an operator.
2. **The evaluation record** — nine-field identity, self-contained,
   reproducible from records alone.
3. **The promotion proposal** — a verdict plus its citations, which a
   human turns into one reviewed diff.

### Why a new language now needs no architectural work

Adopting a language engine is: an **artifact record** (with its
per-version licence verdict), a **deployment** that hosts it, a **route
binding** with its ladder rung and serving-path verdict, and its
**evidence**. That is four records and a config value.

What it explicitly does *not* require, each proven during M5 rather than
asserted:

- **No contract change** — `CONTRACT_VERSION` is 1 through a fourth
  milestone; the synthesis language field M5 planned to add already
  existed and stayed unpopulated.
- **No `runtime-core` change** — zero lines, twice over.
- **No gateway logic** — neither service contains a branch on language.
- **No commercial change** — the fingerprint is identical per route, in
  production, on real traffic.
- **No public API change** — routes, shapes and errors unchanged;
  additions are additive only.
- **No new evaluation machinery** — an invented artifact on an invented
  deployment evaluated end to end with zero code changes.
- **No rollback plan** — rollback is a revert to evidence that never
  expired.

## 12. Definition of Done

| # | Criterion | Status |
|---|---|---|
| 1 | Registry resolves per language and per voice from declarative state | ✅ |
| 2 | One runtime process hosts N artifacts; runtime-core unchanged | ✅ zero diff |
| 3 | Gateway routes by declared intent; honest refusal + demand evidence | ✅ |
| 4 | Evaluation identity complete and reproducible from records alone | ✅ |
| 5 | Promotion bars, the Evidential Chain, and rollback-as-revert | ✅ executed end to end |
| 6 | Deployment topology configurable; naming law enforced | ✅ startup refusal |
| 7 | Production validated on the shipped catalog with both real engines | ✅ two defects found and fixed |
| 8 | Contract, runtime-core, commercial plane, public APIs unchanged | ✅ |
| 9 | Founder decisions F-M5-1/2/5/7 + the corpus precondition ruled and applied | ✅ |
| 10 | PRD v0.9, ARCHITECTURE v0.6, version 0.6.0 | ✅ |

## 13. Retrospective

**Confirmed.** That the M2/M3 architecture was right: the routing seam
existed, `ModelManager` was already multi-slot, artifacts were already
pinned per request, and the registry was already the resolution
authority. M5 spent most of its effort *naming* what was already true and
almost none building new mechanism. That the commercial plane needed no
redesign — asserted at M4 close, now measured per route in production.

**Rejected.** That the runtime contract needed a new field: it had one
already, unused since M3, and the design's "one additive field" figure
was wrong from the start. That Hindi had a corpus: the synthesis corpus
has Hindi *text*, and transcription needs *audio*. That a switching test
could be binary: the `TRADE` verdict exists because a wash on aggregate
with movement underneath is a human's call.

**Surprises.** Declaring Hindi costs an order of magnitude more inference
than declaring English on identical audio — nobody predicted a *latency*
cost to a language declaration. Arabic hallucinates on pure tones where
English and Hindi do not. And a test written in Step 3 turned out to have
encoded a defect as an assertion, which passed until a real engine
disagreed.

**What becomes simpler forever.** Every future capability inherits the
ladder, the route record, the identity, and the chain: adding OCR or
translation languages needs no new vocabulary. Every future engine
adoption is four records. Every future promotion has a verdict with
findings instead of an argument. Every future deployment question has a
measured number behind its default. And every future milestone can
answer "what serves this customer, why, and on what evidence?" from
immutable records alone.
