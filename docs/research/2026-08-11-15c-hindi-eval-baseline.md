# Milestone 15C — Production-Grade Hindi Evaluation: Close-Out Report

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — the official Hindi ruler and baseline exist; no training performed |
| **Date** | 2026-08-11 (all access checks, license reads, ingestion, freezes, and runs performed this date) |
| **Delivers** | gated-dataset access, the speaker-disjoint `stt-hi-public-eval@v1` (frozen, hash-pinned), and the OFFICIAL whisper-small Hindi baseline that 15D must beat |
| **Predecessor** | [2026-08-11-15b-ingestion-baseline-report.md](2026-08-11-15b-ingestion-baseline-report.md) (the FLEURS comparability ruler, retained unchanged) |

Labels: **[EVIDENCE]** committed EvalRun · **[FACT]** read at source,
dated · **[BLOCKED]** recorded refusal · **[VARIANCE]** documented
runtime nondeterminism.

---

## 1. Dataset access and provenance [FACT]

Founder unblocked the HF gates 2026-08-11 (account `Sumitdas06`,
read-scoped token, stored outside the repo; never committed, logged, or
reported). Access verified for all three targets; revisions pinned:

| Source | Revision (repo sha, retrieved 2026-08-11) | License | Role |
|---|---|---|---|
| ai4bharat/IndicVoices | `c96f9088f138cf89d419da7e8e643e1f05c00a87` | CC-BY-4.0 | **evaluation (primary)** — hindi/valid used; hindi/train (49 GB) NOT downloaded |
| ai4bharat/Kathbath | `5b9e92849222026d9141acba4e8434fe816396bf` | CC0 | training (15D) — ingestion deferred: ships M4A, a recorded adapter gap |
| ai4bharat/Lahaja | `d4ffd2ecbdd933e37c917ddcf620eef159ceb3a7` | MIT (card tag) | evaluation (secondary) — preset ready, freeze deferred |
| Common Voice 26.0 | — | CC0 + MDC terms | **[BLOCKED]** Mozilla Data Collective account still required |

## 2. Speaker metadata findings (Step 4) [FACT]

IndicVoices publishes per-row `speaker_id` (stable-format strings,
e.g. `S4259869900354210`): **5,530/5,530 rows carry one; 514 unique
speakers** in hindi/valid. Kathbath: `speaker_id` int64. Lahaja:
`sp_id` strings. No identity was inferred from filenames; no id was
invented. Whether IndicVoices' own valid/train splits are
speaker-disjoint at source is **unverified** (checking requires the
49 GB train metadata) — and deliberately irrelevant to our guarantee,
which is enforced by us (below).

## 3. The frozen primary — `stt-hi-public-eval@v1`

```
EVAL MANIFEST:        ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json
EVAL MANIFEST SHA256: cf6431466722c199f9430fc1d471cbf94301453317c2555fc8301679123e6ffc
NORMALIZATION:        unicode_generic@v2      RULER: cer_unicode primary (registry v3)
```

- **151 natural clips** (1,171.7 s) + 2 probes carried byte-identical
  from seed v2; every clip SHA-256-pinned, path-sourced, provenance in
  the clip notes (source/scenario/gender/district).
- **Speaker-disjoint BY CONSTRUCTION**: whole-speaker curation
  (ascending sha256(speaker_id), ≤8 clips each); the **32-speaker
  roster is frozen in the provenance sidecar** and is a mandatory
  rejection input (`speaker_in_eval`) for every future training freeze,
  alongside content-hash rejection (`eval_contamination`). The
  guarantee does not depend on the source's split hygiene.
- Reference = the source's `normalized` transcript (orthographic);
  `verbatim` respells phonetically (इस्थानीय for स्थानीय) and would
  penalize correct transcription — decision recorded in the manifest
  description, the adapter, and the sidecar.
- Composition [FACT, counted]: styles 72 Conversation / 69 Extempore /
  10 Read · gender 74 F / 77 M · durations 45 <5s / 90 5–15s / 16
  15–30s · transcripts 27 <10w / 72 10–25w / 52 ≥25w.
