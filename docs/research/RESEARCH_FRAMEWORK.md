# IntelliAI Foundation Model Research Framework

| | |
|---|---|
| **Status** | IN FORCE — founder-approved 2026-08-04 |
| **Version** | 0.2 |
| **Last updated** | 2026-08-04 |
| **Nature** | PERMANENT process. This document never names a model; every model lives in [MODEL_LEDGER.md](MODEL_LEDGER.md) with dated evidence. §16 (research priorities) is the one deliberately LIVING section — it evolves through evidence, every change dated in the change log. |
| **Role of this document** | The governing research process for the two asset classes IntelliAI permanently researches: foundation models and, from v0.2, datasets (§12). It connects instruments that are already in force — the scoring framework ([FOUNDATION_MODELS.md §1](../FOUNDATION_MODELS.md)), the licensing policy ([ADR-0005](../adr/0005-permissive-model-licensing-policy.md)), the evaluation methodology ([SPEECH_EVALUATION.md](../../ml/evaluation/SPEECH_EVALUATION.md)), and the fine-tuning framework ([FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md)) — into one stage-gated pipeline with a status lifecycle and an append-only decision ledger. It defines the process; it deliberately redefines none of the instruments. |
| **Consumed by** | every engine research thread; every capability opening (per the [STRATEGY.md](../STRATEGY.md) review cadence); the IntelliAI-STT v2 and IntelliAI-TTS v2 programs |

---

## 1. Charter and scope

The research program is IntelliAI's standing model laboratory. Customers
buy `intelliai-stt` and `intelliai-tts`; foundation models are replaceable
implementation details behind them. The laboratory's job is to know, at
all times and with evidence, which replaceable detail should be serving.
It researches two permanent asset classes: **foundation models** (§§3–11)
and **datasets** (§12) — the second because the long-term strategy (§14)
is built on data the way the first is built on evidence.

**The research program owns:**

- candidate discovery, dossiers, and license screening;
- dataset research: discovery, screening, and provenance of candidate
  datasets (§12);
- the technology watch (§13) and the living research priorities (§16);
- the model status ledger and its complete decision history;
- benchmark *plans* (what to measure, against which baseline, with which
  corpus and judge);
- adoption *recommendations* with cited evidence;
- standing watch over incumbents and the landscape.

**The research program must never own:**

- shipping decisions — the founder decides; research recommends;
- production code, registry state, or deployments — engineering executes
  adoption through the existing Registry/Runtime/Engine architecture,
  which this program does not redesign;
- benchmark *execution* — measurements are produced by the evaluation
  plane (`ml/evaluation`), whose records are the only numbers research may
  cite as evidence.

This mirrors the three-planes law recorded at M3: the causal chain is
one-way — *research → evidence → recommendation → founder decision →
engineering adoption*. Research that skips a link (recommending without
evidence, or "adopting" by writing code) is invalid by construction.

## 2. Epistemic discipline

Every claim in a dossier, ledger entry, or recommendation carries exactly
one label:

| Label | Meaning | Example |
|---|---|---|
| **Fact** | True by definition or by direct inspection, dated | "The repository LICENSE file reads Apache-2.0 (read at source, 2026-08-04)" |
| **Evidence** | A measurement in the evaluation ledger, reproducible from metadata | "round_trip_wer 0.072 EN, run 2026-08-03-kokoro-82m" |
| **Assumption** | Believed without verification — must be flagged and dated | "We assume the ONNX export matches PyTorch quality" |
| **Hypothesis** | A testable prediction that motivates work | "A dedicated Indic engine beats Whisper Small on Hindi by >5 WER points" |
| **Open question** | Known unknown, tracked until answered | "Does the model hallucinate on silence?" |

Standing rules, inherited from M1.5 method and now law for research:

1. **Verify at source, never from reputation.** Licenses are read on the
   model card or repository LICENSE on a stated date. Benchmark numbers
   from papers or leaderboards are *claims* (assumptions at best), never
   evidence — only our own evaluation records are evidence.
