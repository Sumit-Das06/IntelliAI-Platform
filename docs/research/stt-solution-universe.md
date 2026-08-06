# STT Solution Universe v1 — Master Catalog

| | |
|---|---|
| **Status** | Phase 1 deliverable — catalog only. Nothing here is filtered, scored, ranked, benchmarked, or recommended. |
| **Governing law** | [STT Solution Evaluation — Success Criteria v2](STT_EVALUATION_SUCCESS_CRITERIA.md) |
| **Structure** | A solution = **engine** × **improvement axes** × **architecture pattern**. This catalog lists the generators of that product space; Phase 2 filters generators, because an engine that fails Level 1 removes every solution composed from it. |
| **Sources** | Model ledger and Gate-1 licence screen (2026-08-05, at source) · the 16 candidate dossiers · serving-route table (execution matrix §2) · challenger-admission cost report (2026-08-06) · committed baselines · runtime source |

Facts below carry their dossier evidence level where it matters: **F** = verified at source · **C** = claim · **I** = inference. Licence states are the 2026-08-05 at-source readings and **decay**.

---

## Part A — Incumbent lineage (Whisper family; CTranslate2 stack, already operated)

The zero-new-stack part of the universe. Marginal cost of any checkpoint here is one pinned data entry (~1 hour, measured).

| ID | Solution | Languages (en/hi/ar) | State today | Notes |
|---|---|---|---|---|
| **A1** | `whisper-small` int8 CT2 — **the production incumbent** | en strong (F, measured) · hi usable (1 anecdote) · ar claimed, unmeasured | Serving | The baseline every challenger must beat, in its served configuration |
| **A2** | A1 with **tuned decode configuration** (beam size, temperature ladder, `condition_on_previous_text`, VAD gate, language-declaration policy) | same | Rung-1 solution, zero training | 13 decode knobs exist and are recorded evidence; the declaration alone is a measured 5.3× per-clip cost lever — configuration is not a rounding error on this lineage |
| **A3** | A1 under a **different quantization/build** (e.g. fp32, int8_float16 CT2 builds) | same | Rung-2 solution | A build change is a new solution identity |
| **A4** | `whisper-base` int8 — **admitted research challenger**, hosted and resolvable | en (F) · hi/ar weaker (C) | Admitted 2026-08-06, hosting-only licence read | Smaller/faster hypothesis; zero adapter work |
| **A5** | `whisper-large-v3` / `large-v3-turbo` int8 | claims 99 langs (C) | Researching; MIT (F) | The lineage's quality-ceiling hypothesis (H-WHISPER): Hindi gain at CPU cost — a cost decision, not a quality one |
| **A6** | `distil-whisper` distillations | en-centric (C) | Named in the whisper dossier as derivative lineage; licence unverified at source | Speed hypothesis inside the lineage; Level 1 work outstanding |
| **A7** | **Vocabulary/biasing on the incumbent** (initial-prompt / hotword-class biasing where the engine supports it; Pronunciation-Manager-adjacent platform work) | per deployment | Rung-3 solution | Engine support for biasing knobs is an **open question** to verify, not assume |
| **A8** | **LoRA/PEFT adapter on the incumbent lineage** (ours; e.g. Hindi adapter) | target-language | Rung-5 solution; requires a training corpus that does not exist | The frozen external proof-of-concept (IndicWhisper) shows the rung works on this lineage; our own adapter is a distinct solution not touched by their checkpoint-licence problem |
| **A9** | **Domain fine-tune of the incumbent lineage** (ours) | target-language | Rung-6 solution; same corpus dependency | Identity = base + dataset version + recipe |

## Part B — Alternative pretrained engines

Grouped by serving stack because stack stand-up is the dominant cost (route table, matrix §2; **bold** = selected route).

**Stack S2 — ONNX Runtime** (best amortisation of any new stack):

