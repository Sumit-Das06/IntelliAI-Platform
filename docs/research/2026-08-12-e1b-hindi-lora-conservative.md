# Milestone E1b — Hindi Whisper-small LoRA, Conservative Recipe: Close-Out Report

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — both phases executed end-to-end; **every candidate FAILED the benchmark**; the failure is now characterized far more precisely than after 15D |
| **Date** | 2026-08-12 (checkpoint sweep, retrain, and all evaluations this date) |
| **Verdict, stated plainly** | **C. FAILED — the recipe still degrades the model.** The E1 damage was already fully present at checkpoint-500 (~3 epochs, CER 0.7295 vs baseline 0.3629), so "trained too long" is refuted as the primary cause. The conservative retrain (lr 1e-4, 600 steps, best-validation selection, textbook-healthy loss curves) still produced CER 0.7181/0.6535, **74** hallucinated probe words vs 0, and RTF 2.8–6.1. No candidate is eligible for promotion. |
| **What the milestone bought** | The cause space collapsed: not overtraining, not learning rate alone, not checkpoint choice. The damage concentrates in **generation/stopping behavior** (insertions, probes, fallback stalls) while substitutions actually IMPROVED past the baseline — the model is learning Hindi content while losing decode discipline. A precise, cheaply testable prime suspect is recorded (§11). |

Labels: **[EVIDENCE]** committed EvalRun · **[FACT]** verified/recorded ·
**[HYPOTHESIS]** proposed explanation, untested.

---

## 1. What was inspected and reused unchanged

The 15D close-out, the four E1 checkpoints on disk, `ml/training`,
the artifact-admission surface, and the eval harness. **Evaluation
methodology: zero changes** — same frozen `stt-hi-public-eval@v1`
(sha `cf643146…`), same ruler (`cer_unicode` / `unicode_generic@v2`),
same decode policy (verified identical in every run record's `/info`
snapshot: beam 5, temperature fallback 0.0→1.0, int8), same
research-harness route and port, same probes, same CPU RTF
measurement. The decision matrix was fixed and posted **before** any
number existed: SUCCESS required CER ≤ 0.3489 (baseline − noise band)
AND WER < 0.6590 AND probes = 0 AND serving-class RTF AND no English
regression; a candidate better than E1 but worse than baseline is
FAILED for promotion, retained as evidence.

## 2–4. Phase A — the checkpoint sweep [EVIDENCE]

The three earlier checkpoints of the SAME E1 run (adapters unchanged
on disk since 15D; sha256 ck500 `b2aa05a4…`, ck1000 `238ccd29…`,
ck1500 `61bda028…`) were merged and CT2-converted by the identical
pipeline (config/tokenizer/vocabulary pins came out byte-identical to
E1's — only `model.bin` differs), admitted as pinned research
artifacts, and evaluated on the frozen primary:

| Metric | Baseline (15C) | ck500 | ck1000 | ck1500 | ck2000 (=E1, 15D) |
|---|---|---|---|---|---|
| **cer_unicode** | **0.3629** | 0.7295 | 0.8132 | 0.7319 | 0.9049 |
| wer_unicode | 0.6590 | 0.9779 | 1.1068 | 0.9441 | 1.1581 |
| substitution_rate | 0.4764 | 0.3149 | 0.2851 | 0.2735 | 0.2716 |
| insertion_rate | 0.0328 | 0.6093 | 0.7618 | 0.6047 | 0.8287 |
| deletion_rate | 0.1498 | 0.0537 | 0.0599 | 0.0660 | 0.0577 |
| **hallucinated probe words** | **0** | 51 | 59 | 56 | 56 |
| recognition_rtf | 0.785 | 4.89 | 2.93 | 2.70 | 4.15 |
| failures | 0/153 | 0/153 | 0/153 | 0/153 | 0/153 |

**Finding [FACT]: the damage did not accumulate — it was established
by step 500 (~3 epochs at lr 1e-3) and stayed catastrophic at every
step.** No E1 checkpoint is remotely eligible; "evaluate an earlier
checkpoint" is closed as a remedy. (Non-monotonicity between 1000 and
1500 is within the instability documented in §8.)

## 5. Phase B — the conservative recipe [FACT]