2. **Everything decays.** Every verification carries its date. A verdict
   older than the current decision must be re-verified before it is
   load-bearing (the [STRATEGY.md](../STRATEGY.md) cadence already
   requires this at capability opening).
3. **"Newer" is a fact, never an argument.** No status changes because
   something was released. A release is at most an intake trigger.

## 3. Status lifecycle

Every model in the ledger has exactly one current status:

| Status | Meaning | Granted by | Minimum required evidence |
|---|---|---|---|
| **Researching** | Registered; under active investigation | Research (intake) | A named trigger (§4 Gate 0) |
| **Promising** | Dossier complete; clean license screen; a credible, product-relevant hypothesis of what it would beat | Research review | Full dossier (§11), license verdict (Fact, dated), score per FOUNDATION_MODELS §1, explicit hypothesis vs a named baseline |
| **Approved for Benchmark** | A written benchmark plan is approved; engineering may spend effort measuring it | **Founder** | Benchmark plan (§4 Gate 4): corpus, judge, metrics, hardware, baseline-to-beat — reproducible from metadata |
| **Approved for Adoption** | Recommended and approved to become a serving engine | **Founder** | Evaluation-plane records beating the named baseline; re-verified license; deployment economics; risk register entry |
| **Rejected** | Failed a gate; no active work | Research (license/evidence) or Founder | The failing fact or evidence, cited |
| **Deprecated** | Was adopted; no longer a recommended serving engine | **Founder** | The replacement's switching-test evidence, or a forced trigger (license shift, upstream death — FINE_TUNING_STRATEGY Part 4) |

**Legal transitions:**

- *intake* → Researching
- Researching → Promising (research review passes)
- Researching | Promising → Rejected (any §8 rejection trigger)
- Promising → Approved for Benchmark (founder approves the plan)
- Approved for Benchmark → Approved for Adoption (founder; evidence in)
- Approved for Benchmark → Rejected (benchmark lost with no credible
  remediation) or → Researching (partial result spawned a new hypothesis)
- Approved for Adoption → Deprecated (replacement passed the switching
  test, or a forced trigger fired)
- **any status → Rejected** on a license change that fails ADR-0005
- Rejected → Researching **only on new evidence** (new version, license
  change, new capability) — recorded as a new dated entry, never by
  editing the rejection

**Append-only history law (founder directive, 2026-08-04).** A status
change never edits or overwrites a prior entry. It *appends* a dated
decision entry recording the new status, the reason, and the evidence it
rests on. The complete chain must always answer *when, why, and on what
evidence* every status changed. This is the same law the evaluation
evidence ledger already lives by: corrections and reversals are new
records. The ledger's current-status table is a derived convenience view;
the decision history is the source of truth.

## 4. Research workflow — stage gates

Gates are ordered cheapest-kill-first: the license screen costs an hour
and kills permanently; a benchmark costs engineering days. Never spend a
later gate's effort on a candidate that hasn't passed an earlier gate.

**Gate 0 — Intake.** A candidate enters the ledger as *Researching* with
a named trigger: a roadmap question, a watch trigger firing
(FOUNDATION_MODELS §14), a landscape release, a measured product gap, or
a founder request. No trigger, no entry — the ledger is not a catalog of
everything that exists.

**Gate 1 — License screen.** Full review per §5 *before any quality
work*. Fail ⇒ Rejected. This ordering is bought experience: F5-TTS and
XTTS lead quality tiers and are commercially dead to us; espeak-ng
arrived as a *transitive* GPL dependency inside an Apache model's
default pipeline and cost a milestone-level firewall to remove.

**Gate 2 — Desk research.** Build the dossier (§11): capability and
language claims, architecture, deployment profile, fine-tuning support,
ecosystem health. Score it with the permanent 8-criterion framework
(FOUNDATION_MODELS §1) — referenced, never redefined. Paper numbers are
recorded as *claims* with sources, labeled per §2.

