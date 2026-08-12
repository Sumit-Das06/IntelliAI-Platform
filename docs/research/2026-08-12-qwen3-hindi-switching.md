# Milestone 16 — Qwen3 Hindi Switching Test + Production-Readiness Validation: Close-Out

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — runtime supply chain pinned; concurrency measured to saturation on both engines; failures drilled; the switching mechanism proven with bit-identical quality; decisions and gates written |
| **Date** | 2026-08-12 (all measurements this date, same machine as every prior record) |
| **Verdict, stated plainly** | The switching mechanism works and changes nothing it must not change: routed through `hi → qwen3-asr-0.6b` in a multi-slot process, the frozen benchmark reproduced **CER 0.1457 bit-identically** while English stayed on the incumbent at WER 0.0 in the same process. Concurrency, isolation, restart, and rollback behavior are measured, not assumed. **Classification: A. READY FOR LOCAL CANARY** — with the gate table in §11 naming exactly what stands between here and a production canary (chiefly: vendored binary packaging, slot-truthful readiness, and the founder's switching decision). |

Labels: **[EVIDENCE]** committed EvalRun/BenchReport · **[FACT]** verified/recorded ·
**[DRILL]** scripted failure exercise, JSON-recorded · **[ESTIMATED]** derived from measurement, labeled.

---

## 1. Current architecture (what was reused, what was added)

Reused unchanged: the engine seam, slot catalog, artifact store, eval
plane, and the bench harness (which already implements the 1/5/10/20
ladder with nearest-rank percentiles and counts `overloaded` refusals
as measurement). Added: runtime **binary pinning** in the qwen3 engine
(§2), an additive `p99_ms` on ladder evidence, the research switching
route (§6), and the drill/canary-sim scripts under
`research/experiments/16-qwen3-switching/`. Production surfaces:
untouched; a new guard test asserts no committed compose file declares
the research engine.

## 2. Runtime / supply-chain hardening [FACT]

The decoder build is now pinned exactly like the weights:
`RUNTIME_BINARY_PINS` hashes the six load-bearing files of the
llama.cpp **b10344 (7a20b417f) win-cpu-x64** distribution (zip sha256
`c0cec882…`; built with Clang 20.1.8) — `llama-server.exe b2ace4b8…`,
`llama-server-impl.dll 27eb413c…`, `llama.dll b1e50380…`,
`mtmd.dll cd0c5118…`, `ggml.dll 112c29c5…`, `ggml-base.dll 58ef8ecf…` —
and `load_qwen3_asr` verifies them **before spawning anything**; a
wrong or missing file is a refusal naming the law. Model GGUFs remain
store-verified (`bca25981…` / `41a342b5…`, LFS-confirmed). No implicit
downloads (the store's URLs are pinned to revision `928ab958`); no
`trust_remote_code` anywhere; server loopback-only on an ephemeral
port. Five tests guard the pin table, the refusals, and the build
string surfaced in every run record's decode_params. **Future
container representation**: the vendored layer = the pinned zip +
these six hashes + the verify-at-load call — documented here as the
contract a Dockerfile must satisfy; deliberately NOT built or deployed
in this milestone.

## 3. Concurrency ladder [EVIDENCE — BenchReports, median frozen-eval clip 6.88 s, pool defaults max_concurrency=2/max_queue=8]

**Qwen3-ASR 0.6B** (reps 5/worker):

| c | ok/req | overloaded | p50 | p95 | p99 | rps | RTF | peak pool |
|---|---|---|---|---|---|---|---|---|
| 1 | 5/5 | 0 | 0.70 s | 0.73 s | 0.73 s | 1.42 | 0.091 | 1 |
| 5 | 25/25 | 0 | 2.07 s | 2.58 s | 2.88 s | 2.23 | 0.115 | 5 |
| 10 | 50/50 | 0 | 4.25 s | 4.31 s | 4.34 s | 2.34 | 0.113 | 10 |
| 20 | 50/100 | **50 (by design)** | 4.32 s | 4.48 s | 4.51 s | 2.28 | 0.116 | 10 |

**Whisper-small int8** (same clip, reps 3/worker):

| c | ok/req | overloaded | p50 | p95 | p99 | rps | RTF | peak pool |
|---|---|---|---|---|---|---|---|---|
| 1 | 3/3 | 0 | 1.56 s | 1.57 s | 1.57 s | 0.64 | 0.218 | 1 |
| 5 | 15/15 | 0 | 6.83 s | 8.59 s | 8.59 s | 0.65 | 0.424 | 5 |
| 10 | 30/30 | 0 | 14.80 s | 14.88 s | 15.05 s | 0.67 | 0.421 | 10 |
| 20 | 30/60 | 30 (by design) | 14.72 s | 14.82 s | 14.89 s | 0.68 | 0.418 | 10 |

Sidecar [FACT]: qwen3 llama-server RSS max **1,538.5 MiB** under load
(idle 1,362.5 — KV pre-allocated); machine CPU mean **70.2%** / max
80.2% at saturation. Whisper python RSS max 1,151.6 MiB; CPU mean
23.3%. Zero `other_errors` at every level on both engines; every
refusal was a clean 503 `overloaded` envelope — admission control
behaving exactly as documented. Model load: qwen3 1.0–1.1 s; whisper
12–44 s observed across boots.

## 4. Capacity model

**MEASURED:** saturation throughput 2.28–2.34 rps (qwen3) vs
0.65–0.68 rps (whisper) on 6.88 s utterances = **15.8 s of audio
per second (≈16× real-time aggregate)** vs 4.6 s/s (≈4.6×). Stable
through c=10 with zero failures on both; c=20 sheds load exactly at
the configured admission boundary (2+8). Memory flat (KV
pre-allocation); CPU is the binding resource at qwen3 saturation
(~70% of 24 threads), memory is nowhere near binding.

**ESTIMATED (derived, with safety margin, NOT a production
guarantee):** live calls produce ~1 s of audio per second, so
sustainable real-time concurrency ≈ aggregate real-time factor ×
utilization margin: **qwen3 ≈ 12 concurrent live calls per process on
this box** (16× × 0.75), **whisper ≈ 3–4**. The saturation point of
the CURRENT deployment shape is the pool config (10 admitted), not
the model: raising `max_concurrency`/`max_queue` is configuration,
and the CPU headroom (30%) suggests modest gains before compute
binds. These estimates hold for THIS CPU only.

## 5. Failure / resilience results [DRILL — failure-drills.json]

| Drill | Result |
|---|---|
| Garbage audio | 400 `invalid_input`, clean format message |
| Whisper, unsupported language `xx` | 400 `invalid_input`, `param=language` |
| Qwen3, unmapped hint `xx` | 200 (auto-detection; documented asymmetry — the model has no reject-list) |
| **llama-server killed mid-session** | next qwen requests: **500 `internal` in ~2.1 s** — bounded fast failure, no hang, identical on repeat (no crash loop) |
| **Incumbent isolation** | whisper served **200 OK while the qwen child lay dead in the same process** |
| `/info` after child death | 200, still lists the qwen slot — **readiness is NOT slot-truthful (finding → gate)** |
| Runtime restart | both slots healthy; exactly one llama-server child |
| Orphan accounting | **0** stray llama-server processes after every stop |
| Message hygiene | drill caught the timeout message naming `qwen3-asr` → **fixed same-day** (engine messages now name no engine/model/library; regression-tested) |

## 6. The Hindi switching test [EVIDENCE]

`research:intelliai-stt-switch` expresses the exact route shape a
promotion would land in the catalog — `hi → qwen3-asr-0.6b`,
`en`/default → `whisper-small` — resolved per-language by the same
semantics the product registry uses, served by ONE multi-slot process
(`INTELLIAI_STT_SLOTS=whisper,qwen3-asr`):

| Arm | Resolved artifact | Result | vs single-slot 15E |
|---|---|---|---|
| hi (153 frozen clips) | `qwen3-asr-0.6b` | **CER 0.1457 · WER 0.2851 · 0 probes · RTF 0.204 · p50 1.43 s / p95 3.22 s · 0 failures** | **bit-identical CER/WER** |
| en (seed v2) | `whisper-small` | WER 0.0 / CER 0.0 · 0 probes · 0 failures | incumbent untouched by cohabitation |

The routing mechanism adds nothing, subtracts nothing, and leaks
nothing: same envelope, same decode policies, same numbers to the
fourth decimal. Baseline comparison (unchanged from 15E): CER 0.1457
vs whisper's official 0.3629 (−60%, ~15× the noise band), insertions
half the incumbent's, probes 0 vs 0.

## 7. Fallback / rollback decision

**Recommended policy: NO automatic per-request fallback.** Evaluated
against the spec's hazards: engine-level fallback doubles worst-case
compute exactly when the box is already unhealthy, turns one timeout
into (timeout + full whisper decode) latency, and — because our
metering bills by audio seconds served — risks double-ledger entries
unless idempotency is re-engineered around retries. The platform's
existing safety mechanisms are the right ones: **admission control**
(fast honest 503, gateway owns retries), **slot isolation** (proven in
§5), and **registry rollback** (`git revert` of the route commit —
docs/ops/model-rollout.md — with the previous artifact still cached).
The drill evidence makes rollback credible: whisper keeps serving even
with the challenger's child dead. A future supervised child-restart
(auto-respawn of llama-server with backoff) is the ONE resilience
feature worth building before production canary; recorded as a gate,
not silently implemented.

## 8. Hindi timestamp / segment decision [FACT]

The public API promises: default response `{"text"}`; `verbose_json`
returns `segments[]` of `{id, start, end, text}` — **no word
timestamps exist anywhere in the public contract**, for any language.
No committed client consumes multi-segment structure (Studio renders
text; the keyboard consumes text). Whisper today emits multiple
utterance-level segments; Qwen3 emits exactly one spanning segment
with true start/end. **Decision: single-span segments satisfy the
current public contract — not a production blocker.** The observable
change under `verbose_json` for hi (segment count becomes 1) is a
DISCLOSED behavior delta for the founder's promotion decision, and the
ForcedAligner path (a second model; 11 languages, hi excluded) is
recorded as future work, not invented here.

## 9. Call-center model-pool analysis

On this box [MEASURED → ESTIMATED]: **10 concurrent calls — qwen3
handles them in one process today** (c=10: zero failures, p50 4.3 s
turnaround on a 6.9 s utterance, CPU ~70%); whisper cannot (c=10 p50
14.8 s > 2× utterance — falls behind live speech). **20 concurrent
calls — one qwen3 process refuses beyond 10 admitted by pool config**;
either raise the pool (CPU headroom ~30% suggests limited room) or run
**2 replicas ≈ 3.1 GiB total RAM** [ESTIMATED] — horizontal replication
is the honest path, and at ~1.5 GiB/replica it is cheap. The same 20
calls on whisper would need ~5 replicas and more CPU than this box
has. A shared single process per box is sufficient up to ~10–12 calls;
replicas beyond that.

## 10. Productionization checklist

**DONE (this milestone):** binary + model pinning with verify-at-load
and guard tests · loopback-only serving · bounded request timeouts ·
error-envelope hygiene (no internal names; drill-found leak fixed +
regression-tested) · orphan-free lifecycle · concurrency evidence with
saturation behavior · switching mechanism proven · rollback procedure
documented and its precondition (slot isolation) drilled · license
record (apache-2.0 at source, 0.6B card) · production-disabled guard
test.

**REQUIRED BEFORE CANARY:** slot-truthful readiness (a dead child must
mark its slot unready — today `/info` stays green, §5) · supervised
child restart with backoff · vendored runtime layer (container or
checked-in binary bundle satisfying §2's hash contract) · catalog
route + `quality_baseline` prepared as a reviewable commit · founder
sign-off on the hi single-segment behavior delta (§8).

**REQUIRED BEFORE FULL PRODUCTION:** canary results on real traffic
shape · pool sizing decision for the VPS hardware class (all numbers
here are this laptop's) · monitoring on the child process (RSS, restart
count) · load-shedding review at the gateway for 503 bursts · Linux
build of the pinned llama.cpp distribution with its own hash table
(current pins are win-x64 — the VPS needs its own verified build).

**FUTURE:** ForcedAligner evaluation if per-word timing ever enters
the public contract · zh promotion track · replica orchestration.

## 11. Promotion gates (all must pass; status today)

| Gate | Requirement | Status |
|---|---|---|
| Accuracy | beat incumbent beyond noise band | **PASS** (−60% CER, ~15× band, replicated + switch-reproduced) |
| Reliability | 0 failures, 0 probe words on benchmark | **PASS** (0/153 ×4 runs; 0 probes ×8 probes) |
| Performance | RTF within SLO; p95 acceptable | **PASS** (RTF 0.09–0.21; p95 3.2 s vs incumbent 24.2 s) |
| Resources | memory bounded; concurrency measured | **PASS** (1.54 GiB peak; ladder to saturation) |
| Operational | restart, readiness, timeouts, rollback | **PARTIAL** — restart/timeout/rollback PASS; **readiness gate FAILS** (slot not truthful) |
| Security | hashes pinned; no remote code; no leakage | **PASS** (binary+model pinned; leak fixed and tested) |
| Product | contract unchanged; segment behavior accepted | **PARTIAL** — contract proven unchanged; segment delta awaits founder acceptance |

## 12. Canary recommendation

**A local canary is justified now**; a production canary is NOT until
the two PARTIAL gates close. The 90/10 local simulation ran 100/100
requests clean (incumbent p50 2.23 s, challenger p50 1.28 s, zero
fallback events because no fallback exists) — but its honest value is
limited: one machine, frozen-eval audio, no real traffic mix. It
proves mixed routing through one process is stable; it does not prove
production readiness, and this report does not claim otherwise.

## 13. Remaining risks

Linux-build variance (all evidence is win-x64; the VPS build must be
re-pinned and re-laddered) · llama.cpp upgrade cadence vs our pin
(security patches will force reviewed re-pins) · single-model-process
KV sizing under longer audio (600 s product ceiling vs 4096-token ctx
— long-clip behavior unmeasured; eval clips ≤ 22 s) · Qwen
concentration risk (standing, FOUNDATION_MODELS §14) · the hi
segment-count delta surprising an integrator (mitigated by disclosure).

## 14. Exact next milestone

**Milestone 17 — Production canary preparation:** (a) slot-truthful
readiness + supervised child restart in the runtime; (b) the vendored
Linux runtime layer with its own pin table, re-laddered on VPS-class
hardware; (c) long-audio behavior check (60–600 s clips) against the
ctx-4096 KV bound; (d) the catalog commit + quality_baseline prepared
for review; (e) founder decision on §8 and the switching itself. The
evidence for that decision is complete on the accuracy side today.

---

## Reproducibility block [FACT]

Artifacts: GGUFs `bca25981…`/`41a342b5…` @ ggml-org `928ab958` ·
runtime b10344 (7a20b417f) win-cpu-x64, zip `c0cec882…`, six binaries
pinned in code · bench clip `indicvoices-hindi-valid-0-001287` (6.88 s,
wav sha `ea63be5b…`) from the frozen manifest `cf643146…` (untouched) ·
pool config: deployment defaults (2/8) · evidence: 2 EvalRuns +
2 BenchReports (committed) + drill/canary/orphan/sidecar JSONs in
`research/experiments/16-qwen3-switching/` · machine: Intel64 Family 6
Model 183 (24 threads), Windows 11 — identical to every prior record ·
git commits: the Milestone 16 commit set.

*No production surface changed: no deploy, no routing change, no API
change, no Android/Web change, no promotion. The challenger remains
`research:`-namespaced; the switching decision now has its complete
evidence file and belongs to the founder.*
