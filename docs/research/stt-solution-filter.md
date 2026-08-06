# STT Solution Filter & Research Priorities — Phase 2

| | |
|---|---|
| **Status** | Phase 2 deliverable. Levels 1–3 only. **Nothing benchmarked; no winner named.** |
| **Governing law** | [STT Solution Evaluation — Success Criteria v2](STT_EVALUATION_SUCCESS_CRITERIA.md) |
| **Inputs** | [Solution Universe v1](stt-solution-universe.md) · licence screen (2026-08-05, at source) · dossiers · route table · measured admission cost · runtime source |
| **Status vocabulary** | **PASS** — eligible and benchmarkable with zero-to-trivial build (the in-stack mechanism exists) · **NEEDS ENGINEERING** — eligible; a named build precedes measurement · **BLOCKED** — an eligibility question (licence chain, security, access) is unresolved; no effort until it clears · **NOT APPLICABLE** — legally inapplicable today under the improvement ladder |

**Two facts gate everything and are stated once, not per row:** quality measurement per language requires a corpus that supports the claim — today English is C1-scale only, Hindi and Arabic have no referenced audio, so *every* solution's quality tier waits on corpus work regardless of its own status. And the incumbent must be re-baselined under the current methodology before any comparison cites history.

---

## Part A — Incumbent lineage (CTranslate2)

| ID | Solution | L1 | L2 | L3 | **Overall** | Evidence / open questions |
|---|---|---|---|---|---|---|
| A1 | `whisper-small` int8 (incumbent) | PASS — MIT verified incl. transitive chain (faster-whisper MIT, CT2 MIT); pinned; no remote code | PASS — serves all three languages today; the only full-coverage single engine | PASS — it is the architecture | **PASS** | Baseline side of every comparison. Open: hi/ar quality unmeasured |
| A2 | Decode-tuned incumbent | PASS (inherits A1) | PASS | PASS — configuration is recorded evidence (`decode_params`); no code change | **PASS** | Which knob set to vary is a session-design choice; declaration cost already measured 5.3× per-clip |
| A3 | Alternative quantization builds | PASS (same weights) | PASS | PASS — `compute_type` is a runtime constructor parameter, self-described in `/info` | **PASS** | Each build is a distinct solution identity |
| A4 | `whisper-base` (admitted challenger) | PASS — MIT hosting-read 2026-08-06; full re-verification owed before adoption-cited use | PASS — en focus; weaker multilingual claims | PASS — admitted, hosted, described, resolvable (proven live) | **PASS** | No research-status ledger row yet (one intake entry) |
| A5 | `whisper-large-v3` / `-turbo` | PASS — lineage MIT verified at source; per-checkpoint re-read owed at pin time | PASS — claims all three languages | PASS — same stack; admission = one pinned data entry (mechanism measured ~1 h). CPU cost at ~1.5B params is the *hypothesis its session tests*, not an L3 failure | **PASS** | H-WHISPER: quality ceiling vs CPU cost — a cost decision, not a quality one |
| A6 | distil-whisper | **Unverified** — MIT claimed, never read at source | (en-centric — valid) | (CT2-convertible — claim) | **BLOCKED** | Cheapest unblock in the universe: one licence read at source |
| A7 | Vocabulary/biasing on incumbent | PASS — no new dependencies | PASS | **Fails today** — `TranscriptionRequest` carries only `language` and `model` [FACT]: biasing is unsettable through the product path; needs a contract extension or a research-route decode override, plus verification the engine exposes biasing knobs | **NEEDS ENGINEERING** | Knob surface unverified; smallest of the engineering items |
| A8 | LoRA adapter, ours (e.g. Hindi) | PASS in principle — our artifact over an MIT base; training-data licence is ours | PASS — target-language | Needs a merge-and-convert path to CT2 + a training pipeline | **NEEDS ENGINEERING** — and **corpus-blocked**: no training data exists in any product language | Activation trigger: a measured gap + a training corpus |
| A9 | Fine-tune, ours | as A8 | as A8 | as A8, heavier | **NEEDS ENGINEERING** (corpus-blocked) | Behind A8 on the ladder by law |

## Part B — Alternative engines

