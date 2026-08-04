# IntelliAI Strategy Stack — Index

> The entry point for all strategy work. Produced by Milestone 1.5
> (2026-07-31, [review](milestones/1.5-strategy-review.md)); governed by
> the [documentation governor](PRD.md#6-feature-roadmap): every strategy
> document names the milestone that consumes it, and no two consecutive
> milestones may both be documentation-only.

## Reading order for a new engineer

1. [CONSTITUTION.md](CONSTITUTION.md) — 20 minutes, mandatory
2. [ARCHITECTURE.md](ARCHITECTURE.md) + [PRD.md](PRD.md) — the system and the product
3. [CAPABILITIES.md](CAPABILITIES.md) + [MODEL_IDENTITY.md](MODEL_IDENTITY.md) — the nouns everything else uses
4. The rest, as your work touches them

## The documents

| Document | Role | Nature | Consumed by |
|---|---|---|---|
| **[CONSTITUTION.md](CONSTITUTION.md)** | The charter — 20 permanent company principles over four domain constitutions | Permanent; amended only by recorded supersession | every milestone |
| **[AI_STRATEGY.md](AI_STRATEGY.md)** | AI & data law: the flywheel, data/consent constitution, public-model philosophy, lineage, dual lifecycles, hardware posture | Domain constitution (§7 is law) | every AI milestone; M4 metering; M9 evaluation |
| **[CAPABILITIES.md](CAPABILITIES.md)** | The capability map: 11 primitives, composites, artifact-producing capabilities, admission test, 3 serving classes, phased P1–P5 roadmap | Semi-permanent map; primitives change only via admission test | M2 onward (every `api/v1/<domain>/` package traces here) |
| **[FOUNDATION_MODELS.md](FOUNDATION_MODELS.md)** | Which lineages we build on — **two documents in one**: a permanent scoring framework and a dated research snapshot (see its reading guide) | Framework permanent; verdicts decay from 2026-07-31 | M2 (STT), M3 (TTS), each capability's opening |
| **[MODEL_IDENTITY.md](MODEL_IDENTITY.md)** | What a "model" is: capability → public model → routing → artifact → build → deployment → runtime; ownership; 12 identity rules | Domain constitution (§9 statutes) | Registry V1 (M2) shape; Registry V2 (M9) |
| **[REGISTRY_V2.md](REGISTRY_V2.md)** | The control plane: record/resolution planes, admission test, information classes, interaction contracts, 14 laws, definition of done | Domain constitution (§12 is law); architecture conceptual | M2 (V1 as its seed); M9 (V2 implementation) |
| **[FINE_TUNING_STRATEGY.md](FINE_TUNING_STRATEGY.md)** | How serving becomes owning: the per-capability ladder (Stages 0–5), data strategy, switching test, capability tiers, customer fine-tuning philosophy | Domain constitution (Part 10 is law); strategy | fine-tuning track from first adapter (post-eval-seed) through P5 |
| **[AI_RESEARCH_REPORT.md](AI_RESEARCH_REPORT.md)** | The synthesis: 2026 landscape direction, position, 18 load-bearing decisions, consolidated risk register, recommendations | Snapshot with durable reasoning; risk register reviewed at every milestone close | milestone planning; investor/new-hire onboarding |
| **[FOUNDING_STRATEGY.md](FOUNDING_STRATEGY.md)** | The Day-0 re-founding review: what would change (discovery, eval seed, docs governor), refusal list, moat honesty, 22 mistakes, adversarial self-review | Review document; its Part 11 was extracted into CONSTITUTION.md (which is canonical) | company-level reviews; the refusal list at every "should we build X?" |
| **[research/RESEARCH_FRAMEWORK.md](research/RESEARCH_FRAMEWORK.md)** | The model research lab's governing process: status lifecycle, stage gates, licensing review, benchmarking rules, multilingual strategy, adopt-vs-tune tree — with the append-only [MODEL_LEDGER.md](research/MODEL_LEDGER.md) as the status of record | Permanent process (PROPOSED, pending founder approval); ledger is a living append-only record | every engine research thread; capability openings; STT v2 / TTS v2 programs |

## Standing review cadence

- **Every milestone close:** risk-register sweep (AI_RESEARCH_REPORT Part 7 triggers) · foundation-model watch triggers (FOUNDATION_MODELS §14) · portfolio glance (MODEL_IDENTITY §1b) · incumbent watch entries in [research/MODEL_LEDGER.md](research/MODEL_LEDGER.md).
- **Capability opening:** re-run the relevant FOUNDATION_MODELS verdicts through its permanent framework at the current date, appending outcomes to [research/MODEL_LEDGER.md](research/MODEL_LEDGER.md).
- **First ML hire:** structured red-team of this entire stack (pre-committed in AI_RESEARCH_REPORT Part 12).
- **v1.0 launch review:** full re-synthesis of AI_RESEARCH_REPORT.