| ID | Engine | en/hi/ar | Licence (2026-08-05) | CPU path | Key facts |
|---|---|---|---|---|---|
| **B1** | Moonshine tiny/base (~27M+) | en only | MIT (F), no gate, no remote code | **Shipped int8 ONNX — the only first-party quantized CPU artifact in the set** (F) | Lowest integration risk in the universe (dossier); namespace must be pinned; variable-length audio (no 30 s padding) |
| **B2** | Cohere Transcribe 03-2026 (general, 2B) | en ✓ · **hi ✗** · ar ✓ | Apache-2.0 (F); **gated**; remote code on first-party paths | INT8 ONNX export exists (F) — via community org; provenance question | Covers 2 of 3 product languages; ONNX route may avoid remote code (open question) |
| **B3** | IndicConformer-600M | **hi ✓** (22 Indic, C) · en ✗ · ar ✗ | MIT (F); remote code required (F) | ONNX packages are pinned deps (F — strongly implied path) | The dedicated Indic specialist; Devanagari tokenizer vs our ruler unverified |
| **B4** | Cohere Transcribe Arabic 07-2026 (2B) | **ar ✓ + dialects + code-switch** · hi ✗ | Apache-2.0 (F); **gated**; remote code (F) | ONNX quantization is a sibling-model claim (C), unverified for this artifact | The only purpose-built Arabic candidate registered |

**Stack S3 — transformers:**

| ID | Engine | en/hi/ar | Licence | CPU path | Key facts |
|---|---|---|---|---|---|
| **B5** | Granite Speech 4.1 2B (IBM) | en ✓ (+FR/DE/ES/PT/JA) · hi/ar ✗ | Apache-2.0 (F), no gate, **no remote code** | I — unproven; no quantized artifact | Cleanest commercial posture of the 2026 entrants; **PEFT is an inference-path dependency** (F) |
| **B6** | Qwen3-ASR 0.6B | hi claimed (C) · ar unconfirmed | Apache-2.0 (F) | I — "CPU-plausible" at 0.6B, unmeasured | Two-artifact timestamp architecture conflicts with one-slot design; Qwen concentration protocol |
| **B7** | Qwen3-ASR 1.7B | same claims | Apache-2.0 (F) | I — weaker than B6 | Same notes, larger |
| **B8** | Voxtral Mini 3B (Mistral) | **hi claimed** (F—card) · ar ✗ | Apache-2.0 (F); **gated** | I — "nothing indicates a CPU-viable path exists today" (dossier) | The candidate that forces the GPU question; ~20× incumbent params |

**Stack S4 — NeMo:**

| ID | Engine | en/hi/ar | Licence | CPU path | Key facts |
|---|---|---|---|---|---|
| **B9** | Parakeet TDT 0.6B v3 | en ✓ (25 European) · hi/ar ✗ | CC-BY-4.0 (F); attribution question | C — third-party ONNX only | **Native timestamps — unique in the set** (F); documented streaming |
| **B10** | Canary-Qwen 2.5B | en only | CC-BY-4.0 (F), "ready for commercial use" | I — weakest CPU fit of the PASS set | SALM reference; hallucination-class hypothesis |

**Stacks S5–S7 — one lineage each:**

| ID | Engine | en/hi/ar | Licence | CPU path | Key facts |
|---|---|---|---|---|---|
| **B11** | Omnilingual ASR — CTC 300M (Meta) | 1,600+ langs (C); en not the design goal (F) | Apache-2.0 (F) | I — most CPU-plausible architecture in the set; **fairseq2 required** (F) | Long-tail/dialect asset; char-level output vs our normalisation |
| **B12** | Omnilingual ASR — larger variants (1B/3B/7B, LLM heads) | same suite | Apache-2.0 (F per checked card; per-variant verification owed) | I — declining with size | Suite, not a model: each variant is its own artifact verdict |
| **B13** | Kyutai STT (1b-en_fr / 2.6b-en) | en/fr only | CC-BY-4.0 (F) | Negative signal (C: "painfully slow" CPU report) | Streaming-first; WebSocket-shaped serving; contract has no streaming method |

**Frozen at the licence gate** (work halted pending named clarifications; appear in no plan until cleared):

| ID | Lineage | Why frozen (2026-08-05) |
|---|---|---|
| B14 | IndicWhisper (AI4Bharat) | No licence attached to the checkpoint distribution (third-party object storage) |
| B15 | Zipformer / sherpa-onnx **checkpoints** | Per-checkpoint licence absent; training-corpus terms may bind weights. *Toolkit itself is verified Apache-2.0 — see D1* |
| B16 | MOSS-Transcribe-preview-2B | Unverified licences on both Qwen upstream bases; leaderboard-split contamination on record |
| B17 | ARK-ASR-3B | Unverified licences on the three remote-code upstreams |

