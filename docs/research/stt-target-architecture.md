# IntelliAI STT Target Architecture — Phase 3

| | |
|---|---|
| **Status** | Phase 3 deliverable — the product architecture for STT over the next 2–3 years |
| **Governing law** | [STT Solution Evaluation — Success Criteria v2](STT_EVALUATION_SUCCESS_CRITERIA.md) |
| **Inputs** | [Solution Universe](stt-solution-universe.md) · [Filter & Priorities](stt-solution-filter.md) · committed baselines · runtime/registry source |
| **What this is not** | No model is benchmarked here and no winner is declared. The architecture defines the *slots*; evidence fills them. |

---

## 1. One model or routing? — the decision, and why it is already made

**Hybrid routing: one multilingual default engine, plus per-language specialist slots that are filled only by switching-test evidence.**

Three facts make this the only defensible answer, and none of them is a prediction:

1. **No eligible engine covers English, Hindi and Arabic together** (Gate-2 structural finding). The incumbent is the only full-coverage single engine in the universe. A pure single-engine architecture is therefore not a choice — it is the incumbent by default, forever, which is a bet the evidence does not support.
2. **A pure specialist architecture pre-decides the opposite bet.** The Hindi "wedge gap" is one observed error — an anecdote, not a measurement. Designing specialists in before the gap is measured would encode an assumption into the architecture.
3. **The platform already routes per language.** The registry's resolution manifest carries a route per (public model, language); different routes may target different deployments today, with zero gateway change. Hybrid routing is not new architecture — it is the architecture we shipped, used at its full width for the first time.

Hybrid routing makes **both** outcomes cheap: if the incumbent lineage wins everywhere, the routing table stays trivial and we carried no extra engines; if a specialist wins one language, one route changes and nothing else moves. The customer sees `intelliai-stt` either way — engines remain replaceable implementation details, which is the product's founding law.

## 2. Target architecture

```
                            ┌──────────────────────────────────────────────┐
   Customer                 │                IntelliAI Gateway              │
   POST /v1/audio/          │   auth · org & metering · rate limits        │
   transcriptions ─────────►│   public model: intelliai-stt                │
   (language declared       └──────────────────┬───────────────────────────┘
    or omitted)                                │
                                               ▼
                            ┌──────────────────────────────────────────────┐
                            │        Registry resolution (per language)     │
                            │                                               │
                            │  declared "en" ──► route: en                  │
                            │  declared "hi" ──► route: hi                  │
                            │  declared "ar" ──► route: ar                  │
                            │  undeclared    ──► default route              │
                            │                                               │
                            │  Every route → (artifact, deployment, status) │
                            │  status rungs: available / supported          │
                            └──────┬───────────────┬───────────────┬───────┘
                                   │               │               │
                                   ▼               ▼               ▼
                     ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
                     │  DEFAULT /     │ │  HI SPECIALIST │ │  AR SPECIALIST │
                     │  MULTILINGUAL  │ │  SLOT          │ │  SLOT          │
                     │  ENGINE        │ │                │ │                │
                     │                │ │  today: →      │ │  today: →      │
                     │  today:        │ │  default engine│ │  default engine│
                     │  whisper-small │ │                │ │                │
                     │  int8 · CT2    │ │  filled only by│ │  filled only by│
                     │                │ │  a switching-  │ │  a switching-  │
                     │  (EN slot =    │ │  test win      │ │  test win      │
                     │  default until │ │                │ │                │
                     │  evidence says │ │  candidates:   │ │  candidates:   │
                     │  otherwise)    │ │  §4            │ │  §4            │
                     └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
                             │                  │                  │
                             ▼                  ▼                  ▼
                     ┌──────────────────────────────────────────────────────┐
                     │  STT Runtime (one artifact per serving process)      │
                     │  ffmpeg → canonical 16 kHz mono → pipeline VAD →     │
                     │  engine adapter → transcript + segments              │
                     │  /info self-description · hash-pinned ArtifactStore  │
                     └──────────────────────────────────────────────────────┘

   EVIDENCE PLANE (isolated; production cannot see it)
   research runtime (own port, research manifest) · benchmark harness ·
   append-only records · derived reports → per-language switching tests
   — every routing change above is caused by a record produced here —

   FUTURE TRAINING PATH (the data flywheel, rungs 5–7)
   consented production usage ──► corpus versions (permanent assets)
        ──► adapter / fine-tune on the serving lineage (LoRA → FT)
        ──► merge → convert → pinned artifact → admitted as challenger
        ──► switching test ──► route update (same loop as any engine)
```

**Language detection:** declaration-first, deliberately. The routing key is the customer's declared language; undeclared requests take the default route (engine auto-detect — measured at ~1.9× the explicit-English cost). The gateway performs no acoustic language identification in this architecture: declaration is already the billing and routing contract, and a gateway LID stage would be new platform machinery solving a problem no evidence has yet shown we have. It remains a future option behind the same routing table if code-switching evidence ever demands it.

## 3. Per-language architecture and primary candidates

**English — "prove the incumbent, then attack it on cost."**
Serving today: incumbent, `supported`, WER 0.000 on the seed corpus, p95 PASS with ~9× headroom. There is no measured English quality problem. The architecture keeps EN on the default engine; the live English questions are *ceiling* (does `large-v3`/`turbo` buy quality worth its CPU cost?) and *floor* (does `whisper-base` or Moonshine serve at materially lower cost?). Primary candidates, in evidence order: **A5, A4, A2 (decode-tuned incumbent), then B1 Moonshine and B5 Granite** as post-Round-1 challengers.

