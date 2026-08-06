# STT Solution Evaluation — Success Criteria v2

| | |
|---|---|
| **Status** | v2 — refactored from v1: the unit of evaluation is a **solution**, not a pretrained model |
| **Role** | The product requirements for deciding the best speech-to-text solution IntelliAI should serve, per language. Extracted from documents already in force; introduces no new metrics and no new governance. |

---

## 1. Goal

**Find the best speech-to-text solution for the IntelliAI Platform — per product language, with evidence.**

A **solution** is any deployable answer, not only a stock model:

- an existing pretrained model
- a quantized build of one
- a reconfigured deployment (decoding parameters, pipeline settings)
- a fine-tuned model or a LoRA/PEFT-adapted one
- a custom-trained model
- a multi-model routing architecture (different engines per language behind the one public model)

This is already how the platform records identity: a measured subject is *artifact + build/quantization + decode configuration + deployment*, and a fine-tune is a candidate like any other — its identity is base lineage + dataset version + recipe. Two builds of the same weights are two solutions; the same weights under different decoding parameters are two solutions. The evidence layer already keeps them distinct.

**The cheapest successful solution always beats a more expensive one.** "Best" means: measurably better than what we serve today, under identical measurement conditions, within our deployment economics and licensing rules, by a margin that justifies the cost of changing. External numbers are claims; only our own evaluation records are evidence. A different winner per language is a legitimate outcome — the architecture routes multiple engines behind one public model, and "one model for everything" is a hypothesis, never an assumption.

## 2. Product Requirements

| Requirement | Value | Source |
|---|---|---|
| **Languages** | English, Hindi, Arabic — first-class product languages; code-mixed speech (Hinglish, Arabic–English) measured as its own slice, never blended | Core Speech Language Policy v1 |
| **Deployment** | Self-hosted Docker container behind the platform gateway; one model artifact per serving process; artifacts pinned by hash, verified at startup; serves with no external dependencies after start | ARCHITECTURE; runtime source |
| **Offline/online** | Synchronous batch REST today (≤ 25 MiB upload, ≤ 600 s audio, canonical 16 kHz mono pipeline, VAD owned by the pipeline). No streaming requirement — the contract has no streaming method | runtime config/pipeline source |
| **Commercial licensing** | Permissive only (MIT / Apache-2.0 / BSD / CC-BY class) across the **entire serving chain** including transitive dependencies and any adapter/tuning recipe inputs; non-commercial or copyleft anywhere disqualifies regardless of quality; verdicts per artifact version, read at source, decaying | ADR-0005 |
| **CPU/GPU** | CPU-first: must run acceptably on consumer x86 CPU (int8-class) today. GPU-ready is architecture, not a serving assumption — no GPU tier exists | project constitution |
| **Latency** | Sync STT p95 < 1.5× audio duration for ≤ 60 s clips (incumbent measured: PASS, ~9× headroom); gateway overhead p95 < 15 ms; throughput ≥ real-time per worker core-set | PRD SLO table |
| **Memory** | Measured in a container; no absolute cap defined — the operating reference is the incumbent solution's ~800 MiB steady state, and economics must stay viable at our CPU serving class | committed baseline 2026-08-03 |

## 3. The Evaluation Hierarchy

A candidate solution passes these levels **in order**. Failing an early level ends the evaluation — no measurement effort is spent past a disqualifier (the cheapest-kill-first law).

**Level 1 — Eligibility (pass/fail, before anything else).** Commercial licence across the whole serving chain; provenance verified at source (canonical distribution pinned — not a re-upload); security acceptable (in-process vendor code requires review, not just a licence check); every transitive dependency acceptable. *Fail ⇒ stop. Do not benchmark.*

**Level 2 — Product fit.** Does the solution serve what the product promises? Language coverage against §2 (a solution may target one language — routing makes that valid); code-switching where the language demands it; self-hosted, REST-served, offline-serving after start.

**Level 3 — Technical compatibility.** Can we deploy and operate it? Fits the container/runtime/gateway architecture and the canonical audio pipeline; runs on our CPU class today; artifacts pinnable and hash-verifiable; a solution requiring a new serving stack or a contract change is recorded as requiring one — that is a cost carried into Level 7, not a footnote.

**Level 4 — Quality.** The existing accuracy metrics, per language, on the same corpus and ruler (§4).

**Level 5 — Performance.** The existing cost metrics, containerised, on our hardware (§4).

**Level 6 — Operational readiness.** Deployment complexity (measured: an in-stack checkpoint costs ~1 hour to admit; a new stack costs an adapter and its isolation work); runtime stability under the concurrency ladder; reproducibility of its numbers from recorded metadata; scaling behaviour (startup cost, per-worker throughput); maintenance burden (upstream health, ecosystem, our ability to tune it — a solution we cannot adapt is a rented engine).

**Level 7 — Business decision.** Is switching worth it? (§5.) Lowest WER alone never wins.

## 4. Evaluation Metrics

Existing metrics only. The ruler is part of each metric's identity; cross-ruler and cross-language averaging is impossible by construction. Both WER and CER are recorded on every run; which is *cited* is fixed per language, never per candidate.

**Quality (Level 4):**

