# Milestone 17 — Qwen3 Hindi Production Canary Preparation: Close-Out

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — every remaining operational gate from Milestone 16 closed and re-verified live; two NEW defects found by this milestone's own probes were fixed and re-verified the same day |
| **Date** | 2026-08-12 (all engineering and measurements this date) |
| **Verdict, stated plainly** | The candidate is **canary-ready on the evidence available to a laptop**: readiness is slot-truthful (0.76 s to truth), recovery is supervised and bounded (≈9–10 s total outage, zero orphans including the mid-spawn window), the Linux runtime is pinned and quality-identical (CER 0.14594 vs 0.1457), long audio is loudly bounded at the measured-safe 120 s instead of silently truncating, and the promotion is a prepared two-part diff with the baseline riding on the route. **What a laptop cannot provide is VPS hardware** — the Linux validation ran on WSL2 Ubuntu on the same machine, said plainly everywhere it is cited. |

Labels: **[EVIDENCE]** committed EvalRun/BenchReport · **[FACT]** verified/recorded ·
**[DRILL]** scripted live exercise, JSON-recorded · **[ESTIMATED]** derived, labeled.

---

## 1. Starting state

Milestone 16 ended READY FOR LOCAL CANARY with three PARTIAL items:
slot-truthful readiness, supervised child restart, and a pinned Linux
runtime re-validated off Windows. This milestone closed all three,
plus the catalog preparation (Phases 8–9) and the long-audio
characterization (Phase 6) — which found a real product-safety defect.

## 2. Slot-truthful readiness [FACT + DRILL]

`/health/ready` now reports per-slot truth: engines may expose
`slot_state()` (`ready`/`restarting`/`failed`); the DEFAULT slot
decides the HTTP code, so a dead specialist **degrades** a deployment
(200 + `"degraded"`, orchestrators must not kill a process still
serving its core promise — the compose healthcheck philosophy) while a
dead default makes it truthfully `not_ready` (503). `/info` remains
lifetime-constant per its own law; liveness is untouched. Eight
readiness cases are deterministically tested (both healthy, specialist
restarting/failed, default failed, unstarted manager, single-slot,
multi-slot coverage, state visibility by name). **Live [DRILL], Linux:
child killed → readiness told the truth in 0.76 s.**

## 3. Supervised restart [FACT + DRILL]

The engine now supervises its child: a daemon monitor detects death
within 1 s; recovery runs **through the loader's own spawn path**
(same pin verification, same health gate) on a **bounded-by-
construction backoff schedule** (1 s/5 s/25 s — the attempt count IS
the schedule length; exhaustion parks the slot at `failed`, terminal
until process restart — no hidden retry loop). Requests during any
non-ready state refuse with `not_ready` in ~0.04 s, naming nothing
internal. Restart counts/attempts are observable (`slot_stats()` +
structured logs: `qwen3_child_died`, `qwen3_restart_attempt_failed`,
`qwen3_child_restarted`, `qwen3_slot_failed`). Seven supervision cases
tested deterministically (alive, death→restart→ready, bounded
exhaustion, truthful refusals, mid-flight death = not_ready,
close-during-restart never adopts, close leaves no orphan).
**Live [DRILL], Linux, twice: kill → unready 0.76 s → refusals bounded
0.04 s → recovered and serving in 9.8–9.9 s total.**

**Orphan defect found and fixed by this milestone's own drill:** the
first Linux session stranded ONE llama-server when the runtime stopped
while the supervisor was mid-spawn (daemon thread killed at
interpreter exit before adopting/terminating the new child). Fix: the
loader's cancel event is shared with the spawn closure, so closing the
engine aborts an in-flight health-wait which kills its own child.
**Re-verified live by forcing exactly that window: 0 orphans.**

## 4–5. Linux runtime and hashes [FACT]

`llama-b10344-bin-ubuntu-x64.tar.gz` (sha256 `01b90b07…`), the SAME
tag and commit as the Windows pin — `version: 10344 (7a20b417f),
built with GNU 11.4.0 for Linux x86_64`, verified by running it. Pin
tables are now **per-platform** in the engine (`win32` + `linux`;
an unpinned platform is refused outright), verify-at-load unchanged:

| file | sha256 |
|---|---|
| llama-server | `9b7b699e2e9579…` |
| libllama-server-impl.so | `2e5d35d03aefee…` |
| libllama.so | `4b5095195b0cad…` |
| libmtmd.so | `d6a465f5346b4d…` |
| libggml.so | `ffd6a736ad58e2…` |
| libggml-base.so | `e486598626ec06…` |

Model GGUFs unchanged (`bca25981…`/`41a342b5…`, store-verified at
boot). System dependency outside the table, satisfied by the OS or
container layer: `libgomp.so.1` (validated user-space from the Ubuntu
24.04 package). No implicit downloads, no remote code; server
loopback-only. Cross-platform version-skew is test-guarded (both
tables must pin the same tag).

