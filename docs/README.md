# docs/ — Documentation (a first-class product)

- `PRD.md` — Product Requirements Document: the single source of truth for
           product decisions. Updated in the PR that closes each milestone.
- `adr/` — Architecture Decision Records (template: 0000). Write one BEFORE any
           significant decision lands; update Status when superseded. ADRs record
           HOW we build; the PRD records WHAT and WHY.
- `api/` — public API documentation source (Milestone 11; generated from the
           gateway's OpenAPI spec, never hand-drifted).

Docs evolve in the same PR as the code they describe.