**Gate 3 — Promising review.** The dossier must state, explicitly:
*which named baseline this model would beat, on which metrics, and why
that matters to the product* (revenue, language policy, cost, risk). A
candidate that is merely newer, larger, or higher on a leaderboard does
not pass. Pass ⇒ Promising.

**Gate 4 — Benchmark plan.** A written plan naming: corpus (version),
judge (identity — for speech, per the judge discipline in
SPEECH_EVALUATION §4), metrics (from the metric registry, with
directions), hardware, runtime configuration, and the baseline-to-beat by
name. The plan must satisfy the reproducibility-from-metadata rule —
an underspecified benchmark is "an anecdote, not a benchmark." Founder
approval ⇒ *Approved for Benchmark*. Execution belongs to engineering
sessions via `ml/evaluation`; results land in its append-only results
ledger.

**Gate 5 — Adoption recommendation.** An evidence-cited document: the
measured deltas vs the named baseline, the re-verified license verdict,
deployment cost at our economics (CPU-first, GPU-ready), the fine-tuning
path, and a risk-register entry (AI_RESEARCH_REPORT Part 7 format).
Founder approval ⇒ *Approved for Adoption*. Handoff to engineering is a
registry entry plus an engine module behind the existing contract —
nothing in this framework changes that architecture.

## 5. Licensing review process

Builds on [ADR-0005](../adr/0005-permissive-model-licensing-policy.md)
(permissive-only: MIT / Apache-2.0 / BSD / CC-BY class; named bans) and
the M1.5 finding that became a registry law: **verdicts are per artifact
version, never per family** — families have shifted permissive→NC and
back mid-line (Qwen2.5-VL sizes, Canary versions, BGE variants).

A license screen covers, each as a dated Fact with source URL:

1. **Weights license** — on the actual model card / LFS distribution we
   would pin, not the org's reputation.
2. **Code license** — inference code, official pipelines.
3. **Transitive dependencies** — everything the default serving path
   imports: phonemizers, tokenizers, alignment tools, decoders. *(The
   espeak-ng lesson: kokoro is Apache, its G2P chain imported GPL
   unconditionally. The serving chain's license is the license.)*
4. **Field-of-use and revenue traps** — MAU caps, revenue caps,
   non-compete clauses, synthetic-data restrictions (training-on-outputs
   matters to the flywheel).
5. **Patent posture** — Apache-2.0's explicit grant preferred; note
   silence where a license is silent.
6. **Training-data provenance risk** — recorded as a risk note, not a
   gate, unless a concrete legal exposure is identified.

**Re-verification triggers:** at Gate 5 (always, regardless of Gate 1
date); on any version bump of a pinned artifact; at capability opening
(STRATEGY.md cadence); when a watch trigger fires. A verdict is written
to the ledger with its date; the registry's license gate (per-artifact
verdict + date + source) is the enforcement point downstream.

## 6. Benchmarking methodology

The instrument is [SPEECH_EVALUATION.md](../../ml/evaluation/SPEECH_EVALUATION.md)
(methodology v1) and the `ml/evaluation` harness (`speech-eval`, `run`,
`bench`, `bench-tts`). This framework adds the research-side rules:

1. **Comparisons are valid only within same corpus version and same
   judge identity.** A challenger measured on a different judge than the
   incumbent's baseline proves nothing; re-baseline the incumbent first.
2. **Baselines are named company assets.** Every benchmark names the
   baseline it attacks; every result cites baseline names, never bare
   filenames. "What baseline did it beat?" must always have an answer —
   the chain of beaten baselines *is* our model history.
3. **Failures are evidence.** A candidate that crashes, hallucinates on
   silence probes, or times out produces records, not silence.
4. **Anecdote rule.** A number that cannot be reproduced from its
   recorded metadata (corpus, artifact, judge, runtime, hardware) may
   motivate a hypothesis but may never justify a status change.
