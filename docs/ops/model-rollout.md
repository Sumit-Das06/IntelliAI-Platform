# Model Rollout & Rollback — IntelliAI STT & TTS

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
   `make manifest` (or the CLI equivalent) and archive it.

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

## The ACTIVE promotion: IntelliAI TTS, English + Hindi (approved at M42)

*(implemented local/staging at M35-M39; validated at M40; APPROVED by
the founder 2026-08-24 and ACTIVATED by the Milestone 42 promotion
commit — F-M42)*

The repository's production configuration now declares speech
synthesis an approved production service:

    voice english-female / english-male → kokoro-82m (af_heart, am_michael)
    voice hindi-female                  → kokoro-82m (pack hf_alpha)
    voice hindi-male                    → kokoro-82m (pack hm_psi)
    en route: SUPPORTED (unchanged since M3/F-M5-2)
    hi route: UNAVAILABLE → AVAILABLE on kokoro-82m (F-M42)

The promotion landed as one reviewed commit moving four things
together (the E3/M26 shape):

1. **The catalog**: the two Hindi voice records join `_VOICES`, and
   the hi refusal route becomes the served route with the founder's
   approval and the full evidence chain riding on it
   (`quality_baseline` `2026-08-22-hindi-tts-model-selection`,
   `production_benchmark` `2026-08-24-kokoro-hindi-staging-validation-m40`).
2. **The production overlay**: `infra/compose/prod.yml` pins the TTS
   posture explicitly (`INTELLIAI_TTS_SLOTS: kokoro`,
   `NORMALIZE_TEXT: "true"`, `OOV_FALLBACK: espeak`,
   `HINDI_G2P: espeak`) and `make prod-*` carries `--profile tts`, so
   the approved service is one the deployment can actually bring up.
3. **The guards**: readiness now answers for synthesis where the
   deployment serves it (`INTELLIAI_RUNTIMES_TTS_ENABLED`), the
   preflight refuses a prod start whose TTS artifact is not placed for
   seeding, and the production smoke covers the service, its posture,
   its four voices, and one real synthesis per promoted language.
4. **The tests**: the production-refusal pins became production-serving
   pins in the same commit.

No artifact re-admission (kokoro-82m was already registered; its v2
file set carries all four voice packs, SHA-256-pinned at revision
`f3ff3571…`), no image change, no client change, no API change.

**Weights distribution**: `make seed-models` copies
`models/kokoro-82m/v2/` into the model volume, and the store
hash-verifies the placed files at every load exactly like a downloaded
artifact — a box without egress serves the promoted voices, and
`prod-check` refuses to proceed without them.

**Rollback**: `git revert` of the promotion commit → Hindi TTS returns
to the honest refusal, whole-language, never half-promoted (the voices
and the route leave together, so `hindi-female` answers
`voice_not_found` before any plane crossing). The reviewed target
`ROLLBACK_TTS_PRODUCTION_ROUTE` in proposals.py restates it verbatim
and tests pin both the target and the rolled-back console status.
English TTS is untouched by that revert. A deployment-tier rollback
that keeps English while dropping Hindi is one env line
(`INTELLIAI_TTS_HINDI_G2P=off` — the runtime then serves no Hindi
voice; smoke checks the posture both ways), drilled live at M40 at
~40 s per direction.

**Deployment status**: the promotion is a REPOSITORY state. **Nothing
is deployed.** Hostinger, DNS, certificates, production secrets, the
first live smoke, and the VPS capacity measurement all belong to the
deployment/launch milestone. The sequence is deliberately three
separate steps: **promotion** (this commit) → **deployment** (a host
runs `prod-check` → `prod-up` → `prod-migrate` → `prod-smoke`) →
**launch** (customer traffic).

### Deploying the promoted TTS service (when a host exists)

1. `make prod-check` — now also refuses a start whose
   `models/kokoro-82m/v2/` files are missing (base + 4 voice packs).
2. `make prod-up` — brings up the seven-service stack (`--profile tts`
   included); the TTS runtime hash-verifies its artifact at load and
   only then reports ready.
3. `make prod-health` — the gateway's readiness now includes
   `tts-runtime`; green means synthesis is actually up.
4. `INTELLIAI_SMOKE_API_KEY=… make prod-smoke` — seven services, the
   TTS posture (`hindi_g2p`), all four promoted voices, and one real
   synthesis per promoted language through the edge.
5. Rollback: `git revert` the promotion commit → `make prod-up`; or
   drop Hindi alone with `INTELLIAI_TTS_HINDI_G2P=off`.

## What the future ML milestone adds (not now)

Evaluation harness against a held-out set, automated promotion gates,
and registry tooling that turns this manual procedure into a reviewed
pipeline. The seam is already there: `quality_baseline` in the catalog.
