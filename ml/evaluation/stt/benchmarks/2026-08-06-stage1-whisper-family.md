# Stage 1 — Whisper Family Benchmark

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Question** | Is `whisper-small` still the right production engine, does `whisper-base` cut cost, does `whisper-large-v3` buy quality worth its CPU cost? |
| **Subjects** | `whisper-small` int8 (incumbent, product path) · `whisper-base` int8 (research route) · `whisper-large-v3` int8 (research route, admitted this stage from the Systran first-party distribution) |
| **Corpus** | `stt-eval-seed@v2`, `en` slice: 2 referenced clips (one utterance, 44 reference words) + 2 probes (silence, 440 Hz tone). **Quality readings on this corpus are smoke-tier**: it can detect regressions and hallucinations; it cannot rank models upward. The quality-tier verdict waits on the English C2. |
| **Records** | 7, under `ml/evaluation/stt/results/*-stage1*.json` — sessions `CAMP-STT-2026A/PH1/S10-en-ct2-incumbent`, `PH2/S20-en-ct2-whisper-base`, `PH2/S21-en-ct2-whisper-large-v3` (S20/S21 minted here as the first PH2 session numbers) |
| **Route law** | Research-route and product-path numbers are **read side by side, never differenced**. Ratios quoted below are observations with that caveat, not computed evidence fields. |
| **Excluded** | `large-v3-turbo`: every CTranslate2 conversion of it is a third-party artifact and the third-party-conversion policy is unruled. Excluded by discipline, not judgement. |

## 1. Results

**Correctness — deterministic, byte-stable across every machine state observed:**

| Artifact | `wer_unicode` | `cer_unicode` | `hallucinated_words` | Replicate |
|---|---|---|---|---|
| whisper-small | **0.000** | 0.000 | **0** | byte-equal transcripts, 3 runs |
| whisper-base | **0.000** | 0.000 | **0** | byte-equal transcripts, 2 runs |
| whisper-large-v3 | **0.000** | 0.000 | **3** — deterministic | byte-equal transcripts incl. the hallucination, 2 runs |

**The hallucination finding (the headline).** On the 5-second 440 Hz tone declared `en`, `whisper-large-v3` deterministically emits **"Thanks for watching!"** — the YouTube-caption training artifact — in both runs. `whisper-small` and `whisper-base` emit nothing on the identical bytes. The tone **passes the pipeline VAD by design** (it has energy), so this is engine-level hallucination the pipeline did not contain: in production, hold music or line tones would be billed to a customer as fictional text. This is the first hallucination ever recorded in this ledger, and it is the exact failure class the probe corpus was built to catch.

**Cost — wall-clock, honestly bounded.** The machine is not asserted idle (precondition P-9 was not in force for these runs) and slowed ~4–5× across the session — the incumbent itself read RTF 0.094 in the first window and 0.34–0.54 in the last. Absolute RTFs below are therefore per-window observations, **no band established**; the *within-window ratios* were stable across two windows and are the citable shape:

| Artifact | RTF observed (aggregate, per window) | Ratio vs small, same window | Load / warm-up (ms, runtime-reported) |
|---|---|---|---|
| whisper-small | 0.094 (fast window) · ~0.43 (slow window) | 1.0× | 27 209 / 2 029 |
| whisper-base | 0.035* (fast) · 0.17 (mid) | **≈ 0.4×** in both windows | 2 803 / 1 927 |
| whisper-large-v3 | 0.46* (fast) · **2.70 (slow — slower than real time)**, internally consistent ±1 % in both | **≈ 5–6×** in both windows | 7 407 / 9 484 |

\* readings from records superseded during this stage (see §3, F-S1-1), quoted as observations only; the committed large-v3 pair is from the slow window.

`whisper-small` and `whisper-base` transcribed faster than real time in every observed machine state. **`whisper-large-v3` did not**: in the slow window its committed records show RTF 2.70 on speech and **5.29 on the tone clip** — a realistic busy-consumer-machine state in which the 1.5×-audio-duration PRD promise is violated outright at c=1, before any concurrency. Even its fast-window observation (0.46) leaves thin-to-no headroom under load; the incumbent's measured production headroom is ~9×.