5. **Production benchmarks accompany quality benchmarks** for adoption:
   the incumbent baselines pair a quality run with a containerized
   production benchmark (startup, ladder, memory, PRD verdicts). A
   challenger must present both before Gate 5.

## 7. Multilingual evaluation strategy

The Core Speech Language Policy v1 (recorded in the M3 design review,
PRD, and ARCHITECTURE) is the product law this strategy serves:
**English, Hindi, and Arabic are first-class product languages** —
requirements on the *product*, never on any single engine.

1. **Per-language evidence bar.** "Complete support" for a language is
   defined measurably: a corpus, a quality baseline, and a production
   benchmark for that language. A model "supporting Arabic" on its card
   is a claim; Arabic support exists when the evidence triple exists.
2. **Every candidate is evaluated per language, plus code-mixed.**
   Corpus categories already encode this (the `TextCategory` pattern:
   per-language cases plus `code_mixed`, proper names, script-specific
   traps). Accent and dialect coverage enter as corpus categories, not as
   separate frameworks.
3. **Per-language engines are a legitimate outcome.** One multilingual
   model and several specialized models are competing *hypotheses*, both
   testable: compare the multilingual candidate against the best
   specialist per language, on the same corpus and judge. The
   architecture already routes multiple engines behind one public model;
   research must not privilege "one model for everything."
4. **A language may be gated by license, not capability.** Hindi TTS is
   the standing example: the capable path was GPL-encumbered, so the
   language is gated — "commercial cleanliness has higher priority than
   feature completeness." Language-support claims in dossiers must state
   the license status of the *language-specific serving path* (voice
   packs, G2P, lexicons), not just the base model.
5. **Arabic is the first standing research thread.** It has policy
   status, no corpus, no baseline, and no candidate engine — the ledger
   carries it as an open slot until candidates enter Gate 0.

## 8. Adoption criteria and rejection criteria

**Adoption requires all of:**

1. Clean license verdict on the full serving chain, re-verified at Gate 5
   (§5);
2. Beats the named baseline on the declared metrics, same corpus, same
   judge — evaluation-plane records cited (§6);
3. Deployment fits our economics: CPU-first viable today (or an explicit
   founder-approved GPU exception), GPU path open, memory and cold-start
   measured in a container;
4. A fine-tuning path exists (recipes, adapters, community precedent) —
   a model we cannot tune is a rented engine (FOUNDATION_MODELS §1
   rationale);
5. Ecosystem health: maintained upstream, credible org commitment,
   serving stack we can operate;
6. Risk register entry written (concentration, license trajectory,
   upstream viability), with named watch triggers.

**Rejection is triggered by any of:**

1. Non-commercial, copyleft, or trap-clause license anywhere in the
   serving chain, with no compliant path;
2. Loses to the baseline with no credible, written remediation
   hypothesis;
3. Upstream abandoned or archived with a decaying ecosystem (the Piper
   lesson: archived → GPL fork → exit);
4. Deployment economics broken for our serving classes with no plausible
   quantization/optimization path;
5. Safety or robustness disqualifiers our product cannot absorb
   (e.g. hallucination behavior that no pipeline gate can contain);
6. Founder veto (recorded with reason, like every other entry).

Rejection is permanent for the *evidence that caused it*, not for the
lineage: a new version with a changed license or fixed defect re-enters
at Gate 0 as a new dated entry.

## 9. Fine-tuning and pretraining decision framework

The question "should we adopt a new model?" always competes with
"should we improve what we serve?" The decision tree is ordered by cost,
and each rung must be *measured insufficient* before the next is funded:

1. **Configuration and prompting** — decoding parameters, pipeline
   gates (VAD), chunking strategy. Zero training cost.
2. **Vocabulary and lexicon** — pronunciation and domain terms. This is
   *platform* work (the Pronunciation Manager is a platform-level
   component by founder law — never an engine fix), plus STT biasing
   where supported.
3. **Adapters** (Ladder Stage 1, [FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md)
   Part 2) — LoRA/QLoRA on the incumbent lineage.
