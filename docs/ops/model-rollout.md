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

## The ACTIVE promotion: Hindi → Qwen3-ASR E3 (approved at M26)

*(prepared at M17/M20 for the base candidate; superseded by the E3
fine-tune at M24; APPROVED by the founder 2026-08-19 and ACTIVATED by
the Milestone 26 promotion commit)*

The repository's production configuration now routes:

    hi / hi-IN → qwen3-asr-0.6b-hi-ft-e3@v1   (approved specialist)
    en / default / ar → whisper-small          (incumbent, unchanged)

The promotion landed exactly as this document rehearsed — one reviewed
commit moving three things together:

1. `infra/compose/prod.yml`: `INTELLIAI_STT_SLOTS:
   whisper,qwen3-asr:qwen3-asr-0.6b-hi-ft-e3` — the deployment hosts
   the EXACT approved artifact, never the generic family (a bare
   `qwen3-asr` would resolve to the base challenger and is
   guard-forbidden).
2. The catalog: the hi route serves `qwen3-asr-0.6b-hi-ft-e3` with the
   founder's approval record and the full evidence chain riding on the
   route (`quality_baseline`
   `2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23`,
   `production_benchmark` `2026-08-18-qwen3-e3-cpu-ladder`).
3. The guards: updated in the same commit to pin the NEW posture —
   Hindi must resolve to E3 exactly; base/E1/E2 stay forbidden in every
   committed deployment; the staging profile still refuses `prod`.

**Weights distribution**: E3 is deliberately NOT downloadable (its URL
never resolves). Deployment SEEDS the bytes into the model volume
(`models/qwen3-asr-0.6b-hi-ft-e3/v1/` + `make staging-seed-models`);
the store hash-verifies the placed files at every load exactly like a
downloaded artifact, and `prod-check` refuses to proceed without them.

**Rollback** stays `git revert` of the promotion commit: Hindi returns
to whisper-small (the reviewed `ROLLBACK_HINDI_ROUTE` in proposals.py
restates the target verbatim, test-pinned), the incumbent is still
registered and cached, and no client or image changes. Rollback is a
deliberate route change — automatic per-request fallback does not
exist, by the standing M16 decision. The flip was last drilled against
the running Docker stack in M25 (`rollback-drill.json`): seconds, both
directions.

**Deployment status**: the promotion is a REPOSITORY state. Nothing is
deployed — Hostinger, DNS, certificates, secrets, canary, and the VPS
capacity re-measurement (~4–5 concurrent 300 s long requests, ~4 GiB
steady-state RSS per busy long-audio slot — Windows-measured) all
belong to the future deployment milestone.

## What the future ML milestone adds (not now)

Evaluation harness against a held-out set, automated promotion gates,
and registry tooling that turns this manual procedure into a reviewed
pipeline. The seam is already there: `quality_baseline` in the catalog.