**Closed by licence (Rejected in the ledger; re-entry only on a changed release):** Canary 1B (CC-BY-NC) · ArTST (CC-BY-NC) · SeamlessM4T v2 (CC-BY-NC).

**Excluded by product law (not filtered — never eligible):** hosted third-party STT APIs (Deepgram/OpenAI-API class). The platform's requirements are self-hosted, offline-after-start, data-sovereign serving; a vendor API fails Level 2 by construction and appears nowhere below.

## Part C — Improvement axes (compose with any Part A/B engine)

The ladder from Success Criteria v2 §6, as catalog entries. Each axis applied to an engine yields a new solution identity.

| Axis | Rung | Applies to | Current evidence |
|---|---|---|---|
| **IMP-1** Decode/configuration tuning | 1 | Every engine exposing decode knobs (incumbent: 13 recorded) | Declaration cost measured 5.3× per-clip / 9.4× median — configuration effects on this stack are first-order |
| **IMP-2** Quantization / build change | 2 | Engines with a quantization path (F: Moonshine shipped; F: Cohere-general INT8 ONNX; I/C: everyone else) | Only two candidates have first-party quantized CPU artifacts (Gate-2 structural finding) |
| **IMP-3** Vocabulary/lexicon + biasing | 3 | Platform-level (Pronunciation Manager law) + per-engine biasing where supported | Engine-level biasing support: open question per engine |
| **IMP-4** LoRA/PEFT adapters | 5 | Whisper lineage (rich precedent, F); Granite (PEFT native to its stack); Qwen3-ASR (unverified transfer); most others: no precedent (dossiers) | **All training rungs are corpus-blocked today** — no training data exists in any product language |
| **IMP-5** Domain fine-tune | 6 | As IMP-4 | Same corpus dependency |
| **IMP-6** Custom training | 7 | See Part D | Gated on measured ceilings + data moat, per law |

## Part D — Custom-training solutions (rung 7; listed for completeness, gated by law)

| ID | Solution | State |
|---|---|---|
| **D1** | IntelliAI-native model on the **Zipformer/k2/icefall training stack** (the toolkit path is verified Apache-2.0 and unobstructed — distinct from the frozen B15 checkpoints) | The only candidate that is a training stack, not just a serving stack. Legal to pursue **only** after a quantified paying gap + data moat + measured ceiling on tuned incumbents — none of which exists yet |
| **D2** | Any other from-scratch training | Same gate; no stack identified |

## Part E — Architecture patterns (compose with any set of per-language winners)

| ID | Pattern | Platform support today |
|---|---|---|
| **E1** | **Single multilingual engine** — one model serves en+hi+ar (the incumbent shape) | Supported — serving today |
| **E2** | **Per-language routing** — a specialist engine per language behind the one public model | **Supported today** — the manifest routes per language; no gateway change needed |
| **E3** | **Hybrid routing** — multilingual default + specialist override for specific languages | Supported today — E2 mechanics with a default route |
| **E4** | **Content-based routing** (e.g. by audio length, per the Moonshine short-utterance hypothesis) | **Not supported** — routing-by-audio-property is a new gateway capability and a new registry concept (dossier F) |

A structural fact from Gate 2 bounds this part: **no eligible engine covers en+hi+ar together** — the strongest English candidates have neither Hindi nor Arabic, and the only Arabic specialist has no Hindi. E1 with the incumbent is therefore the only single-engine solution in the entire universe that covers all three product languages today; every other complete answer is a composition (E2/E3).

---

## Universe summary

- **9** incumbent-lineage solutions (A1–A9) — zero new-stack cost
- **13** alternative engines across 6 stacks (B1–B13) · **4** frozen (B14–B17) · **3** closed by licence · **1** excluded class (vendor APIs)
- **6** improvement axes (IMP-1–6) composing with every eligible engine
- **2** custom-training entries (D1–D2), gated by law
- **4** architecture patterns (E1–E4), three deployable today

*Phase 2 filters Parts A, B, D through Levels 1–3. Parts C and E are filtered per composition: an axis or pattern is only as eligible as the engine it composes with, plus its own requirements.*
