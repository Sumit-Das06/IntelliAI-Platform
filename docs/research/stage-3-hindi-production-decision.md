# Stage 3 — Hindi Production Decision

| | |
|---|---|
| **Status** | IN FORCE — execution specification (2026-08-06). Not a roadmap; the implementation plan. |
| **Rule of this stage** | If Whisper is sufficient, Stage 3 ends with **zero new engineering**. That outcome is a complete success, not a disappointment. |

## 1. Objective

Answer one business question:

> **Can `whisper-small` (the engine already in production) satisfy IntelliAI's Hindi production requirements?**

Nothing else. Not "which Hindi model is best" — that question only exists if the answer here is no, and then only for the specific weakness measured.

## 2. Success Criteria

Stage 3 concludes **A — Whisper is sufficient** when all of:
- `cer_unicode` (the Hindi primary metric) on the Hindi C2 corpus (≥100 natural-speech clips) is **at or under the Hindi quality bar** — a number the founder declares at corpus commissioning, *before* the first measurement exists (see Inputs);
- no disqualifier-class behaviour appears in the record: zero hallucinated words on the probe clips, no systematic corruption pattern (e.g. entities or numerals wrong as a class rather than as noise);
- production requirements hold under a `hi` declaration — they are already measured for this engine in English (p95 within PRD, ~800 MiB, zero-hallucination probes); the Hindi run confirms nothing changed that the declaration itself doesn't explain (the known 5.3× non-speech declaration cost is on record).

Stage 3 concludes **B — Whisper is insufficient** when the measured `cer_unicode` exceeds the bar, or a disqualifier-class pattern appears. Conclusion B must name the weakness from the error profile: **matra/diacritic class** (sub-word errors), **word class** (substitutions/deletions), **entity/numeral class**, **code-mixed class** (Hinglish slice), or **hallucination class**. The named weakness selects the remedy — no remedy is selected by preference.

No opinions anywhere in the gate: a number against a pre-declared bar, plus the presence/absence of named patterns.

## 3. Inputs

**Already available (verified, nothing to build):**
- Evaluation framework: metric registry (`cer_unicode` primary, `wer_unicode` co-primary, S/I/D rates, `hallucinated_words`), immutable evidence records, self-describing runtime, refusal of quality claims under 100 clips — all in CI.
- The Hindi ruler: `unicode_generic@v2`, registered and pinned; a reference that normalises to nothing raises instead of scoring (the silent-corruption path is closed).
- Runtime + incumbent: `whisper-small` int8 serving today; fresh-process benchmark procedure proven in Stage 1.
- Baseline discipline: Stage 1 English records as the procedural template; Hindi probe records (declaration cost) already committed.
- Two probe clips (silence, tone) under `hi` declaration, already in the released corpus.

**Still missing (in order):**
1. **Founder: corpus sourcing decision** — collect / purchase / adopt — plus consent & PII policy for recorded audio. Collect-and-never-publish is the only contamination-clean option; an adopted corpus carries its licence into every future Hindi promotion.
2. **Founder: the Hindi quality bar** — declared at commissioning, before any measurement, so sufficiency is never argued backward from a number.
3. **Engineering (~1 day, the only code):** `EvalClip` local-path audio source — self-recorded audio is currently unregisterable by schema.
4. **The corpus itself:** C1 first (10–20 clips — fast signal inside week one, supports no quality claim), then C2: ≥100 natural-speech clips, ≥10 speakers, double transcription with reconciliation, a written convention sheet, verbatim references (no normalisation at creation), matra/conjunct coverage, Devanagari and Arabic numerals as separate cases, entities, a Hinglish slice tagged code-mixed, ≥3 probe clips.

## 4. Execution Flow

```
Hindi corpus (C1 fast signal → C2 decision-grade)
        ↓
Evaluate whisper-small  (product path, explicit hi; record committed)
        ↓
┌─ Is Whisper sufficient? (§2 gate) ─────────── YES ─► STOP. Hindi stays on
│                                                      whisper-small. Stage
│  NO — weakness named from the error profile          closed. Zero new
↓                                                      engineering.
Can CONFIGURATION solve it?
   cheap sessions, same corpus, same engine: decode parameters
   (beam size, temperature, condition_on_previous_text), language-
   declaration mode (explicit vs auto — both directions measured),
   VAD gate settings. Each variant = one recorded session.
        ↓ solved? ── YES ─► STOP. Ship the configuration.
        ↓ NO
Can LoRA solve it?
   adapter on whisper-small, trained on the same corpus that measured
   the gap (train/eval split discipline: evaluation clips never train).
   Cheapest training rung; richest precedent in this lineage.
   Diagnostic rider: one in-stack hi reading of whisper-large-v3
   (~1 day) to learn whether the lineage ceiling clears the bar —
   informs whether LoRA-on-small can plausibly close the gap. It is
   a diagnostic, NOT a production candidate (Stage 1: real-time
   breach + deterministic hallucination stand against it).
        ↓ solved? ── YES ─► STOP. Adapter becomes the Hindi solution
        ↓ NO                (merge → convert → pin → switching test).
Can FINE-TUNING solve it?
   full fine-tune of the incumbent lineage on grown corpus data —
   only if adapters measurably plateau on a revenue-carrying gap.
        ↓ solved? ── YES ─► STOP.
        ↓ NO
Benchmark NEW ENGINES — last resort, smallest set (§5),
   only those matching the named weakness. Winner must beat the
   best tuned Whisper, meet production requirements on CPU, and
   justify a new serving stack.
```

