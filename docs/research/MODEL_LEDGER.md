# IntelliAI Model Research Ledger

| | |
|---|---|
| **Status** | LIVING LEDGER — append-only (law: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)) |
| **Last entry** | 2026-08-04 |
| **Role of this document** | The status of record for every foundation model IntelliAI has researched, and the complete dated history of every status decision. The **decision history is the source of truth**; the current-status table is a derived convenience view, regenerated whenever an entry is appended. |
| **The law** | A status change never edits a prior entry — it appends a dated entry with the new status, the reason, and the evidence. The chain must always answer *when, why, and on what evidence*. Every date-stamped fact decays: re-verify before it becomes load-bearing again. |

Statuses: `Researching` · `Promising` · `Approved for Benchmark` ·
`Approved for Adoption` · `Rejected` · `Deprecated`
(definitions and legal transitions: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)).

---

## Current status (derived view)

| Model | Capability | Languages (evidenced) | License (verified) | Current status | Last decision |
|---|---|---|---|---|---|
| Whisper Small (faster-whisper) | transcription | EN strong · HI usable · AR unevaluated | MIT (2026-07-31) | **Approved for Adoption** — incumbent, in production | 2026-08-04 |
| Whisper large-v3 / -turbo | transcription | claims 99 langs; unmeasured on our corpus | MIT (2026-07-31) | Researching | 2026-08-04 |
| Qwen3-ASR 0.6B/1.7B | transcription | claims incl. HI; unmeasured | Apache-2.0 (2026-07-31) | Researching | 2026-08-04 |
| IndicConformer-600M | transcription | claims 22 scheduled Indic langs; unmeasured | MIT (2026-07-31) | Researching | 2026-08-04 |
| Omnilingual ASR (Meta) | transcription | claims 1,600+ langs; unmeasured | Apache-2.0 (2026-07-31) | Researching | 2026-08-04 |
| Canary 1B (NVIDIA) | transcription | — | CC-BY-NC (2026-07-31) | Rejected | 2026-08-04 |
| Kokoro-82M | speech_synthesis | EN shipped · HI gated (license) · AR none | Apache-2.0 (2026-08-03) | **Approved for Adoption** — incumbent, in production (EN only) | 2026-08-04 |
| Chatterbox (Resemble) | speech_synthesis | claims 23 langs incl. HI; unmeasured | MIT (2026-07-31) | Researching | 2026-08-04 |
| Qwen3-TTS | speech_synthesis | no Indic yet (claim) | Apache-2.0 (2026-07-31) | Researching | 2026-08-04 |
| IndicF5 | speech_synthesis | claims 11 Indic langs; unmeasured | MIT (2026-07-31) | Researching | 2026-08-04 |
| F5-TTS | speech_synthesis | — | NC (2026-07-31) | Rejected | 2026-08-04 |
| XTTS-v2 (Coqui) | speech_synthesis | — | CPML non-commercial (2026-07-29) | Rejected | 2026-08-04 |
| Fish-Speech | speech_synthesis | — | NC (2026-07-31) | Rejected | 2026-08-04 |
| Piper (fork) | speech_synthesis | — | GPL-3.0 fork (2026-07-31) | Rejected | 2026-08-04 |
| espeak-ng in-process phonemization | serving-chain component | — | GPL-3.0 (2026-08-03) | Rejected | 2026-08-04 |

---

## Decision history (source of truth, append-only)

Seed entries (2026-08-04) carry statuses earned *before* this ledger
existed; each cites the original evidence and its date, so day-one
statuses have the same provenance discipline as future ones.

### transcription

**Whisper Small (faster-whisper)**
- 2026-08-04 — **Approved for Adoption** *(seed entry; adoption predates ledger, M2)* — Incumbent engine behind `intelliai-stt`, in production since v0.3. License MIT, verified at the Systran faster-whisper distribution 2026-07-31. Permanent production baseline 2026-08-03: WER 0.000 on stt-eval-v1, mean RTF 0.162 (~6× realtime CPU int8), 0 hallucinated words on probes, PRD p95 PASS with ~9× headroom. Known evidence gaps: Hindi wedge gap observed (लगता→लकता, founder self-test, single data point); Arabic unevaluated — evidence: [stt baseline](../../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md), [FOUNDATION_MODELS §2](../FOUNDATION_MODELS.md), [ADR-0017](../adr/0017-registry-v1-code-declarative-resolution.md)

