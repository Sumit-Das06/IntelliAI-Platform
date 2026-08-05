# IntelliAI Model Research Ledger

| | |
|---|---|
| **Status** | LIVING LEDGER — append-only (law: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)) |
| **Last entry** | 2026-08-05 (STT Gate 4 campaign planning) |
| **Role of this document** | The status of record for every foundation model IntelliAI has researched, and the complete dated history of every status decision. The **decision history is the source of truth**; the current-status table is a derived convenience view, regenerated whenever an entry is appended. |
| **The law** | A status change never edits a prior entry — it appends a dated entry with the new status, the reason, and the evidence. The chain must always answer *when, why, and on what evidence*. Every date-stamped fact decays: re-verify before it becomes load-bearing again. |

Statuses: `Researching` · `Promising` · `Approved for Benchmark` ·
`Approved for Adoption` · `Rejected` · `Deprecated`
(definitions and legal transitions: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)).

From framework v0.2: no model may hold `Promising` or any later status
without a formal dossier under `models/`
([RESEARCH_FRAMEWORK.md §11](RESEARCH_FRAMEWORK.md)) — the ledger stays
concise; the dossier carries the analysis. Research attention across
entries is ordered by the living priorities
([RESEARCH_FRAMEWORK.md §16](RESEARCH_FRAMEWORK.md)).

---

## Current status (derived view)

| Model | Capability | Languages (evidenced) | License (verified) | Current status | Last decision |
|---|---|---|---|---|---|
| Whisper Small (faster-whisper) | transcription | EN strong · HI usable · AR unevaluated | MIT (2026-07-31) | **Approved for Adoption** — incumbent, in production | 2026-08-04 |
| Whisper large-v3 / -turbo | transcription | claims 99 langs; unmeasured on our corpus | MIT (2026-07-31) | Researching | 2026-08-04 |
| Qwen3-ASR 0.6B/1.7B | transcription | claims incl. HI; unmeasured | Apache-2.0 (2026-07-31) | Researching | 2026-08-04 |
| IndicConformer-600M | transcription | claims 22 scheduled Indic langs; unmeasured | MIT (2026-07-31) | Researching | 2026-08-04 |
| Omnilingual ASR (Meta) | transcription | claims 1,600+ langs; unmeasured | Apache-2.0 (2026-07-31) | Researching | 2026-08-04 |
| Cohere Transcribe Arabic | transcription | claims AR + dialects + AR-EN code-switch | **Apache-2.0 (source, 2026-08-05)** | Researching | 2026-08-05 |
| Cohere Transcribe 2B (general) | transcription | multilingual; list unconfirmed | Apache-2.0 (claimed) | Researching | 2026-08-05 |
| Voxtral (Mistral) | transcription | claims 8 langs incl. HI | **Apache-2.0 (source, 2026-08-05)** | Researching | 2026-08-05 |
| Granite Speech 4.1 2B (IBM) | transcription | claims EN/FR/DE/ES/PT/JA — no HI, no AR | **Apache-2.0 (source, 2026-08-05)** | Researching | 2026-08-05 |
| Parakeet TDT 0.6B v3 (NVIDIA) | transcription | claims 25 European — no HI, no AR | **CC-BY-4.0 (source, 2026-08-05)** | Researching | 2026-08-05 |
| Canary-Qwen 2.5B (NVIDIA) | transcription | EN only | CC-BY-4.0 (claimed) | Researching | 2026-08-05 |
| ARK-ASR-3B (Audio8) | transcription | claims 19 langs — no HI, no AR | **Apache-2.0 (source, 2026-08-05)** | Researching | 2026-08-05 |
| MOSS-Transcribe-preview-2B | transcription | EN only | Apache-2.0 (claimed) | Researching | 2026-08-05 |
| IndicWhisper (AI4Bharat) | transcription | claims Indic incl. HI | MIT (claimed) | Researching | 2026-08-05 |
| Moonshine (Useful Sensors) | transcription | EN-centric | MIT (claimed) | Researching | 2026-08-05 |
| Kyutai STT | transcription | EN/FR only | CC-BY-4.0 (claimed) | Researching | 2026-08-05 |
| Zipformer / sherpa-onnx (Next-gen Kaldi) | transcription | per-recipe; varies | Apache-2.0 (claimed) | Researching | 2026-08-05 |
| Canary 1B (NVIDIA) | transcription | — | CC-BY-NC (2026-07-31) | Rejected | 2026-08-04 |
| ArTST (MBZUAI) | transcription | Arabic specialist | **CC-BY-NC-4.0 (source, 2026-08-05)** | Rejected | 2026-08-05 |
| SeamlessM4T v2 (Meta) | transcription | — | **CC-BY-NC-4.0 (source, 2026-08-05)** | Rejected | 2026-08-05 |
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
- 2026-08-05 — *status unchanged (Researching)* — Intake record created at the STT candidate sweep; the Whisper lineage (incl. distil-whisper and IndicWhisper derivatives) is now documented — [whisper-dossier.md](models/whisper-dossier.md)

