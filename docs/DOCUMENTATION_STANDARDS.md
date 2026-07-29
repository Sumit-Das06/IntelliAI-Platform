# Documentation Standards

Documentation explains intent and decisions; tooling enforces
implementation. This document maps where every kind of truth lives, so
nothing is written twice and nothing important is written nowhere.

## The single-source-of-truth map

| Question | Lives in | Never in |
|---|---|---|
| What are we building and why? | `docs/PRD.md` | READMEs, code comments |
| Why is it built this way? | `docs/adr/` | commit messages alone |
| What exists right now? | `docs/ARCHITECTURE.md` | (rewritten per milestone; never aspirational) |
| What is this module for? | its docstring (the charter) | a central wiki |
| How do I run/change things? | root README + Makefile + CONTRIBUTING | tribal memory |
| What happened historically? | `docs/milestones/` reviews | ARCHITECTURE.md |
| Public API reference | generated from OpenAPI (M11) | hand-written pages |

## Rules

1. **Docs ship in the PR that changes the truth.** A merged PR with stale
   docs is a bug; "docs later" means "docs never".
2. **Every package README answers:** what this is, what it must never
   become, how to run it. Three paragraphs, not thirty.
3. **Docstrings** exist where a name can't carry the meaning — module
   charters always; functions when behavior surprises (Google style).
   A docstring restating the signature is deleted on sight.
4. **Comments explain *why*, never *what*.** The code says what. A comment
   narrating the next line is noise; a comment explaining a non-obvious
   constraint ("asyncpg speaks libpq DSNs, not SQLAlchemy URLs") is gold.
5. **Generated artifacts are never hand-edited** (OpenAPI output, lockfiles,
   migration scaffolds get *reviewed and owned*, not regenerated blindly —
   but reference docs built from the spec are rebuilt, never patched).
6. **Prose style:** short, active, opinionated, example-first. Write like a
   senior engineer explaining to a capable newcomer — never like a policy.
7. **No document restates what a machine enforces.** Link to the config;
   don't transcribe it. If you find such a restatement, delete it.

## Update cadence

- PRD + ARCHITECTURE + milestone review: at every milestone close, in the
  closing PR (standing rule).
- ADRs: at decision time, before implementation.
- Everything else: with the change, same PR.
