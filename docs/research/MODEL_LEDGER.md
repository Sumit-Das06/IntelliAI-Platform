# IntelliAI Model Research Ledger

| | |
|---|---|
| **Status** | LIVING LEDGER — append-only (law: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)) |
| **Last entry** | 2026-08-05 (STT candidate intake sweep, Gate 0) |
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

*This file grows by appended entries only. Do not edit prior entries — including their mistakes.*
