# Qwen3 E3 Hindi Promotion & Switching Validation (Milestone 24)

| | |
|---|---|
| **Status** | PROMOTION-READINESS EVIDENCE COMPLETE — production untouched; the proposal remains PENDING |
| **Date** | 2026-08-18 (every measurement this date, same machine as every prior record, unless cited) |
| **Question** | Is `qwen3-asr-0.6b-hi-ft-e3@v1` safe and operationally better than the CURRENT production Hindi model, whisper-small, through the real IntelliAI product path? |
| **Answer** | **Yes, on every gate a laptop can prove.** Fresh same-day incumbent baseline CER 0.37617 vs the candidate's 0.11612 (**−69% relative**, ~15× the noise band), the full safety battery matches-or-beats the incumbent row by row, English retained at WER 0.0, the product path (auth → routing → metering → collection → correction → verbose_json → 120/300/600 s) drills clean with zero leaks, ~3× the incumbent's concurrency at ~3× lower latency, supervised recovery in under 4 s with the incumbent never blinking, four canary shares 400/400 clean, and rollback proven as a pure configuration flip. |
| **Classification (Phase 14)** | **A. READY FOR PRODUCTION CANARY** — on LOCAL/STAGING evidence. VPS validation is PENDING by fact (no VPS exists yet); the Linux re-pin + re-ladder on VPS hardware remains the documented pre-production requirement (M16 §10, M17). Activation requires the founder decision that replaces the proposal's PENDING sentinel. |

Labels: **[EVIDENCE]** committed EvalRun/BenchReport/JSON · **[FACT]** verified/recorded ·
**[DRILL]** scripted exercise, JSON-recorded · **[ESTIMATED]** derived, labeled ·
**[CITED]** prior committed evidence, unchanged.

## 1. E3 artifact identity [FACT — identity.json]

`qwen3-asr-0.6b-hi-ft-e3@v1`, re-verified byte-for-byte through the
runtime's own admission table before anything else ran: model GGUF
`e54586c4…` (804,749,248 bytes, structure identical to the official
artifact), official mmproj `41a342b5…` byte-shared, distinct from
base AND E1 AND E2, training manifest `qwen-hi-public-train@v3`
`6cfc585d…`, frozen eval `stt-hi-public-eval@v1` `cf643146…`, base
revision `5eb14417…`, six runtime binaries pinned (b10344 win-cpu-x64).
Exporter: the M21 template rewrite whose control reproduced the
official base GGUF byte-for-byte. Guard tests hold the identity laws
(`.invalid/m23/` URL, mmproj shared, three-way distinctness).

## 2-4. The decision comparison — frozen benchmark [EVIDENCE]

All on frozen `stt-hi-public-eval@v1` (153 clips), same ruler
(`cer_unicode` / `unicode_generic@v2`), same decode configuration
class, adapter/runtime-side:

| | **whisper-small (incumbent, FRESH today)** | qwen base [CITED 15E] | **E3 candidate [CITED M23]** |
|---|---|---|---|
| CER | **0.37617** (15C: 0.36288 / 0.37721 — today inside the band) | 0.1457 | **0.11612** (replicate 0.11750, spread 0.0014) |
| WER | 0.66575 | 0.2851 | **0.24064** |
| Sub/ins/del | — | — | .180/.026/.034 |
| Hallucinated probes | 0 | 0 | **0** |
| RTF | 0.916 | 0.207 | 0.218 (0.160 replicate) |

**The decision number: E3 beats the production incumbent by −69%
relative CER and −64% relative WER** — ~15× beyond the replicate noise
band, measured through the SAME multi-slot runtime process on the same
day. (Base qwen is supporting context: E3 additionally beats it by
−20.3%.) The fresh incumbent record is
`2026-08-18-intelliai-stt-hi-whisper-small-int8-m24-incumbent.json`.

## 5-8. Extended product safety battery [EVIDENCE — safety-battery.json]

Identical inputs, same process, per artifact. E3 vs incumbent, row by
row: digital silence, −50 dBFS noise → **both EMPTY**; speech↔silence
transitions, normal Hindi → both Devanagari; English JFK → both
English; malformed / empty / tiny inputs → both clean 400
`invalid_input`, zero leaks; **the 0.5–2.5 s ladder → E3 transcribes
every rung including 0.5 s where the incumbent returns EMPTY**; real
held-out sub-2 s utterances → both transcribe. No repetition anywhere.
English retention [CITED M23]: safety record WER 0.0 / CER 0.0 —
identical to the incumbent's English behavior class. Base-qwen rows
are cited from the committed M22/M23 batteries (base voices text on
noise; E3 is strictly safer). **No row exists where the incumbent is
safe and E3 is not.**