| ID | Engine | L1 | L2 | L3 | **Overall** | Evidence / open questions |
|---|---|---|---|---|---|---|
| B1 | Moonshine (S2/ONNX) | PASS — MIT (F), no gate, no remote code; **condition: pin the canonical namespace** (org migration observed) | PASS — en-only is valid under routing; REST/offline fine | S2 adapter does not exist; multi-file ONNX pinning needed; artifacts otherwise pinnable. **Cheapest new stack in the universe**: first-party int8 ONNX is the shipped default | **NEEDS ENGINEERING** (light) | Lowest integration risk of any candidate (dossier) |
| B2 | Cohere Transcribe general (S2) | Licence Apache-2.0 (F) — but **gated fetch** (unauthenticated store cannot download it) and **remote code on first-party paths** (security review required) | PASS — en+ar, **no hi**; 2 of 3 languages | S2 adapter (shared with B1); INT8 ONNX export exists but is a **community artifact** — third-party-conversion ruling applies | **BLOCKED** (fetch policy + security review + conversion ruling) | Open question worth a spike when unblocked: does the ONNX route avoid remote code entirely? |
| B3 | IndicConformer-600M (S2) | Licence MIT (F) — but **remote code required** (F): security review before any in-process execution | PASS — the Hindi specialist; hi is product priority #2 | S2 adapter (shared); ONNX path strongly implied by exact-pinned deps; exact `==` pins may conflict in workspace | **BLOCKED** (security review) — light unblock if the ONNX route avoids the remote code, else needs the review process | Devanagari tokenizer vs our ruler: session records it |
| B4 | Cohere Transcribe Arabic (S2/S6) | Licence Apache-2.0 (F) — but **gated + remote code** (both F) | PASS — the only purpose-built Arabic candidate; ar+code-switch; no hi | S2/vLLM; quantization claim is sibling-only (C) | **BLOCKED** (fetch + security) | Priority rises the day Arabic corpus work starts; unmeasurable before it regardless |
| B5 | Granite Speech 4.1 2B (S3) | PASS — Apache-2.0 (F), no gate, **no remote code**; PEFT dependency is permissive | PASS — en-only is valid | S3 adapter does not exist; **PEFT in the inference path** is a new dependency class needing isolation work; 2B on CPU unproven (its own hypothesis) | **NEEDS ENGINEERING** (moderate) | Cleanest commercial posture of the 2026 entrants |
| B6 | Qwen3-ASR 0.6B (S3) | PASS — Apache-2.0 (F), no gate, no remote code | PASS — **hi claimed** (priority #2); ar unconfirmed. Caveat recorded: timestamps need a second model covering 11 languages — contract requires timestamps; whether hi is among the 11 is open | S3 adapter (shared with B5); 0.6B is CPU-plausible (I); two-artifact timestamps vs one-slot design is a recorded cost | **NEEDS ENGINEERING** (moderate) | The cheapest Hindi-generalist hypothesis |
| B7 | Qwen3-ASR 1.7B (S3) | PASS — as B6 | PASS — as B6 | as B6, ~3× size | **NEEDS ENGINEERING** (moderate) | Conditional on what B6's evidence shows |
| B8 | Voxtral Mini 3B (S6/S3) | Licence Apache-2.0 (F) — but **gated fetch** | PASS — hi claimed (F); no ar | No CPU path indicated (dossier: "nothing indicates a CPU-viable path exists today"); ~20× incumbent params; `mistral-common` preprocessing | **BLOCKED** (fetch policy) — and on unblock, its session is a CPU-viability determination, not a quality run | The candidate that forces the GPU question |
| B9 | Parakeet TDT 0.6B v3 (S4) | PASS — CC-BY-4.0 (F); attribution is a pre-adoption condition, not a measurement blocker | PASS — en (25 European); **native timestamps, unique in the set** | NeMo is a heavy new stack; the alternative (third-party ONNX) trips the conversion ruling | **NEEDS ENGINEERING** (heavy) | Its unique advantage (timestamp quality) has **no registered metric** — unmeasurable today, which lowers near-term research value through no fault of its own |
| B10 | Canary-Qwen 2.5B (S4) | PASS — CC-BY-4.0 (F) | PASS — en-only | NeMo heavy stack **and** the weakest CPU fit of the PASS set (GPU-bound at practical latencies) | **NEEDS ENGINEERING** (heavy) | En-only where we are already strong, at the highest deployment distance |
| B11 | Omnilingual CTC 300M (S5) | Apache-2.0 (F on the checked card); **per-variant verdict owed** for the CTC artifact specifically | Long-tail coverage; en not the design goal (F); hi/ar plausible but unconfirmed | fairseq2 — a research framework inside the engine boundary; heaviest isolation work per lineage | **NEEDS ENGINEERING** (heavy) + one licence read | Strategic long-tail asset more than a near-term product answer |
| B12 | Omnilingual larger variants | per-variant verdicts owed | as B11 | as B11, larger | **NEEDS ENGINEERING** (heavy) | — |
| B13 | Kyutai STT (S7) | PASS — CC-BY-4.0 (F) | en/fr only; its defining property (streaming) has no contract method — unmeasurable | moshi/Rust WebSocket serving mismatches the request/response runtime; negative CPU signal (C) | **NEEDS ENGINEERING** (heavy) | An architecture to learn from, per its own dossier — not a near-term serving candidate |
| B14–B17 | IndicWhisper · Zipformer checkpoints · MOSS · ARK | **Licence chain unresolved** (the Gate-1 freeze) | — | — | **BLOCKED** (frozen) | Named unblock conditions recorded in the ledger; no effort until they clear |

## Part D — Custom training

| ID | Solution | **Overall** | Evidence |
|---|---|---|---|
| D1 | IntelliAI-native on the Zipformer/k2 toolkit (toolkit Apache-2.0, F) | **NOT APPLICABLE** | Rung 7 is legally gated on a quantified paying gap + data moat + a *measured* ceiling on tuned incumbents. None exists. The toolkit path stays open and costs nothing to keep open |
| D2 | Any other from-scratch training | **NOT APPLICABLE** | Same gate, no stack identified |

## Parts C & E — axes and patterns (filtered per composition)

IMP-1 (decode) and IMP-2 (quantization): **PASS** on the incumbent today. IMP-3 (vocabulary/biasing): **NEEDS ENGINEERING** (= A7). IMP-4/5 (LoRA/fine-tune): **BLOCKED on data** for every lineage — no training corpus exists in any product language. IMP-6: **NOT APPLICABLE** (rung-7 law). E1/E2/E3 (single engine, per-language routing, hybrid): **PASS** — supported by the platform today with no gateway change. E4 (content-based routing): **NEEDS ENGINEERING** (new gateway capability + registry concept).

---

## Research Priority

Execution priority, not quality. Criteria: product-language coverage · deployment fit · engineering effort · likelihood of improving on the served solution · return on engineering investment.

**P0 — benchmark immediately** *(zero-to-trivial build; the whole whisper-lineage bracket)*
- **A1** — the mandatory re-baseline; the left side of every future comparison
- **A2** — rung 1 by law: cheapest improvement first; directly tests whether configuration moves quality/cost before any adoption question is asked
- **A5** — the lineage's quality ceiling (the standing "should Large replace Small" roadmap question, for en and — when a corpus exists — hi)
- **A4** — the cost frontier downward; already admitted and hosted
- **A3** — build variants, riding along the same sessions
*Rationale: P0 brackets the incumbent lineage from ~39 MB to ~1.5B params on the stack we already operate. Total engineering: two pinned data entries. Maximum learning per unit effort in the entire universe.*

**P1 — after P0** *(first new stacks, cheapest first, shared adapters amortised)*
- **B1** Moonshine — the cheapest new stack (S2), first-party int8; also stands up S2 for B3/B2
- **B6** Qwen3-ASR 0.6B — the cheapest Hindi-generalist hypothesis; stands up S3 for B5/B7
- **B3** IndicConformer — the Hindi specialist; enters the moment its remote-code question resolves (ONNX-avoids-it spike first)
- **B5** Granite — rides the S3 adapter B6 builds; the en quality reference among 2026 entrants

**P2 — keep under observation** *(named activation triggers)*
- **B4** Cohere Arabic — activates with (fetch policy + security review) **and** the start of Arabic corpus work
- **B2** Cohere general — activates with the same unblocks; covers en+ar
- **B7** Qwen3-ASR 1.7B — activates on B6 evidence
- **B8** Voxtral — activates on fetch policy; session shape is a CPU-viability determination
- **B9** Parakeet — activates if/when timestamp quality gains a registered metric, or the S4 stack is funded for other reasons
- **B11** Omnilingual CTC 300M — strategic long-tail; activates if product languages beyond en/hi/ar approach
- **A6** distil-whisper — activates on a single at-source licence read (minutes)
- **A7** biasing — activates on the contract/research-route surface decision
- **A8/A9** LoRA/fine-tune — activate on (training corpus exists) + (a measured gap the ladder assigns to rung 5+)

**P3 — archive until a major change**
- **B10** Canary-Qwen (GPU-bound + heavy stack + en-only where we are already strong)
- **B12** Omnilingual large variants · **B13** Kyutai (unmeasurable defining property + serving mismatch)
- **B14–B17** (frozen; ledger carries the unblock conditions)
- **D1/D2** (rung-7 law) · **E4** (no platform capability)

## Benchmark Roadmap

**Round 1 — the whisper-lineage bracket (P0).** Zero new stacks; two new pinned entries (A5 checkpoints; A4 already admitted). Sessions per solution on the existing corpus (cost, probes, determinism — honest C1 scale), quality tier the day the English C2 lands. Decode variants (A2) and builds (A3) run as configured sessions of the same artifacts. **What Round 1 teaches:** where the incumbent lineage's quality ceiling and cost floor sit — which is exactly the evidence the improvement ladder needs before any rung-4+ spending is justified.

**Round 2 — first new stacks (P1), only as justified by Round 1.** Trigger examples, stated in advance: if A5 closes a quality gap at unacceptable CPU cost, the cheap-specialist hypotheses (B1, B6, B3) gain value; if the lineage brackets *without* closing product gaps, the alternative-engine hypotheses are the next-cheapest rung by law. Order within Round 2: S2 first (B1 → B3), S3 second (B6 → B5) — adapter amortisation, not preference.

**To LoRA/fine-tuning if benchmarking reveals promise:** the incumbent lineage first (A8 Hindi adapter is the canonical case — cheapest training rung on the lineage with the richest adapter precedent), and only with a training corpus and a measured gap. Any Round-2 winner's own tuning path is a later question the ladder answers the same way.

**Dropped before any benchmark effort** (P3 above): B10, B12, B13 on deployment-economics/measurability grounds; B14–B17 stay frozen at the licence gate; D1/D2 remain legally inapplicable. Each carries a named re-entry condition — dropped is a status with a trigger, not an ending.

---

*Phase 2 contains no measurements, no scores, no rankings by quality, and no winner. Every status above cites the licence screen, a dossier fact, the runtime source, or a measured cost.*
