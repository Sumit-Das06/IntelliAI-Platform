# Contributing to IntelliAI

This is the workflow handbook. Style, types, formatting, commit-message
format, and secrets are enforced by machines (`make check`, pre-commit, CI) —
if a rule can be automated, it lives there, not here. This document covers
what requires judgment.

## Setup (once per clone)

```bash
cp .env.example .env
make up        # full platform in Docker
make sync      # Python dependencies (uv)
make hooks     # git hooks — not optional
make check     # lint + types + tests: must be green before you start
```

On Windows, work inside WSL2. `make` with no arguments lists every command.

## Workflow

- **Trunk-based.** `main` is always releasable. Short-lived branches:
  `feat/…`, `fix/…`, `chore/…`, `docs/…` — hours to days, never weeks.
- **Small PRs.** One logical change per PR. If the description needs "and",
  split it. Squash-merge; the squashed message follows Conventional Commits.
- **A change is done when:** `make check` is green; behavior changes have
  tests; schema changes have a reviewed migration; significant decisions
  have an ADR; product-visible changes update the PRD; docs land in the
  same PR as the code they describe.

## Code review checklist

Reviewers check what machines cannot:

1. **Boundaries** — dependency direction respected (ADR-0001)? Nothing above
   repositories imports sqlalchemy? Nothing in `core/` is domain-aware?
2. **Charters** — new modules introduced with the six charter questions
   (see DESIGN_PATTERNS.md)? Existing charters honored?
3. **Tenancy** — every query on tenant-owned data explicitly org-scoped
   (ADR-0010)? Org identity derived from the API key, never from client input?
4. **Errors** — failures raise typed `IntelliAIError` subclasses; no bare
   `HTTPException` in domain code; new `code` values documented?
5. **Logging** — events, not prose; no new sensitive keys; nothing logged
   that shouldn't be (bodies, credentials)?
6. **Contracts** — any change to a `/v1` shape or the runtime contract
   called out loudly in the PR description? Additive only?
7. **Migrations** — reversible? Safe against the *currently deployed* code
   (expand → migrate → contract)? No table locks on hot paths?
8. **Tests** — do they pin behavior (would fail if the promise broke), not
   implementation details (would fail on harmless refactor)?

## When you disagree with a standard

Standards are decisions, not scripture. Challenge them with an ADR that
supersedes the old one — never with a silent exception in code.