Everything E1 had, except the optimizer schedule: same base
(`openai/whisper-small @ 973afd24`), same frozen train manifest
(`hi-public-train@v1`, sha `a4748dee…`, 4,822 train / 166 validation
after the hash-pure 3% split), same LoRA shape (r=32, α=64, dropout
0.05, q_proj+v_proj), same seed 20260811, same batch 8 × accum 4,
bf16, gradient checkpointing. Changed: **lr 1e-4** (10× lower),
**600 max steps** (~4 epochs), warmup 60, **checkpoint + validation
every 100 steps** — the trainer now runs the validation pass at every
checkpoint boundary and records the curve in the run record
(`validation_history`), which is what makes best-checkpoint selection
an evidence-based act. E1 computed validation once, post-hoc; that
gap is closed permanently.

## 6. Smoke test [FACT]

PASSED before the full run was funded: losses finite (2.14→2.02 over
5 steps), **peak VRAM 2,536 / 8,150 MiB**, 2.89 s/step, checkpoint
write+reload verified, RTX 5070 Laptop + torch 2.11.0+cu128 + bf16
confirmed. Full-run estimate ~35–40 min — matched (29.9 min + val).

## 7. Training run [FACT]

600/600 steps · **1,797 s (29.9 min)** · peak VRAM **3,353 MiB**
(never near the 8 GB limit; ₹0 rented) · final train loss **0.3502** ·
validation curve **0.6961 → 0.5566 → 0.4434 → 0.4236 → 0.4105 →
0.4064**, monotonically improving, still descending at 600 — **no
overfitting signal anywhere** (E1: train 0.0053 / val 0.4654).
Checkpoint-600 selected on lowest validation loss; its 0.4064 beats
E1's best-ever validation despite 3× fewer steps. Adapter sha256
`e73aa33c2125fd1c…`; run record `weights/e1b-hi-lora/run-record.json`
(git `385cf64`). Packaged identically to E1: merge → CT2 float32
(model.bin pin `806cfdb9…`) → research artifact
`whisper-small-hi-lora-e1b@v1`, non-distributed (.invalid URL),
served from the hash-verified local store.

## 8. Phase B evaluation on the frozen benchmark [EVIDENCE]

| Metric | Baseline (15C) | **E1b primary** | E1b replicate | E1 (15D) |
|---|---|---|---|---|
| **cer_unicode** | **0.3629** | **0.7181** | 0.6535 | 0.9049 |
| wer_unicode | 0.6590 | 1.0028 | 0.9220 | 1.1581 |
| substitution_rate | 0.4764 | **0.4236** | 0.4236 | 0.2716 |
| insertion_rate | 0.0328 | 0.5160 | 0.4150 | 0.8287 |
| deletion_rate | 0.1498 | 0.0632 | 0.0835 | 0.0577 |
| **hallucinated probe words** | **0** | **74** | **74** | 56 |
| recognition_rtf | 0.785 | 6.10 | 2.80 | 4.15 |
| inference p50 / p95 | 2.7 s / 24.2 s | 51.2 s / 79.0 s | — | 30.6 s / 77.9 s |
| failures | 0/153 | 0/153 | 0/153 | 0/153 |

**Noise-band discussion (mandatory):** the degradation vs baseline is
+0.355 / +0.291 CER — **~25× and ~21× the 0.014 band**. Not noise.
But note the **primary-vs-replicate spread of 0.0646 CER — itself
4.6× the baseline's band** (E1's spread was 0.0015). Degenerate
decoding is not merely slow and wrong; it is **unstable** — identical
inputs through an identical server produce materially different
transcripts run-to-run, because temperature-fallback sampling engages
constantly. A damaged model widens the apparatus's error bars.

## 9. English regression [EVIDENCE]

`stt-eval-seed@v2`: **WER 0.0000 / CER 0.0000**, RTF 0.483,
**1 hallucinated probe word** (E1: 1; incumbent: 0). English remains
intact; the damage stays concentrated where the adapter trained.

## 10. Did E1b beat the noise band? Eligibility?

**No.** Every gate of the pre-committed matrix fails independently:
CER worse than baseline far beyond the band (both runs), WER worse,
probes 74 ≠ 0 (the worst of any candidate measured in this program),
RTF 2.8–6.1 vs the serving class. **No candidate from Phase A or
Phase B is eligible for promotion. Verdict: C. FAILED.** Better than
E1 on CER/WER/insertions, worse on probes — research evidence only.