| Metric | Purpose | Why it matters |
|---|---|---|
| `wer_unicode` | Word error rate, Unicode ruler | **English primary** — headline quality where word boundaries are stable |
| `cer_unicode` | Character error rate, Unicode ruler | **Hindi and Arabic primary** — matra/diacritic errors are sub-word, invisible to word-level scoring |
| `substitution_rate` / `insertion_rate` / `deletion_rate` | Error decomposition | *How* a solution fails (drops vs invents vs mishears); additive with WER |
| `excess_word_ratio` | Words beyond reference length | Over-generation symptom — the LLM-decoder failure mode |
| `hallucinated_words` | Words emitted on declared-empty reference | **The safety metric** — invented text on silence bills customers for fiction; uncontainable hallucination disqualifies |
| `wer_ascii` | Legacy ASCII ruler | Continuity with the pre-Unicode English baseline only; never a decision ruler |

**Performance (Level 5):** `recognition_rtf` (duration-weighted unit cost of transcription) · `peak_memory_mib` and `cpu_percent_max` (containerised worker cost) · end-to-end latency percentiles from the concurrency ladder (≥ 20 samples per cited p95; saturation and refusals counted) · startup timings (load, warm-up — reported by the runtime itself) · gateway overhead (the < 15 ms platform promise).

A quality result and a production result together form the evidence for one solution in one language; neither alone supports a serving decision.

## 5. Decision Rule

> **Replace the production STT solution for a language when a challenger solution — measured on the same corpus, same ruler, and same hardware — beats what we actually serve on that language's primary accuracy metric, without unacceptable regression on the others, while meeting the same latency, memory, and startup requirements on our CPU hardware, under a clean commercial licence across its whole chain — and the improvement is worth more than the full cost of switching.**

Corollaries already in force:

- The incumbent side of every comparison is **the solution we actually serve** — current weights, current build, current configuration, plus any tuning we have applied. A challenger beats *that*, not a stock download.
- **Per language.** A solution may win Hindi and not English; routing then serves each language with its winner. No cross-language average exists to say otherwise.
- **"Cannot tell" is not "worse."** A blocked comparison produces no decision; the remedy is another measurement.
- **A tie or small win is a loss for the challenger** — switching has real cost and the incumbent has operational history.
- **Forced exceptions** regardless of margin: a disqualifying licence change on the incumbent, upstream abandonment, or a hard architectural ceiling on a product requirement.
- **Disqualifiers end the evaluation at any level:** non-commercial licensing anywhere in the chain, uncontainable hallucination, broken deployment economics with no plausible optimisation path.

## 6. Improvement Strategy — the order of investigation

When a gap is found (a language underserved, a quality complaint, a cost problem), solutions are investigated **cheapest first**, and each rung is funded only after the previous rung is *measured* insufficient — never assumed insufficient. This ladder is existing project law (the adopt-vs-improve decision tree), restated for solutions:

| Rung | Investigate | Cost character | Notes |
|---|---|---|---|
| 1 | **Current production solution, reconfigured** — decoding parameters, pipeline gates (VAD), chunking, runtime settings | Zero training; configuration is recorded evidence, so each variant is a comparable solution | Always first |
| 2 | **Quantization / build changes** — a different precision or build of the same weights | Hours; same lineage, same operational knowledge | A build change is a new solution identity, measured like any other |
| 3 | **Vocabulary and lexicon** — pronunciation and domain terms | Platform-level work (the Pronunciation Manager is platform law, never an engine fix), plus STT biasing where supported | Fixes term-level errors no decoder setting reaches |
| 4 | **Alternative pretrained model** — a researched candidate through Levels 1–7 | Admission measured at ~1 hour in-stack; a new serving stack costs real engineering | The dossiers exist; use them |
| 5 | **LoRA / PEFT adapters on the incumbent lineage** | First rung that trains; cheapest training rung | Adapter identity = base + dataset version + recipe; evaluated as a solution like any other |
| 6 | **Domain fine-tune** | When adapters plateau and the gap carries revenue | Same evaluation path |
| 7 | **Training a new model** | Only with a quantified paying gap, a data moat, and a *measured* ceiling on tuned incumbents | Never before the evaluation evidence can prove the ceiling exists |
| — | **Multi-model routing** | An architecture outcome available at every rung, not a rung itself | The gateway already routes per language behind one public model; "English → A, Hindi → B, Arabic → C" is a deployment decision the moment per-language winners exist |

Skipping rungs is how money is wasted twice: once on the expensive solution, once on the cheap one that would have worked. The ladder is descended only by evidence.

## 7. Explicitly Out of Scope

Campaign phasing and scheduling · approval workflow and status lifecycle · corpus acquisition strategy (a precondition of measuring, not a criterion of winning) · GPU strategy ("does not run on our CPU" is a recordable result, not a criterion) · streaming (no contract method; streaming claims carry no weight) · timestamp quality (presence recorded, no quality metric) · pricing the switching cost in the evidence itself (evidence names the costs; weighing them is the deciding human's act) · TTS, translation, diarisation · vendor reputation, recency, parameter count, leaderboard positions — none is evidence.

---

*This document extracts; it does not invent. The hierarchy is the existing gate ordering; the ladder is the existing improvement decision tree; every metric exists in the registry today.*
