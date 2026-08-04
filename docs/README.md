# docs/ — Documentation (a first-class product)

Start here: [CONSTITUTION.md](CONSTITUTION.md) (the company's highest-level
principles), then [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md),
which maps where every kind of truth lives.

- `CONSTITUTION.md` — the charter: 20 permanent principles above all other docs.
- `STRATEGY.md` — index of the strategy stack (AI strategy, capabilities,
           foundation models, model identity, Registry V2, fine-tuning,
           research report, founding review) with reading order and cadence.
- `ARCHITECTURE.md` — the current system, updated at every milestone close.
- `PRD.md` — Product Requirements Document: the single source of truth for
           product decisions. Updated in the PR that closes each milestone.
- `ENGINEERING_PRINCIPLES.md` — the philosophy that breaks ties.
- `DESIGN_PATTERNS.md` — the blessed ways to build things here.
- `SECURITY_GUIDELINES.md` — judgment rules tooling can't automate.
- `TESTING_STRATEGY.md` — what we test, at which level, and why.
- `DOCUMENTATION_STANDARDS.md` — this map itself.
- (Workflow & review checklist: [/CONTRIBUTING.md](../CONTRIBUTING.md) at repo root.)
- `research/` — the foundation model research lab: governing framework,
           append-only model status ledger, and per-candidate dossiers.
           Knowledge base only — code experiments live in `/research` at
           the repo root.
- `adr/` — Architecture Decision Records (template: 0000). Write one BEFORE any
           significant decision lands; update Status when superseded. ADRs record
           HOW we build; the PRD records WHAT and WHY.
- `api/` — public API documentation source (Milestone 11; generated from the
           gateway's OpenAPI spec, never hand-drifted).
- `milestones/` — the official close-out review of every milestone.

Docs evolve in the same PR as the code they describe.