## 2. Answers to the Stage 1 questions

**Is whisper-small still the best production choice? — Yes, on this evidence.** Nothing displaced it: quality is tied at the corpus's ceiling (0.000 — this corpus cannot rank upward), it carries zero hallucinations, and its cost has ~9× production headroom.

**Does whisper-base reduce cost? — Yes, ≈ 2.5× (stable ratio across windows), with an invisible quality risk.** A 74M model is expected to transcribe worse than a 244M one; 44 reference words cannot see that difference. **Switching English to base on this evidence would be reckless**; the opportunity is real and priced, and it waits for the English C2.

**Does whisper-large-v3 improve quality enough to justify CPU cost? — No observable quality gain, a 5–6× cost that breaches real time in a realistic machine state, and a deterministic engine-level hallucination the pipeline did not contain.** On this corpus the incumbent is already at 0.000, so large-v3 *cannot* demonstrate a gain in English here — but it demonstrated two disqualifier-class costs: its committed records show RTF 2.70 on speech (the PRD's 1.5× promise violated at c=1), and it invents text on non-speech audio the VAD legitimately passes. Under the Success Criteria (deployment economics; uncontainable hallucination), large-v3 is **not a candidate for the default engine** on current evidence. Its remaining live question is Hindi (H-WHISPER — the lineage's quality ceiling for the wedge language), which Stage 3's corpus will ask, with both findings carried into that reading.

## 3. Findings beyond the questions

- **F-S1-1 · Route-derivation defect, found and fixed by execution.** The evidence writer hardcoded `route=product_path` with a pre-B6 rationale; the first research-route records were mislabeled, caught before commit, deleted (uncommitted working files), and re-measured after the fix — route now derives from the recorded subject's `research:` namespace, which depends on no filesystem or registry state. Two superseded wall-clock observations from the deleted files are quoted in §1 as observations only.
- **F-S1-2 · The idleness precondition is not bureaucracy.** A 4–5× wall-clock swing on identical bytes within one hour, with correctness byte-stable throughout — measured proof that cost decisions need controlled runs (the ladder, with P-9 asserted), and that per-clip RTF from unasserted sessions supports ratios at best.
- **F-S1-3 · The probe corpus works.** One 5-second tone clip discriminated the hallucination behaviour of a 1.5B model from its smaller siblings, deterministically, at near-zero cost.
- **F-S1-4 · Admission economics confirmed at 3.1 GB scale.** Large-v3's admission was one pinned data entry; cold start ~4.5 min download-dominated, load 7.4 s, warm-up 9.5 s — all runtime-reported.

## 4. Recommendation (Whisper family only)

1. **English production stays on `whisper-small` int8.** No challenger produced evidence to displace it.
2. **`whisper-base` is the standing cost opportunity (≈ 2.5×), gated entirely on the English C2 corpus.** No further engineering on it until then — the next unit of work on this question is data, not models.
3. **`whisper-large-v3` is set aside as a default-engine candidate** (cost ~5×, real-time parity on non-speech, deterministic hallucination). It remains the lineage's Hindi-ceiling probe for Stage 3, measured there with the hallucination finding on the table.
4. **`large-v3-turbo` stays excluded** until the third-party-conversion policy is ruled or we produce our own conversion.

## 5. Go / No-Go — Stage 2 (English decision)

**GO, and the decision is short:** English shows **no measured quality deficit** — the incumbent sits at this corpus's ceiling with ~9× production headroom and zero hallucinations. Under the evaluation hierarchy, benchmarking Moonshine now would answer no live product question: the only English opportunity on the table is *cost*, it is priced (≈ 2.5× via base, in-lineage, zero new stacks), and it is corpus-gated, not engine-gated. **Stage 2 resolves to: English stays on Whisper; Moonshine is not needed at current evidence** (re-triggered if English serving cost becomes a business problem). The program's live uncertainty is Hindi — **proceed to Stage 3: build the Hindi corpus and measure the wedge gap.**