**Whisper large-v3 / large-v3-turbo**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: standing roadmap question "should Whisper Large replace Whisper Small?". MIT; scored 8.6 in the 2026-07-31 sweep (the "ownership leader"). The Small→Large quality delta on *our* corpus (especially Hindi, and CPU cost delta) is unmeasured — that measurement is the gate to Promising — evidence: [FOUNDATION_MODELS §2](../FOUNDATION_MODELS.md) (dated 2026-07-31)

**Qwen3-ASR 0.6B/1.7B**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: named backup lineage for transcription (successor if Whisper's age starts losing our wedge evaluations). Apache-2.0 verified 2026-07-31; scored 8.1; Hindi in scope; 0.6B CPU-plausible; rides the Qwen serving stack (concentration-risk protocol applies, [FOUNDATION_MODELS §14](../FOUNDATION_MODELS.md)) — evidence: FOUNDATION_MODELS §2 (dated 2026-07-31)

**IndicConformer-600M (AI4Bharat)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: standing roadmap question "should Indic models serve Hindi?" — designated Indic wedge engine and evaluation-baseline candidate in the 2026-07-31 sweep. MIT; 22 scheduled languages claimed; unmeasured on our corpus — evidence: [FOUNDATION_MODELS §2](../FOUNDATION_MODELS.md) (dated 2026-07-31)

**Omnilingual ASR (Meta)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: long-tail language coverage asset (1,600+ languages claimed — includes Arabic dialect potential). Apache-2.0 (2026-07-31); known friction: fairseq2 stack, English not competitive — evidence: FOUNDATION_MODELS §2 (dated 2026-07-31)

**Canary 1B (NVIDIA)**
- 2026-08-04 — **Rejected** *(seed entry)* — CC-BY-NC: non-commercial license fails [ADR-0005](../adr/0005-permissive-model-licensing-policy.md); named ban since 2026-07-29, re-confirmed in the 2026-07-31 sweep. Re-entry requires a future version under a permissive license. (Note: Canary-*qwen*-2.5b is a distinct CC-BY-4.0 artifact — per-version verdicts; it would enter as its own row if triggered.)

### speech_synthesis

**Kokoro-82M**
- 2026-08-04 — **Approved for Adoption** *(seed entry; adoption predates ledger, M3)* — Incumbent engine behind `intelliai-tts`, in production since v0.4, **English only**. Apache-2.0 across weights / kokoro pip / misaki, verified at source 2026-08-03; served GPL-free by construction (espeak chain excluded at build, verified in container). Baseline 2026-08-03: EN round-trip WER 0.072, RTF ~0.2 CPU, production bench: TTFB PRD FAIL on long input → streaming GO (M8). **Hindi path GATED by license** (voice pack needs espeak-ng GPL G2P in-process; compliant paths: subprocess isolation spike or a separate Indic engine). Known ceiling: dictionary-only G2P drops OOV words (Pronunciation Manager is the platform answer); no cloning, no training pipeline — not an ownership lineage — evidence: [tts baseline](../../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md), [M3 design §8](../milestones/3-tts-design.md), [M3 review](../milestones/3-tts-review.md)

**Chatterbox (Resemble)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: standing roadmap question "should Chatterbox replace Kokoro?" — designated *ownership lineage* for speech synthesis in the 2026-07-31 sweep (MIT end-to-end, zero-shot cloning, 23 languages claimed incl. Hindi, corporate release cadence, built-in watermarker aligning with consent-gated cloning policy). Scored 8.0. Unmeasured on our corpus — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)

**Qwen3-TTS**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: named backup for all three TTS roles (serve/own/wedge). Apache-2.0 (2026-07-31); scored 7.7; explicit fine-tune support; no Indic languages yet — watch its language expansion. Qwen concentration protocol applies — evidence: FOUNDATION_MODELS §3 (dated 2026-07-31)