4. **Domain fine-tunes** (Stage 2) — when adapters plateau and the gap
   carries revenue.
5. **New engine adoption** (this framework, Gates 0–5) — when the
   incumbent *lineage* has a measured ceiling on a product requirement.
6. **Pretraining an IntelliAI-native model** (Stage 5) — only under
   FINE_TUNING_STRATEGY Part 4's conditions: a quantified paying gap, a
   data moat foundation models don't have, and a measured ceiling on
   tuned incumbents. Never before the evaluation harness can prove the
   ceiling exists.

**When is fine-tuning justified?** Part 4's answer, adopted verbatim:
a paying gap (Step 1) + a scored lineage (Step 2) + fine-tuning capital
that compounds within the lineage. **When is switching justified?** The
switching test: a challenger must beat *our tuned incumbent*, not the
stock incumbent, by a margin exceeding the full switching cost — unless
an override trigger (license shift, upstream death, architectural
ceiling) forces the question. Research's job at Gate 3 is to say, for
every Promising candidate, which rung of this tree it competes with.

## 10. Long-term model lifecycle

1. **Incumbents are watched, not trusted.** Each *Approved for Adoption*
   model carries named watch triggers in the ledger: license drift on new
   versions, upstream maintenance stalls, cadence stalls, quality of the
   successor landscape (FOUNDATION_MODELS §14 pattern). Watch triggers
   are reviewed at every milestone close (STRATEGY.md standing cadence).
2. **Re-evaluation cadence.** At every capability opening, the relevant
   verdicts re-run through the permanent scoring framework at the current
   date. Dated evidence in FOUNDATION_MODELS §§2–13 decays; the ledger
   inherits the same decay discipline via per-entry dates.
3. **Deprecation is a founder decision with evidence** — the switching
   test passed by a replacement, or a forced trigger. The deprecated
   model's ledger history, dossier, baselines, and evaluation records are
   never deleted: *models depreciate; knowledge compounds.* The evidence
   a model generated remains the ruler its successor was measured with.
4. **The ledger outlives every model in it.** Five years from now, the
   question "why did we leave X for Y in 2026?" must be answerable from
   the ledger alone — the append-only history law (§3) exists for that
   reader.

## 11. Research record formats

**The dossier** — one document per candidate under `docs/research/models/`,
named `<model>-dossier.md`. Drafting begins at Gate 2 (desk research);
**from Promising status onward a formal dossier is mandatory** (v0.2,
founder directive) — no candidate may hold Promising or any later status
without one. The division of labor is fixed: **the ledger stays concise**
(status, reason, evidence links); **the dossier carries the detailed
analysis**, and the ledger entry that grants Promising links to it.

Every dossier contains these thirteen sections (each claim labeled per §2):

| # | Section | Contents |
|---|---|---|
| 1 | Identity | Name, org, capability, artifact versions considered, Gate 0 trigger |
| 2 | Architecture | Model family and approach, parameter count, context/window limits, streaming properties (native or engineering path) |
| 3 | Languages | EN/HI/AR + code-mixed per §7 — claims vs evidence, incl. licensing of each language-specific serving path |
| 4 | Licensing | Per-version verdict: weights, code, transitive dependencies; source URLs; dates (§5) |
| 5 | Deployment profile | CPU viability, quantization support, container/offline fit, serving stack we would operate |
| 6 | Quality evidence | Our evaluation records (evidence) and external numbers (claims, with sources); robustness and hallucination behavior |
| 7 | Latency | TTFB / RTF / streaming latency — measured where we have records, labeled claims otherwise |
| 8 | Memory | Load and steady-state footprint at the target precision |
| 9 | Fine-tuning support | LoRA/QLoRA/adapters, official recipes, community precedent |
| 10 | Training support | Released training pipeline and data recipes — can the lineage be continued, not just adapted? (feeds §15) |
| 11 | Ecosystem | Maintenance activity, community, documentation, production adoption |
| 12 | Risks | License trajectory, concentration, org viability, named watch triggers; open questions carried explicitly |
| 13 | Recommendation | FOUNDATION_MODELS §1 weighted score (per-criterion), the Gate 3 hypothesis (what it would beat and why it matters), and the proposed next status |