- Validation: 5,530 candidates → 3,836 accepted → 151 curated;
  **1,694 rejections, all `duration_too_short`** (<2 s conversational
  fragments), each recorded. Nothing silently skipped.
- FLAC bytes stored exactly as shipped (original-bytes law); probe
  durations verified against the source's own duration column
  (**max delta 0.0 s** over the checked sample).

## 4. Reproducibility (Step 15) — verified, with one documented variance

- Ingestion run twice → **byte-identical candidates files**
  (sha256 `4983cd89…` both runs). [FACT]
- Freeze run twice → **identical manifest SHA-256** (`cf643146…`),
  identical roster, identical counts. [FACT]
- Evaluation run twice (same process, manifest, ruler, artifact):
  **[VARIANCE]** 34/153 clips produced different hypothesis text
  between runs — whisper's temperature-fallback schedule
  (0.0→1.0) samples stochastically when quality thresholds trip, and
  spontaneous Hindi trips them often. Metric spread: CER 0.3629 →
  0.3772 (Δ 0.0143), WER 0.6590 → 0.6679 (Δ 0.0089). This is engine
  nondeterminism, not harness nondeterminism; the official number is
  the named-baseline run, the replicate bounds the variance, and any
  15D delta claim must exceed this band to mean anything. (Pinning
  temperature=0 is a rung-1 decode-config option — a distinct solution
  identity, deliberately not changed in 15C.)

## 5. OFFICIAL HINDI BASELINE [EVIDENCE]

Committed + named: `2026-08-11-intelliai-stt-hi-whisper-small-int8-public`
([record](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public.json) ·
[replicate](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public-replicate.json)).
Product path (`intelliai-stt`/`hi` from the exported registry manifest),
artifact `whisper-small@1` (SHA-pinned files), faster-whisper 1.2.1,
int8, CPU, fresh native runtime.

| Metric (151 natural clips, 3,258 ref words) | **Official** | Replicate |
|---|---|---|
| **cer_unicode (primary)** | **0.3629** | 0.3772 |
| wer_unicode | 0.6590 | 0.6679 |
| substitution / insertion / deletion | 0.4764 / 0.0328 / 0.1498 | 0.4736 / 0.0322 / 0.1621 |
| hallucinated_words (probes) | **0** | 0 |
| recognition_rtf | 0.7846 | 0.9142 |
| inference p50 / p95 | 2.73 s / 24.17 s | 2.94 s / 28.20 s |
| failures | 0 / 153 | 0 / 153 |

**This is the ruler 15D must move.** Every future Hindi candidate —
LoRA'd whisper, Qwen3 behind an adapter, IndicConformer — is measured
against CER 0.3629 on this exact manifest.

## 6. Why the official baseline differs from the FLEURS number (Step 12)

FLEURS baseline (retained, unchanged): CER 0.2919 / WER 0.5624 on
`stt-hi-fleurs-eval@v1`. The official numbers are **worse because the
corpus is harder and more real**: 93% spontaneous/conversational speech
from 32 field-recorded speakers versus read-aloud news-domain
sentences; real disfluency, code-mixing, and acoustic variety. RTF also
roughly doubled (0.35 → 0.78) — conversational audio triggers more
decode fallback. **The two numbers are different rulers and must never
be differenced**; FLEURS remains the cross-paper comparability ruler,
`stt-hi-public-eval@v1` is the product decision ruler.

## 7. Qwen3 note (Step 13, scope respected)

The 15B Qwen3 spike (CER 0.0796 on 30 FLEURS clips) remains a
RESEARCH SPIKE — not re-run on the new manifest in 15C (a fresh spike
on the primary would still not be product-path evidence; the honest
comparison requires the engine adapter). No production engine, registry,
or routing was touched.

## 8. What remains for 15D

1. Train-side data: IndicVoices hindi/train subset strategy (49 GB —
   selective shard ingestion), Kathbath M4A adapter, roster + hash
   rejection already enforced by `freeze-train`.
2. The E1 LoRA run (local RTX 5070) against **CER 0.3629**.
3. Optional counsel/accounts: MDC (Common Voice), SPRING-INX license.

*No training was performed. No production system changed. Public data
only. The token lives outside the repository and appears nowhere in it.*