## 9. Long audio [EVIDENCE — gateway-drills.json, long-concurrent.json]

Through the REAL gateway as ONE customer request each: 300 s → 200, 4
segments, space-join == text, offsets 0→300; 600 s → 200, 7 segments,
join == text, 0→600; 602 s → clean 400 naming the 600 s limit, billed
zero. Concurrent long audio (pool at deployment defaults 2/8):
2×300 all 200; **5×300 all five 200** (walls 78.7→399.5 s, matching
M19's idle-box 422.3 s); 2×600 both 200 (182.3/363.4 s). Peak
llama-server RSS under sustained long-audio: 3,558–3,565 MiB (M19
class: 3,382–3,407). An earlier attempt under residual bench load
timed out the 5th request at the client — recorded honestly; the
clean repeat above is the standing measurement.

## 10-11. Performance and concurrency [EVIDENCE — the two M24 ladders]

Same clip (6.88 s median), same levels, same multi-slot process,
same day:

| c | **E3** ok / p50 / p95 | **whisper-small** ok / p50 / p95 |
|---|---|---|
| 1 | 5/5 · 1.04 s · 1.09 s | 3/3 · 2.06 s · 2.09 s |
| 5 | 25/25 · 3.28 s · 3.76 s | 15/15 · 9.54 s · 12.46 s |
| 10 | 50/50 · **6.54 s** · 6.64 s | 30/30 · **21.0 s** · 21.4 s |
| 20 | 50/100, 50 shed (by design) · 7.72 s | 30/60, 30 shed · 20.9 s |

At c=10 the incumbent falls 3× behind live speech; E3 keeps up. Both
engines shed excess load as clean 503s exactly at the admission
boundary. Serving RSS [CITED M23]: 1,559 MiB short-clip class
(incumbent's python: ~1.15 GiB; both bounded). Model load: E3 1.7 s
vs whisper 12–44 s observed. **MEASURED on this laptop; VPS capacity
is deliberately NOT claimed** (Phase 15).

## 12-17. The real gateway product path [DRILL — gateway-drills.json]

Staging profile (hi → E3, everything else → incumbent), real auth,
real Postgres/Redis/MinIO, real multi-slot runtime, `internal_qa`
tenant. Every row clean, zero internal-name leaks in every response
body scanned:

- **Routing**: hi → E3 (runtime log names the artifact), hi-IN → E3,
  en → incumbent, undeclared → default route (incumbent), `xx` →
  clean 400 `param=language`. Auth 401s without/with-invalid key.
- **verbose_json**: short = ONE clean `{id,start,end,text}` segment
  spanning the clip; 300 s = 4 segments; 600 s = 7 segments; join ==
  text; no word timestamps invented. (Web consumes exactly this
  contract — M18's Studio evidence stands, the contract is unchanged.
  Android consumes final text only — the M18 contract replay stands,
  the public API is unchanged.)
- **Metering**: one usage event per success; **+300.0 s and +600.0 s
  exactly** for the long requests; the 602 s refusal billed ZERO; the
  public usage surface names `intelliai-stt`, never an artifact.
- **Collection**: consented Hindi request → exactly one Speech Sample
  (original == model output verbatim); contribution OFF → transcript
  returned, NO sample; correction → original immutable, current
  updated. All under the SAME laws as the incumbent path — no
  semantics changed.

## 18. Failure / restart / readiness [DRILL — failure-drill.json]

Two kill cycles of the E3 llama-server child through the M17
supervision: readiness told the truth in **1.33 s / 1.10 s**
(`ready → restarting`), supervised recovery completed in **3.85 s /
3.62 s** (M17 recorded ≈9–10 s; the E3 GGUF loads fast), the incumbent
served 200s DURING both outages, post-recovery E3 requests 200, final
state both slots ready, **exactly one llama-server process, zero
orphans, zero message leaks**. No automatic per-request fallback
exists — re-verified (nothing re-routed; the M16 decision stands:
rollback is a route change, not a hidden retry).

## 19. Staging canary simulation [DRILL — canary-sim-*.json]

Deterministic mixed traffic through the multi-slot process, 100
requests per share, escalated only as each rung came back clean:

| Split (incumbent/challenger) | Results | Incumbent p50 | E3 p50 / p95 |
|---|---|---|---|
| 90/10 | 100/100, 0 failures | 2.24 s | 1.29 s / 1.86 s |
| 75/25 | 100/100, 0 failures | 2.24 s | 1.34 s / 1.48 s |
| 50/50 | 100/100, 0 failures | 2.32 s | 1.34 s / 1.47 s |
| 25/75 | 100/100, 0 failures | 2.38 s | 1.35 s / 1.54 s |

**400/400 clean; latency flat as the challenger share escalates**;
zero fallback events (none exist). NOT ledger evidence: one machine,
frozen-eval audio — it proves mixed routing is stable, nothing more.

## 20. Rollback [DRILL — rollback-drill.json]

The staging gateway was stopped and relaunched WITHOUT the staging
profile — a pure configuration flip, nothing else changed. The next
Hindi request served 200 via **whisper-small** (runtime log named the
artifact); no rebuild, no retraining, no client change, no runtime
restart; the incumbent artifact was valid and cached. In production
the same flip is the git revert of the promotion commit
(docs/ops/model-rollout.md); `ROLLBACK_HINDI_ROUTE` restates the
revert target verbatim and a test pins it equal to today's live route.

## 21. The proposal diff [FACT — proposals.py]

`apps/api/src/intelliai_api/registry/proposals.py` now prepares the
E3-SPECIFIC promotion (superseding the never-approved M17 base-qwen
proposal): artifact record `qwen3-asr-0.6b-hi-ft-e3` v1 with the full
provenance chain (base revision, v3 corpus sha, checkpoint-1500,
export sha, runtime pin), the hi route carrying
`quality_baseline=2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23`
and `production_benchmark=2026-08-18-qwen3-e3-cpu-ladder`, and the
**PENDING sentinel referencing this report**. Activation = add the
artifact to `_ARTIFACTS`, swap the hi route in `_ROUTES`, replace the
sentinel with the founder decision — rehearsed by test. The staging
overlay (`local-staging.yml`) now declares the E3-specific slot; the
guard test pins that exact string so the generic base can never
silently return. **The live catalog is untouched and test-pinned:
Hindi still resolves to whisper-small.**

## 22. Local/staging vs VPS status [FACT]

**LOCAL/STAGING VERIFIED** — everything above. **VPS: PENDING** — no
VPS exists yet (M20's deployment readiness awaits Hostinger access).
NOT verified and NOT claimed: VPS capacity, Linux-runtime ladder on
VPS hardware (the WSL2 Linux pin from M17 is quality-identical but is
not a capacity measurement), production monitoring. **PRODUCTION:
UNCHANGED** by construction and by test.

## 23. Blockers before a real production canary

1. **Founder approval** — the sentinel replacement itself.
2. **VPS**: access, deploy (M20 runbook), Linux runtime re-pin +
   re-ladder on that hardware class, pool sizing for it.
3. Founder acceptance of the disclosed hi `verbose_json` delta
   (multi-utterance segments become chunk-level segments: 1 for
   ≤120 s, per-window for 120–600 s — M16 §8, unchanged since).

## 24. Final classification

**A. READY FOR PRODUCTION CANARY** — every Phase 14 criterion
measured and passed on this hardware: accuracy (−69% CER vs the
incumbent), safety (battery clean; strictly safer than incumbent on
short speech), retention (English WER 0.0), performance (3× incumbent
concurrency at 3× lower latency; RTF 0.22 vs 0.92), resources
(1.56 GiB short-clip / 3.56 GiB sustained-long-audio RSS, bounded),
operational (truthful readiness ~1.2 s, bounded recovery <4 s, zero
orphans), product (gateway/Web/Android contracts unchanged and
drilled), data (metering exact, samples/corrections lawful), security
(identity pinned end to end, zero leaks), rollback (drilled
configuration flip).

## 25. Recommendation

Present this report and the M23 experiment record to the founder for
the switching decision. If approved: land the promotion commit
(activate the proposal + replace the sentinel), then proceed to the
VPS deployment milestone (M20 runbook) with the production canary at
the 90/10 shape first. Rollback remains one git revert away at every
step. Until that decision, E3 stays research-only and production
routes Hindi to whisper-small.

---

## Reproducibility block [FACT]

Artifact: `e54586c4…` + mmproj `41a342b5…` @ pinned b10344 · corpus
v3 `6cfc585d…` · eval `cf643146…` (untouched) · evidence:
identity.json, gateway-drills.json, safety-battery.json, two M24
BenchReports (committed to ml/evaluation/stt/benchmarks/), the fresh
incumbent EvalRun, long-concurrent.json, failure-drill.json, four
canary-sim JSONs, rollback-drill.json — all under
`research/experiments/24-e3-promotion/` · stack: native staging pair
(gateway :8010 staging profile, multi-slot runtime :8011
whisper+E3) beside the dev compose infra, `internal_qa` tenant, no
secrets committed · machine: Intel64 Family 6 Model 183 (24 threads),
Windows 11 — identical to every prior record.

*No production surface changed: no deploy, no routing change, no API
change, no Android/Web change, no promotion. The proposal is prepared
and PENDING; the decision belongs to the founder.*