**The ledger entry** — in [MODEL_LEDGER.md](MODEL_LEDGER.md), append-only:

```
YYYY-MM-DD — <Status granted> — <reason, one or two sentences> —
evidence: <links/facts with their own dates>
```

**The benchmark plan** and **adoption recommendation** are standalone
documents under `docs/research/`, referenced from the ledger entries that
cite them.

## 12. Dataset research — the second asset class *(v0.2)*

The program permanently researches **datasets** alongside foundation
models, and for the same strategic reason the evaluation corpora exist:
*models depreciate; knowledge compounds.* Evaluation corpora are already
permanent company assets by law ("models improve, corpora accumulate");
training and benchmark datasets join that same asset class. In the
long-term strategy (§14), datasets are the moat — every model in this
framework is replaceable, but data collected from our own consented
usage is something no upstream vendor has.

**What dataset research owns now** (research only — no collection or
tooling implementation until a future milestone opens it):

- discovery and screening of candidate datasets: public corpora,
  purchasable data, and collection strategies;
- license, consent, and PII screening — the §5 discipline applies
  unchanged, because dataset licenses trap exactly like model licenses
  (NC clauses, share-alike, field-of-use limits, consent provenance;
  consent-collected data is explicitly rewarded, per the data
  constitution);
- provenance documentation: source, date, license, collection method —
  recorded at intake, because provenance cannot be reconstructed later.

**Future dataset lifecycle** — placeholder stages, adopted now so future
milestones land in a named frame; definitions bind when the first
dataset milestone opens:

```
Collected → Verified → Annotated → Training Ready → Benchmark Ready → Production Dataset
```

- **Collected** — raw data acquired; provenance, license, and consent
  basis recorded at intake.
- **Verified** — integrity checked, deduplicated, license/consent
  verified, PII policy applied.
- **Annotated** — labels, transcripts, or alignments produced;
  annotation method and provenance recorded.
- **Training Ready** — split discipline enforced (training data never
  contaminates evaluation), format pinned, versioned immutable manifest.
- **Benchmark Ready** — eligible to become or extend an evaluation
  corpus (thereafter immutable once cited, per the corpus law in
  [SPEECH_EVALUATION.md](../../ml/evaluation/SPEECH_EVALUATION.md)).
- **Production Dataset** — a versioned company asset cited by training
  runs and lineage records.

Dataset statuses and history will live under the same append-only ledger
law as models (§3); a dataset ledger is created alongside the first
*Collected* entry, not before.

## 13. Technology Watch *(v0.2 — permanent)*

Every review cycle (milestone close, per the [STRATEGY.md](../STRATEGY.md)
standing cadence) the program monitors:

- new foundation model releases;
- important research papers;
- license changes on watched lineages and incumbents;
- inference frameworks (vLLM/ONNX/GGUF/CT2-class);
- quantization methods;
- serving infrastructure;
- hardware changes (CPU/GPU economics at our serving classes).

**The law: watching never creates work by itself.** Technology Watch
feeds Gate 0 and nothing else. An observation becomes research only when
it carries a named trigger worth an intake entry, and every status
change still passes the full gates. This institutionalizes §2's rule —
"newer is a fact, never an argument": the watch exists so nothing
surprises us, not so novelty sets the agenda.

An observation that justifies intake becomes a Gate 0 ledger entry
citing it; an observation that doesn't is noted at the review and costs
nothing further.

## 14. The data flywheel *(v0.2 — permanent)*

IntelliAI's long-term improvement loop, stated as a cycle:

```
Research → Benchmark → Adoption → Serving → Real Usage
    ↑                                          ↓
Promotion ← Fine-tuning ← Dataset ← Data Collection
```