## 11. Scientific interpretation [HYPOTHESIS, with the facts that constrain it]

What is now REFUTED as the primary cause: over-training (damage
complete by step 500), learning rate alone (1e-4 with healthy curves
still fails), checkpoint choice (all seven evaluated artifacts fail),
and validation loss as a proxy for decode health (E1b's val 0.4064 —
the best measured — coexists with 74 probe hallucinations).

What the numbers point at: E1b's **substitution rate 0.4236 is BETTER
than the baseline's 0.4764** — the adapter is genuinely learning
Hindi acoustics/content — while insertions (0.52 vs 0.03) and probes
(74 vs 0) destroy the result. The failure lives in **generation and
stopping behavior**, not recognition.

Prime suspect for E1c, recorded for founder decision, cheaply
testable: **decode-mode mismatch.** Training labels are built from
the processor's `<|notimestamps|>` prompt regime (no timestamp
tokens in any target), while the product decode policy runs WITH
timestamps (`without_timestamps: false` in every run record). The
adapter therefore shifts q/v attention for a token regime the server
never uses; degraded timestamp/EOS calibration is exactly the
repetition-loop + fallback-cascade signature measured three times.
Tests, cheapest first: (a) one DIAGNOSTIC decode of the existing E1b
artifact with `without_timestamps=true` — clearly recorded as
research_harness evidence, never a benchmark claim, since it changes
decode policy; (b) retrain with timestamp-mode-consistent labels;
(c) shrink the adapter (r=8/16, q-only, or encoder-only) to bound
how much decoder attention may move. None of this ran — E1b stops
here by order.

## 12. Reproducibility [FACT]

Phase A artifacts rebuild from the E1 run record + step number; Phase
B from: base `973afd24` · manifest `a4748dee` (pin re-verified before
training) · config committed in `weights/e1b-hi-lora/run-record.json` ·
seed 20260811 · git `385cf64` · adapter `e73aa33c…` · CT2 pins in
`artifact-pins.json`. Six new EvalRuns in the append-only ledger; all
run against manifest sha `cf643146…` with per-record `/info` decode
snapshots. Mid-run interference documented: a Windows-Update reboot
(TrustedInstaller, 05:32 IST) killed the first E1b eval attempt
before any record was written; the run was restarted from clip 1 —
the ledger holds only complete records.

## 13. Resource use [FACT]

Local RTX 5070 Laptop only, ₹0 rented. Training 29.9 min at peak
3,353 MiB; three sweep merges + one candidate merge ~2 min each
(CPU); evaluations are CPU-side (int8) and dominated the wall clock
(~6.5 h total, inflated by the candidates' own degenerate RTF).

## 14. What remains blocked / unchanged

Common Voice (MDC account decision), TA/ML/ZH policy extension,
Arabic fold-table — all untouched. No production, API, Android, Web,
routing, or promotion surface changed. No customer data. The frozen
eval set, normalization, ruler, and decode policy are byte-identical
to 15C. Failed artifacts E1 and E1b are preserved, not deleted.

## 15. Tests / CI

Golden ledger extensions: results count 20 → 26; ascii reproduction
sum 24 → 26. Training package gains validation-history + CLI-mapping
tests. Full local suite green; ruff + strict mypy clean; CI green on
the milestone commits.

## 16. Recommendation for the next milestone

1. **Do not fund another blind LoRA arm.** Two recipes, seven
   artifacts, one conclusion: this adapter shape damages decoding on
   this stack regardless of schedule discipline.
2. **The Qwen3-ASR engine-adapter milestone is now the highest-value
   move** — its sandbox Hindi reading (CER 0.0796, same clip class)
   stands against two failed fine-tunes, and an adapter makes it
   measurable on the product path, the only route to a legal
   switching test.
3. If the fine-tuning thread continues, it continues as **E1c: the
   §11 diagnostic first** (hours, not days) — confirm or kill the
   decode-mode-mismatch hypothesis before any retrain is funded.

*A second recorded failure is not a setback of the program — it is
the program: the benchmark caught both bad models before any
promotion machinery could see them, and each failure removed a
hypothesis the next rupee would otherwise have been spent on.*