## 6. Benchmark environment — the honest caveat

**A real VPS was not available to this milestone.** Linux validation
ran on **WSL2 Ubuntu 24.04 on the same Intel64 F6M183 laptop (24
threads, 15 GiB visible)** — real Linux kernel/userland and the real
pinned Linux binaries, but the dev machine's CPU, not Hostinger's.
Every Linux record carries this label in its own notes/hardware
fields. VPS-hardware numbers are collected at deploy time by re-running
the same committed scripts (`m17_linux_session.sh`).

## 7. Linux concurrency ladder [EVIDENCE]

Same clip, methodology, and pool (2+8) as Milestone 16's Windows
ladder:

| c | ok/req | 503 | p50 | p95 | p99 | rps | RTF |
|---|---|---|---|---|---|---|---|
| 1 | 5/5 | 0 | 0.77 s | 0.91 s | 0.91 s | 1.27 | 0.091 |
| 5 | 25/25 | 0 | 2.13 s | 2.43 s | 3.07 s | 2.27 | 0.116 |
| 10 | 50/50 | 0 | 4.22 s | 4.46 s | 4.82 s | 2.27 | 0.119 |
| 20 | 61/100 | 39 | 5.35 s | 6.44 s | 7.85 s | 2.26 | 0.114 |

The plateau (≈2.27 rps ≈ 16× real-time aggregate) matches Windows
(2.28–2.34) — the serving envelope is platform-stable on this CPU.
Zero non-503 errors. Full frozen-benchmark quality on the SAME Linux
process [EVIDENCE]: **CER 0.14594 / WER 0.28637 / 0 probes /
0 failures / RTF 0.223 / p50 1.55 s / p95 3.71 s** — within 0.0003 CER
of the Windows primary: the pinned Linux build is quality-identical.

## 8. Capacity estimate

Unchanged from Milestone 16 in structure, now cross-platform:
**MEASURED** saturation ≈2.27 rps of 6.88 s utterances; ladder CPU max
62 % (Linux sidecar) with memory flat. **[ESTIMATED]** ≈12 concurrent
live calls per process on THIS CPU with margin; beyond that,
horizontal replicas at ~1.5 GiB each (short-audio serving). VPS-class
numbers pending real hardware (§6).

## 9. Long audio 60/120/300/600 [DRILL → FIX → RE-VERIFIED]

At ctx = 4096 (probe: concatenated frozen-eval audio, structural
completeness vs the short-clip density norm):

| input | before the fix | completeness | RSS |
|---|---|---|---|
| 60 s | 200 | 1.36 (complete) | 5.4 GiB |
| 120 s | 200 | 1.38 (complete) | 5.6 GiB |
| 300 s | **200 — SILENT truncation** | **0.083** | 6.0 GiB |
| 600 s | 500 internal | — | 6.5 GiB |

Two findings. (a) **The 600-second product ceiling is NOT supportable
at ctx 4096** — the measured-safe ceiling is **120 s**; 300 s returns
one-twelfth of the transcript with a success code, which is silent
data loss, the one failure a customer cannot detect. (b) **Long inputs
balloon memory** (audio-encoder allocations): ~6.5 GiB peak — a VPS
sizing fact and an argument against quietly raising ctx. Fix shipped:
the engine now refuses audio beyond `qwen3_max_audio_seconds`
(default 120) with a clean 400 `invalid_input` naming the limit and
nothing internal — re-verified live (300 s → 400; 120 s → 200).
Chunking or a context re-measurement is FUTURE work, deliberately not
smuggled into this milestone.

## 10. Failure matrix (Linux, post-fix) [DRILL]

| Drill | Expected | Observed | Verdict |
|---|---|---|---|
| child kill → request | truthful refusal, bounded | **503 `not_ready`, 0.04 s, no leak** (M16 was 500 + leak) | PASS |
| child kill → readiness | flips within monitor interval | 0.76 s to `restarting` | PASS |
| supervised recovery | bounded backoff, serves after | ready in 8.5–9.1 s, 200 after | PASS |
| repeated spawn failure | stop at bound, terminal `failed` | 3 attempts, terminal, no hidden retry (deterministic test) | PASS |
| malformed audio | 400 invalid_input | 400, clean format message | PASS |
| unmapped language hint | detection (no reject-list) | 200, correct language | PASS (documented asymmetry) |
| oversize audio | loud refusal | 400 with named limit | PASS (post-fix) |
| queue saturation | clean 503s at bound | 39/100 at c=20, zero other errors | PASS |
| runtime stop | no orphans | 0 (including forced mid-spawn window) | PASS (post-fix) |
| model corrupt/missing | store refuses at boot | store hash-verify at every boot (existing law; not re-drilled — no network isolation available to bound a 1 GB re-download honestly) | PASS by construction, noted |

## 11–12. Route preparation + quality baseline [FACT]