**This loop is the long-term ownership strategy of IntelliAI.** Serving
is not the end of the pipeline — it is the instrument that generates
real usage, and (under the data/consent constitution in
[AI_STRATEGY.md](../AI_STRATEGY.md)) the data that no foundation model
vendor has. Each pass around the loop shifts dependency from "the
upstream's future" to "our lineage's future" — the concentration hedge
of FOUNDATION_MODELS §14, generalized into the operating strategy.
Research sits at both ends of the loop: it selects what enters
(Gates 0–5) and evaluates what the loop produces (§15). The flywheel
runs on consented data, or it does not run.

## 15. Connection to the training program *(v0.2)*

This framework and [FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md)
are two views of one pipeline. The intended end-to-end evolution:

```
Foundation Models → Evaluation → Serving → Data Collection
  → Dataset Cleaning → Training Dataset → LoRA → Fine-tune
  → Merge → Promotion → Production
```

**This framework eventually governs both model adoption and model
improvement.** An IntelliAI fine-tune is a candidate like any other: its
identity is base lineage + dataset version + recipe; it gets a dossier
(§11), a benchmark plan against the named baseline — the *tuned or
stock incumbent*, per the switching test — and the same founder gates
before promotion. The ladder (FINE_TUNING_STRATEGY Part 2, Stages 0–5)
decides *when to climb*; this framework decides *how any rung's
artifact earns production*. Promotion mechanics (registry lifecycle,
FINE_TUNING_STRATEGY Part 5) remain engineering's, per §1. Nothing on
this chain is implemented today; the connection is stated now so the
first adapter, when the ladder calls for it, already knows its gates.

## 16. Research priorities *(v0.2 — LIVING list)*

Priorities order research attention; they never skip gates or lower the
evidence bar. Changes to this list are appended to the change log with
reasons — priorities evolve through evidence, like everything else here.

Initial list (founder-set, 2026-08-04):

| # | Priority | Anchor (see [MODEL_LEDGER.md](MODEL_LEDGER.md)) |
|---|---|---|
| 1 | English STT improvement | Incumbent adopted; production baseline 2026-08-03 |
| 2 | Hindi STT | Wedge gap anecdotally observed, unmeasured — open thread |
| 3 | Arabic STT | Open slot: no corpus, no candidate |
| 4 | English TTS | Incumbent adopted (EN); streaming verdict GO (M8) |
| 5 | Hindi TTS | License-gated; two candidate paths tracked |
| 6 | Arabic TTS | Open slot: no candidate |
| 7 | Translation | Capability not opened; verdicts dated 2026-07-31 |
| 8 | Speech-to-Speech | Composite capability; no commercial open native S2ST as of 2026-07-31 |
| 9 | Voice Cloning | Ownership lineage pre-assigned (P2 roadmap); consent-gated |
| 10 | IntelliAI native models | Parked at §9 rung 6: requires measured ceilings + data moat |

---

*Change log:*
- *0.2 (2026-08-04): Founder approval — status IN FORCE. Refinements
  folded, additive only: dataset research as the second permanent asset
  class with placeholder lifecycle (§12); Technology Watch (§13); the
  data flywheel stated as the long-term ownership strategy (§14);
  training-program connection — the framework eventually governs
  adoption and improvement (§15); living research priorities (§16);
  dossier mandatory from Promising, thirteen-section structure (§11).
  Status lifecycle, stage gates, append-only ledger law, founder gates,
  licensing process, multilingual strategy, adoption/rejection criteria,
  and the fine-tuning decision tree are unchanged — approved as-is.*
- *0.1 (2026-08-04): Initial framework — status lifecycle with append-only
  history law, six stage gates, licensing/benchmarking/multilingual
  processes, adoption/rejection criteria, fine-tune-vs-adopt-vs-pretrain
  tree, lifecycle, record formats. Status PROPOSED pending founder
  approval.*
