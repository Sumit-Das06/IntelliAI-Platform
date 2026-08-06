# STT Execution Roadmap — the shortest path to the production solution

| | |
|---|---|
| **Status** | IN FORCE (founder-directed simplification, 2026-08-06). **This document supersedes every earlier execution plan** — the campaign session matrix, the P0–P3 research priority list, and the phase inventories. The *instruments* those documents built (metric registry, rulers, evidence records, admission mechanism, [Success Criteria v2](STT_EVALUATION_SUCCESS_CRITERIA.md)) remain in force unchanged; only the execution plans are replaced. |
| **The objective** | Find the best Speech-to-Text solution for IntelliAI Platform — English, Hindi, Arabic — at minimum engineering complexity. |
| **The governing principle** | **No challenger is benchmarked until the incumbent demonstrates a measured weakness in that language.** If Whisper satisfies a language, that language's investigation ends. The objective is not to compare models; it is to ship the minimum-complexity production solution. |

## How to read this if you just joined

The platform serves STT behind one public model (`intelliai-stt`) on `whisper-small` (int8, CPU). The registry already routes per language, so a specialist engine for one language is a routing entry, not an architecture change. An evaluation harness exists that produces immutable, self-describing evidence records; quality claims below 100 corpus clips are refused by law. Everything below is a sequence of *questions*, each answered by the cheapest evidence that can answer it, each ending in a decision gate that either **stops** (Whisper stays — the good outcome) or triggers the smallest possible challenger round.

```
Stage 1 Whisper family ── COMPLETE ──► no Whisper replaces the incumbent
Stage 2 English        ── CLOSED ────► whisper-small stays; no challenger justified
Stage 3 Hindi          ── ACTIVE ────► corpus → measure Whisper → sufficient? STOP : smallest challenger round
Stage 4 Arabic         ── QUEUED ────► same pattern, deeper prerequisites
Stage 5 Architecture   ── FINAL ─────► one engine vs hybrid routing, from evidence only
```

---

## Stage 1 — Whisper Family · **COMPLETE**

**Question:** should another Whisper model replace the incumbent? **Answer: No.**
Evidence (7 committed records, [report](../../ml/evaluation/stt/benchmarks/2026-08-06-stage1-whisper-family.md)): `whisper-small` at the corpus quality ceiling with zero hallucinations and ~9× production headroom · `whisper-base` ≈ 2.5× cheaper but its quality risk is invisible on the current corpus (a cost opportunity dormant until an English C2 exists *and* cost becomes a business problem) · `whisper-large-v3` breaches real time on CPU in a realistic machine state and deterministically hallucinates on non-speech audio the VAD legitimately passes. **Do not reopen without new evidence.**

## Stage 2 — English · **CLOSED**

**Question:** does English require another engine? **Answer: No.**
No measured quality deficit exists; the only English opportunity is cost, priced in-lineage, corpus-gated, and currently unjustified. **Decision: `whisper-small` remains the English production engine.**
*Reopen triggers (recorded, not scheduled):* English serving cost becomes a business problem → measure `whisper-base` on an English C2; measured customer-visible quality complaints → reopen with that evidence.

## Stage 3 — Hindi Investigation · **ACTIVE**

| | |
|---|---|
| **Goal** | Determine whether `whisper-small` is *actually* insufficient for Hindi. Today's entire Hindi quality evidence is one observed error (लगता → लकता) — an anecdote. This stage replaces it with a measurement. |
| **Product question** | Can we honestly move Hindi from "available" to a promise, on the engine we already run? |
| **Success criteria** | A committed Hindi evidence record with WER/CER on ≥100 natural-speech clips (quality-claim law), plus an error profile (matra-class vs word-class vs entity vs code-mixed) — enough for the founder to rule *sufficient* or *insufficient* with named weaknesses. |
| **Inputs** | Founder decision: corpus sourcing (collect / purchase / adopt) + consent/PII policy. Engineering: the one missing schema piece — `EvalClip` local-path source (~1 day; blocks all self-recorded audio). The Hindi ruler is already live and guarded (`unicode_generic@v2` + `RulerFailureError`). |
| **Steps** | 1. Corpus decision (founder) → 2. local-path source lands → 3. **fast signal first:** a Hindi C1 (10–20 clips) inside week one — an early weakness profile, supports no quality claim, costs almost nothing → 4. full C2 (≥100 clips, double-transcribed, ≥10 speakers, Hinglish slice) → 5. measure `whisper-small` (product path, explicit `hi` declaration; the measured 5.3× declaration cost is part of the cost picture) → 6. error-profile analysis → 7. **decision gate**. |
| **Decision gate** | Founder reads the record. **Sufficient → STOP.** Hindi stays on Whisper; the stage closes; no challenger is ever benchmarked. **Insufficient → the smallest challenger round that targets the *named* weakness**, in complexity order: ① `whisper-large-v3` Hindi reading (in-stack, ~1 day, hallucination + cost findings carried) — the lineage's own ceiling; ② LoRA on the incumbent (the same corpus that measured the gap trains against it; cheapest training rung, richest precedent); ③ only if the lineage ceiling fails: Qwen3-ASR 0.6B (transformers adapter) and/or IndicConformer (ONNX adapter + remote-code ruling) — whichever the weakness profile says could realistically fix it. |
| **Estimated effort** | Corpus: 2–4 weeks, human-dominated (the critical path). Measurement: days. Challenger round *if triggered*: ~1 day in-lineage; 1–2 weeks if a new stack is justified. |
| **Deliverables** | The Hindi C2 (a permanent company asset), the incumbent Hindi baseline record, the error-profile reading, the gate decision — and if triggered, challenger records + **the Best Hindi Production Solution** recommendation. |