`apps/api/src/intelliai_api/registry/proposals.py`: the COMPLETE
promotion diff, validated and unreachable — `QWEN3_ASR_ARTIFACT`
(provenance + apache-2.0 verdicts at both sources), the hi route with
the serving-path license verdict, `LanguageEvidence` binding corpus
`stt-hi-public-eval@v1`, quality baseline
`2026-08-12-research-qwen3-asr-0.6b-hi-15e`, production benchmark
`2026-08-12-qwen3-asr-0.6b-cpu-ladder`, and an `approval` field
holding a **PENDING sentinel a test refuses to ever see in the live
catalog** — promotion physically requires replacing it with the
founder decision. Six tests: the promoted composition resolves
hi→qwen3 and everything else→whisper; the live registry still resolves
hi→whisper-small; the candidate artifact is absent from the live
catalog; the rollback route equals today's live route verbatim.

## 13. Monitoring requirements (existing conventions only)

Process: `slot_stats()` counters + the four structured supervisor log
events + `/health/ready` slot states (poll). Requests: the existing
`transcription_completed` structured logs already carry artifact,
audio_seconds, total_ms per request; 503s are countable from access
logs. Quality: the attached baseline + correction signals later. No
new observability platform — the gap list for the VPS is: scrape
`/health/ready`, alert on `degraded`/`failed` and on restart-count
growth.

## 14. Segment behavior (disclosure wording, prepared)

> IntelliAI STT continues to return full transcripts for Hindi. With
> the new Hindi engine, `verbose_json` responses contain a single
> segment spanning the full utterance (previously several ~chunk-level
> segments). No word-level timestamps were ever part of the API, and
> none are removed. Applications that display `text` are unaffected.

Retained single-span behavior; no aligner added; no timestamps
invented. The public contract is structurally unchanged.

## 15. Rollback [FACT + rehearsed]

Registry route revert (docs/ops/model-rollout.md), rehearsed in code:
the proposal test composes BOTH directions (promoted registry resolves
hi→qwen3; live registry resolves hi→whisper), and the rollback route
is pinned verbatim. The incumbent artifact stays registered, pinned,
and cached. NO per-request fallback (Milestone 16 decision stands:
double-compute + double-metering hazards; admission control + slot
isolation + route revert are the safety mechanisms).

## 16. Canary readiness gates

| Gate | Requirement | Status |
|---|---|---|
| A. Accuracy | beats incumbent beyond noise band | **PASS** (−60 % CER; replicated; switch-reproduced; Linux-reproduced) |
| B. Reliability | 0 failures, 0 probe words | **PASS** (5 full benchmark runs across 3 serving shapes ×0/153; 8 probes silent) |
| C. Performance | RTF/p95 in SLO | **PASS** (RTF 0.09–0.22; p95 3.2–3.7 s vs incumbent 24.2 s) |
| D. Resources | bounded RAM; Linux concurrency measured | **PASS with caveat** — measured on WSL2 (§6), not VPS hardware; short-audio 1.5 GiB, long-audio ceiling bounded by the new guard |
| E. Operations | truthful readiness, supervised restart, clean shutdown, no orphans | **PASS** (live-drilled, twice, including the forced orphan window) |
| F. Security | pinned runtime + model, no remote code, no implicit download | **PASS** (per-platform tables, verify-at-load, tests) |
| G. Product | segment behavior documented, API unchanged | **PASS** (disclosure §14 prepared; founder signs at promotion) |
| H. Rollback | revert prepared and rehearsed, incumbent available | **PASS** (proposal tests compose both directions) |

## 17. Staging canary

Not re-run this milestone: the Milestone 16 mixed-traffic simulation
(100/100 clean, 90/10) remains the local canary evidence; nothing in
this milestone changed routing mechanics. A NEW canary becomes
meaningful only on VPS hardware with the vendored runtime — first item
of the next milestone.

## 18. Remaining blockers (all deploy-side, none engineering-side)

1. **VPS-hardware validation** — re-run `m17_linux_session.sh` on the
   real box (scripts committed; expected ~1 h).
2. **Vendored runtime layer** — a container/image step that lays down
   the pinned tar.gz + libgomp and points
   `INTELLIAI_STT_QWEN3_SERVER_BINARY` at it (the hash contract is
   already enforced in code).
3. **Founder decisions** — the switching itself, the §14 disclosure,
   and the promotion commit (replace the PENDING sentinel, register
   the artifact, swap the route).

## 19. Recommendation

**Proceed to the production canary milestone.** Sequence: vendored
layer → VPS re-validation (same scripts) → founder sign-off → land the
prepared promotion diff with a small-percentage Hindi canary via the
registry (route flip is the mechanism; percentage splits, if wanted,
are a gateway concern to design there, not in the runtime). Rollback
is one revert away throughout. The engineering evidence is complete;
what remains is hardware access and the decision itself.

---

*No production surface changed. No customer traffic touched. The
candidate remains research-namespaced; the promotion diff exists,
validated, awaiting exactly one human decision.*
