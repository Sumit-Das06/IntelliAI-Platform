# Challenger Admission — B6

| | |
|---|---|
| **Milestone** | Objective 1 (Benchmark Infrastructure) · B6 |
| **Date** | 2026-08-06 |
| **Challenger** | `whisper-base` v1 — Systran/faster-whisper-base, CTranslate2 family (stack S1, already operated) |
| **Licence** | MIT, read at the distribution 2026-08-06. **Hosting-only verification**: the full per-artifact-version re-verification is owed before any measurement is cited toward adoption (verdicts decay; Gate 5 re-checks regardless). |
| **Status** | This admission grants **no research status**. Every lineage remains exactly where the ledger has it. Nothing was benchmarked, compared, scored, or recommended. |

## 1. What admission is

One assertion, proven executable: *this artifact, at these pinned bytes, is
hosted, self-described, and resolvable through the research harness — while
production cannot see it.* Admission is the engineering precondition of the
first measurement (`require_hosted` and `resolve()` both refuse an unadmitted
subject), and it is **not** the measurement.

## 2. The admission, executed

```
make research-stt artifact=whisper-base        # port 8003, own process
```

Cold start → ready: **40 s** — `model.bin` (145 MB) downloaded and SHA-256
verified in ~28 s, three small files verified, engine loaded (`load_ms`
3113.9), W0 lifecycle warm-up (`warmup_ms` 2504.4; internal synthetic audio —
lifecycle, not benchmarking). All four files matched their pins; `model.bin`'s
pin is Hugging Face's own LFS object id, the small files were downloaded and
hashed locally at pin time. The Whisper family shares one tokenizer:
`tokenizer.json` and `vocabulary.txt` hash identically to the incumbent's —
kept as per-artifact copies anyway, because identity is per artifact directory.

**Measurability, demonstrated without measuring.** The exact B4b preconditions
a PH1 session runs through were executed against the live research runtime —
`research.json` resolved `research:whisper-base` → `whisper-base@1` on
`stt-runtime-research`; `read_info` + `require_hosted` confirmed it hosted;
`describe()` supplied `compute_type=int8`, `emitted_unit=word`, 13 decode
keys. **Zero bytes of audio were sent.**

## 3. Production isolation, proven three ways

1. **Manifest byte-identity.** `resolution.json` regenerated from the live
   registry with the challenger admitted:
   `cb5da0cb…dce6d` before = `cb5da0cb…dce6d` after. Byte-identical.
2. **Source absence.** `whisper-base` appears nowhere in `apps/`
   (gateway/registry/commercial), `packages/` (contract, runtime-core),
   `infra/`, or `docker-compose.yml` — checked by grep and pinned by test.
   `ENGINE_VOCABULARY` required **no edit**: a challenger is an artifact, not
   an engine, and the test now pins that admission never touches it.
3. **Resolution refusals, both directions.** The production manifest refuses
   `research:whisper-base`; the research manifest refuses `intelliai-stt`.
   The two documents share no subject, by test. A run against the research
   manifest structurally cannot claim to have measured the product promise.

## 4. What admission cost — the number B-28 wanted

| Component | Cost |
|---|---|
| Pin acquisition (LFS sha256 via HF API + 3 files hashed locally) | ~5 min |
| Engine table entry (`WHISPER_BASE_FILES` + `ARTIFACT_SPECS`) | **1 data entry**, ~40 lines of pins |
| Slot semantics (one-time, benefits every future admission) | ~20 lines in `slots.py` |
| Adapter changes | **0** — same family, same loader, same `describe()` |
| Gateway / registry / vocabulary / contract changes | **0 / 0 / 0 / 0** |
| Research manifest entry | 1 JSON stanza |
| Cold start (download + verify + load + warm-up) | 40 s |
| Wall-clock engineering, end to end | **≈ 1 hour** including tests and this report |

**The honest caveat on that number:** it is the marginal cost of admitting a
checkpoint into an *already-operated* serving stack, with the selection
mechanism now built. It does **not** extrapolate to a new stack — S2–S6 still
each require an adapter module, an isolation-denylist entry, an optional
extra, and a `describe()` implementation. The campaign's stack-grouping table
remains the cost model for those; what B6 establishes is that *within* a
stack, the per-checkpoint cost is one pinned data entry.

## 5. Risks discovered

- **R-1 · The research manifest is hand-authored and can drift from reality.**
  Nothing checks that `stt-runtime-research` is actually running — by design
  (the registry must not know it), and `require_hosted` re-verifies against
  live `/info` at run time, so drift produces a refusal, never a mislabelled
  record. Accepted.
- **R-2 · Ad-hoc research processes can collide on ports** — the PH0 F-1
  stale-runtime lesson applies doubly with two runtimes about. The B7 session
  layer should verify process freshness; until then the procedure says: one
  research runtime at a time, stopped after use.
- **R-3 · The multi-slot research process composes** (incumbent + challenger
  behind one `/info`, proven by test) **and must not become production
  posture** — F-M5-5's one-artifact-per-deployment ruling stands; the
  composed form exists for future bridging sessions only.
- **R-4 · Licence decay.** MIT read today, hosting only. A measurement cited
  at Gate 5 re-verifies the artifact version; the admission table is not a
  licence record.

## 6. Definition of Done

| # | | |
|---|---|---|
| 1 | Challenger hosted, described, resolvable through the research harness | ✅ executed live |
| 2 | Production manifest byte-identical before/after | ✅ sha256-equal |
| 3 | No production route resolves to the challenger; no registry state changed | ✅ by test, both directions |
| 4 | `ENGINE_VOCABULARY` untouched, and pinned so by test | ✅ |
| 5 | Admission data-driven: next same-family checkpoint = one pinned entry | ✅ mechanism + test |
| 6 | Executable procedure (`make research-stt artifact=…`) | ✅ |
| 7 | Engineering cost measured and recorded | ✅ §4 |
| 8 | Zero benchmarking: no audio sent, no WER, no RTF, no comparison | ✅ |
