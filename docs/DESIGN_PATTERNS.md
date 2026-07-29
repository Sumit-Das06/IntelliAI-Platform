# Design Patterns

The blessed ways to build things here, each with its living example. If a
new need doesn't fit a pattern below, that's an architecture conversation
(and possibly an ADR), not an improvisation.

## Composition & wiring

- **App factory** — apps are built by `create_app(settings=None)`; importing
  a module never constructs anything. Tests build their own configured
  instances. *(`main.py`)*
- **Lifespan resources** — anything with a connection or thread is created
  before `yield`, destroyed after, in reverse order. *(engine in `main.py`)*
- **Dependency injection** — endpoints receive everything via annotated
  aliases in `api/deps.py` (`SettingsDep`, `SessionDep`, `HealthDep`).
  Module-level state is a review-blocker; add a new dependency by adding an
  alias, not an import-time singleton.

## Layering

```
router (thin: parse → call → shape)
  → service (business rules; owns transaction *shape*)
    → repository (the only SQLAlchemy in the codebase)
```

- Routers live in domain *packages* under `api/v1/`; nothing outside `api/`
  is version-aware.
- **Module charter** — every new module/package is introduced answering:
  why it exists; what it owns; what it must NEVER own; who it may talk to;
  who it must never depend on; how it scales. The charter lives in the
  module docstring. *(see `core/`, `db/repositories/`)*

## Configuration

New config = a field on an existing settings group, or a new
`BaseSettings` group with an `INTELLIAI_<GROUP>_` prefix, composed into
`Settings`. Secrets are `SecretStr`, unwrapped at the last moment. Update
`.env.example` in the same commit — it is the documentation.

## Errors

Raise typed `IntelliAIError` subclasses with a machine `code` and `param`
where identifiable. Never render an envelope by hand; never raise bare
`HTTPException` in domain code. New failure modes get new *codes* (free);
new *types* are SDK-breaking events requiring an ADR. *(ADR-0009)*

## Logging

Event names are `noun_verbed` past-tense facts (`request_completed`,
`app_started`), stable forever once dashboards may depend on them. Context
(org, key, model) is *bound* via contextvars at the boundary, never passed
parameter-by-parameter. New standard fields = one processor, never edits to
call sites. *(ADR-0008)*

## Health

A new dependency implements the `HealthCheck` protocol (name, critical,
async `check()` that raises on failure) and registers in `default_checks`.
`critical=True` means "cannot serve without it" — decide honestly; it
drives 503s and pager noise. *(`core/health.py`)*

## Migrations

`make migration m="…"` drafts; a human edits and owns the result.
Autogenerate cannot see renames (drop+add = data loss) or data transforms —
write those by hand. Production-safe ordering: expand → migrate → contract.
Every migration's `downgrade` must actually work. *(ADR under `db/base.py`
conventions; ADR-0010)*

## Adding a new AI domain (the recipe)

1. Domain package under `api/v1/<domain>/` exposing a router.
2. Typed request/response schemas (OpenAI-compatible where free).
3. Service layer calling inference via the runtime contract — never a
   concrete engine, never a named provider.
4. Registry entries carrying capability metadata (languages, license…).
5. Errors mapped to existing types + new codes. Zero changes to `core/`.

## Anti-patterns (instant review-blockers)

- SQLAlchemy imports above the repository layer
- Bare `HTTPException` in domain code; hand-built error JSON
- Module-level singletons; work at import time
- Blocking I/O (`requests`, `time.sleep`, sync drivers) in async paths
- Unscoped queries on tenant-owned tables
- Prose log messages; f-string log interpolation
- A "util(s)" module — name the responsibility or don't create it
