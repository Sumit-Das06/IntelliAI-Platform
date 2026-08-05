# PH0 — Apparatus Validation

| | |
|---|---|
| **Campaign** | `CAMP-STT-2026A` · phase **PH0** |
| **Date** | 2026-08-06 · repo at `e8333e2` + the PH0 execution changes committed with this document |
| **Subject** | **The instrument.** No candidate was measured, no model compared, no baseline christened, no validity computed. The incumbent (`whisper-small`, `Approved for Adoption`) served only as the known target the apparatus was fired at. |
| **Runtime** | `stt-runtime 0.1.0`, contract 1, hosting real `whisper-small` (int8), fresh process launched for this phase |
| **Records** | Four `EvalRun` files beside this document, cited by session id below. `--benchmark` was never passed: none of them is a named baseline. |

## 1. Sessions

| Session | Slice | Clips | Purpose |
|---|---|---|---|
| `CAMP-STT-2026A/PH0/S01-en` | `en` | 2 referenced + 2 probes | instrument cross-check |
| `CAMP-STT-2026A/PH0/S02-en-replicate` | `en` | same, same runtime process | determinism replicate |
| `CAMP-STT-2026A/PH0/S03-hi` | `hi` | 2 probes | explicit-declaration cost; undeterminable-timestamp branch |
| `CAMP-STT-2026A/PH0/S04-zxx` | `zxx` | 2 probes | auto-detect cost via the **default route** |

Session ids identify the experiment only (founder ruling, PH0). The artifact,
deployment, route, ruler, decode configuration and environment live inside each
record's `ExecutionContext` — observed from the runtime, not typed by anyone.

## 2. Instrument cross-check — the new harness against the committed baseline

Pre-registered expectation: S01 must reproduce the committed
`2026-08-05-intelliai-stt-en` record on the two JFK clips **to the integer**.

| Clip | S/I/D, ref, hyp counts | Transcript |
|---|---|---|
| `jfk-flac` | equal | **byte-equal** |
| `jfk-wav` | equal | **byte-equal** |

`wer_ascii = 0.000`, matching the committed `overall_wer`. The old harness
(operator-declared, pre-methodology) and the new one (observed, evidence-writing)
agree exactly on identical clips against the identical artifact. The instrument
did not move the ruler.

## 3. Determinism replicate

S02 repeated S01 in the same runtime process. Every correctness field —
alignment counts, transcripts, all metrics except `recognition_rtf` — is equal
between the two records. Wall-clock differed (RTF 0.131 vs 0.125), as wall-clock
does; no noise band is claimed from n=2.

## 4. Probe behaviour, per declared language

All six probes, every session: **zero hallucinated words** — including every
tone probe. The silence result is structural (the pipeline VAD short-circuits
before the engine; `vad_owner=pipeline` is observed in the same records that
carry the number, which is what makes it readable as a pipeline property).

The declaration cost, on the *identical* tone clip (`recognition_rtf`, per clip):

| Declaration | RTF | vs `en` |
|---|---|---|
| `en` (explicit) | 0.281 | 1.0× |
| none (auto-detect, default route) | 0.544 | 1.9× |
| `hi` (explicit) | 1.479 | **5.3×** |

This upgrades the Gate 4 R-10 finding from a flagged anecdote to registered,
reproducible evidence carrying its decode configuration and environment. It
remains a **non-speech** measurement (`is_quality_claim: false` on every probe
record) and says nothing about any model's quality.

## 5. Determination inventory

Exactly the predicted floor, on all four records: `manifest_provenance_unverified`,
`stack_not_reported`, `cpu_physical_cores_unavailable`, `ram_total_mib_unavailable`,
`thread_env_unavailable`, `hardware_class_unruled` — plus
`timestamp_source_undeterminable` on **S03 and S04 only**, the two slices that
produced no text, exactly the case the three-way design exists for. No
unexplained determination appeared; no expected one is missing.

## 6. Shakedown findings