**Qwen3-ASR 0.6B/1.7B**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: named backup lineage for transcription (successor if Whisper's age starts losing our wedge evaluations). Apache-2.0 verified 2026-07-31; scored 8.1; Hindi in scope; 0.6B CPU-plausible; rides the Qwen serving stack (concentration-risk protocol applies, [FOUNDATION_MODELS §14](../FOUNDATION_MODELS.md)) — evidence: FOUNDATION_MODELS §2 (dated 2026-07-31)
- 2026-08-05 — *status unchanged (Researching)* — Intake record created. New landscape claim recorded: 52 languages/dialects (≈30 languages + 22 Chinese dialects) with a separate forced-alignment model for timestamps in 11 languages; Arabic coverage unresolved — [qwen3-asr-dossier.md](models/qwen3-asr-dossier.md)

**IndicConformer-600M (AI4Bharat)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: standing roadmap question "should Indic models serve Hindi?" — designated Indic wedge engine and evaluation-baseline candidate in the 2026-07-31 sweep. MIT; 22 scheduled languages claimed; unmeasured on our corpus — evidence: [FOUNDATION_MODELS §2](../FOUNDATION_MODELS.md) (dated 2026-07-31)
- 2026-08-05 — *status unchanged (Researching)* — Intake record created — [indicconformer-dossier.md](models/indicconformer-dossier.md)

**Omnilingual ASR (Meta)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: long-tail language coverage asset (1,600+ languages claimed — includes Arabic dialect potential). Apache-2.0 (2026-07-31); known friction: fairseq2 stack, English not competitive — evidence: FOUNDATION_MODELS §2 (dated 2026-07-31)
- 2026-08-05 — *status unchanged (Researching)* — Intake record created. Licence-verification priority raised: sibling Meta speech releases (MMS, SeamlessM4T) are CC-BY-NC, so the Apache-2.0 claim must be verified at source per repository before any other work — [omnilingual-asr-dossier.md](models/omnilingual-asr-dossier.md)

**Canary 1B (NVIDIA)**
- 2026-08-04 — **Rejected** *(seed entry)* — CC-BY-NC: non-commercial license fails [ADR-0005](../adr/0005-permissive-model-licensing-policy.md); named ban since 2026-07-29, re-confirmed in the 2026-07-31 sweep. Re-entry requires a future version under a permissive license. (Note: Canary-*qwen*-2.5b is a distinct CC-BY-4.0 artifact — per-version verdicts; it would enter as its own row if triggered.)
- 2026-08-05 — *status unchanged (Rejected)* — The noted distinct artifact was in fact triggered at this sweep and registered separately as Canary-Qwen 2.5B below. Rejection of this artifact stands.

---

*Entries below appended at the **2026-08-05 STT candidate intake sweep (Gate 0)**.
Trigger for the sweep: founder-directed opening of the speech-to-text research
universe under research priorities #1–#3, informed by a Technology Watch pass
(§13). Every entry is intake only — no candidate has been screened (Gate 1),
scored (Gate 2), compared, or benchmarked. Licences marked "source" were read on
the model card on 2026-08-05; all other licence values are claims awaiting Gate 1.*

**Cohere Transcribe Arabic**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: the Arabic open slot under Core Speech Language Policy v1, which has carried no candidate since the policy was written. Released 2026-07-07; 2B FastConformer encoder-decoder purpose-built for Arabic dialect variation and Arabic-English code-switching. **Licence `apache-2.0` verified at source on the model card 2026-08-05** — notable because the same lab ships CC-BY-NC weights on other product lines, so the verdict binds to this artifact only — [cohere-transcribe-arabic-dossier.md](models/cohere-transcribe-arabic-dossier.md)

**Cohere Transcribe 2B (general)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: same lineage as the Arabic model; if the general model covers Hindi, one organisation could serve two product languages on one serving stack. Apache-2.0 claimed (2026-07-31 sweep + landscape), unverified at source; language list unconfirmed — [cohere-transcribe-dossier.md](models/cohere-transcribe-dossier.md)

**Voxtral (Mistral)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: research priority #2 (Hindi STT) and the standing M8 streaming question — the only lineage in this intake claiming permissive licence, Hindi, and native streaming together. **Licence `apache-2.0` verified at source on the `Voxtral-Mini-3B-2507` card 2026-08-05** (other variants unverified). Audio-LLM architecture; vendor claims a realtime variant with a causal audio encoder and unbounded streaming on a single 16GB GPU — CPU viability unknown and the first Gate 2 question — [voxtral-dossier.md](models/voxtral-dossier.md)

**Granite Speech 4.1 2B (IBM)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: research priority #1 (English STT improvement); credible English specialist with enterprise provenance/indemnification posture. **Licence `apache-2.0` verified at source 2026-08-05.** Claims EN/FR/DE/ES/PT/JA — no Hindi, no Arabic, so it could only ever be a per-language engine — [granite-speech-dossier.md](models/granite-speech-dossier.md)

**Parakeet TDT 0.6B v3 (NVIDIA)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: efficiency/throughput reference and a natively streaming transducer architecture. **Licence `CC-BY-4.0` verified at source 2026-08-05**; card confirms a streaming inference path. 25 European languages, no Hindi or Arabic. Open commercial question recorded: CC-BY **attribution** obligations versus our engine-hiding public API — [parakeet-tdt-dossier.md](models/parakeet-tdt-dossier.md)

**Canary-Qwen 2.5B (NVIDIA)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: reference implementation of the SALM architecture now shared by several 2026 entrants. CC-BY-4.0 claimed (2026-07-31), unverified at source — verification is high-value here because a sibling artifact in the same family is CC-BY-NC and already Rejected. English-only, GPU-bound — [canary-qwen-dossier.md](models/canary-qwen-dossier.md)

**ARK-ASR-3B (Audio8)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: current top of the public English short-form leaderboard under a permissive licence. **Licence `apache-2.0` verified at source on the `Audio8/ARK-ASR-3B` card 2026-08-05.** Two flags recorded at intake: an identically named repository exists under a second organisation (`AutoArk-AI`) so canonical provenance is unresolved; and the model requires custom `arkasr` remote code, which conflicts with weights-import hygiene and needs security review, not merely a licence check — [ark-asr-dossier.md](models/ark-asr-dossier.md)

**MOSS-Transcribe-preview-2B (OpenMOSS)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: current top-tier English leaderboard entrant, claimed Apache-2.0 (unverified at source). Recorded at intake: the publisher states the model was RL-fine-tuned on Open ASR Leaderboard training splits, so its leaderboard standing is not transferable evidence — carried partly as a worked example of why §6 permits comparison only on our own corpus and judge — [moss-transcribe-dossier.md](models/moss-transcribe-dossier.md)

**IndicWhisper (AI4Bharat)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: research priority #2 (Hindi STT) via the cheapest possible route — a fine-tune *inside* our incumbent lineage, so serving stack, tooling, and operational knowledge transfer unchanged. MIT claimed (lab states MIT covers the fine-tuned models and the Vistaar benchmark), unverified at source; checkpoint provenance must be pinned to the lab's own distribution — [indicwhisper-dossier.md](models/indicwhisper-dossier.md)

**Moonshine (Useful Sensors)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: the lower bound of the cost/latency frontier and the only plausible future offline/on-device candidate; processes variable-length audio without Whisper's fixed 30s padding. MIT claimed, unverified. English-centric; smallest organisation in this intake (continuity risk) — [moonshine-dossier.md](models/moonshine-dossier.md)

**Kyutai STT**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: the strongest open expression of streaming-first ASR design (delayed-streams modelling), as an architectural reference for the M8 streaming decision rather than a likely engine. CC-BY-4.0 claimed, unverified; EN/FR only; same CC-BY attribution question as Parakeet — [kyutai-stt-dossier.md](models/kyutai-stt-dossier.md)

**Zipformer / sherpa-onnx (Next-gen Kaldi)**
- 2026-08-05 — **Researching** *(Gate 0 intake)* — Trigger: the CPU-native streaming reference, directly aligned with CPU-first economics; and uniquely in this intake, a **training** stack as well as a serving stack, making it relevant to the training-program connection (§15) and any future IntelliAI-native model. Apache-2.0 claimed for the toolkit, unverified; per-checkpoint and per-training-corpus terms may differ and can bind derived checkpoints — [zipformer-sherpa-dossier.md](models/zipformer-sherpa-dossier.md)

**ArTST (MBZUAI)**
- 2026-08-05 — **Rejected** *(Gate 0 intake; licence alone)* — Registered and rejected in the same sweep. Arabic-specialist SpeechT5-based ASR (0.2B) from MBZUAI's speech lab, and the most-cited academic Arabic ASR lineage — but **licence `cc-by-nc-4.0` verified at source on the `MBZUAI/artst_asr` model card 2026-08-05**, which fails [ADR-0005](../adr/0005-permissive-model-licensing-policy.md); non-commercial makes commercial adoption impossible regardless of quality. No dossier created (rejected before desk research, per the cheapest-kill-first gate ordering). Re-entry only on a future permissively licensed release.

**SeamlessM4T v2 (Meta)**
- 2026-08-05 — **Rejected** *(Gate 0 intake; licence alone)* — Considered for multilingual ASR and as a composite speech-translation component. **Licence `cc-by-nc-4.0` verified at source on the `facebook/seamless-m4t-v2-large` model card 2026-08-05** — fails ADR-0005. No dossier created. This verdict also raises the verification priority on Meta's Omnilingual ASR, whose Apache-2.0 claim is unverified and cannot be inherited from a sibling.

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

Thread order below is historical; attention across threads follows the
living research priorities ([RESEARCH_FRAMEWORK.md §16](RESEARCH_FRAMEWORK.md)).

| Thread | Standing question | State (2026-08-05, updated at the STT intake sweep) |
|---|---|---|
| **Arabic STT** | Which engine serves Arabic transcription? | **Candidate slot now filled; corpus slot still empty.** Cohere Transcribe Arabic registered 2026-08-05 (Apache-2.0 verified at source, purpose-built for dialects + AR-EN code-switching); the academic specialist ArTST was rejected the same day on CC-BY-NC. Whisper's Arabic remains the unevaluated null hypothesis. **The binding constraint is no longer "no candidate" — it is that no Arabic corpus, baseline, or benchmark exists**, so nothing here can yet be measured. |
| **Arabic TTS** | Which engine serves Arabic synthesis? | **Open slot — no candidate registered.** Kokoro has no Arabic. |
| **Hindi TTS** | Which compliant path un-gates Hindi synthesis? | Two candidate paths tracked: IndicF5 (Researching) and subprocess-isolated espeak (unregistered spike). |
| **Hindi STT improvement** | Fine-tune Whisper vs adopt an Indic engine? | Governed by [RESEARCH_FRAMEWORK §9](RESEARCH_FRAMEWORK.md): needs the wedge gap *measured* first (one anecdotal data point exists; corpus ≥100 gate from M2.5 C3 applies). Three registered shapes now exist for the eventual comparison: in-lineage fine-tune (IndicWhisper), dedicated Indic engine (IndicConformer), multilingual generalist claiming Hindi (Qwen3-ASR, Voxtral). |
| **Multilingual TTS shape** | One multilingual engine or per-language engines? | A hypothesis pair to test per [RESEARCH_FRAMEWORK §7](RESEARCH_FRAMEWORK.md) — the architecture supports either; no assumption made. |
| **STT engine shape** | One multilingual STT engine or per-language engines? | Opened 2026-08-05 by the intake itself: no registered candidate covers EN, HI **and** AR together — the strongest EN candidates (Granite, Parakeet, ARK, MOSS, Canary-Qwen) have neither Hindi nor Arabic, and the only Arabic candidate is Arabic-specialised. Whether one engine can serve all three is now an open empirical question, not an assumption. |
| **Streaming STT/TTS** | Which lineages support the M8 streaming decision? | TTS streaming verdict GO (M3 evidence). STT streaming candidates now registered across three architectural families: transducer (Parakeet), delayed-streams (Kyutai), audio-LLM causal encoder (Voxtral), plus the CPU-native streaming stack (Zipformer/sherpa-onnx). |
| **CPU-vs-GPU serving tier** | Does any 2026-generation candidate justify a GPU tier? | Opened 2026-08-05: most new entrants are 2–3B and GPU-oriented, while our constitution is CPU-first with GPU-ready architecture. Whether the quality on offer justifies a GPU serving class is a decision this research must eventually inform with measurements, not preferences. |
| **Own IntelliAI-STT / IntelliAI-TTS** | When is pretraining justified? | Parked at Ladder rung 6 ([RESEARCH_FRAMEWORK §9](RESEARCH_FRAMEWORK.md)): requires measured ceilings on tuned incumbents + data moat. Not before the evaluation harness can prove the ceiling. |

---

---

## Gate 1 verdicts — STT universe (appended 2026-08-05)

Full evidence, per-candidate reasoning, and sources:
[2026-08-05-stt-gate1-license-screen.md](2026-08-05-stt-gate1-license-screen.md).

**Statuses are unchanged.** All 16 lineages remain `Researching`; status
transitions occur at Gate 3 ([RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)).
`PASS` / `BLOCKED` are gate outcomes, not ledger statuses — no new status was
introduced. Work on BLOCKED lineages is **halted**: no Gate 2 dossier may be
created for them until the named clarification is obtained.

Result: **12 PASS · 4 BLOCKED · 0 REJECTED.** Every licence below was read at
source on 2026-08-05; verdicts bind to the named artifact version only.

**PASS — eligible for Gate 2**
- 2026-08-05 — **Whisper (OpenAI)** — MIT covering *code and weights* explicitly; transitive chain verified the same day (faster-whisper MIT, CTranslate2 MIT). No gate, no remote code, no attribution beyond MIT notice. Cleanest lineage in the universe.
- 2026-08-05 — **Qwen3-ASR 1.7B / 0.6B** — `apache-2.0` on card; not gated; no remote code; no separate LICENSE file. Verdict does **not** generalise to Qwen text repositories, several of which ship custom LICENSE files.
- 2026-08-05 — **Granite Speech 4.1 2B (IBM)** — `apache-2.0`; not gated; **no remote code**. The only 2026-generation entrant carrying none of the three recurring risks.
- 2026-08-05 — **Omnilingual ASR (Meta)** — `apache-2.0` verified in the raw YAML frontmatter of `facebook/omniASR-LLM-300M`, no `extra_gated` fields. Discharges the Gate 0 flag that Meta's claim could not be inherited from a sibling — SeamlessM4T v2 is CC-BY-NC, this is not.
- 2026-08-05 — **Parakeet TDT 0.6B v3 (NVIDIA)** — CC-BY-4.0 verbatim ("Use of this model is governed by the CC-BY-4.0 license"); not gated; no remote code. ⚠ Attribution obligation vs engine-hiding API recorded as a condition.
- 2026-08-05 — **Canary-Qwen 2.5B (NVIDIA)** — CC-BY-4.0; card states "ready for commercial use", Deployment Geography Global; no remote code. Confirms the split from the CC-BY-**NC** `Canary 1B` already Rejected — same family, opposite terms. ⚠ Attribution recorded.
- 2026-08-05 — **Kyutai STT (stt-1b-en_fr)** — `cc-by-4.0` verified in raw frontmatter; nine named authors published for credit. ⚠ Attribution recorded.
- 2026-08-05 — **Moonshine** — `mit`; not gated; no remote code. Provenance note: published under `moonshine-ai` while examples reference `UsefulSensors`; both namespaces MIT, reads as an org migration. ⚠ Canonical repository must be pinned before any fetch.
- 2026-08-05 — **Cohere Transcribe Arabic 07-2026** — `apache-2.0`, card states verbatim "This model is governed by an Apache 2.0 license". Research-flavoured Terms-of-Use wording does **not** narrow the grant; commercial use genuinely permitted. ⚠ Gated ("agree to share your contact information") and requires `--trust-remote-code`.
- 2026-08-05 — **Cohere Transcribe 03-2026** — `apache-2.0`; gated (the `/raw/` endpoint returned HTTP 401, the first signal); `trust_remote_code=True` required. Commercial-scope fact recorded: 14 languages including **Arabic**, **Hindi absent**. ⚠ Same two conditions.
- 2026-08-05 — **Voxtral-Mini-3B-2507 (Mistral)** — `apache-2.0`; gated via privacy-policy notice. ⚠ Verdict covers the **Mini artifact only**; Small-24B and realtime/transcribe variants were not verified today and each needs its own verdict.
- 2026-08-05 — **IndicConformer-600M (AI4Bharat)** — `mit` on card; not gated; `trust_remote_code=True` required, served from the same MIT repository. ⚠ Remote-code execution recorded.

**BLOCKED — work halted pending clarification**
- 2026-08-05 — **IndicWhisper (AI4Bharat)** — Repo states "Vistaar is MIT-licensed. The license applies to all the fine-tuned language models", but the checkpoints are **not hosted in that repository**: they are distributed from third-party object storage (`indicwhisper.objectstore.e2enetworks.net/*.zip`) with **no licence statement attached to the checkpoint files**, and the discoverable HuggingFace copies are third-party re-uploads. *Clarification required:* a licence attached to the checkpoint distribution itself, or an AI4Bharat-published repository with an explicit licence field.
- 2026-08-05 — **Zipformer / sherpa-onnx (Next-gen Kaldi)** — Toolkit verified Apache-2.0 and actively maintained, but pretrained checkpoints ship **separately via GitHub Releases with no per-checkpoint licence statement**, and each is trained on a corpus whose terms may bind derived weights. *Split verdict:* the **toolkit-as-training-stack path is unobstructed** (relevant to §12/§15); no checkpoint may enter Gate 2 as a serving candidate until its own licence and training-corpus terms are verified.
- 2026-08-05 — **MOSS-Transcribe-preview-2B (OpenMOSS)** — `apache-2.0` on card, but built on **Qwen3-1.7B-base** and a **Qwen3-Omni-MoE** encoder with **no licences stated for either base**. A derivative cannot grant more than its bases allow. *Clarification required:* verified licences for both upstream components.
- 2026-08-05 — **ARK-ASR-3B (Audio8)** — Gate 0 provenance ambiguity **resolved**: Audio8 publishes, AutoArk is the research origin (`github.com/AutoArk/open-audio-opd`, arXiv:2605.28139); the card is canonical and no competing authority exists. Licence `apache-2.0`. **Blocked on the executing chain:** mandatory `trust_remote_code=True` whose code derives from repositories whose licences are unverified — the card states the work builds on `THUNLP/OPD` and `volcengine/verl`. Structurally the espeak-ng failure mode: permissive weights, unverified in-process code. *Clarification required:* licences for `AutoArk/open-audio-opd`, `THUNLP/OPD`, `volcengine/verl`, and confirmation the shipped `arkasr` code falls under the repository's Apache-2.0 grant.

**REJECTED — none at this gate.** Gate 0's licence-first ordering had already
removed the two non-commercial lineages the same day (ArTST, SeamlessM4T v2,
both `cc-by-nc-4.0` verified at source). Notably, **no candidate's headline
licence claim proved false** — every problem found was structural (access
mechanics, in-process code, unverifiable chains), not a mislabelled licence.

---

---

## Gate 2 — desk research complete (appended 2026-08-05)

Synthesis: [2026-08-05-stt-gate2-synthesis.md](2026-08-05-stt-gate2-synthesis.md).
Full dossiers: [models/](models/).

**Statuses unchanged.** All 12 PASS lineages remain `Researching`. Promotion to
`Promising` happens at **Gate 3**, requires an explicit hypothesis against a named
baseline, and is **not proposed** by this gate. The 4 BLOCKED lineages were **not
researched** and remain frozen.

- 2026-08-05 — **Gate 2 complete for all 12 PASS lineages** — each Gate 0 intake record
  expanded into a full [§11](RESEARCH_FRAMEWORK.md) dossier covering architecture, runtime
  and deployment profile, fine-tuning ecosystem, training support, research maturity,
  strengths, weaknesses, integration risks, strategic value, open questions, and one
  falsifiable benchmark hypothesis. Every statement labelled FACT / CLAIM / INFERENCE.
  Dossiers: [whisper](models/whisper-dossier.md) · [qwen3-asr](models/qwen3-asr-dossier.md) ·
  [granite-speech](models/granite-speech-dossier.md) · [voxtral](models/voxtral-dossier.md) ·
  [cohere-transcribe-arabic](models/cohere-transcribe-arabic-dossier.md) ·
  [cohere-transcribe](models/cohere-transcribe-dossier.md) ·
  [parakeet-tdt](models/parakeet-tdt-dossier.md) · [canary-qwen](models/canary-qwen-dossier.md) ·
  [omnilingual-asr](models/omnilingual-asr-dossier.md) · [kyutai-stt](models/kyutai-stt-dossier.md) ·
  [moonshine](models/moonshine-dossier.md) · [indicconformer](models/indicconformer-dossier.md)

**Structural findings recorded at Gate 2** (observations, not recommendations):

- **No candidate covers English, Hindi and Arabic together.** A multi-engine topology is
  now the most likely shape of any future STT deployment — the hypothesis reserved in
  [§7](RESEARCH_FRAMEWORK.md) now has coverage evidence behind it.
- **The Arabic constraint moved** from *no candidate exists* to *no evaluation
  infrastructure exists* — no Arabic corpus, baseline, or benchmark. That blocker is
  entirely within our control.
- **Hindi has three architecturally distinct claimant shapes** — dedicated Indic
  specialist (IndicConformer), small audio-LLM generalist (Qwen3-ASR 0.6B), larger
  audio-LLM generalist (Voxtral). The cheapest fourth path — an in-lineage Whisper
  fine-tune — is frozen at Gate 1 (IndicWhisper BLOCKED), which raises the cost of every
  remaining Hindi option.
- **Only two candidates have first-party quantized CPU artifacts today**: Moonshine (int8
  by default) and Cohere Transcribe general (INT8 ONNX, dynamic quantization, no
  calibration data).
- **We hold exactly one CPU measurement in this entire universe** — our own whisper-small.
  Every other CPU statement across the 12 dossiers is inference.
- **Timestamps are a contract requirement, not a nicety** (`verbose_json` already returns
  them) and are native in only one candidate (Parakeet); Qwen3-ASR requires a *second
  model* covering only 11 languages; the rest are undocumented or unverified.
- **Four of twelve hypotheses predict the binding constraint is not model quality** but
  our own infrastructure — deployment engineering, dependency isolation, evaluation
  infrastructure, or measurement validity.

---

---

## Gate 3 — benchmark methodology designed (appended 2026-08-05)

Deliverables: [methodology](STT_BENCHMARK_METHODOLOGY.md) · [record schema](STT_BENCHMARK_RECORD.md) ·
[procedure](STT_BENCHMARK_PROCEDURE.md) · [environment spec](STT_BENCHMARK_HARDWARE.md) ·
[corpus specification](STT_BENCHMARK_CORPORA.md) · [open prerequisites](2026-08-05-stt-gate3-prerequisites.md).

**No candidate was benchmarked, scored, ranked, compared, or recommended.** All 12 PASS
lineages remain `Researching`. Gate 3 designs measurement; it produces none. Promotion to
`Promising` remains Gate 3 review work not yet performed, and execution requires a
founder-approved plan at Gate 4.

- 2026-08-05 — **Gate 3 complete** — permanent STT benchmark methodology designed and
  reconciled. Produced by six parallel design tracks, then adversarially reviewed for gate
  discipline, five-year durability, and integration fidelity against the actual code
  (49 findings: 14 critical, 24 major, 11 minor). The critical findings were arbitrated into
  a single reconciled vocabulary rather than merged, because the colliding artifacts are
  append-only and first landing is permanent.

**Findings about our own evaluation infrastructure, recorded as ledger evidence:**

- **[FACT] Two evidence schemas exist, not one.** `results.EvalRun` (recognition) has no
  metric registry, no validators, and no `methodology_version`; every discipline previously
  described as platform-wide exists only on `speech_results.SpeechEvalRun` (generation).
  Recognition evidence is the less-disciplined half. Recognition therefore extends `EvalRun`
  while importing the same registry — `SpeechEvalRun` cannot hold an STT run because its
  `judge` is required and STT's reference is a human transcript.
- **[FACT] A live hazard in the scoring path.** `normalize_words` strips to `[^a-z0-9\s']+`,
  so a Devanagari or Arabic reference normalises to nothing: `ClipResult.wer` returns `None`
  silently and `hallucinated_words` returns the entire hypothesis. A perfectly transcribed
  Hindi clip would be committed to an append-only ledger as *N hallucinated words*. Verified
  at source. **Consequence: per-language rulers are a prerequisite that precedes corpus
  collection** — Hindi and Arabic audio must not be recorded through this path.
- **[FACT] Metric withdrawal would break the ledger.** `_require_registered` is a pydantic
  `field_validator`, so it runs on every *read*. Removing or reserving a metric name makes
  every historical record citing it unparseable, violating the charter that readers in five
  years must parse today's records. Fixed by write-time enforcement with a permissive read
  path.
- **[FACT] Judge identity as defined is insufficient.** In the committed `kokoro-82m` /
  `-repro` pair, with identical judge artifact *and version*, 9 of 25 transcripts differed
  and `round_trip_wer` moved 0.5000 → 0.5042 — because the judge ran on a different host.
  The existing claim that wall-clock is the only expected variance is contradicted by our own
  evidence.
- **[FACT] `rtf` is a name collision** — registered generically but described as synthesis
  time over produced audio duration. Recognition registers `recognition_rtf`.
- **[FACT] CER is named in PRD §10 and implemented nowhere.**
- **[FACT] `TextCategory` cannot be appended to** without breaking
  `test_corpus.py:102-104` against the immutable generation corpus.
- **[FACT] Our entire STT natural-speech holding is one speaker, one ~11-second utterance,
  21 reference words, one language.** Zero Arabic clips of any kind. The founder recording
  protocol references a corpus version that does not exist, and `corpus-inbox/` is not
  gitignored despite the protocol saying it is.
- ~60 open prerequisites across six dependency layers, weighted toward **our own
  infrastructure** rather than toward models.

---

---

## Gate 4 — benchmark campaign planned (appended 2026-08-05)

Deliverables: [campaign plan](gate4-benchmark-campaign.md) · [execution matrix](benchmark-matrix.md) ·
[order rationale](benchmark-order.md) · [hardware profiles](hardware-profiles.md) ·
[readiness review](gate4-review.md). Campaign id **`CAMP-STT-2026A`**.

**No benchmark was executed. No candidate was scored, ranked, compared, or recommended.**
All 12 PASS lineages remain `Researching`. The 4 BLOCKED lineages appear in no session.

- 2026-08-05 — **Gate 4 complete** — ~40 sessions defined across 8 phases, grouped by serving
  stack (7 groups) and ordered by prerequisite depth (English → Hindi → Arabic → streaming →
  robustness → regression). **Zero sessions are executable today**, including a re-run against
  our own incumbent.

**Findings recorded as ledger evidence:**

- **[FACT] Our published language-declaration figure was wrong.** The circulating 9.4× is a
  *median of three that was never committed*. The committed pair gives **12.8×** (17859 ms vs
  1391 ms on identical audio). The effect also interacts with duration: RTF 2.740 at 5 s,
  ≈30 at 1 s. The Gate 3 procedure document cites the uncommitted anecdote as its rationale —
  which framework §6.4 forbids as justification. **Correction carried forward.**
- **[FACT] Zero of the ~20 Gate 3 metric names are registered or recorded today.** `EvalRun`
  has no `metrics` dict. `cer_unicode` does not exist, so **no Hindi or Arabic primary ruler is
  computable** — not merely un-run.
- **[FACT] A candidate that fails a clip is unrecordable**: `raise_for_status()` aborts the
  whole run and `ClipResult` has no `failure` field. Three hypotheses concern candidates
  failing to run.
- **[FACT] `_comparability` has two defects beyond the known gaps**: it *blocks* same-artifact
  version upgrades as `not_a_replacement`, and on non-Latin slices it returns TRADE while
  differencing whole-hypothesis "hallucination" counts — i.e. it would confidently compare
  corrupted numbers. It can never fire `different_judge` on STT, since both sides record
  `judge=None`.
- **[FACT] `enablement_test` currently REFUSES every language** while defect F-M5-3 is open, so
  no session can terminate in an enablement verdict regardless of its measurements.
- **[FACT] The Promising review is not merely unperformed — it is currently ungrantable as
  specified.** Framework §3 requires a FOUNDATION_MODELS §1 weighted score among the minimum
  evidence and §11 mandates a Recommendation section; the twelve Gate 2 dossiers use a
  16-section structure with **neither**. This applies identically to all twelve — a process
  gap, not a judgement about any candidate.
- **[FACT] `hardware_class` exists in docs and in zero Python files**, so the fairness
  mechanism the order rationale depends on is a prerequisite, not a present-tense fact.
- **[FACT] The reference machine is spelled four different ways** across committed artifacts.
  A free string is not an identity; profile **P1 `cpu-x86-consumer-2026`** now names it, with
  the four legacy spellings recorded as aliases. No historical record was edited.
- **[FACT] The reference machine has a discrete GPU that no measurement has ever used**
  (`device="cpu"` is a literal in the engine). Recorded as a determination rather than by
  letting `accelerator = None` imply a GPU-less machine.
- **[FACT] Outbound contamination risk**: `corpus-inbox/` is not gitignored, so the
  clean-corpus position can be destroyed by one `git add` — irreversibly, and to exactly the
  crawlers that build the next training sets.
- **[FACT] The JFK reference is 22 words per clip / 44 in the slice**, not 21 as previously
  recorded in this ledger.

**Process disclosure:** three planned adversarial verification passes did **not run** (session
usage limit), as did the campaign-plan and matrix designers. Those two documents were written
by the orchestrator; the other three received a gate-discipline scan only. Cross-document
consistency is **unverified** — recorded as a prerequisite in [gate4-review.md](gate4-review.md).

---

---

## CORRECTION — appended 2026-08-05, after Gate 4 verification

**The Gate 4 entry above contains an error. It is corrected here, not edited.** This is the
append-only law working as designed: the mistake stays visible, and the correction carries
the evidence.

### C-1 · The language-declaration figure — the correction was itself wrong

The Gate 4 entry states as **[FACT]**: *"the circulating 9.4× is a median of three that was
never committed. The committed pair gives 12.8×."*

**Both halves are false.** Verified at source 2026-08-05 in
[`ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md`](../../ml/evaluation/stt/benchmarks/2026-08-05-multilingual-baselines.md)
§2a *"The declaration costs 9× on non-speech input"*:

> Identical 5-second tone clip, three declarations, **median of three runs each**, same process:
> `en` 1462.4 ms (RTF 0.292) · `ar` 1389.4 ms (RTF 0.278) · **`hi` 13698.1 ms (RTF 2.740)**

- The 9.4× figure **is committed**, in a published baseline document.
- It is a **median of three runs per declaration** — the *stronger* measurement.
- The 12.8× pair that displaced it is a **single-sample** comparison — the *weaker* one.

**The standing figure is ~9.4×** (13698.1 ms `hi` vs 1462.4 ms `en`). RTF 2.740 on a
5-second tone means the Hindi route passes real time on this hardware. Arabic is
indistinguishable from English (1389.4 ms).

**How the error happened, recorded because the process failure matters more than the number:**
a research agent reported the figure as uncommitted; I did not verify that claim at source
before repeating it to the founder and writing it into this ledger as a labelled **[FACT]**.
Framework §2 requires verification at source for exactly this class of claim, and I applied
the rule to external claims while exempting a claim about our own repository.

**Consequence for the campaign:** none to the design. The declaration effect is real, large,
and if anything better evidenced than the entry claimed. Documents citing 12.8× are corrected
to 9.4× with this source. The Gate 3 procedure document's citation of the figure remains
defensible, since the committed baseline is a legitimate source.

### C-2 · Gate 4 verification did run, and its findings stand against the entry above

The Gate 4 entry disclosed that no adversarial verification ran. It has since run: four
passes, **87 findings, 24 critical**. The verdict was that the five documents are
*"individually well-argued and collectively incoherent at every seam where they had to agree
without ever being reconciled"* — the Gate 3 failure mode, in the same shape, concentrated in
the two documents written without designer review.

Material findings against the campaign documents, since corrected:

- The execution matrix specified sessions in a **private vocabulary** (`M1`–`M12` unit codes,
  `<subject>` placeholders, "the five S2 lineages") never translated into registered metric
  names, artifact identities, or lineage names — so no session could reach its first measured
  value. Stack-group membership was **not recoverable** from committed dossiers: no reading of
  "has an ONNX path" returns the five the matrix claimed.
- The matrix **deleted an entire stack group** on the premise that its members are GPU-only.
  That premise is the hypothesis under test (falsifiable in the "it does run on CPU"
  direction), is contradicted by a **[FACT]**-labelled dossier line, and is overruled by the
  order document committed beside it. **A row precise enough to encode its own expected
  result** — the reverse of the failure this gate guards against.
- The matrix **under-blocked systematically**, omitting universal prerequisites and — most
  dangerously — omitting the ruler prerequisites from the Hindi and Arabic re-baseline rows,
  which would have run non-Latin audio through the ASCII stripper and committed the exact
  silent corruption the campaign exists to prevent.
- The campaign plan presented founder approval as granting `Approved for Benchmark` **directly
  from `Researching`** — an illegal transition under framework §3, which requires the
  Promising review first.
- `P<n>` was overloaded across **three** meanings (campaign phase, hardware profile,
  prerequisite item) inside single matrix rows, in identifiers the plan declares permanent.

---

*This file grows by appended entries only. Do not edit prior entries — including their mistakes.*
