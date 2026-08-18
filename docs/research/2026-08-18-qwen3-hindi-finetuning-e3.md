# Qwen3-ASR 0.6B Hindi Fine-Tuning — Experiment E3 (Milestone 23)

| | |
|---|---|
| **Status** | EXPERIMENT COMPLETE — research only; production untouched |
| **Date** | 2026-08-18 (data plane, training, evaluation, export, records — one day) |
| **Question** | Can a controlled retention mix (E2's corpus + ~6% English + a bounded 0.5–2 s slice) preserve E2's Hindi gain without the English and 1-second regressions? |
| **Answer** | **Yes — both regressions were distribution shift, and the mix closes both.** English returns to **WER 0.0** (E2: WER 1.0 — silence or translation), the full 0.5–2.5 s short-speech ladder transcribes (E2: empty at 1 s), silence/noise safety holds — priced at a **~5% relative Hindi giveback vs E2's best** (CER 0.11612 vs 0.11044) that still stands **−20.3% vs the base** and −6.9% vs E1, through the real adapter. |
| **Classification (Phase 20)** | **A. PROMOTION CANDIDATE** — first candidate in the program to pass ALL EIGHT gates. Research-only until a separate switching/promotion milestone (Phase 21 law); production still routes Hindi to whisper-small. |

## 1. Baselines this experiment answers to (M22 record)

Base CER 0.1457 / E1 0.12477 / E2 0.11044 — all adapter-side on frozen
`stt-hi-public-eval@v1`. E2's recorded gate failures: English erased
(ck300/600 silence, ck900+ en→hi translation; threshold between 10 h
and 27 h) and 1 s speech suppressed (2 s corpus floor + negatives
taught "when unsure, silence").

## 2. Hypothesis and the strict rule

Both E2 regressions are DATA DISTRIBUTION artifacts, not capacity or
optimizer failures. E3 therefore changes ONLY the composition; every
optimizer variable, the base revision, the seed, and the export
pipeline stay at E2's exact values.

## 3–5. The three slices and the frozen composition [EVIDENCE]

**`qwen-hi-public-train@v3`** — 15,192 rows / **30.11 h**, sha
`6cfc585d3cecbdc177f31f476ec10aa54232706c2e74015af28e2a041e73a467`,
built by a new pin-reverified `merge-train` verb (global id/path
uniqueness; per-language row-share ceilings that REFUSE rather than
trim; `merged_from` pins in provenance):

- **E2's corpus verbatim** — v2's 13,492 rows byte-identical inside v3
  (containment proven row-for-row in `data-comparison.json`), keeping
  the 68 no-speech negatives (0.45%) exactly as frozen.
- **English retention slice** — `qwen-en-retention-slice@v1`: 900 rows
  / 2.58 h of FLEURS `en_us/train` (sha `c3bbff63…`), the one approved
  OPEN English source (CC-BY-4.0, registry verdict 2026-08-11,
  re-read at ingest). **5.92% of rows** (8.6% of hours), ceiling 8%
  enforced mechanically at merge. Purpose: retain multilingual
  behavior, not optimize English. FLEURS publishes no speaker ids
  (recorded; official splits claimed speaker-aware by the authors).
- **Short-speech slice** — `qwen-hi-short-slice@v1`: 800 rows / 0.25 h
  (sha `d381d8ca…`) of REAL sub-2 s IndicVoices utterances (median
  1.1 s, all speaker-attributed) admitted through a new bounded
  validation window **[0.5 s, 2.0 s)** whose upper bound is exclusive
  at the standard floor — no clip can satisfy both freezes. No
  windowing, no manufactured transcripts. 5.27% of rows. Rejection
  ledger: 10,806 outside-window, 938 sub-0.5 s, 672 markup, 151
  eval-roster speakers.

## 6. Disjointness [EVIDENCE]

Frozen eval untouched. Content-hash + 32-speaker roster enforced at
each slice freeze (151 roster rejections recorded in the short slice);
the governance test now sweeps EVERY frozen train manifest against the
eval's ids and audio paths. Cross-slice overlap is structural: the
duration windows are disjoint and the merge refuses id/path collisions.

## 7. What changed in E3 — and only this

| | E1 (v1) | E2 (v2) | E3 (v3) |
|---|---|---|---|
| Hours / rows | 10.0 / 4,988 | 27.27 / 13,492 | 30.11 / 15,192 |
| English rows | 0 | 0 | **900 (5.92%)** |
| Rows < 2 s | 0 | 0 | **800 (5.27%)** |
| Negatives | 0 | 68 | 68 (carried) |
| Duration min/median | 2.0 / 5.5 | 2.0 / 5.9 | **0.5** / 5.6 |
| Config | — | identical | **identical** |

## 8–10. Training, hardware, smoke, pilot [EVIDENCE]

E2's exact configuration: lr 1e-5 linear + 3% warmup, 2 epochs,
Adafactor, bf16, non-reentrant gradient checkpointing, frozen audio
tower (596M/782M trainable), seed 20260817, effective batch 16 as
micro-batch 1×16 (E2's recorded full-run shape), checkpoints every
300. Same pinned base revision `5eb14417…`. Step count changed only as
an arithmetic consequence of more rows (1,840 steps).

Smoke verified the three-and-only-three converted row shapes: 14,224
`language Hindi<asr_text>…` + 900 `language English<asr_text>…` + 68
`language None<asr_text>`. Pilot (30 steps) already showed NO E2
failure mode: JFK in English, 1 s Hindi in Devanagari, silence empty —
the full run was funded per the milestone's pilot gate. Full run: RTX
5070 Laptop, **1,840 steps in 3.30 h** (warm decode cache; E2's 5.48 h
included a cold start), peak VRAM **5,096 MiB**, validation monotonic
0.2047 → **0.1759** (ck300 later rotated out by the trainer's
6-checkpoint retention limit — recorded, not hidden).

## 11. Checkpoint sweep — the E3 story in one table [EVIDENCE]

HF-side (M21 harness; anchors base 0.14781, E1-best 0.12401, E2-best
0.11100), plus the retention probes per checkpoint:

| Checkpoint | CER | WER | JFK en WER | 1 s hi | silence/noise |
|---|---|---|---|---|---|
| ck600 | 0.11757 | 0.24156 | 0.0 | ✓ | empty |
| ck900 | 0.11875 | 0.25138 | 0.0 | ✓ | empty |
| ck1200 | 0.11833 | 0.24616 | 0.0 | ✓ | empty |
| **ck1500 (selected)** | **0.11612** | **0.24064** | 0.0 | ✓ | empty |
| ck1800 | 0.11688 | 0.24217 | 0.0 | ✓ | empty |
| ck1840 | 0.11771 | 0.24463 | 0.0 | ✓ | empty |

**The retention board is CLEAN at every depth** — 5.92% English held
multilingual behavior even at full training depth, where E2's ck900+
translated English into Hindi. Zero empty outputs, zero hallucination
probe hits anywhere. Selection: ck1500 wins CER and WER outright with
gates identical (validation loss would have picked ck1840 — gates, not
loss, decide).

## 12. Official frozen evaluation — through the REAL adapter [EVIDENCE]

Template-rewrite export (the pipeline whose control reproduced the
official base GGUF byte-for-byte; structure identical, 311 tensors,
byte-length equal to the official artifact) served by the pinned
b10344 runtime, store-verified at load:

| | Base (15E) | E1 (M21) | E2 (M22) | **E3 ck1500 (M23)** |
|---|---|---|---|---|
| CER | 0.1457 | 0.12477 | 0.11044 | **0.11612** (replicate 0.11750; spread 0.0014) |
| WER | 0.2851 | 0.26642 | 0.22805 | **0.24064** |
| Sub/ins/del | — | .200/.029/.037 | .170/.027/.031 | .180/.026/.034 |
| Hallucinated | 0 | 0 | 0 | **0** |
| **English (JFK record)** | WER 0.0 | WER 0.0 | **WER 1.0** | **WER 0.0, CER 0.0** |

Adapter-side CER matches the HF-side number to five figures — the
export is behavior-faithful. Records:
`2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-{hi-m23,hi-m23-replicate,en-m23-safety}.json`.

## 13–16. The retention gates, adapter-side (the product path) [EVIDENCE]

`adapter-battery.json`, all through the served quantized artifact:

| Input | E2 (recorded) | **E3 served** |
|---|---|---|
| Digital silence 10 s / −50 dBFS / −40 dBFS | empty | **empty / empty / empty** |
| Speech↔silence transitions (both orders) | transcribes | transcribes |
| **Speech ladder 0.5 / 1.0 / 1.5 / 2.0 / 2.5 s** | 1 s → EMPTY | **Devanagari at every rung, 0.5 s included** |
| Real held-out sub-2 s utterances (×2) | — | transcribe (HF-side CER 0.0/0.25) |
| JFK English | silence or hi-translation | **English (Latin), WER 0.0** |
| Repeated-token hallucination | — | none anywhere |

## 17. Hindi primary quality — the priced trade

E3 gives back **+0.0057 CER (+5.1% relative) vs E2's best** — real
(~4× the replicate spread) and bounded — while keeping **−20.3% vs
base** and −6.9% vs E1. The milestone's own framework says it: a
slightly worse Hindi CER with full retention is a better product than
E2's lower CER with English destroyed. E2 remains the program's best
pure-Hindi number and remains gate-failed for anything user-facing.

## 18. Long audio and performance [EVIDENCE]

M19 chunked path untouched and re-proven on E3: **300 s → 4 segments,
join==text, offsets 0→300, 76.5 s wall; 600 s → 7 segments,
join==text, offsets 0→600, 196.5 s wall.** Performance: RTF 0.218
(primary) / 0.160 (replicate) — class-consistent with base 0.207 / E1
0.237 / E2 0.262 (machine variance dominates); serving RSS **1,559 MiB**
after short-clip decodes (base class 1,363–1,551; E2 1,652); load
1,712.8 ms; artifact sizes identical (804.7 MB + shared 214.4 MB
mmproj). CPU-first deployability unchanged.

## 19. Registration [EVIDENCE]

`qwen3-asr-0.6b-hi-ft-e3@v1` — model sha `e54586c4…`, official mmproj
byte-shared, research-only `.invalid/m23/` URL, admission-law
selectable, guard-tested (distinct from official AND e1 AND e2), local
bytes hash-verified by the store at every load. E1/E2/base artifacts
preserved untouched.

## 20. Final classification

**A. PROMOTION CANDIDATE** — the first in this program to pass all
eight Phase 20 criteria:

1. Hindi materially better than base ✓ (−20.3%, ~84× the replicate spread)
2. English retained ✓ (WER 0.0 — the M21-proven level)
3. Very-short speech restored ✓ (full ladder + real held-out shorts)
4. Silence/noise safe ✓ (E2's win preserved, both noise levels)
5. No hallucination regression ✓ (0 everywhere)
6. Long-audio intact ✓ (300/600 s complete, join==text)
7. CPU/RAM acceptable ✓ (RSS 1,559 MiB, RTF class-consistent)
8. Export/serving works ✓ (hash-verified, full benchmark served)

**Production remains untouched** (Phase 21): Hindi still routes to
whisper-small; the M18 promotion proposal still names the incumbent
qwen artifact; no E3 artifact touches any product surface. Promotion
requires its own milestone: the M16-style switching battery re-run
against THIS artifact, a promotion-proposal update, and founder
approval.

## 21. Recommendation

E3 closes the experiment arc E1 opened: E1 proved the pipeline, E2
proved data was the bottleneck, E3 proved the regressions were
composition. Next decisions (all founder-gated): (a) a
switching/promotion milestone for `qwen3-asr-0.6b-hi-ft-e3@v1` vs the
incumbent whisper-small route; (b) optionally, a data-scale E4 (the
25–40 h band's upper half plus the same retention recipe) only if more
Hindi headroom is wanted before promotion; (c) the deferred throughput
hygiene (parallel dataloader decode) — engineering, not science.