| # | Finding | Feeds |
|---|---|---|
| F-1 | A **stale pre-B4a runtime** held port 8001 from the M5 sessions. Had it been measured, the harness would have refused (`RuntimeNotDescribedError`) — the guard worked before the operator did. Session preconditions should verify the serving process is fresh and self-describing. | B7 preconditions; operator checklist |
| F-2 | The CLI **conflated slice language with routing key**: `zxx` was unmeasurable until the resolution was corrected to the default route (a declaration-less slice resolves as declaration-less requests do). Fixed during PH0; the session layer must keep the two facts distinct. | fixed here; B7 |
| F-3 | **Build-label era boundary.** Observed build is `int8`; historical operator-typed records say `cpu-int8`. Same build, two spellings — the last such drift, since nobody types it now. Consequence: a switching test between a new record and a pre-PH0 record would read the build as *changed*. The incumbent must be re-baselined under the new instrument (PH1's first act anyway) before any switching test cites history. | PH1, B8 |
| F-4 | `thread_env` is unset in the runtime's environment — engine libraries are defaulting internally. Recorded honestly, but thread pinning (hardware spec T-1) is an unmade operational decision. | D-6 adjacency; B7 |
| F-5 | No W1 session warm-up phase exists (register 4.10 / B-10); the replicate served as de-facto warm coverage here. | B7 |
| F-6 | The reversed-order audit (procedure step 7) is unsupported by the runner and was not performed. | B7 |
| F-7 | The benchmark organization is still uncreated. PH0 never touched the gateway so nothing was misattributed, but the first gateway-path phase requires it. | founder homework (B0) |
| F-8 | `zxx → unicode_generic@v2` binding ruled and landed — the one policy change PH0 required. | done |

## 7. PH0 Readiness Assessment

Engineering sign-off for challenger benchmarking. Judged **entirely from
evidence produced during PH0**; no statement below interprets model quality.

| Item | Verdict | Evidence |
|---|---|---|
| **Metric registry** | **PASS** | Every emitted name (9 distinct across 4 records) resolves in registry v3; write-guard active; uniqueness and withdrawal pinned in CI |
| **Normalization** | **PASS** | V-7 control-string round-trip green in CI; three rulers pinned; `zxx` binding ruled; no ruler failure fired on any declared reference |
| **Runtime self-description** | **PASS** | `/info` supplied build, 13-key decode configuration, granularity, `vad_owner`, environment; the runner declared nothing |
| **Evidence schema** | **PASS** | All four records parse back through CI's own validators; all seven historical records still parse |
| **ExecutionContext** | **PASS** | Fully populated on all four records; `observed_from="runtime"`; every field Observed or Derived per the classification law |
| **Determinations** | **PASS** | Exact predicted floor; the undeterminable-timestamp branch fired only where designed; every absence explained, none invented |
| **Registry validation** | **PASS** | Per-clip and aggregate metric maps registry-checked at write; legacy `mean_rtf` structurally unrecordable |
| **Reproducibility** | **PASS** | Replicate byte-equal on every correctness field within one process; offline recompute of S01 from record-verbatim hypotheses matches to the integer |
| **Historical baseline cross-check** | **PASS** | S01 reproduces the committed English baseline: integer-equal counts, byte-equal transcripts |
| **Known limitations** | **PARTIAL** | Enumerated, not closed: no W1 warm-up phase, no reversed-order audit, no validity computation (B7 by ruling), `hardware_class` unruled (D-6), thread configuration unpinned, one machine, non-speech probes only, F-3 era boundary pending the PH1 re-baseline |

### Verdict

**READY FOR CHALLENGER BENCHMARKING**

Justification, from PH0 evidence alone: the instrument reproduces the committed
baseline exactly; it replicates deterministically; it refused dishonest
configurations twice during this very phase (the stale runtime, the unroutable
slice) rather than recording them; and every fact it could not establish is a
named Determination rather than a guess. The PARTIAL above bounds *what may be
claimed* — the limitations are session-layer and corpus constraints that PH1+
and B7 own — not whether the apparatus tells the truth. It does.
