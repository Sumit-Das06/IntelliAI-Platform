# Qwen3-ASR 0.6B Hindi Fine-Tuning — Experiment E2 (Milestone 22)

| | |
|---|---|
| **Status** | EXPERIMENT COMPLETE — research only; production untouched |
| **Dates** | 2026-08-17 (data plane, training) / 2026-08-18 (evaluation, export, records) |
| **Question** | Is training-data quality and quantity the current bottleneck? And can better data remove E1's silence regression? |
| **Answer** | **Yes to both.** Cleaned 27.3 h + 0.5% no-speech negatives, config held at E1's: **CER 0.12477 → 0.11044 (−11.5% vs E1; −24.2% vs base) on the frozen benchmark through the real adapter**, WER 0.26642 → 0.22805 (−14.4%), zero hallucinations, and **silence → empty at every checkpoint** through both the HF and quantized serving paths. |
| **Cost, recorded plainly** | **English is gone.** 27 h of all-Hindi supervision crossed a retention threshold E1's 10 h did not: late checkpoints TRANSLATE English speech into Hindi; early ones emit nothing on it. Gate-failing for promotion under this milestone's own rules. |
| **Classification (Phase 19)** | **B. MODEST IMPROVEMENT** over M21 on the primary axis (same scale that called E1's −14.4% modest), with the silence gate PASSED and the English gate FAILED → **NOT a promotion candidate**; the E3 path is a retention mix. |

## 1. Baselines this experiment answers to

Base CER 0.1457 / E1 CER 0.12477 (both adapter-side, frozen
`stt-hi-public-eval@v1`, replicate bands ~0.001).

## 2–3. Data-quality findings and cleaning rules [EVIDENCE]

E1's corpus measured: 10.0 h with `<unintelligible>` in 3.3% of rows
(the only markup present) and ZERO no-speech examples — the silence
regression was a data property, not an optimizer one. Cleaning policy
(deterministic, tested, OFF by default so all earlier manifests stay
byte-reproducible): markup rows REJECTED with the tag recorded
(stripping would supervise deletions), control characters stripped,
whitespace collapsed with categories logged; **no Hindi text
normalization** — the ruler and the frozen eval corpus untouched.

## 4. Negative-example design [FACT/EVIDENCE]

Representation verified from committed evidence, not assumed: the
pinned base emits literally `language None<asr_text>` on silence (15E
probe, pinned by the adapter's parser tests) — so that exact string is
the training target. `zxx` (ISO "no linguistic content") candidates
with empty transcripts, admitted by a scoped validation inversion.
Three deterministic kinds (seeded): digital silence, −50 dBFS gaussian
noise, and the quietest 4 s window cut from approved ingested clips
(parent ids recorded; two new registered sources — synthetic in-repo,
CC-BY-4.0 derivative). 100 generated → 68 unique after byte-dedup
(identical-length digital silences hash identically — correct) =
**0.50% of rows**, deliberately conservative.

## 5–8. Corpus, manifest, disjointness [EVIDENCE]

**`qwen-hi-public-train@v2`** — 13,492 rows / **27.27 h**, sha
`31e61c1cd6240177f4d88009254746beb091b9dfada5b00c4c1d683337e86708`:
IndicVoices 10,556 (train split + roster-excluded valid split) +
Kathbath 2,868 + 68 negatives. All sources already approved
(CC-BY-4.0/CC0); **no new dataset gates**. 5,864 rejections recorded
by reason: 4,910 too-short, **672 markup**, **101 eval-speaker**,
**149 eval content-hash**, 32 duplicates. Speaker governance is now
STRONGER than v1's wording: per-clip speaker ids exist for every
speech source and the frozen eval's 32-speaker roster is mechanically
enforced; the valid-split admission policy (non-roster speakers,
closer to eval recording conditions, speaker- and content-disjoint) is
recorded openly in provenance. Validation split: same id-hash rule
(421 rows). Derived JSONLs: train `ef624a38eb53…`, val `1808623be493…`.

### Phase 6 comparison (what changed, and only this)

| | E1 (v1) | E2 (v2) |
|---|---|---|
| Hours / rows | 10.0 / 4,988 | 27.27 / 13,492 (2.7×) |
| Markup rows | 166 (3.3%) | **0** (672 rejected) |
| Negatives | 0 | 68 (0.50%) |
| Sources | IV 3,604 / KB 1,384 | IV 10,556 / KB 2,868 / neg 68 |
| Config | — | **identical** (see §9) |

## 9–10. Training configuration and hardware [EVIDENCE]

Held at E1: lr 1e-5 linear + 3% warmup, 2 epochs, Adafactor, bf16,
non-reentrant gradient checkpointing, frozen audio tower (596M/782M
trainable), seed 20260817, effective batch 16. Two recorded
adjustments, both pre-explained: checkpoint cadence 150→300 steps
(bookkeeping — same early/mid/late coverage over 1,634 steps) and
**micro-batch 2×8 → 1×16** after the first attempt OOMed at step 378
(v2's longer conversational clips paired two ~30 s items; the logits
tensor alone for such a pair nears a GiB on 8 GiB hardware — same
effective batch, halved worst-case peak; restarted from step 0 so the
record is single-configuration). RTX 5070 Laptop, torch 2.11+cu128,
peak VRAM **5,105 MiB**, duration **5.48 h** (micro-batch-1 forwards +
single-threaded audio decode set the pace; a throughput fix is E3
hygiene, not science).

## 11. Pilot [EVIDENCE]

30 steps: validation 1.776 → 1.657 (E1-pilot-shaped), coherent
Devanagari — and **silence → EMPTY already at step 30**. The negative
lesson lands almost immediately.

## 12–13. Full run and checkpoint sweep [EVIDENCE]

Validation loss 0.1968 → 0.1752, monotonic across all five boundaries.
HF-side sweep (same harness; anchors base 0.14781, E1-best 0.12401):

| Checkpoint | CER | WER |
|---|---|---|
| ck300 | 0.12172 | 0.25261 |
| ck600 | 0.11439 | 0.23972 |
| ck900 | 0.11349 | 0.23603 |
| **ck1200 (selected)** | **0.11100** | **0.23297** |
| ck1500 | 0.11134 | 0.23358 |
| ck1634 | 0.11155 | 0.23297 |

**Every E2 checkpoint beats E1's best.** Selection weighed CER + WER +
the silence probe + the English probe (not validation loss alone);
ck1200 wins accuracy, and among English failure modes its
translation behavior beats ck300/600's SILENT loss (the platform's own
M17 law: silent loss is the unforgivable failure).

## 14. Official frozen evaluation — through the REAL adapter [EVIDENCE]

Template-rewrite export served by the pinned b10344 binary with the
official mmproj, standard runner, same clips/ruler/decode as every
prior record:

| | Base (15E) | E1 (M21) | **E2 ck1200 (M22)** |
|---|---|---|---|
| CER | 0.1457 | 0.12477 | **0.11044** (replicate 0.10871; spread 0.0017) |
| WER | 0.2851 | 0.26642 | **0.22805** |
| Sub/ins/del | — | 0.200/0.029/0.037 | 0.170/0.027/0.031 |
| Hallucinated probes | 0 | 0 | **0** |
| RTF | 0.207 | 0.237 | 0.262 |

Records: `2026-08-18-research-qwen3-asr-0.6b-hi-ft-e2-hi-m22{,-replicate}.json`.

## 15. Silence results — the primary E2 gate: PASSED [EVIDENCE]

| Input | E1 candidate | **E2 candidate** |
|---|---|---|
| Digital silence 10 s | "इस्ट्रिक्ट इस्ट्रिक्ट" (the regression) | **empty** |
| Tone 440 Hz | empty | **empty** |
| Adapter-side silence/tone (quantized path) | — | **empty** |

Silence → empty at EVERY E2 checkpoint probed (300/600/900/1200), on
both the HF path and through the served artifact. 0.5% negatives
sufficed. The extended battery (`silence-battery.json`) widens the
win — E2 stays empty on real noise at −50 AND −40 dBFS where E1
voices text on both — and transitions behave (speech→silence and
silence→speech both transcribe the speech):

| Input | E1 | E2 |
|---|---|---|
| Digital silence / quiet noise / moderate noise | voices text on all three | **empty on all three** |
| Speech↔silence transitions (both orders) | transcribes | transcribes |
| Short speech 2.5 s in noise | transcribes | transcribes |
| **Very short speech (1 s)** | transcribes | **EMPTY — a NEW recorded edge regression** |

The very-short finding: the corpus's 2 s validation floor means
sub-2 s speech was never supervised, and the negatives taught "when
unsure, silence" — so a 1 s utterance ("हाँ") now suppresses. Product
impact is real for dictation (short confirmations) and unmeasured by
the frozen benchmark (whose clips are ≥2 s by corpus law). Recorded
beside the English gate; the E3 data plan addresses both.

## 16. English regression — recorded, gate-failing [EVIDENCE]

No E2 checkpoint retains English. The failure mode EVOLVES with depth:
ck300/ck600 emit NOTHING on English (the no-speech lesson
over-generalized to "not Hindi → silence"); ck900+ TRANSLATE English
speech into Hindi (JFK → "और तो मेरे फेलो अमरिकन्स आपको नहीं पूछना
चाहिए कि आपका देश…"). Adapter-side safety record shows both modes
(flac→translation, wav→empty). E1 at 10 h kept English at WER 0.0 —
**the monolingual retention threshold sits between 10 h and 27 h**.
Not optimized during E2, per spec; recorded as the promotion-blocking
gate.

## 17–18. Serving export and long audio [EVIDENCE]

Same pipeline whose control reproduced the official base GGUF
byte-for-byte (M21) — unchanged and un-bypassed. E2 export
`2fbd9faf…`, registered as `qwen3-asr-0.6b-hi-ft-e2@v1` (research-only
`.invalid` URL, official mmproj byte-shared, admission-law selectable,
guard-tested), hash-verified at load by the store, served by the
pinned runtime for the entire evaluation. **Long-audio chunked path
intact**: 300 s → 4 segments, 3,546 chars, join==text, complete;
600 s → 7 segments, 7,936 chars, join==text, complete (342 s wall,
inside the M19 deadline analysis).

## 19. Performance [EVIDENCE]

RTF 0.262 (class-consistent with base 0.207/E1 0.237 — run-to-run
machine variance dominates at this scale), serving RSS 1,652 MiB
mid-benchmark (base class: 1,363–1,551), artifact sizes identical
(804.7 MB + shared 214.4 MB mmproj), load time unchanged (same
architecture, same quantization). CPU feasibility unchanged.

## 20. Comparison with M21 — the Phase 18 answer

**Data was the bottleneck.** With every optimizer variable frozen,
cleaned+scaled data delivered −11.5% relative CER over E1 (−24.2% over
base), −14.4% relative WER, and fixed the silence regression — while
proving a NEW data lesson: monolingual scale erases other languages.
No hyperparameter sweep is warranted yet; the next binding constraint
is again data (composition, not volume).

## 21. Final classification

**B. MODEST IMPROVEMENT** over the M21 baseline (the scale that called
E1's −14.4% modest), silence gate PASSED, hallucination gate PASSED,
serving/export PASSED, long-audio PASSED, performance PASSED —
**English gate FAILED → not a promotion candidate.** Production
unchanged: Hindi still routes to whisper-small; the M18 promotion
proposal still names the incumbent qwen artifact; no E2 artifact
touches any product surface.

## 22. Recommendation

**E3 = the retention mix, one theme (data composition) with two
ingredients:** v2's exact corpus + ~5–8% English rows from an
already-approved open source (FLEURS en is registered and OPEN) + a
short-speech slice (0.5–2 s Hindi utterances — lower the validation
floor for a bounded slice, or window existing clips) to close BOTH
recorded regressions: English retention and very-short suppression.
Same configuration otherwise. Hypothesis: Hindi keeps most of the E2
gain while English returns to WER ≈ 0 and 1 s utterances transcribe —
both regressions are distribution shift, not capacity. Secondary E3
hygiene: parallelize the dataloader (the 5.5 h wall was decode-bound,
not GPU-bound). Only if E3's composition fix fails does
optimizer/recipe work earn its turn.
