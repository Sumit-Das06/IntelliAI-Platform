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

## The prepared (and deliberately DISABLED) promotion: Hindi → Qwen3-ASR

*(added at Milestone 20; status: PENDING, exactly as the ledger says)*

The candidate is fully validated (accuracy, switching, canary prep,
product path, 600 s long audio — `docs/research/MODEL_LEDGER.md`), and
every artifact of the promotion already exists in the repository:

- the **proposal route** in `apps/api/src/intelliai_api/registry/proposals.py`
  (active only under the staging profile, which production refuses by
  validator);
- the **runtime image** already carries the pinned llama.cpp layer and
  the qwen artifact pins — hosting it is a declaration, not a build;
- the **guards** that keep it disabled:
  `test_research_engines_never_appear_in_committed_deployments` (no
  committed compose may say `qwen3`),
  `test_the_staging_registry_profile_is_never_committed_configuration`,
  and the settings validator refusing `staging`+`prod`.

Promoting it, when the founder decides, is ONE reviewed commit that
moves three things together — loud by construction, because each is
individually guard-pinned today:

1. `infra/compose/prod.yml`: `INTELLIAI_STT_SLOTS: whisper` →
   `whisper,qwen3-asr` (the deployment now hosts the artifact;
   first boot downloads ~1 GB hash-verified — allow the healthcheck's
   start period, and raise it in the same commit if the VPS link is
   slow).
2. The catalog: the hi route moves from the incumbent to
   `qwen3-asr-0.6b` with its `quality_baseline`
   (`2026-08-12-qwen3-asr-adapter-evaluation`), promoted from
   proposals.py into catalog.py — the same diff the staging profile
   has been exercising since M18.
3. The guards: the two tests above are UPDATED in the same commit to
   pin the new posture (the diff that flips them is the review).

Rollback stays `git revert` of that one commit: whisper is still
pinned, still cached in the model volume, and the ledger's lineage
marks the boundary. Capacity facts to price in before the decision
(measured, M19): ~4–5 concurrent 300 s long requests per deployment,
~4 GiB steady-state RSS per busy long-audio slot — re-measure both on
the VPS before enabling long audio for customers.

## What the future ML milestone adds (not now)

Evaluation harness against a held-out set, automated promotion gates,
and registry tooling that turns this manual procedure into a reviewed
pipeline. The seam is already there: `quality_baseline` in the catalog.
