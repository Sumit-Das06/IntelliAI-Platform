# Model Rollout & Rollback — IntelliAI STT

> The minimum production procedure for changing what serves
> `intelliai-stt`, written at 14A. No promotion *tooling* exists yet —
> that belongs to the ML milestones; this documents how the pieces that
> already exist compose into a safe manual procedure.

## How serving is selected today

- **The registry is code-declarative.** `apps/api/src/intelliai_api/
  registry/catalog.py` pins, per public model and language, the exact
  artifact id a deployment serves, plus the `quality_baseline` naming
  the benchmark that justified it. Changing what serves customers is a
  **code change** — reviewed, tested, versioned — never a runtime flag.
- **Artifacts are hash-verified** at download by the STT runtime; the
  model volume is a cache, not a source of truth.
- **Every request's lineage is recorded** in the usage ledger (artifact,
  versions, runtime identity), so any historical transcript can be
  attributed to exactly what served it — before, during, and after a
  rollout.
- **Datasets and training artifacts are model-independent** (original
  audio bytes + pinned transcripts + recorded lineage), so a rollout
  never invalidates collected data.

## Promote

1. Land the catalog change (artifact pin / route) on `main` — tests
   green, including registry manifest tests.
2. On the VPS: `git pull && make prod-up` (rebuilds only what changed;
   the runtime downloads and hash-verifies the new artifact — first
   start may take minutes, the healthcheck allows it).
3. Verify: `curl -s https://$DOMAIN/health/ready` all-ok, then one real
   dictation per served language.
4. Export the new truth for readers outside the gateway:
   `make registry-manifest` (or the CLI equivalent) and archive it.

## Roll back

`git revert` the catalog commit → `make prod-up` → the same two
verifications. The previous artifact is still hash-pinned and usually
still in the model volume, so rollback is faster than rollout. The
ledger's lineage marks the exact boundary between the two models'
traffic.

## Invariants

- Customers only ever see `intelliai-stt`; engine and artifact names
  stay internal at every step.
- Never change the catalog and the runtime image in the same commit
  unless the change is inseparable — two knobs moved at once make a bad
  rollout ambiguous.
- A rollout with no `quality_baseline` update is a smell: what
  measurement justified it?

## What the future ML milestone adds (not now)

Evaluation harness against a held-out set, automated promotion gates,
and registry tooling that turns this manual procedure into a reviewed
pipeline. The seam is already there: `quality_baseline` in the catalog.