**Hindi — "measure the gap before funding anything."**
Serving today: incumbent, `available`, one observed matra-class error — an anecdote. The first Hindi act is not an engine: it is the corpus that turns the anecdote into a measurement. If the measured gap is small, Hindi stays on the default engine and the specialist slot stays empty — a success. If it is real: **A5 (lineage ceiling), B6 Qwen3-ASR 0.6B (cheap generalist), B3 IndicConformer (specialist, pending its remote-code resolution)** compete for the slot, and **A8 (Hindi LoRA on the incumbent)** becomes the cheapest training rung the moment the corpus that measured the gap can also train against it.

**Arabic — "the slot exists; the instrument comes first."**
Serving today: incumbent, `available`, never measured in any form — the highest product risk in the portfolio. No engine decision is even *askable* until the Arabic ruler (enumerated fold table + native review) and corpus (with dialect verifier) exist. The incumbent's Arabic is the null hypothesis and gets the first baseline; **B4 Cohere Transcribe Arabic** is the only purpose-built specialist candidate (blocked on gated-fetch + security review) and activates when the corpus work starts. The architecture holds the AR slot open either way.

## 4. Shortest engineering path from today to the target

The distance is small because the platform was built multi-engine from the start. In order:

| Step | What | Engineering cost |
|---|---|---|
| 0 | **Nothing changes in production.** The target topology (default engine + three routes) is the current deployment read correctly | zero |
| 1 | Re-baseline the incumbent under the current methodology (the anchor for every later comparison) | ~1 day, exists |
| 2 | Round-1 lineage bracket (A4 · A5 · A2 · A3) on the existing stack | two pinned data entries |
| 3 | English C2 corpus → quality tier of everything above | the one multi-week clock (human work) |
| 4 | Hindi corpus → the wedge gap becomes a number | decision + collection |
| 5 | If Round 1 justifies it: first new stack (S2 → B1/B3, then S3 → B6/B5) | one adapter per stack, amortised |
| 6 | Per-language switching tests → fill (or leave empty) each specialist slot; adoption = a registry entry + route update | the mechanism exists |
| 7 | Arabic ruler + corpus + verifier → repeat steps 1→6 for AR | the long pole, mostly human |

No step requires touching the gateway, the public API, or the contract. The only genuinely new engineering anywhere on the path is stack adapters (step 5) — and only if the evidence sends us there.

## 5. The smallest experiment set that chooses the architecture

Seven experiment classes; each named for the decision it discriminates. Nothing else needs to run before the architecture is chosen.

| # | Experiment | Decides |
|---|---|---|
| X1 | Incumbent re-baseline (en, current methodology) | The left side of every comparison; closes the evidence-era boundary |
| X2 | Lineage bracket: A4 / A5 / A2-variants on en | **Does English need a challenger at all?** Ceiling and floor of the lineage at measured CPU cost |
| X3 | English C2 quality run of X1+X2 winners | Converts X2 from cost evidence into quality evidence; the EN slot decision |
| X4 | Hindi corpus + incumbent-hi baseline + A5-hi | **Is the Hindi wedge gap real, and how big?** Decides whether the HI slot is ever filled |
| X5 | (only if X4 shows a real gap) B6 vs B3 vs A5-hi on the same Hindi corpus; A8 LoRA joins when trainable | The HI slot |
| X6 | Arabic ruler + corpus + incumbent-ar baseline | **What does our Arabic actually look like?** The null hypothesis before any specialist |
| X7 | (only if X6 shows a real gap) B4 vs incumbent-ar | The AR slot |
| — | Cost-frontier rider: B1 / A4 en cost sessions | Only if English serving cost becomes a business problem; otherwise deferred |

Deferred safely, with triggers recorded in the Filter document: B2, B7, B8, B9, B10, B11–B13, the frozen four, D1/D2. None of them can change the *architecture* — only the occupant of a slot — so none blocks the architecture decision.

## 6. Where LoRA, fine-tuning, and custom training fit (the 2–3 year view)

- **Year 1 — adopt and route (rungs 1–4).** Configuration first, then the lineage bracket, then specialists only where a measured gap survives the cheap rungs. Corpora are built; the routing table fills with evidence. The data flywheel starts turning: consented production usage begins accumulating into corpus versions.
- **Years 1–2 — tune the lineage we serve (rungs 5–6).** Wherever a measured gap persists on a language, the cheapest training rung attacks it: LoRA on the serving lineage (A8 — richest adapter precedent in the universe), then domain fine-tunes if adapters plateau on a revenue-carrying gap. Every tuned artifact is a solution like any other: pinned, admitted, switching-tested, routed. Owning tuned weights is also the concentration hedge — each pass shifts dependency from the upstream's future to our lineage's future.
- **Years 2–3 — custom training (rung 7), only if the evidence forces it.** The gate is unchanged and deliberate: a quantified paying gap + a data moat foundation vendors don't have + a *measured* ceiling on our tuned incumbents. The toolkit path (D1, verified Apache-2.0) stays open at zero cost. If the gate is never met, that is the system working — not a failure of ambition.

**The end state either way:** one gateway, one public model, a routing table whose every entry is backed by a switching-test record, engines that are replaceable weekly if evidence demands it, and corpora + tuned weights as the accumulating assets. Models depreciate; the routing table and the data compound.

---

*Phase 3 defines slots and the evidence that fills them. It benchmarks nothing and names no winner.*