**IndicF5**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: the Hindi TTS gated path (M3 license gate named it as the MIT-lineage alternative to espeak-based Hindi) and the Indic wedge lineage. MIT; 11 Indic languages claimed; consent-collected training data (rare in TTS; our data constitution rewards it). Unmeasured on our corpus — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md), [M3 design §8](../milestones/3-tts-design.md) (dated 2026-07-31 / 2026-08-03)

**F5-TTS**
- 2026-08-04 — **Rejected** *(seed entry)* — Non-commercial license (verified in the 2026-07-31 sweep; scored 0 — "quality-tier leaders, commercially dead to us"). Fails ADR-0005. Answers the roadmap question "should F5-TTS be evaluated?": not under this license; the lineage's compliant relative is IndicF5 (MIT), tracked above — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)

**XTTS-v2 (Coqui)**
- 2026-08-04 — **Rejected** *(seed entry)* — Coqui CPML is non-commercial; named ban in [ADR-0005](../adr/0005-permissive-model-licensing-policy.md) since 2026-07-29, re-confirmed 2026-07-31 (scored 0). Upstream company defunct; re-entry effectively closed.

**Fish-Speech**
- 2026-08-04 — **Rejected** *(seed entry)* — Non-commercial weights license (2026-07-31 sweep, scored 0). Fails ADR-0005.

**Piper (fork)**
- 2026-08-04 — **Rejected** *(seed entry)* — Original archived Oct 2025; the maintained fork is GPL-3.0; maintainer vacancy. Verdict "exit" in the 2026-07-31 sweep (scored 3.5); replaced by Kokoro-82M in the roadmap at M1.5 close — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)

### serving-chain components

**espeak-ng in-process phonemization (phonemizer-fork / espeakng-loader chain)**
- 2026-08-04 — **Rejected** *(seed entry)* — GPL-3.0 arriving transitively inside Apache models' default G2P pipelines (the M3 discovery that motivated Gate 1's ordering). Banned in-process platform-wide; the tts image is GPL-free by construction (build fails if the chain is importable). A *subprocess-isolated* espeak spike is a distinct architecture and would enter the ledger as its own entry if pursued for Hindi — evidence: [M3 design §8](../milestones/3-tts-design.md), [M3 review](../milestones/3-tts-review.md) (dated 2026-08-03)

---

## Open research threads (no candidate or no measurement yet)

| Thread | Standing question | State (2026-08-04) |
|---|---|---|
| **Arabic STT** | Which engine serves Arabic transcription? | **Open slot — no candidate registered.** Language Policy v1 makes AR first-class; no AR corpus, baseline, or benchmark exists. First deliverables: candidate intake (Whisper's AR is the null hypothesis, unevaluated) + AR corpus plan. |
| **Arabic TTS** | Which engine serves Arabic synthesis? | **Open slot — no candidate registered.** Kokoro has no Arabic. |
| **Hindi TTS** | Which compliant path un-gates Hindi synthesis? | Two candidate paths tracked: IndicF5 (Researching) and subprocess-isolated espeak (unregistered spike). |
| **Hindi STT improvement** | Fine-tune Whisper vs adopt an Indic engine? | Governed by [RESEARCH_FRAMEWORK §9](RESEARCH_FRAMEWORK.md): needs the wedge gap *measured* first (one anecdotal data point exists; corpus ≥100 gate from M2.5 C3 applies). |
| **Multilingual TTS shape** | One multilingual engine or per-language engines? | A hypothesis pair to test per [RESEARCH_FRAMEWORK §7](RESEARCH_FRAMEWORK.md) — the architecture supports either; no assumption made. |
| **Streaming STT/TTS** | Which lineages support the M8 streaming decision? | TTS streaming verdict GO (M3 evidence); candidate streaming properties recorded in dossiers as they are built. |
| **Own IntelliAI-STT / IntelliAI-TTS** | When is pretraining justified? | Parked at Ladder rung 6 ([RESEARCH_FRAMEWORK §9](RESEARCH_FRAMEWORK.md)): requires measured ceilings on tuned incumbents + data moat. Not before the evaluation harness can prove the ceiling. |

---

*This file grows by appended entries only. Do not edit prior entries — including their mistakes.*
