# Milestone 26 — Qwen E3 Hindi Production Promotion (Approved & Activated)

| | |
|---|---|
| **Status** | PROMOTION APPROVED AND ACTIVATED in the repository — nothing deployed, no customer traffic |
| **Date** | 2026-08-19 |
| **Decision** | The founder explicitly approved `qwen3-asr-0.6b-hi-ft-e3@v1` as the Hindi production model. **Qwen E3 is now the approved IntelliAI Hindi production model in the repository's production configuration.** Separately and explicitly: **the model has not yet been deployed to a production server.** |

## 1. Previous → 2. New production route

| | Before (since F-M5-1) | After (M26) |
|---|---|---|
| Hindi / hi-IN | whisper-small | **qwen3-asr-0.6b-hi-ft-e3@v1** |
| English | whisper-small (SUPPORTED) | whisper-small (unchanged) |
| Undeclared / default | whisper-small | whisper-small (unchanged) |
| Arabic | whisper-small (AVAILABLE) | whisper-small (unchanged) |

Hindi's ladder rung stays `available` — the switch changes what
honestly serves the existing promise level; `supported` remains a
separate, later decision.

## 3. Artifact identity + 4. Provenance [FACT — identity.json re-verified M24]

`qwen3-asr-0.6b-hi-ft-e3@v1`: export sha `e54586c4…` (byte-length equal
to the official artifact; template-rewrite pipeline whose control
reproduced the official base GGUF byte-for-byte), official mmproj
`41a342b5…` byte-shared, checkpoint-1500 of qwen-e3-hi-sft, base
`Qwen/Qwen3-ASR-0.6B @ 5eb14417…` (apache-2.0), training corpus
`qwen-hi-public-train@v3` sha `6cfc585d…`, frozen evaluation
`stt-hi-public-eval@v1` (sha `cf643146…`, untouched since 15C), runtime
pinned llama.cpp b10344 per platform. Distinctness from base/E1/E2 is
guard-tested; the weights distribute by SEEDING (deliberately
non-downloadable URL; store hash-verify at load; preflight-enforced).

## 5. Evidence the decision stood on

M23 (all eight research gates; CER 0.11612 on the frozen primary
through the real adapter; English WER 0.0; short-speech and silence
batteries clean) → M24 (readiness vs the incumbent: **−69% relative
CER** against whisper-small's same-day 0.37617; ladders, failure
drills, canary sims, rollback drill; classification A) → M25
(production-shaped Docker stack; founder-driven REAL Web and Android
sessions through a live Cloudflare tunnel, both languages, both
correctly routed).

## 6. What the promotion commit changed

1. **Catalog** (`registry/catalog.py`): the E3 ArtifactRecord (full
   provenance chain) + the hi route with the founder approval record
   riding on the route evidence (`approval="F-M26 — founder promotion
   decision, 2026-08-19 …"`, `approved_on=2026-08-19`).
2. **Proposals** (`registry/proposals.py`): the pending proposal is
   retired — no PENDING sentinel exists; the module keeps the reviewed
   `ROLLBACK_HINDI_ROUTE` and the `staging_registry()` hook (now
   composing exactly the live catalog) for the NEXT candidate.
3. **Prod compose** (`infra/compose/prod.yml`): slots declare the
   EXACT approved artifact
   (`whisper,qwen3-asr:qwen3-asr-0.6b-hi-ft-e3`).
4. **Preflight**: refuses a production start without the seedable E3
   bytes present.
5. **Guards/tests updated to pin the NEW posture** (none weakened):
   Hindi must resolve to E3 exactly; English/default/Arabic stay on
   the incumbent; base/E1/E2 forbidden in every committed deployment;
   a bare `qwen3-asr` family slot (which would resolve to the base
   challenger) explicitly forbidden; no live evidence may carry a
   PENDING sentinel; staging profile still refused under prod; the
   registry manifest (`resolution.json`) regenerated and test-pinned.
6. **Docs**: model-rollout.md (the active promotion + seeding +
   rollback), production-readiness.md checklist, MODEL_LEDGER append,
   this report.

## 7. Regression validation [EVIDENCE]

- Full api suite (622), runtime, evaluation, dataset, training suites,
  ruff, ruff format, mypy strict: green (final counts in the commit).
- Registry law re-verified: catalog loads; hi/hi-IN → E3; en/ar/
  undeclared → whisper-small; staging == live (no divergence
  possible); rollback target constructible and equal in shape to the
  live route.
- **Real infrastructure, PRODUCTION registry profile**: the api
  container was rebuilt with the promoted catalog and recreated from
  the BASE compose — **no staging profile anywhere** (log-verified) —
  and through the Caddy HTTPS edge: hi → E3, hi-IN → E3, en → whisper,
  undeclared → whisper, xx → 400, with the runtime log naming the
  artifacts. This is the exact composition a production deployment
  runs.
- **Post-promotion battery through the edge**
  (`research/experiments/26-e3-promotion/post-promotion-drills.json`):
  auth 401s; routing; verbose_json single segment short / 4 segments at
  300 s / 7 at 600 s with join==text at real offsets; usage +300.0 s
  and +600.0 s exact; 602 s refused naming the limit, billed zero;
  sample under consent; contribution-off honored; correction
  immutable-original; malformed/empty/tiny → clean 400s; zero
  internal-name leaks.
- Readiness/restart: both slots ready (hash-verified at load);
  supervised-restart behavior unchanged from the M25 in-container
  drills (~3 s bounded recovery, zero orphans) — the runtime container
  and image are untouched by this commit.

## 8. Rollback

`git revert` of the promotion commit → Hindi returns to whisper-small
(`ROLLBACK_HINDI_ROUTE` restates the target verbatim; test pins it
equals the live route's shape). The incumbent stays registered, pinned,
and cached — no re-admission, no rebuild, no client change. Drilled
against the running Docker stack in M25, both directions, in seconds.
No automatic per-request fallback exists (standing M16 decision).

## 9. Deployment status — the explicit distinction

```
Production route in REPOSITORY:   Hindi → qwen3-asr-0.6b-hi-ft-e3@v1
                                  English → whisper-small

Actual deployed production:       NOT DEPLOYED
```

Hostinger untouched: no VPS, no DNS, no certificates, no production
secrets, no canary, no customer traffic. The future deployment
milestone owns: VPS provisioning per docs/ops/deployment.md · seeding
the E3 weights on the box (preflight-enforced) · Linux runtime
re-ladder on VPS hardware · monitoring/backup destinations · the real
production canary (90/10 shape from the M24/M25 simulations).

---

    MODEL PROMOTION APPROVED: YES

    PRODUCTION ROUTING IN REPOSITORY:
        Hindi → qwen3-asr-0.6b-hi-ft-e3@v1
        English → whisper-small

    HOSTINGER DEPLOYED:
        NO

    REAL CUSTOMER TRAFFIC:
        NO