## Stage 4 — Arabic Investigation · **QUEUED**

| | |
|---|---|
| **Goal** | Same question, same discipline: is `whisper-small` actually insufficient for Arabic? Arabic is served "available" today and has never been measured in any form — the highest product risk in the portfolio, and also zero evidence of a weakness. |
| **Product question** | Can the language with our least evidence be served honestly on the engine we already run? |
| **Success criteria** | A committed Arabic evidence record (≥100 clips: MSA and dialect as separate slices, code-switch slice) + error profile + gate decision. |
| **Inputs** | Everything Hindi needs, plus three Arabic-only prerequisites no engineering can shorten: the `arabic_orthographic@v1` normalisation profile (an enumerated fold table needing native-speaker review — `profile_for("ar")` refuses until it exists, deliberately), a dialect-competent verifier (a person), and the corpus itself. |
| **Steps** | Fold-table commissioning + verifier recruitment (start these first — longest lead) → corpus → measure Whisper → error profile → decision gate. |
| **Decision gate** | **Sufficient → STOP.** **Insufficient →** the realistic challenger set is short: ① `whisper-large-v3` Arabic reading (in-stack, findings carried); ② **Cohere Transcribe Arabic** — the only purpose-built Arabic candidate (requires two founder rulings first: gated-fetch acceptance and remote-code security review); ③ LoRA/fine-tune on the incumbent with the new corpus. |
| **Estimated effort** | 4–8 weeks, dominated by fold table + verifier + corpus. Measurement: days. Challenger round if triggered: 1–2 weeks. |
| **Deliverables** | The Arabic ruler and corpus (permanent assets), the incumbent Arabic baseline, the gate decision — and if triggered, **the Best Arabic Production Solution** recommendation. |

## Stage 5 — Final Production Architecture · **FINAL**

| | |
|---|---|
| **Goal** | Answer, from collected evidence only: one multilingual engine, or hybrid routing? |
| **Inputs** | The three per-language gate decisions and any challenger evidence they triggered. Nothing else. |
| **Decision** | If all three stages closed on "Whisper sufficient" → **one engine**, routing table trivial, engineering complexity zero — the best possible outcome. Each language whose gate triggered and produced a winning challenger → one routing entry for that language. The gateway needs no change in either case. |
| **Success criteria** | Every routing entry backed by a committed record; the platform serves the best measured solution per language at the minimum complexity the evidence permits. |
| **Effort** | Days: registry entries + adoption checklist (licence re-verification, production benchmark, risk entry) per any adopted challenger. |
| **Deliverables** | The production architecture decision + updated routes + the adoption records. |

---

## Work permanently eliminated

Removed from all execution planning. Ledger entries and dossiers remain (knowledge compounds); the *work* is dead unless a reopen trigger fires.

| Eliminated | Why |
|---|---|
| **All English challenger benchmarks** — Moonshine, Granite, Parakeet, Canary-Qwen, Kyutai, Omnilingual | English is closed with no measured weakness. None of these addresses a Hindi or Arabic weakness either (none covers those languages). They answer no product question this platform has. |
| **Cohere Transcribe general (2B)** | Covers en+ar; English is closed and the Arabic specialist is the realistic Arabic challenger. No remaining question is *its* question. |
| **`large-v3-turbo`** | Third-party CT2 conversions only (policy unruled), and Stage 1 made the variant moot as a default engine. |
| **Qwen3-ASR 1.7B, Omnilingual large variants, Voxtral** | GPU-shaped or oversized for CPU-first serving; no triggered question. Voxtral's only unique claim (Hindi) is covered by cheaper Stage-3 challengers. |
| **The ~45-session campaign matrix as an execution plan** | Superseded by the five stages above. The methodology, record schema, and procedure documents stay in force as instruments. |
| **The 12-candidate Promising-review batch** | Reviews now happen only for engines an open gate actually triggers — at most a handful, ever, instead of twelve up front. |
| **Cross-language probe sessions, C3 robustness phase, streaming phase, GPU-tier investigation** | No product question on the path to the STT decision. Streaming waits for the platform contract; robustness enters with future corpus tiers; GPU reopens only if a triggered challenger requires it. |
| **Custom training (rung 7)** | Stays legally gated on evidence that does not exist (measured ceiling + data moat). Not on any roadmap horizon. |

**Dormant with named triggers (not eliminated):** `whisper-base` English cost swap (trigger: cost becomes a business problem + English C2 exists) · the four Gate-1-frozen lineages (trigger: their licence clarifications) · LoRA/fine-tuning (trigger: a gate rules "insufficient" and a corpus exists — then it is a first-line remedy, not research).

## The one thing that matters next

Every path through this roadmap now runs through the same bottleneck: **the Hindi corpus decision** (sourcing + consent — yours), followed by the Arabic fold-table/verifier commissioning (longest human lead time; can start in parallel). All remaining engineering ahead of those gates totals about one day. The instruments are built, the incumbent is proven where we can prove it, and the shortest path to "the best STT solution for IntelliAI Platform" is now made of data and two decisions — not models, not code.