No step may be skipped. Each "solved?" is the §2 gate re-run with the same bar.

## 5. Candidate Order (only if every earlier gate said NO)

Candidates exist only as answers to a *named* weakness. If the weakness profile doesn't match a candidate's claim, it is not benchmarked.

1. **Qwen3-ASR 0.6B** — exists because it is the smallest eligible engine claiming Hindi (Apache-2.0 verified, no gate, no remote code, CPU-plausible at 0.6B). Expected to solve: general Hindi accuracy if the Whisper *lineage* (not just the small checkpoint) proved unable to reach the bar. Evaluated first because it is the cheapest new-engine hypothesis: the lightest stack (transformers adapter), no access rulings needed. Known cost carried in: its timestamp story (a second model) conflicts with our one-artifact serving design.
2. **IndicConformer-600M** — exists because it is the dedicated Indic specialist (MIT, 22 languages, built for Devanagari). Expected to solve: matra/diacritic-class and Devanagari-specific weaknesses if a generalist can't. Evaluated second because it requires a founder ruling first (mandatory `trust_remote_code` → security review, unless its ONNX route avoids it — checked before any review is commissioned) and its exact-pinned ONNX dependencies need workspace isolation checks.
3. Nothing else. Voxtral (GPU-shaped, gated), IndicWhisper (licence-frozen), and all English-only engines cannot realistically change the Hindi decision and are excluded by name.

Any winner here still faces the standing switching rule: beat the best tuned Whisper on the same corpus and ruler, meet CPU production requirements, clean licence across its chain, margin worth the full switching cost — and it enters production as one routing entry (the platform already routes per language; no gateway change under any outcome).

## 6. Deliverables

1. **The Hindi corpus** (C1 + C2), released, versioned, immutable once cited — a permanent company asset regardless of the decision.
2. **The incumbent Hindi baseline record(s)** — committed, self-describing, replicate included.
3. **The error-profile reading** — the weakness named, or the sufficiency shown.
4. **The gate decision**, recorded (founder rules; the record is appended to the ledger).
5. *Only if triggered:* configuration-session records → adapter evaluation records → challenger records — each layer only if the previous gate failed — plus the **switching-test evidence** and **the Hindi production recommendation** (Best Hindi Production Solution).

## 7. Exit Conditions

Stage 3 is complete when **one** of these is true:
- **A:** the sufficiency gate passed — Whisper stays; the decision and its record are committed; no further Hindi work is scheduled. *(Complete success.)*
- **B-solved:** a gate failed, and the cheapest remedy that passed its own gate is adopted through the standing adoption checklist (licence re-verification, production benchmark, switching evidence, routing entry) — the Hindi production solution is serving.
- **B-open:** every rung including new engines failed to clear the bar — Stage 3 closes with the honest finding that the bar is not currently reachable, the founder re-rules (adjust the bar with reasons, or hold Hindi at "available"), and the evidence remains for the next attempt.

In every case: all records committed, the ledger appended, and no engineering built beyond what the reached rung required.

## 8. What is NOT part of Stage 3

Arabic (Stage 4 — its fold-table and verifier commissioning may run in parallel but decide nothing here) · streaming · GPU anything · gateway or architecture changes (routing exists; a Hindi specialist would be one registry entry) · custom model training (rung 7 stays gated) · English (closed; reopening requires new evidence) · timestamp quality (no metric exists) · robustness/C3 tiers · any benchmark of any engine not named in §5 · cross-language comparisons of any kind (illegal by construction) · Promising reviews for engines no gate has triggered.

---

*One page of engineering, two founder decisions, and a corpus. If Whisper clears the bar, IntelliAI's Hindi solution costs nothing at all — which is the outcome this stage is designed to make provable.*
