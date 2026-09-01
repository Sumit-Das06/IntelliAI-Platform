# IntelliAI Model Research Ledger

| | |
|---|---|
| **Status** | LIVING LEDGER — append-only (law: [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md)) |
| **Last entry** | 2026-08-28 (Milestone 53: realtime STT web implementation on LOCAL/STAGING - decision A: one WebSocket session architecture for EN (whisper-small CUDA realtime instance) + HI (unchanged E3 via same-commit CUDA llama-server), live in the real Playground with LA2 display, existing punctuation/provenance/consent; batch byte-identical; flags OFF everywhere, prod pinned empty; recorded latency misses on Hindi finals kept honest. Production untouched) |
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
| XLS-R 300m/1b/2b (Meta) | transcription (SSL encoder, CTC base) | 128-lang pretraining incl. HI+AR; ASR only after per-language fine-tune | **Apache-2.0 (source, 2026-08-10, all three cards)** | Researching | 2026-08-10 |
| w2v-BERT 2.0 (Meta) | transcription (SSL encoder, CTC base) | 143-lang pretraining incl. HI+AR; ASR only after fine-tune | **MIT (source, 2026-08-10)** | Researching | 2026-08-10 |
| IndicConformer ta / ml per-language (AI4Bharat) | transcription | Tamil / Malayalam specialists, ~120M each | **MIT (source, 2026-08-11)** | Researching | 2026-08-11 |
| Dolphin base/small (DataoceanAI) | transcription | claims zh + 40 Eastern langs + 22 zh dialects | **Apache-2.0 (source, code+weights, 2026-08-11)** | Researching | 2026-08-11 |
| OWSM v3.1/v4 (CMU/ESPnet) | transcription | claims 151 langs; our six unenumerated | **CC-BY-4.0 (source, 2026-08-11)** | Researching | 2026-08-11 |
| FireRedASR-AED-L (FireRedTeam) | transcription | zh(+en) specialist, 1.1B | **Apache-2.0 (source, 2026-08-11)** | Researching | 2026-08-11 |
| Paraformer-zh (FunASR/Alibaba) | transcription | zh (+en code-switch) | **contradictory** — HF mirror `apache-2.0` vs FunASR Model License at origin (2026-08-11) | Researching — work halted pending clarification | 2026-08-11 |
| SenseVoice-Small (FunAudioLLM) | transcription | zh/yue/en/ja/ko | **FunASR Model License (source, 2026-08-11)** — no express commercial grant | Rejected | 2026-08-11 |
| TeleSpeech-ASR (Tele-AI) | transcription | zh + dialects | custom community licence; commercial use requires written approval (source, 2026-08-11) | Rejected | 2026-08-11 |
| ECAPA VoxLingua107 LID (SpeechBrain) | serving-chain component (audio LID) | 107 langs incl. our six | **Apache-2.0 (source, 2026-08-11)** | Researching | 2026-08-11 |
| Canary 1B (NVIDIA) | transcription | — | CC-BY-NC (2026-07-31) | Rejected | 2026-08-04 |
| ArTST (MBZUAI) | transcription | Arabic specialist | **CC-BY-NC-4.0 (source, 2026-08-05)** | Rejected | 2026-08-05 |
| SeamlessM4T v2 (Meta) | transcription | — | **CC-BY-NC-4.0 (source, 2026-08-05; re-verified unchanged 2026-08-10)** | Rejected | 2026-08-05 |
| MMS 1b-all / 1b-fl102 (Meta) | transcription | claims 1,162 langs incl. HI+AR | **CC-BY-NC-4.0 (source, 2026-08-10, both cards)** | Rejected | 2026-08-10 |
| Kokoro-82M | speech_synthesis | EN **hardened (M35)** · HI **implemented (M39) + validated (M40)**; **M42: BOTH languages PRODUCTION-APPROVED (F-M42)** — catalog route hi=AVAILABLE on kokoro-82m, voices english-female/english-male/hindi-female/hindi-male, prod overlay + preflight + readiness + smoke all declare it (promoted in repository; NOT deployed) · AR none | Apache-2.0 (re-verified 2026-08-20); Hindi G2P = pinned espeak-ng binary at the M35 exec boundary | **Approved for Adoption** — incumbent, EN+HI, production-approved; deployment/launch (Hostinger) is the remaining gate | 2026-08-24 |
| Supertonic 3 (Supertone) | speech_synthesis | 31 langs incl. EN+HI+**AR**; measured: EN trap-set WER 0.0832 · RTF 0.28-0.33 · 0.65-1.18 GiB · HI clean CER 0.023 (M38) — **but M38 found two hard-failure classes: ValueError CRASH on Devanagari numerals (४५९), ONNX broadcast CRASH on Hindi >1189 chars; Hindi digit verbalization broken (English digit names / garbage)** | code MIT; **weights OpenRAIL-M (re-verified 2026-08-22)** — not permissive | Researching — runner-up DEMOTED on robustness (M38) + license gate unchanged | 2026-08-22 |
| **Magpie-TTS Multilingual 357M (NVIDIA)** + NeMo NanoCodec | speech_synthesis | 12 langs incl. EN+HI; 5 preset voices; **MEASURED CPU (GGUF v2602 via NeMo-Speech.cpp): 25/25 ok, median RTF 1.30, RSS 1.42 GiB — a single CPU stream cannot keep up with playback**; speaks OOV names ("Kavya" clean); strongest punctuation prosody measured; GPU tier untested locally | **NVIDIA Open Model License** (weights + codec; conditioned-permissive, NVIDIA-may-update-terms) — REVIEW REQUIRED; runtime Apache-2.0 | Researching — fails the CPU-first serve bar; GPU-tier + Hindi interest noted | 2026-08-20 |
| Chatterbox (Resemble) | speech_synthesis | family grown: multilingual V3 0.5B (23 langs incl. HI+AR) + dedicated `-hi` finetune + nano 110M EN-CPU; unmeasured on our corpus | MIT (re-verified per-card 2026-08-20) | Researching — ownership/cloning lineage (P2); GPU tier for HI | 2026-08-20 |
| Qwen3-TTS | speech_synthesis | **MEASURED (M44 quality + M45 runtime)**: LJ 0.0468-0.0478 beats incumbent's 0.0535 on clean text; OOV worse in every rep · M45 built TRUE streaming on the official runtime (TTFA **0.80 s**, continuity exact) but **no runtime reaches RTF < 1 on the 8 GB laptop GPU** (best 1.39; vLLM-Omni 1.36-3.86, TTFA ~6.5 s) — playback starves · 0.6B fine-tune FAILED (M44, verdict F) · 10 langs, no Indic | Apache-2.0 end-to-end — weights + `qwen-tts` lib (2026-08-20) | Researching — **M45 verdict: C, still too slow on available hardware; DEFERRED.** Re-entry: rented desktop/datacenter GPU rerun of the M45 harnesses (RTF < 0.8 reopens the prototype), or vLLM-Omni maturing on sm_120; fine-tune re-entry only via 1.7B | 2026-08-25 |
| IndicF5 | speech_synthesis | claims 11 Indic langs | card `MIT` but **provenance contradicts**: no repo LICENSE; likely initialized from CC-BY-NC F5 (re-checked 2026-08-22: still no LICENSE file, no provenance statement) | **Rejected — license provenance**; revival on AI4Bharat written clarification | 2026-08-22 |
| **F5-Hindi 24KHz (SPRING Lab, IIT Madras)** | speech_synthesis | HI dedicated (151M F5-small, flow matching); **MEASURED (M38)**: clean RT-WER 0.169 (~3× incumbent) but best long-text behavior (ladder WER 0.042, no truncation) · **CPU RTF 6.34 / 4.1 GiB — fails CPU-first** · drops Latin tokens + digits (Devanagari-only vocab) · cloning-style ref interface, no streaming | **CC-BY-4.0** (card, 2026-08-22); card: trained FROM SCRATCH on IndicTTS-Hindi + IndicVoices-R (no NC-F5 init) | Researching — not a serving candidate; standing value: proves the from-scratch permissive Hindi recipe adjacent to E-TTS-1 | 2026-08-22 |
| KittenTTS nano (KittenML) | speech_synthesis | EN only; measured: WER 0.098 · RTF 0.34 · fails >~1 k chars | Apache-2.0 weights; pip package runs GPL espeak in-process for EN (source, 2026-08-20) | **Rejected — no niche** (not faster, not cleaner, preview-grade) | 2026-08-20 |
| MMS-TTS-hin (Meta) | speech_synthesis | HI, VITS 36M — the CPU-viable size-class datapoint | **CC-BY-NC 4.0 (source, 2026-08-20)** | Rejected | 2026-08-20 |
| F5-TTS | speech_synthesis | — | NC (2026-07-31) | Rejected | 2026-08-04 |
| XTTS-v2 (Coqui) | speech_synthesis | — | CPML non-commercial (2026-07-29) | Rejected | 2026-08-04 |
| Fish-Speech | speech_synthesis | — | NC (2026-07-31) | Rejected | 2026-08-04 |
| Piper (fork) | speech_synthesis | — | GPL-3.0 fork (re-verified: original archived read-only 2025-10-06; 2026-08-20) | Rejected | 2026-08-04 |
| espeak-ng in-process phonemization | serving-chain component | — | GPL-3.0 (2026-08-03) | Rejected | 2026-08-04 |
| espeak-ng subprocess phonemization (exec boundary) | serving-chain component (G2P: un-gates Kokoro HI; closes the EN OOV gap) | HI G2P proven; EN fallback halves probe WER (0.077→0.034) | GPL-3.0 **binary behind an exec boundary** — the ffmpeg posture, M3-blessed compliant shape | Researching — parity measured 16/29 exact, all diffs mechanically mappable; production decision is the next milestone's gate | 2026-08-20 |
| punct_cap_seg_47_language (1-800-BAD-CODE) | punctuation_restoration (text post-processing) | 47 langs incl. HI+EN; HI gated on hi-punct-eval@v3 | **Apache-2.0 (source, 2026-08-19)** | **Approved for Adoption** — runtime-integrated as `punct-cap-seg-47@v1`, staged 22/22, all approved gates PASS; PRODUCTION ACTIVATION PENDING (M30) | 2026-08-19 |
| Cadence-Fast (AI4Bharat) | punctuation_restoration (text post-processing) | claims EN + 22 Indic incl. HI; unmeasured | **contradictory** — card `MIT` vs Gemma-3 base Terms of Use flow-down (2026-08-19) | Researching — benchmark BLOCKED pending license clarity | 2026-08-19 |

---

## Decision history (source of truth, append-only)

Seed entries (2026-08-04) carry statuses earned *before* this ledger
existed; each cites the original evidence and its date, so day-one
statuses have the same provenance discipline as future ones.

### transcription

**Whisper Small (faster-whisper)**
- 2026-08-04 — **Approved for Adoption** *(seed entry; adoption predates ledger, M2)* — Incumbent engine behind `intelliai-stt`, in production since v0.3. License MIT, verified at the Systran faster-whisper distribution 2026-07-31. Permanent production baseline 2026-08-03: WER 0.000 on stt-eval-v1, mean RTF 0.162 (~6× realtime CPU int8), 0 hallucinated words on probes, PRD p95 PASS with ~9× headroom. Known evidence gaps: Hindi wedge gap observed (लगता→लकता, founder self-test, single data point); Arabic unevaluated — evidence: [stt baseline](../../ml/evaluation/stt/benchmarks/2026-08-03-whisper-small-cpu-baseline.md), [FOUNDATION_MODELS §2](../FOUNDATION_MODELS.md), [ADR-0017](../adr/0017-registry-v1-code-declarative-resolution.md)
- 2026-08-27 — **Approved for Adoption** *(status unchanged; M48 competitive comparison vs Sarvam saaras:v4 appended — the "why does Sarvam look better?" question, measured)* — Same 102 s real-world English clip through both systems (frozen wer.py ruler, punctuation excluded from WER by construction): English-route WER delta ≤ ~4 pts on n=1 and inside DRAFT-reference uncertainty (7 disputed spans await the founder's listen-through; one clear incumbent miss: "drafts"→"droughts"), **but punctuation F1 0.000 vs Sarvam 0.794, boundary 0.000 vs 0.875 — the product ships NO English punctuation stage (M30 v1 is Hindi-scoped, prod-OFF), and that alone explains the visible gap on this clip.** Latency strong (6.71 s / 102 s, RTF 0.066); silence probe clean; NEW recorded weakness: a 1 s ambiguous slice fabricates "Thank you." (the Whisper short-audio hallucination class). EXPERIMENTAL probe: the vendored punct-cap-seg-47 with an English label map reaches only F1 0.092 — v1's model/scope does not transfer to English. **M48 classification B (readability, not recognition); recommended next: M49 English punctuation/readability stage under the M29/M30 gates.** Sarvam internals/latency UNKNOWN (playground capture; API access pending) — evidence: [M48 report](2026-08-27-stt-intelliai-vs-sarvam.md), `research/experiments/48-stt-sarvam-comparison/`
- 2026-08-27 (correction + completion, same day) — **Approved for Adoption** *(status unchanged; founder directive applied: Sarvam credentials are NOT available)* — The entry above quotes punctuation-F1 numbers computed on Sarvam's CAPTURED playground text; per the founder's M48 update those figures are RECLASSIFIED as qualitative text-structure evidence, not Sarvam measurements — **every Sarvam quantitative metric is BLOCKED — CREDENTIALS REQUIRED** (no fabrication, no auth workarounds), reproducible later via the committed `m48_harness.py` plug-in adapter. What the capture already PROVES without any Sarvam metric: near-identical words on the same audio, one output fully sentence-punctuated, ours with none — the structural cause (no English punctuation stage) stands. IntelliAI-side battery COMPLETED and MEASURED: latency ×5 median 6.37 s/102 s (RTF 0.062, stable); long ladder 5 min WER 0.067 and 9.5 min WER 0.058 with ZERO truncation; numbers/names synthetic round-trip mean RT-WER 0.108 (names/IntelliAI/FastAPI/currency perfect; QwikCart/OpenAI/Kubernetes/slash-date slip); Hinglish on the hi route TRANSLITERATES English tokens to Devanagari (0/8 Latin kept, "QwikCart"→"क्यूबिक कार्ड") — recorded as a script-policy product question. Classification B unchanged — evidence: `evidence/intelliai-battery.json`, [M48 report](2026-08-27-stt-intelliai-vs-sarvam.md)

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

- 2026-08-20 — **Approved for Adoption** *(status unchanged; M32 re-examination appended)* — The Hindi gate is now MEASURED, not hypothetical: upstream KPipeline `h` (espeak-ng `hi` G2P, research venv, revision `f3ff3571…`) synthesized all 31 hi/mixed probes with zero failures; round-trip through the promoted E3 judge: hi WER 0.1615 / CER 0.1190 overall, **WER 0.0834 / CER 0.0347 on the clean slice** (digits/currency/dates excluded — those conflate verbalization with error; transcripts show correct Hindi number expansion). Solo timing: median RTF 0.2875, TTFA (first sentence chunk) median 1.26 s / min 0.68 s, peak RSS 2.17 GiB. Both voice sexes equally intelligible (hm_omega CER 0.1183). EN production path re-baselined on the current source: frozen-corpus WER 0.0759 (reproduces M3's 0.072); espeak-fallback comparison run halves the extended-probe EN error (0.0344 vs 0.0773) by rescuing OOV words — the measured cost of the dictionary-only verdict. **espeak subprocess parity**: 16/29 phoneme strings byte-identical; every diff is one of three mechanical transforms (punctuation preservation, language-switch-marker stripping, misaki diphthong table) — the compliant path is engineering, not research. Naturalness remains UNMEASURED pending founder listening (upstream grades the 4 hi voices C, minutes-scale training data). M32 recommendation: extend the incumbent to Hindi via subprocess phonemization, founder-gated — evidence: [M32 research doc](2026-08-20-tts-model-selection.md), [dossier](models/kokoro-82m-dossier.md), `research/experiments/32-tts-model-selection/evidence/`

- 2026-08-20 — **Approved for Adoption** *(status unchanged; M33 English re-examination appended — the "keep or switch?" question, answered with measurements)* — The M33 25-probe English trap set (names, brands, acronyms, phones, slash-dates, %, mixed punctuation) puts the incumbent's production path at RT-WER 0.1247 — and the errors decompose entirely to the dictionary-only G2P's OOV drops (measured: "Hello, Sumit." loses the founder's own name; Priya/Rajesh/IntelliAI/QwikCart silently absent). The espeak-fallback research twin on the SAME set scores **RT-WER 0.0716 / CER 0.0194 — the best quality measured in M33, beating every challenger** (Supertonic 0.0832, Magpie-CPU 0.1991). Solo timing: gateway RTF 0.283 / 0.557 rps saturation at c=8 / zero refusals / overhead 25.8 ms / PRD-TTFB FAIL beyond one sentence reproduced. New product fact: output is **not byte-deterministic** (5 runs → 5 hashes, duration stdev 0.0 s) — no byte caching, feature-level regression only. M33 verdict: **KEEP + HARDEN** (subprocess-espeak OOV fallback, TN v1, ONNX RAM lever, chunk merging, billing fix) — evidence: [M33 report](2026-08-20-english-tts-model-selection.md), `research/experiments/33-english-tts-selection/evidence/`

- 2026-08-20 — **Approved for Adoption** *(status unchanged; M35 hardening shipped to the LOCAL/staging tier)* — The M33 §22 hardening implemented through the PRODUCTION path and regression-proven on the same 25-text trap set, same judge: **RT-WER 0.1247 → 0.0659** (beats the research twin's 0.0716), CER 0.094 → 0.0251, median probe wall 1110 → 748 ms (chunk-merging closes the M3 debt; c=1 pinned-sentence p50 2972 → 1592 ms), ladder healthy to c=8 (0.59 rps, zero refusals). The enablers: espeak-ng **binary at the exec boundary** (M3 §8 posture recorded CLOSED: constant argv, stdin transport, version pin 1.5x, fail-open; GPL python chain still banned build-fatally), normalization v1 at the pipeline seam (currency/percent/slash-dates/phone; original text remains the billing fact), voices renamed `english-female`/`english-male` (legacy ids alias forever), billing law fixed (characters-only rated; `measured_audio_seconds` telemetry), stale-image smoke (`make tts-smoke`, version floor 0.2.0). **Community ONNX evaluated and DECLINED**: q8f16 via kokoro-onnx measured RTF 1.078 / WER 0.0956 vs torch 0.168-0.29 / 0.0659 (RAM 1.2 vs 2.4 GiB is real but loses the axes that matter; first-party export = PROPOSED lever). Web Speech Studio at `/console/speech` verified end to end through the HTTPS edge — judge heard *"Hello, Sumit. Welcome to IntelliAI. Your invoice of $4.99 is due on 12 August, 2026…"*. Production still ships no TTS — launch is the founder's gate — evidence: [M35 milestone doc](../milestones/35-kokoro-english-tts-hardening.md), `research/experiments/35-kokoro-hardening/evidence/`

- 2026-08-22 — **Approved for Adoption** *(status unchanged; M38 Hindi selection appended — the "Kokoro or a Hindi specialist?" question, answered with measurements)* — The M38 fixed Hindi benchmark (61 probes: M32 set verbatim + exclamation/Devanagari-numerals/percent/phone/time/slash-date/places/orgs/abbreviations + a 118-1897-char ladder) measured ALL FOUR upstream Hindi voices solo, judged by E3 through the real gateway: **clean-slice RT-WER 0.0450 (hm_psi, best) / 0.0593 (hf_alpha) / 0.0653 (hm_omega) / 0.0710 (hf_beta)**, CER 0.018-0.026; M32's comparable slice reproduced (alpha 0.1634/0.1191 vs 0.1615/0.1190); RTF 0.169-0.185; RSS 2.2-2.4 GiB; zero probe failures on all four. Devanagari+English code-switching is the strongest measured of any candidate ("IntelliAI का नया version आज release हुआ है" → judge heard it perfectly). **Two new facts with teeth**: (1) the upstream KPipeline `h` path SILENTLY TRUNCATES beyond ~350 chars — 683/1189/1897-char inputs all emit the same ~23.9 s (~510 phonemes), correcting M32's "zero failures on long text" (its 545-char probe was already truncated, unnoticed); danda-aware chunking is a CORRECTNESS requirement for M39, and our runtime's existing chunker needs only `।`/`॥` in the split law. (2) The in-process espeak chain is NOT thread-safe (concurrent phonemize corrupts its buffer — measured crash); the production subprocess shape is structurally immune. espeak `hi` over the M35 stdin transport verified working as-is. Hindi-TN gaps named and measured: ₹-comma, phone-as-one-number, slash-date "स्लाश", Devanagari digits misread (४५ → "पंद्रह सौ"). **M38 recommendation: Option A — extend the incumbent to Hindi (2 public voices, founder listening picks which packs); M39 defined** — evidence: [M38 report](2026-08-22-hindi-tts-model-selection.md), `research/experiments/38-hindi-tts-selection/evidence/`, [dossier §13c](models/kokoro-82m-dossier.md)

- 2026-08-24 — **Approved for Adoption** *(status unchanged; M39 — the Hindi voices IMPLEMENTED on the LOCAL/staging tier)* — The M38 recommendation and the founder's voice decision (hindi-female=**hf_alpha**, hindi-male=**hm_psi**) shipped through the production path, staging-gated: artifact spec v2 adds the two SHA-pinned packs (hf_alpha 06906fe0…, hm_psi 2f0f055c…, same upstream revision f3ff3571… as the M38 runs); `EspeakHindiG2P` = the M35 exec-boundary posture at sentence level (**12/12 byte-identical parity** vs upstream misaki EspeakG2P(hi), fixture-pinned); Hindi normalization v1 (₹/dates/%/phone/Devanagari digits/AM-PM — Hindi words only); the danda-aware splitter closes the M38 silent-truncation defect (**re-measured gone**: 1897 chars → 149.6 s audio through the gateway vs the research twin's 23.9 s cap). MEASURED (frozen M38 set, real gateway, E3 judge): clean-slice RT-WER **0.0707 (F) / 0.0547 (M)** — the PROPOSED ≤0.08 gate passes both voices; ladder slice 0.0482/0.0288 (long text is now the BEST slice); stream TTFA length-independent 0.5-1.6 s (29.9× at 1897 chars); c=1-8 ladder clean; M35 English battery 23/23 on the same rebuilt stack; Web E2E through the HTTPS edge verified (₹4,999 → "चार हज़ार नौ सौ निन्यानवे रुपये", 12/09/2026 → "बारह सितंबर दो हज़ार छब्बीस"). Production untouched: the hi route + voice records live as a STAGING PROPOSAL carrying the PENDING sentinel (the M24 mechanism); production promotion is a separate founder gate. Naturalness still rides the UNSCORED M38 audition pack — evidence: [M39 milestone doc](../milestones/39-kokoro-hindi-tts-local-web.md), `research/experiments/39-hindi-tts-local-web/evidence/`

- 2026-08-24 — **Approved for Adoption** *(status unchanged; M40 — staging validation replicated, production promotion PREPARED)* — Fresh replicate of every M39 gate on the same production-shaped stack: clean-slice RT-WER **0.0620 (F) / 0.0547 (M)** (gate ≤0.08 passes again; replicate noise ≤0.009), ladder 0.0458/0.0260 with zero truncation, stream TTFA 0.77-1.5 s length-independent, c=1-8 zero errors, M35 English battery 23/23. NEW evidence classes: LIVE billing drill on real Postgres rows (speed/voice/transport invariance at characters=57; mid-stream client abort bills characters=342 per F1; refusals write zero rows), live leak sweep (zero engine tokens; `hf_alpha` as a voice → plain voice_not_found), and the staging rollback drill (hindi_g2p=off → 4 voices + customer-safe 400; restore → 6 voices; ~40 s/direction). The FUTURE production promotion is prepared as one reviewed reversible commit (`registry/proposals.py` + runbook): catalog gains the voices + route, sentinel → founder reference, guards flip — with `ROLLBACK_HINDI_TTS_ROUTE` test-pinned EQUAL to today's live refusal. `make seed-models` now seeds kokoro-82m v2 when present (offline-box parity with E3). Production untouched; promotion + TTS launch remain founder gates — evidence: [M40 milestone doc](../milestones/40-hindi-tts-final-staging-validation.md), `research/experiments/40-hindi-tts-staging-validation/evidence/`

- 2026-08-24 — **Approved for Adoption** *(status unchanged; M42 — PRODUCTION PROMOTION APPROVED, decision F-M42)* — The founder approved speech synthesis as a production service, and the repository's production configuration now declares it. **English** (english-female=af_heart, english-male=am_michael) was already the catalog's `supported` route since M3/F-M5-2; what M42 adds is the production DEPLOYMENT posture — `infra/compose/prod.yml` pins the TTS block explicitly, `make prod-*` carries `--profile tts`, gateway readiness answers for `tts-runtime`, the preflight refuses a prod start whose artifact is not placed for seeding, and the production smoke covers the service. **Hindi** (hindi-female=**hf_alpha**, hindi-male=**hm_psi**) moved from a staging proposal to the LIVE catalog: `intelliai-tts × hi` UNAVAILABLE → **AVAILABLE on kokoro-82m** with the founder reference replacing the pending sentinel, cited to the M38 corpus, the M38 selection baseline, and the M40 staging validation (clean RT-WER 0.0620 / 0.0547 ≤ 0.08 gate; zero truncation; stream TTFA 0.77-1.5 s; EN battery 23/23). One artifact serves both languages — kokoro-82m v2, all four voice packs SHA-256-pinned at revision `f3ff3571…`, Hindi G2P through the pinned espeak-ng binary at the M35 exec boundary (no GPL code in-process, build-verified). Rollback is the git revert of the promotion commit, target `ROLLBACK_TTS_PRODUCTION_ROUTE` restated verbatim and test-pinned (whole-language: voices and route leave together). **This is production APPROVED / PROMOTED IN REPOSITORY — NOT production deployed**: Hostinger, DNS, secrets, and customer traffic remain the separate deployment/launch milestone, and no server was touched — evidence: [M42 milestone doc](../milestones/42-tts-production-promotion.md), [runbook](../ops/model-rollout.md)

**Chatterbox (Resemble)**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: standing roadmap question "should Chatterbox replace Kokoro?" — designated *ownership lineage* for speech synthesis in the 2026-07-31 sweep (MIT end-to-end, zero-shot cloning, 23 languages claimed incl. Hindi, corporate release cadence, built-in watermarker aligning with consent-gated cloning policy). Scored 8.0. Unmeasured on our corpus — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)
- 2026-08-20 — **Researching** *(re-verified; family expanded)* — MIT confirmed per-card at source for base, multilingual V3 (0.5B, 23 langs incl. HI+AR), the dedicated **Chatterbox-Multilingual-hi** finetune (2.14 GB), and **chatterbox-nano** (110M, EN-only, reference-audio-required, "3× realtime on 8 CPU cores" claim). No official training code; a community Indic LoRA exists (evidence fine-tuning is feasible on consumer hardware). Library applies the Perth watermark to all output. Still unmeasured on our corpus — deliberately: the 0.5B class is GPU-tier and outside the small-CPU serve mandate; its role stays P2 ownership/cloning. Deferred, not forgotten — evidence: HF cards + GitHub (2026-08-20), [M32 §6](2026-08-20-tts-model-selection.md)
- 2026-08-20 — **Researching** *(M33 nano measurement attempt — blocked by packaging, recorded)* — Chatterbox-nano could NOT be benchmarked despite MIT weights and a CPU-speed claim worth testing: **no released loader constructs it**. PyPI 0.1.7 and GitHub main both lack the model card's `nano=True` API; the turbo loader pointed at the nano repo fails on filenames, then (symlinked) on architecture shape mismatches (nano t3 = 768-dim vs the class's 1024-dim). Verdict fact for the M33 decision: a candidate that no published library can load is not implementable in a next milestone without vendoring unreleased code — the CPU-speed claim stays CLAIMED, and the M33 matrix carries nano as NOT MEASURED (packaging). Re-attempt when upstream ships the loader — evidence: [M33 §7, §9](2026-08-20-english-tts-model-selection.md), `research/experiments/33-english-tts-selection/harness/m33_nano_bench.py` (outcome header)

**Qwen3-TTS**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: named backup for all three TTS roles (serve/own/wedge). Apache-2.0 (2026-07-31); scored 7.7; explicit fine-tune support; no Indic languages yet — watch its language expansion. Qwen concentration protocol applies — evidence: FOUNDATION_MODELS §3 (dated 2026-07-31)
- 2026-08-20 — **Researching** *(re-verified at repo)* — Open weights since 2026-01-22: `Qwen3-TTS-12Hz-0.6B/1.7B` (Base / CustomVoice / VoiceDesign), Apache-2.0 confirmed per-repo; the "0.6B" repo actually carries 0.9B params (BF16, 2.5 GB). 10 languages — **still no Hindi, no Arabic**. True streaming (97 ms E2E claim) and rapid voice cloning, but sample code is CUDA-only and no training code is published on the card. Verdict unchanged: watch-list backup; wrong size class for the CPU call-center serve tier and no Indic coverage — evidence: HF cards + QwenLM GitHub (2026-08-20), [M32 §6](2026-08-20-tts-model-selection.md)
- 2026-08-20 — **Researching** *(M34 English spike — MEASURED head-to-head vs the incumbent; the "should we switch?" question answered)* — `Qwen3-TTS-12Hz-0.6B-CustomVoice` @ rev `85e237c12c02…`, voice Ryan, official `qwen-tts` 0.1.1 (Apache — **the only fully-permissive challenger stack measured this week**), 24 kHz mono out. On the M33 25-text trap set, same whisper judge: **RT-WER 0.2449 / CER 0.1524 — weakest of the field**, driven by expressive INSERTIONS on dry prompts ("Hello, Sumit." → "Heh heh heh heh heh. Hello, Sumit!"; "uh, um" injected) — conversational-expressiveness training working against deterministic call-center text. OOV preservation GOOD (Sumit/Kavya/Priya/IntelliAI/QwikCart all spoken); slash-dates mangled (TN required); **best question contour measured** ("?" → +3.24 Hz/frame rising slope). Performance: **GPU (RTX 5070, bf16) median RTF 1.486** — slower than playback even on GPU; long ladder clean to 2 039 chars but RTF degrades to 1.65 (205.7 s wall for 124.3 s audio); **CPU (official runtime) RTF 3.054, 6.0 GiB RSS** — works, infeasible; **released lib has NO streaming API** (introspected) so TTFA = full wall (2.9 s for "How are you?"); VRAM 2.8 GiB peak. **M34 verdict: B — KOKORO WINS**; Kokoro hardening proceeds unchanged. Standing revisit trigger: a locally-runnable official streaming/vLLM TTS runtime plus insertion suppression — nothing else moves the decision — evidence: [M34 spike report](2026-08-20-qwen3-tts-english-spike.md), `research/experiments/34-qwen3-tts/evidence/`
- 2026-08-25 — **Researching** *(M44 — Base measured properly + the official fine-tuning recipe run to a verdict; two facts with teeth)* — **Fact 1: M34's terrible quality number was the SPEAKER, not the model.** `Qwen3-TTS-12Hz-0.6B-Base` @ rev `5d83992436…` (Apache-2.0), zero-shot clone conditioned on a calm public-domain LJSpeech reference (LJ001-0004, hash-pinned), same gateway whisper judge as every TTS milestone: trap-set RT-WER **0.0515** (vs CustomVoice-Ryan's 0.2449 — and vs the hardened incumbent's 0.0659), LJ held-out 100 **0.0478** (vs Kokoro 0.0535 on identical texts) — **the first system measured to beat Kokoro on clean-text WER**, 137/137 zero failures. But: OOV set 0.1724 vs Kokoro 0.1085 (brands/tech terms — the product-critical class), GPU RTF 1.42-1.60 / CPU spot RTF 2.85, VRAM 2.9 GiB alloc, and `qwen-tts` 0.1.1 still has **no streaming API** (re-introspected) → TTFA = full wall, vs the incumbent's 0.4-1.6 s streamed. Under the founder's new UX-first rule the responsiveness axis decides: **M44 verdict D — KOKORO STILL WINS**; revisit trigger narrowed to *vLLM/official streaming with TTFA ≤ ~1 s*. **Fact 2: the official SFT recipe FAILED on 0.6B (verdict F)** — single-speaker custom-voice fine-tune on `qwen-en-public-train@v1` (LJSpeech-1.1 public domain, frozen seed-44 splits 1000/50/100, per-row SHA-256 manifest): the released script does not even run on 0.6B unmodified (2048-vs-1024 text-embedding dim crash; minimal faithful fix = the model's own inference-path `text_projection`, documented), and the full 3-epoch run (750 updates, lr 5e-6, bf16, loss 12.27 → 3.33 plateau, exit 0) produced checkpoints that speak fluent LJ-voice audio while **ignoring the input text** ("Thank you for calling." → an expletive; a 16-word in-domain VAL sentence → 655 s of runaway audio; 1/10 VAL texts completed in 25 min). Tiny-overfit control proved the pipeline can fit (loss → 0.056), so the failure is the recipe-on-0.6B, not the harness. Scope honestly bounded: 1.7B (the recipe's evident target) untested — that, on rented GPU, is the only fine-tuning re-entry path — evidence: [M44 report](2026-08-24-qwen3-tts-english-finetuning.md), `research/experiments/44-qwen3-tts-finetuning/evidence/` (incl. `qwen-ft-full-collapse.json`)
- 2026-08-25 — **Researching** *(M45 — the "can runtime work make 0.6B responsive?" question, answered on this hardware; no weight changes anywhere)* — The M44 UX blocker was dissected with GPU-synced profiling: **the sub-talker consumes ~73% of wall (a full HF generate() per 12 Hz frame; ~120 ms/frame vs the 83 ms real-time budget), the Code2Wav decode is ~free (115 s of audio in 0.84 s)** — the model is kernel-launch-bound on the RTX 5070 Laptop. Three real results: (1) **TRUE frame-level streaming was BUILT on the official runtime** (forward hook harvests each frame's codes; growing-prefix decode through the verified-causal codec with a right-edge guard): **TTFA 0.80–0.82 s text-length-independent, continuity exact** (Δlen 0, RMS ≤ 0.0008 vs one-shot decode of the same codes) — the M45 primary gate met, and the harness is reusable as-is on any GPU. (2) A manual sub-talker loop (fastsub, EXPERIMENTAL) trims RTF 1.54–1.65 → 1.39–1.45 and was proven **output-identical** (same-seed unmodified-runtime rep reproduced the judge aggregates to 4 decimals); torch.compile/CUDA-graph attempts failed twice (transformers output buffers vs graph replay — recorded). (3) **vLLM-Omni 0.26.0 measured on this GPU: steady TTFA ~6.5 s, RTF 1.36–3.86** (flashinfer sampler JIT broken on sm_120, worked around; the 97 ms card claim did not transfer). Concurrency collapses on the official runtime (capacity = 1 stream); no VRAM/RAM leaks over 50 requests; sentence-chunking measured and dominated (TTFA 7.5–8.5 s). **The wall is singular: no runtime reached RTF < 1, so streamed playback starves after the first chunk. M45 decision C — still too slow on the available GPU; path DEFERRED** with one cheap re-entry trigger: rent a desktop/datacenter GPU hour and re-run the unchanged harnesses — RTF < 0.8 there reopens the M46 prototype question with streaming already solved. Kokoro production untouched — evidence: [M45 report](2026-08-25-qwen3-tts-low-latency.md), `research/experiments/45-qwen3-tts-low-latency/evidence/`

**IndicF5**
- 2026-08-04 — **Researching** *(seed entry)* — Trigger: the Hindi TTS gated path (M3 license gate named it as the MIT-lineage alternative to espeak-based Hindi) and the Indic wedge lineage. MIT; 11 Indic languages claimed; consent-collected training data (rare in TTS; our data constitution rewards it). Unmeasured on our corpus — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md), [M3 design §8](../milestones/3-tts-design.md) (dated 2026-07-31 / 2026-08-03)
- 2026-08-20 — **Rejected — license provenance** *(the M1.5 "MIT wedge" fails one level deeper)* — Three converging facts, verified at source 2026-08-20: (1) the HF card says `mit`, but the GitHub repo publishes **no LICENSE file**; (2) AI4Bharat's own study of how IndicF5 was built ("Phir Hera Fairy", arXiv 2505.20693) compares training from scratch vs fine-tuning the English **F5-TTS checkpoint** and reports *fine-tuning wins* — and F5's released weights are **CC-BY-NC** (Emilia-trained); (3) the released checkpoint's initialization is stated nowhere. An NC-derivative relabeled MIT would be exactly the "Emilia-contaminated weights" trap FOUNDATION_MODELS §15.4 warned about. Per the license-first law we did **not** download or benchmark it. Also shape-misfit regardless: 0.4B multi-step flow matching (CPU-hostile) + reference-prompt cloning interface (consent governance). **Revival condition**: written AI4Bharat clarification that the released weights were trained from scratch (or from a permissively-licensed base) — then it re-enters as the wedge candidate it was meant to be — evidence: [M32 §7](2026-08-20-tts-model-selection.md)

**F5-Hindi 24KHz (SPRING Lab, IIT Madras)**
- 2026-08-22 — **Researching** *(new entry — the only new CLEAR Hindi specialist in the M38 sweep; measured the same day)* — `SPRINGLab/F5-Hindi-24KHz`: 151M F5-small flow-matching, **CC-BY-4.0**, and — the fact that separates it from the blocked IndicF5 lineage — the card states it was **trained from scratch** on IndicTTS-Hindi + IndicVoices-R (no CC-BY-NC English-F5 initialization). MEASURED (M38 fixed set, CPU, NFE 32, checkpoint `model_2500000.safetensors` sha256 `011d5b81…`, reference = an IntelliAI-synthesized Kokoro WAV — synthetic voice, consent-clean; naturalness biased down by that choice and excluded from the audition pack): 61/61 no failures; clean-slice RT-WER **0.169** (~3× the incumbent's 0.045-0.059); **long text is its best axis** — internal chunking, zero truncation, ladder RT-WER 0.0424 on 118-1897 chars; but **Latin tokens and digits are silently DROPPED** (355-byte Devanagari-only vocab; "IntelliAI…version…release" → all English words gone) — disqualifying for a Hinglish call-center product; **CPU RTF 6.34 median / 15.6 p95, 4.10 GiB peak** — fails CPU-first at any concurrency; cloning-style per-request reference interface (consent governance surface), no streaming. GPU deliberately unrun — no number would change the serving verdict. **Standing value**: proof that a permissive from-scratch Hindi voice trains on open CC-BY data — the recipe class E-TTS-1 belongs to — evidence: [M38 report §5-8, §20](2026-08-22-hindi-tts-model-selection.md), `research/experiments/38-hindi-tts-selection/evidence/f5-hindi-*`

**Supertonic 3 (Supertone)**
- 2026-08-20 — **Researching** *(new entry — the only small tri-language candidate)* — ~99M ONNX, 31 languages incl. EN + **HI** + **AR** (the Arabic open slot's first synthesis candidate), preset voice styles, 44.1 kHz. MEASURED via the `supertonic` PyPI package (supertonic-3 assets, v1.3.1): EN round-trip WER 0.0738 / CER 0.0344 (ties the incumbent's production EN path); HI round-trip WER 0.1524 / CER 0.1211 overall, **clean-slice CER 0.0419** (statistically tied with the Kokoro-hi spike); zero failures on 52 probes incl. the full Hindi paragraph (CER 0.0); solo median RTF ~0.44; **~0.7 GiB peak RSS** (the lightest usable Hindi path measured); warm load 2.9 s; no incremental audio API. **License is the gate**: code MIT but **model weights OpenRAIL-M** — commercial use permitted with behavioral use-restrictions that flow downstream; NOT permissive, so adoption requires an explicit founder call under ADR-0005. No training code. Single-vendor cadence (v2 2025 → v3 2026-04) — evidence: `research/experiments/32-tts-model-selection/evidence/supertonic-*.json`, [M32 §6-7](2026-08-20-tts-model-selection.md)
- 2026-08-20 (M33 follow-up, same day) — **Researching** *(English refresh on the M33 trap set — the measured runner-up)* — Solo M33 numbers: RT-WER **0.0832 / CER 0.0270** (2nd best; "Hello, Sumit." rendered perfectly, names near-perfect — the byte-level frontend never drops words), RTF **0.282** (statistically ties the incumbent), peak RSS **0.65 GiB** (3.7× lighter than torch Kokoro), warm load 1.3 s, 25/25 ok. Still no incremental-audio API, preset shared style vectors only, and the weights remain **OpenRAIL-M** — so it stays the runner-up pending the founder's license stance, not the recommendation — evidence: [M33 §9-15, §20](2026-08-20-english-tts-model-selection.md), `evidence/supertonic-en-m33-bench.json`, `evidence/roundtrip-supertonic-m33.json`
- 2026-08-22 — **Researching** *(M38 Hindi refresh — runner-up DEMOTED on robustness)* — On the M38 fixed Hindi set (F1 preset, solo): clean-slice RT-WER 0.0611 / CER 0.0234 (ties the Kokoro voices), RTF 0.329, peak RSS 1.18 GiB — but **3 hard failures out of 61**: `ValueError` CRASH on Devanagari numerals (`['४','५','९'] unsupported`), and ONNX broadcast CRASHES on Hindi inputs ≥1189 chars (its internal chunking gives up instead of truncating). Hindi digit verbalization is broken where it doesn't crash: "12345" spoken as English digit names, "₹12,500" and "12 अगस्त 2026" round-trip as garbage — the frontend has no Hindi number grammar. License unchanged (OpenRAIL-M weights re-verified 2026-08-22; sherpa-onnx now redistributes int8 builds, inheriting it). Verdict: quality tie, robustness loss, license gate — not the M38 recommendation — evidence: [M38 report §8, §17, §20](2026-08-22-hindi-tts-model-selection.md), `research/experiments/38-hindi-tts-selection/evidence/supertonic-hi-*`

**Magpie-TTS Multilingual 357M (NVIDIA) — with NeMo NanoCodec**
- 2026-08-20 — **Researching** *(new entry; measured on CPU the same day — M33)* — The management-referenced NVIDIA candidate, verified at official sources only (the supplied LinkedIn URL resolved to an unrelated post and the video cannot be watched; recorded honestly in M33 §5). Card facts: 364M AR transformer over **NanoCodec** tokens (22.05 kHz, codec is a separate NOML artifact `nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps`), 12 languages **incl. EN and HI**, 5 preset voices (zero-shot cloning removed upstream), 20 s/utterance + sliding window, "text normalization is required", NeMo-python inference GPU-required; latest rev v2607 (2026-07-21). **License: NVIDIA Open Model License** — commercial + redistribution with attribution, BUT guardrail-preservation conditions, Trustworthy-AI terms, and an NVIDIA-may-update-terms clause → **REVIEW REQUIRED class** under the permissive-only law. **MEASURED (CPU, GGUF v2602 f16 @ rev `452ef560…` through NeMo-Speech.cpp's verified pull, solo run, M33 25-probe set)**: 25/25 ok incl. 795-char long-form via sliding window; **median RTF 1.30** (min 1.06 / max 1.76), median wall 5.4 s for typical sentences, server RSS 1.42 GiB, TTFA = full response (HTTP subset is whole-body). **CPU verdict: a single stream cannot keep up with playback — fails the CPU-first call-center bar regardless of quality**; GPU tier untested locally (364M f16 fits 8 GB — CLAIMED). Round-trip quality + audition samples in the M33 evidence — evidence: [M33 §5-§9](2026-08-20-english-tts-model-selection.md), `research/experiments/33-english-tts-selection/evidence/magpie-cpu-bench.json`

**KittenTTS nano (KittenML)**
- 2026-08-20 — **Rejected — no niche** *(new entry; measured before rejecting)* — 15M ONNX "developer preview", EN-only, 8 preset voices. MEASURED (nano-0.2, revision `9c81564a…`): median RTF 0.3375 — **not faster than the 82M incumbent** (frontend + vocoder dominate at this scale); EN round-trip WER 0.0979 — worse than the incumbent's 0.0773; hard-fails inputs beyond ~1 k chars (no internal chunking; ONNX Expand-node error on the long-paragraph probe); and the pip package phonemizes English through the **GPL espeak chain in-process, unconditionally** — so it is not even license-cleaner. Smaller-but-not-better on every axis that matters here — evidence: `evidence/kitten-nano-bench.json`, `evidence/roundtrip-kitten.json`

**MMS-TTS-hin (Meta)**
- 2026-08-20 — **Rejected** *(new entry — license, recorded so nobody reaches for it)* — Hindi VITS, 36.3M params. **CC-BY-NC 4.0 verified at source 2026-08-20**; not downloaded, not benchmarked. Kept in the ledger for one honest reason: it proves the **VITS-36M size class serves Hindi on CPU** — the architecture datapoint behind the M32 first-fine-tune experiment (an in-house, permissively-trained voice of exactly this class) — evidence: [M32 §6](2026-08-20-tts-model-selection.md)

**F5-TTS**
- 2026-08-04 — **Rejected** *(seed entry)* — Non-commercial license (verified in the 2026-07-31 sweep; scored 0 — "quality-tier leaders, commercially dead to us"). Fails ADR-0005. Answers the roadmap question "should F5-TTS be evaluated?": not under this license; the lineage's compliant relative is IndicF5 (MIT), tracked above — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)

**XTTS-v2 (Coqui)**
- 2026-08-04 — **Rejected** *(seed entry)* — Coqui CPML is non-commercial; named ban in [ADR-0005](../adr/0005-permissive-model-licensing-policy.md) since 2026-07-29, re-confirmed 2026-07-31 (scored 0). Upstream company defunct; re-entry effectively closed.

**Fish-Speech**
- 2026-08-04 — **Rejected** *(seed entry)* — Non-commercial weights license (2026-07-31 sweep, scored 0). Fails ADR-0005.

**Piper (fork)**
- 2026-08-04 — **Rejected** *(seed entry)* — Original archived Oct 2025; the maintained fork is GPL-3.0; maintainer vacancy. Verdict "exit" in the 2026-07-31 sweep (scored 3.5); replaced by Kokoro-82M in the roadmap at M1.5 close — evidence: [FOUNDATION_MODELS §3](../FOUNDATION_MODELS.md) (dated 2026-07-31)
- 2026-08-20 — **Rejected** *(re-verified; unchanged)* — `rhasspy/piper` archived read-only 2025-10-06 (MIT, frozen); successor `OHF-Voice/piper1-gpl` GPL-3.0; a community MIT fork ("piper-plus", espeak-free) exists with unproven maintenance. Exit stands. Its *architecture class* — small per-language VITS voices on ONNX — is, however, exactly the shape of the M32 first-fine-tune experiment, built in-house on clean data instead — evidence: GitHub (2026-08-20), [M32 §6, §22](2026-08-20-tts-model-selection.md)
- 2026-08-22 — **Rejected** *(M38: the Hindi voices specifically, now checked at the data level so nobody reaches for them)* — Three `hi_IN` medium voices exist in `rhasspy/piper-voices` (pratham, priyamvada, rohan). Per-voice MODEL_CARDs verified at source: pratham + priyamvada trained on **CC-BY-NC-SA** data; rohan on IIT-M IndicTTS data under the custom sign-up license (terms PDF unreachable, commercial grant unverified) and finetuned from an EN voice. **All three BLOCKED for commercial use regardless of the runtime question** — this also closes the sherpa-onnx `vits-piper-hi_IN-*` route, which redistributes exactly these voices — evidence: rhasspy/piper-voices hi_IN MODEL_CARDs, k2-fsa/sherpa-onnx apk script (2026-08-22), [M38 §5-6](2026-08-22-hindi-tts-model-selection.md)

### serving-chain components

**espeak-ng in-process phonemization (phonemizer-fork / espeakng-loader chain)**
- 2026-08-04 — **Rejected** *(seed entry)* — GPL-3.0 arriving transitively inside Apache models' default G2P pipelines (the M3 discovery that motivated Gate 1's ordering). Banned in-process platform-wide; the tts image is GPL-free by construction (build fails if the chain is importable). A *subprocess-isolated* espeak spike is a distinct architecture and would enter the ledger as its own entry if pursued for Hindi — evidence: [M3 design §8](../milestones/3-tts-design.md), [M3 review](../milestones/3-tts-review.md) (dated 2026-08-03)

**NeMo-Speech.cpp (NVIDIA native speech runtime)**
- 2026-08-20 — **Researching** *(new entry — runtime component, M33)* — Apache-2.0 C++ runtime on ggml/llama.cpp for the Nemotron/Magpie family: `synthesize` CLI, OpenAI-compatible HTTP subset (`/v1/audio/speech`, whole-body only — streaming synthesis explicitly not in the subset; `speed` fixed at 1.0), Riva gRPC, optional **Sparrowhawk text normalization** (FAR grammars — a ready-made implementation of the normalization layer M32 §15 called for), CPU/Metal/Vulkan/CUDA backends. Built clean in WSL (`cpu-tts` preset; HTTP needs `-DNEMO_SPEECH_BUILD_HTTP=ON` — the preset silently omits it, and a stale binary reproduced the M32 "healthy-but-wrong" lesson in miniature). **Very young upstream: 8 commits / 64 stars at verification** — single-digit maturity for a serving dependency. Its model pulls are identity-disciplined (pinned revision + SHA-256 verification built in). Useful regardless of Magpie's verdict: the Sparrowhawk TN path and the GGUF conversion tooling are the reusable pieces — evidence: [M33 §5, §18](2026-08-20-english-tts-model-selection.md)

**espeak-ng subprocess phonemization (binary behind an exec boundary)**
- 2026-08-20 — **Researching** *(new entry — the M3 spike, now measured)* — The distinct architecture the 2026-08-04 entry reserved: the GPL **binary** invoked as a subprocess (the ffmpeg posture — no linking, no derivative-work surface, binary swappable), which the M3 license review §8 already named the defensible shape. M32 measured both sides: (1) **what it buys** — Kokoro Hindi (clean-slice round-trip CER 0.0347 through E3) and, run as the EN OOV fallback, a halving of extended-probe EN WER (0.0773 → 0.0344; "IntelliAI"/"Kavya" rescued); (2) **its faithfulness** — phoneme parity vs the in-process chain on 29 hi/mixed texts: 16/29 byte-identical, every mismatch one of three mechanical transforms (punctuation preservation, `(en)/(hi)` switch-marker stripping, misaki's Apache-licensed diphthong table), zero divergent phonemizations; espeak-ng 1.51 CLI vs espeakng-loader data — the production implementation must pin one espeak-ng build. Not adopted here (M32 is research-only); the adoption decision — including the policy call that a GPL binary at an exec boundary satisfies the permissive-only law the way ffmpeg does — is the founder gate of the next milestone — evidence: `evidence/espeak-parity.json`, [M32 §7, §21](2026-08-20-tts-model-selection.md)

---

## Open research threads (no candidate or no measurement yet)

Thread order below is historical; attention across threads follows the
living research priorities ([RESEARCH_FRAMEWORK.md §16](RESEARCH_FRAMEWORK.md)).

| Thread | Standing question | State (2026-08-05, updated at the STT intake sweep) |
|---|---|---|
| **Arabic STT** | Which engine serves Arabic transcription? | **Candidate slot now filled; corpus slot still empty.** Cohere Transcribe Arabic registered 2026-08-05 (Apache-2.0 verified at source, purpose-built for dialects + AR-EN code-switching); the academic specialist ArTST was rejected the same day on CC-BY-NC. Whisper's Arabic remains the unevaluated null hypothesis. **The binding constraint is no longer "no candidate" — it is that no Arabic corpus, baseline, or benchmark exists**, so nothing here can yet be measured. |
| **Arabic TTS** | Which engine serves Arabic synthesis? | Updated 2026-08-20 (M32): **first candidate registered** — Supertonic 3 claims Arabic among its 31 languages (quality unmeasured for ar; weights OpenRAIL-M, founder review required). Kokoro still has no Arabic. Corpus/baseline slots remain empty. |
| **Hindi TTS** | Which compliant path un-gates Hindi synthesis? | **CLOSED 2026-08-24 (M42): promoted to production posture.** Kokoro Hindi serves hindi-female (hf_alpha) and hindi-male (hm_psi) through the existing M35-M37 architecture; the live catalog routes hi to kokoro-82m with the founder approval F-M42 and the M38→M40 evidence chain. Deployment (Hostinger) is the only remaining gate; naturalness improvement remains the E-TTS-1 thread ([M42 doc](../milestones/42-tts-production-promotion.md)). |
| **Hindi STT improvement** | Fine-tune Whisper vs adopt an Indic engine? | Governed by [RESEARCH_FRAMEWORK §9](RESEARCH_FRAMEWORK.md): needs the wedge gap *measured* first (one anecdotal data point exists; corpus ≥100 gate from M2.5 C3 applies). Three registered shapes now exist for the eventual comparison: in-lineage fine-tune (IndicWhisper), dedicated Indic engine (IndicConformer), multilingual generalist claiming Hindi (Qwen3-ASR, Voxtral). **Resolved by M15D→M26 (noted 2026-08-20):** the Qwen3-ASR fine-tune lineage won — `qwen3-asr-0.6b-hi-ft-e3@v1` serves the promoted Hindi route (CER 0.11612, −69 % vs incumbent; founder decision F-M26). |
| **Multilingual TTS shape** | One multilingual engine or per-language engines? | Updated 2026-08-20 (M32): first real evidence — intelligibility TIES between the multilingual incumbent (Kokoro EN+HI, one 2.2 GiB process, voices are +0.5 MB packs) and a second small multilingual engine (Supertonic); no per-language specialist survives licensing today (MMS NC, Piper GPL, IndicF5 provenance). M32 recommends ONE multilingual serve engine now, with the owned per-language specialist entering via the E-TTS-1 fine-tune ([M32 §21-22](2026-08-20-tts-model-selection.md)). |
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

---

## Fine-tuning experiment research — appended 2026-08-10

Trigger: founder directive to research and recommend the pretrained base
for IntelliAI's first fine-tuning experiment and design a public-data
experiment. Full report:
[2026-08-10-first-finetuning-experiment.md](2026-08-10-first-finetuning-experiment.md).
**Statuses of existing candidates unchanged.** New intakes and
corrections below; every licence was read at source on 2026-08-10.

### New intakes (Gate 0 + Gate 1 licence screen, same day)

**XLS-R 300m / 1b / 2b (Meta)**
- 2026-08-10 — **Researching** *(Gate 0 intake)* — Trigger: founder-named candidate family for the fine-tuning-base decision. **Licence `apache-2.0` verified at source on all three HF cards 2026-08-10.** wav2vec 2.0 SSL encoders (436K h, 128 languages, HI+AR in pretraining tags); ASR requires per-language CTC fine-tune (official HF recipe). Screened as fine-tuning base: structurally regressive for our product — lowercase, unpunctuated, vocab-bound output, no timestamps; best documented community Hindi fine-tunes WER 0.34–0.46 (with/without LM), an order weaker than in-lineage Whisper fine-tune evidence. FOUNDATION_MODELS §1 score 6.9 (report §4) — evidence: report §§3–4, §15, §19

**w2v-BERT 2.0 (Meta)**
- 2026-08-10 — **Researching** *(Gate 0 intake)* — Trigger: same decision; the Seamless-era encoder released permissively where SeamlessM4T itself is NC. **Licence `mit` verified at source 2026-08-10.** ~600M Conformer encoder, 4.5M h / 143 languages incl. HI+AR; official `Wav2Vec2BertForCTC` recipe (14 h → 32% WER Mongolian on a 16 GB V100 — publisher blog claim). Same CTC product regressions as XLS-R; **not in the Optimum ONNX supported list** (verified 2026-08-10). Strongest permissive SSL encoder on pretraining scale; not a first base. Score 6.7 — evidence: report §§3–4, §15

**MMS 1b-all / 1b-fl102 (Meta)**
- 2026-08-10 — **Rejected** *(Gate 0 intake; licence alone)* — Registered and rejected in the same sweep, the ArTST pattern. **Licence `cc-by-nc-4.0` verified at source on both cards 2026-08-10** — fails [ADR-0005](../adr/0005-permissive-model-licensing-policy.md) regardless of its 1,162-language coverage (HI+AR both in scope). No dossier (cheapest-kill-first). Re-entry only on a permissive re-release.

### Corrections and landscape evidence appended to existing entries

**Whisper (all sizes) — licence record correction**
- 2026-08-10 — *status unchanged (Approved for Adoption / Researching per row)* — **Per-artifact licence correction [FACT]:** the HF cards our ArtifactStore pins (`openai/whisper-small`, `-medium`, `-large-v3`) read **`apache-2.0`**; `-large-v3-turbo` reads **`mit`**; the OpenAI GitHub repository is MIT; faster-whisper/CTranslate2 MIT (unchanged from Gate 1). Prior ledger rows say "MIT" from the repo-chain read. Both grants are permissive with derivative rights — **no verdict changes** — recorded because verdicts bind per artifact distribution. Additional fine-tuning evidence recorded (external claims, sources in report §§1,6–7): whisper-small Hindi CV11 63.5→32.0 WER after ~8 h fine-tune (official HF recipe); IndicWhisper (medium base) 13.6 avg WER across 7 Hindi benchmarks; large-v2 Arabic MGB-2 34.7→15.5 full FT; **fine-tuned whisper-small underperforms zero-shot large-v2 on every published Arabic test set** — a base-size warning binding on any future Arabic fine-tune. `ct2-transformers-converter` officially supports fine-tuned checkpoints.

**Qwen3-ASR 0.6B/1.7B — open questions discharged**
- 2026-08-10 — *status unchanged (Researching)* — **Arabic coverage CONFIRMED [FACT]:** the official repository's 52-language list includes both Hindi and Arabic (read 2026-08-10), discharging the dossier's "Arabic unresolved" question. **First-party fine-tuning support CONFIRMED [FACT]:** the repo publishes a Qwen3-ASR-Finetuning path and the technical report describes an open-sourced fine-tuning framework. This amends the Gate 2 structural finding: **one permissive candidate besides Whisper now claims EN+HI+AR.** Named second-choice fine-tuning lineage in the 2026-08-10 report; unmeasured on our corpus; GPU-published operating points and the two-model timestamp story stand.

**Parakeet (NVIDIA) — landscape note**
- 2026-08-10 — *status unchanged (Researching)* — NVIDIA's **Parakeet-RNNT-1.1B multilingual** (NGC) lists `hi-IN` and `ar-AR` among 25 languages but under the "AI Foundation Models Community License", not CC-BY-4.0 [FACT, read 2026-08-10]. [INFERENCE] Fails ADR-0005's permissive-only rule; would require its own Gate 0 entry and licence read if ever triggered. The permissive `tdt-0.6b-v3` remains European-only — the coverage verdict on this row is unchanged.

**SeamlessM4T v2 — re-verification**
- 2026-08-10 — *status unchanged (Rejected)* — `cc-by-nc-4.0` re-read at source 2026-08-10; unchanged from the 2026-08-05 verdict.

### Report recommendation (research → founder; no status change)

- 2026-08-10 — The report recommends **whisper-small (LoRA, Hindi, ≤10 h commercially-clean public data)** as the first fine-tuning experiment base, **Qwen3-ASR 0.6B** as second choice, and a staged (not balanced-mixture) language order: Hindi now, Arabic after its ruler exists, English closed per Stage 2. The experiment proves Ladder Stage 0→1 machinery and feeds the Stage 3 gate a ready remedy; it proposes **no serving change**. Founder decision pending — evidence: [2026-08-10-first-finetuning-experiment.md](2026-08-10-first-finetuning-experiment.md)

---

---

## Small-model strategy sweep — appended 2026-08-11

Trigger: management directive to investigate a small-model / modular
multilingual STT architecture across EN·HI·AR·TA·ML·ZH. Full report:
[2026-08-11-small-asr-model-strategy.md](2026-08-11-small-asr-model-strategy.md).
**Statuses of prior candidates unchanged.** All licences below read at
source 2026-08-11. TA/ML/ZH are **not yet product languages** — every
entry here is research pending the founder's policy decision.

### New intakes (Gate 0 + licence screen, same day)

**IndicConformer ta / ml per-language checkpoints (AI4Bharat)**
- 2026-08-11 — **Researching** *(Gate 0 intake)* — Trigger: TA/ML slot candidates for the modular strategy. **MIT verified at source on both cards**; ~120M each, Conformer hybrid CTC+RNNT, AI4Bharat NeMo fork (`nemo-v2`) required, repos gated (contact-info). Publisher benchmark (IndicVoices spontaneous, 600M sibling): ta 31.2 / ml 40.5 WER vs Whisper ta 78.4 / ml 148.6 [CLAIM, ACL 2024 paper]. ONNX/CPU export undocumented — the named spike before any adoption. Same remote-code condition as the 600M row.

**Dolphin base 140M / small 372M (DataoceanAI)**
- 2026-08-11 — **Researching** *(Gate 0 intake)* — Trigger: permissive zh backup. **Apache-2.0 verified at source for code AND weights** (prior NC suspicion was wrong for this artifact). CTC-attention, 40 Eastern languages + 22 zh dialects claimed; zh-specific WER not published; 2026 streaming variants noted. No Arabic.

**OWSM v3.1 / v4 (CMU/ESPnet)**
- 2026-08-11 — **Researching** *(Gate 0 intake)* — Trigger: fully-public-data Whisper-style lineage, 102M–1B. **CC-BY-4.0 verified at source.** Coverage of our six languages unenumerated on cards; ESPnet serving; per-language numbers Unknown. Attribution condition (CC-BY class) applies.

**FireRedASR-AED-L (FireRedTeam)**
- 2026-08-11 — **Researching** *(Gate 0 intake)* — Trigger: near-SOTA permissive zh (AISHELL-1 CER 0.55 [CLAIM, repo]). **Apache-2.0 verified at source.** 1.1B — outside the small class; no streaming/timestamps/FT scripts/CPU story documented; ≤60 s audio cap. Registered for completeness of the zh universe.

**Paraformer-zh (FunASR/Alibaba)**
- 2026-08-11 — **Researching — work halted** *(Gate 0 intake; licence contradiction)* — HF mirror card tags `apache-2.0`, but the canonical ModelScope/FunASR distribution binds weights to the FunASR Model License Agreement. A mirror tag is not a grant. *Clarification required:* an Alibaba-published permissive licence on the distribution we would pin. Until then no Gate 2 work.

**SenseVoice-Small (FunAudioLLM)**
- 2026-08-11 — **Rejected** *(Gate 0 intake; licence alone)* — Weights under the **FunASR Model Open Source License** (read at source): "provided for reference and learning purposes only", mandatory naming/attribution, conduct clause with automatic forfeiture, unilateral revision, **no express commercial grant**. Code MIT; weights are not. Fails ADR-0005. Re-entry on a permissive re-licence only.

**TeleSpeech-ASR (Tele-AI)**
- 2026-08-11 — **Rejected** *(Gate 0 intake; licence alone)* — TeleSpeech Community License: commercial use requires application and **written approval** from China Telecom. An approval-gated grant is not a permissive licence. Fails ADR-0005.

**ECAPA VoxLingua107 LID (SpeechBrain)** *(serving-chain component)*
- 2026-08-11 — **Researching** *(Gate 0 intake)* — Trigger: router/LID component for the hybrid-pool architecture (needed only if undeclared-traffic volume ever justifies acoustic LID; declaration-first law stands). **Apache-2.0 verified at source**; 107 languages incl. all six targets; 6.7% VoxLingua dev error [CLAIM]; utterance-level only — code-switch routing law applies. Alternative recorded: whisper-tiny `detect_language` (39M, MIT). facebook/mms-lid is **CC-BY-NC-4.0 (source, 2026-08-11)** — excluded without registration.

### Evidence appended to existing entries

**Whisper — per-language paper numbers now on record [CLAIM, OpenAI paper Appendix D, read 2026-08-11]**
- 2026-08-11 — *status unchanged* — FLEURS WER by size: **ta** small 35.2 / large-v2 17.5; **ml** ~100+ at every size (small 100.9, large-v2 100.7) — **Malayalam is effectively unsupported by the entire Whisper family**; **zh** small 20.8 / medium 12.1; CV9: ta small 28.7, ml small 225.8, zh small 29.4. Product consequence: Whisper can be the ta floor and is a weak zh engine, but **the ml slot cannot be served by this lineage** — the strongest single piece of evidence for the modular architecture.

**Qwen3-ASR 0.6B/1.7B — coverage boundary + small-variant facts [FACT, official card/repo/tech report, 2026-08-11]**
- 2026-08-11 — *status unchanged (Researching)* — Full official language list obtained: 30 languages + 22 zh dialects; **Tamil and Malayalam absent** — the lineage cannot be the sole engine for a six-language product. FLEURS WER (0.6B/1.7B): zh 2.88/2.41 · hi 19.12/17.15 · ar 25.51/16.98; LID 96.8%/97.9%. **Official GGUF exists (ggml-org, Q8_0 805 MB)** — first credible CPU path; RTF unmeasured. Fine-tuning recipe is **full-FT only, no LoRA documented**; VRAM figures Unknown. ForcedAligner's 11 languages **exclude hi, ar, ta** — timestamp gap on exactly our slot languages except zh.

**Omnilingual ASR — six-language coverage + product cap [FACT, official repo, 2026-08-11]**
- 2026-08-11 — *status unchanged (Researching)* — `tam_Taml`, `mal_Mlym`, `cmn_Hans/Hant` confirmed in the official language list alongside eng/hin/arb(+dialects): **the only permissive lineage covering all six targets**. But CTC/LLM variants accept **audio < 40 s** (vs our 600 s product ceiling) and no CPU path is documented — long-tail asset, not a slot candidate today.

### Report recommendation (research → founder; no status change)

- 2026-08-11 — The report recommends the **hybrid pool** (small multilingual default + evidence-won per-language specialist slots — the in-force target architecture at full width) and a **two-arm first experiment**: E1 Hindi LoRA on whisper-small (unchanged) + a zero-shot CPU bracket (whisper-small vs Qwen3-ASR 0.6B GGUF vs IndicConformer on the frozen Hindi eval; Qwen3 0.6B on CV26 zh-CN test). Founder decisions required: TA/ML/ZH policy extension; experiment approval — evidence: [2026-08-11-small-asr-model-strategy.md](2026-08-11-small-asr-model-strategy.md)

---

---

## Milestone 15B — first Hindi evidence + candidate spikes (appended 2026-08-11)

Full report: [2026-08-11-15b-ingestion-baseline-report.md](2026-08-11-15b-ingestion-baseline-report.md).
**No status changes.** Dated evidence appended below; frozen manifests
`stt-hi-fleurs-eval@v1` (sha256 `5b2c8396…`), `hi-fleurs-train@v1`
(`93426dff…`, 6.61 h), `stt-zh-fleurs-eval@v1` (`8fdbe098…`) — FLEURS,
CC-BY-4.0, contamination `known_overlap` recorded (comparability rulers;
the approved primaries remain access-blocked pending an HF/MDC account).

**Whisper Small (faster-whisper) — first natural-speech Hindi measurement**
- 2026-08-11 — *status unchanged (Approved for Adoption)* — **[EVIDENCE]**
  Named baseline `2026-08-11-intelliai-stt-hi-whisper-small-int8-fleurs`,
  product path, 120 clips / 3,042 ref words: **cer_unicode 0.2919 ·
  wer_unicode 0.5624** (S/I/D 0.412/0.036/0.114) · recognition_rtf 0.347 ·
  0 hallucinated words on both probes · 0 failures. The Hindi wedge gap is
  now measured, not anecdotal. Real-speech `hi` RTF 0.347 bounds the 9.4×
  declaration figure as a non-speech artifact — evidence:
  [EvalRun](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15b-fleurs.json)

**Qwen3-ASR 0.6B — first CPU measurements (research-sandbox spike, NOT ledger-grade)**
- 2026-08-11 — *status unchanged (Researching)* — **[SPIKE — no
  MeasurementRoute; read beside EvalRuns, never differenced]** Official
  GGUF (Q8_0, sha256 `bca25981…` + mmproj `41a342b5…`), llama.cpp b10344
  CPU, ctx 4096, identical frozen-eval clips: **Hindi CER 0.0796 vs the
  incumbent's 0.2515 on the same 30 clips (~3.6×)**, net RTF 0.184;
  **Chinese CER 0.1313, net RTF 0.086**; **peak RSS 1,515 MiB at ctx 4096**
  (default 32k ctx allocates 8,238 MiB — configurational, not fundamental);
  0 hallucinated words on all probes; language tag self-reported correctly
  30/30 in both languages. Consequence: the conditional Qwen3 engine-adapter
  milestone is now evidence-justified — a switching test requires the
  product path, which requires an adapter — evidence:
  [spike records](../../research/experiments/15b-qwen3-gguf-spike/)

**IndicConformer — evaluation blocked (recorded verdict)**
- 2026-08-11 — *status unchanged (Researching)* — **[BLOCKED]** Two
  independent grounds, verified at source 2026-08-11: repos `gated: auto`
  with anonymous fetch 401 (no HF token on the machine), and the 600M
  card's `custom_code` requirement meets the unruled remote-code
  security-review prerequisite (5.3). A ~5-minute founder HF action clears
  the first; the review must clear the second before any in-process run.

---

---

## Milestone 15C — the official Hindi ruler and baseline (appended 2026-08-11)

Full report: [2026-08-11-15c-hindi-eval-baseline.md](2026-08-11-15c-hindi-eval-baseline.md).
**No status changes.** Gated access unblocked by the founder (HF terms
accepted; read token held outside the repository). Frozen:
**`stt-hi-public-eval@v1`** (sha256 `cf643146…`), 151 IndicVoices
hindi/valid clips + 2 probes, **speaker-disjoint by construction**
(32-speaker frozen roster, enforced on every future training freeze),
revision-pinned (`c96f9088…`), byte-reproducible (ingest ×2 identical,
freeze ×2 identical).

**Whisper Small (faster-whisper) — OFFICIAL Hindi baseline**
- 2026-08-11 — *status unchanged (Approved for Adoption)* — **[EVIDENCE]**
  Named baseline `2026-08-11-intelliai-stt-hi-whisper-small-int8-public`,
  product path, 151 spontaneous-heavy clips / 3,258 ref words:
  **cer_unicode 0.3629 · wer_unicode 0.6590** (S/I/D 0.476/0.033/0.150) ·
  recognition_rtf 0.785 · 0 hallucinated words · 0 failures. Replicate
  committed: CER 0.3772 — **documented engine variance** (34/153
  hypotheses differ across identical runs; temperature-fallback
  sampling), so a 15D improvement claim must exceed ΔCER ≈ 0.015 to
  clear the noise band. The FLEURS comparability baseline (CER 0.2919)
  is retained and is a different ruler — never differenced. The official
  corpus is harder (93% spontaneous/conversational): the Hindi wedge gap
  at product scale is now **CER 0.36 / WER 0.66** — evidence:
  [official](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public.json) ·
  [replicate](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public-replicate.json)

---

---

## Milestone 15D — E1 Hindi LoRA: a measured failure (appended 2026-08-11)

Full report: [2026-08-11-15d-e1-hindi-lora.md](2026-08-11-15d-e1-hindi-lora.md).
**No status changes.** The first fine-tune of the training program ran
end-to-end on the local GPU and was evaluated on the frozen primary.

**whisper-small-hi-lora-e1 (IntelliAI fine-tune candidate; identity = base 973afd24 + hi-public-train@v1 a4748dee + LoRA r32/α64/lr1e-3/2000steps/seed 20260811)**
- 2026-08-11 — **Rejected** *(evidence; first entry for this artifact)* —
  **[EVIDENCE]** On `stt-hi-public-eval@v1` (research-harness route,
  int8, same ruler and decode policy as the baseline): **cer_unicode
  0.9049 (replicate 0.9064) vs the official baseline 0.3629** —
  +0.542 absolute, ~40× the measured 0.014 noise band; wer_unicode
  1.158 (>1: insertion_rate 0.829, degenerate over-generation);
  **56 hallucinated probe words vs 0** (safety disqualifier at engine
  level); recognition_rtf 2.9–4.2 (breaches the CPU serving SLO).
  English intact (WER 0.0; one probe word). Root-cause hypothesis:
  over-training (train loss 0.0053 vs val 0.4654 at lr 1e-3 ×
  ~13 epochs) damaging decode calibration. Remediation candidates
  recorded in the report (§12); earlier checkpoints preserved on disk.
  Re-entry: a new recipe is a NEW candidate identity with its own
  entry — evidence:
  [candidate](../../ml/evaluation/stt/results/2026-08-11-research-whisper-small-hi-lora-e1-hi-15d.json) ·
  [replicate](../../ml/evaluation/stt/results/2026-08-11-research-whisper-small-hi-lora-e1-hi-15d-replicate.json) ·
  [en regression](../../ml/evaluation/stt/results/2026-08-11-research-whisper-small-hi-lora-e1-en-15d-regression.json) ·
  [run record](../../weights/e1-hi-lora/run-record.json)

**What the milestone proved for the program [FACT]:** the full ladder
Stage 0→1 machinery — frozen manifests (train `a4748dee`, 10.0 h,
speaker-roster enforcement observed rejecting 40 leaked speakers),
deterministic training (176 min, peak 3,354 MiB of 8,150 on the local
RTX 5070), merge → CT2 → hash-pinned research artifact → standard-
runner evaluation — works end-to-end and caught a bad model **before**
any promotion machinery could see it. A recorded failure is the
system working (Part 10, law 13).

**Consequence for priorities:** the Qwen3-ASR engine-adapter track
strengthens (its sandbox Hindi reading now stands against a failed
first fine-tune); the cheap E1b remedies (checkpoint sweep, lower LR /
fewer epochs) are queued for founder decision, not auto-run.

---

---

## Milestone E1b — checkpoint sweep + conservative retrain: the cause space collapses (appended 2026-08-12)

Full report: [2026-08-12-e1b-hindi-lora-conservative.md](2026-08-12-e1b-hindi-lora-conservative.md).
**No status changes.** Same frozen benchmark, ruler, decode policy and
harness as 15C/15D; decision matrix fixed before any number existed.

**whisper-small-hi-lora-e1 checkpoints 500/1000/1500 (same artifact lineage as the rejected E1; identity = E1 run + step)**
- 2026-08-12 — **Rejected** *(evidence; sweep of the preserved E1 run)* —
  **[EVIDENCE]** On `stt-hi-public-eval@v1`: cer_unicode **0.7295 /
  0.8132 / 0.7319** vs baseline 0.3629; hallucinated probe words
  **51 / 59 / 56** vs 0; recognition_rtf 4.89 / 2.93 / 2.70. **The E1
  damage was fully established by step 500 (~3 epochs) — "evaluate an
  earlier checkpoint" is closed as a remedy** — evidence:
  [ck500](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1-ck500-hi-e1b-sweep.json) ·
  [ck1000](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1-ck1000-hi-e1b-sweep.json) ·
  [ck1500](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1-ck1500-hi-e1b-sweep.json)

**whisper-small-hi-lora-e1b (NEW candidate identity; base 973afd24 + hi-public-train@v1 a4748dee + LoRA r32/α64/lr1e-4/600steps/warmup60/val-selected ck600/seed 20260811)**
- 2026-08-12 — **Rejected** *(evidence; first entry for this artifact)* —
  **[EVIDENCE]** Training was textbook-healthy (train 0.3502; validation
  monotone 0.6961→**0.4064**, better than E1's best; no overfit signal;
  29.9 min, peak 3,353 MiB local RTX 5070) and the benchmark still
  failed it: **cer_unicode 0.7181 (replicate 0.6535) vs 0.3629**;
  wer_unicode 1.0028/0.9220; **74 hallucinated probe words vs 0 — the
  worst measured in this program**; recognition_rtf 6.10/2.80;
  primary↔replicate spread 0.0646 CER (4.6× the 0.014 band —
  degenerate decoding is unstable, not just slow). English intact
  (WER 0.0; one probe word). **Refuted as primary cause: over-training,
  learning rate alone, checkpoint choice, and validation loss as a
  decode-health proxy.** Substitutions BEAT the baseline (0.4236 vs
  0.4764) while insertions/probes destroy the result: the failure
  lives in generation/stopping behavior. Prime suspect recorded for a
  founder-gated E1c: decode-mode mismatch (trained `<|notimestamps|>`
  labels vs timestamped product decode) — diagnostic costs hours
  (report §11). Re-entry: a new recipe is a NEW candidate identity —
  evidence:
  [candidate](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1b-hi-e1b.json) ·
  [replicate](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1b-hi-e1b-replicate.json) ·
  [en regression](../../ml/evaluation/stt/results/2026-08-12-research-whisper-small-hi-lora-e1b-en-e1b-regression.json) ·
  [run record](../../weights/e1b-hi-lora/run-record.json)

**Consequence for priorities:** the fine-tuning ladder pauses — no
third blind LoRA arm. The **Qwen3-ASR engine-adapter** track is now
the highest-value Hindi move (sandbox CER 0.0796 vs two failed tunes);
if fine-tuning resumes it resumes as the E1c diagnostic, founder-gated.

---

---

## Milestone 15E — Qwen3-ASR engine adapter: the first positive result (appended 2026-08-12)

Full report: [2026-08-12-qwen3-asr-adapter-evaluation.md](2026-08-12-qwen3-asr-adapter-evaluation.md).
The candidate now has a real engine behind the runtime contract; these
are standard-runner EvalRuns on the frozen manifests, not spike readings.

**Qwen3-ASR 0.6B (ggml-org Q8_0 GGUF @ 928ab958, pins bca25981/41a342b5; upstream Qwen/Qwen3-ASR-0.6B @ 5eb14417, apache-2.0 verified on the 0.6B card 2026-08-12)**
- 2026-08-12 — **Researching → measured STRONG CANDIDATE** *(evidence;
  promotion NOT granted — switching test + productization owed)* —
  **[EVIDENCE]** On `stt-hi-public-eval@v1` (sha cf643146, 153 clips,
  same ruler/harness/decode-discipline as the official baseline), via
  the new `qwen3-asr` engine (pinned llama.cpp b10344 llama-server,
  ctx 4096, greedy): **cer_unicode 0.1457 (replicate 0.1446 — spread
  0.0011) vs the incumbent's 0.3629 — −60%, ~15× the noise band**;
  wer_unicode 0.2851 (replicate identical); insertion_rate 0.0169
  (HALF the incumbent's); **0 hallucinated probe words** (six probes
  across hi/en/zh, all silent); recognition_rtf 0.207/0.152, p50
  1.45 s, **p95 3.32 s vs the incumbent's 24.2 s**; 0 failures.
  English intact (WER 0.0, RTF 0.061). **Chinese cer_unicode 0.1129**
  on the frozen zh comparability manifest, RTF 0.094. Peak RSS
  **1,362.5 MiB** (ctx-4096 KV pre-allocated; flat under load); model
  load 1.0 s. The incumbent has now shown measured weakness on its own
  primary — the roadmap's precondition for a challenger is met by
  ledger evidence. Owed before any promotion: vendored/reviewed
  llama.cpp build, concurrency ladder, the formal switching test, and
  the hi timestamp-granularity decision (no aligner for hi) — evidence:
  [hi](../../ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-hi-15e.json) ·
  [replicate](../../ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-hi-15e-replicate.json) ·
  [en](../../ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-en-15e.json) ·
  [zh](../../ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-zh-15e.json) ·
  [RSS/load](../../research/experiments/15e-qwen3-adapter/rss-eval-session.json)

**whisper-small-hi-lora-e1b — E1c decode-mode diagnostic [SPIKE, arms compare to each other only]**
- 2026-08-12 — *status unchanged (Rejected)* — The E1b close-out's
  prime remediation suspect (`<|notimestamps|>` training labels vs
  timestamped product decode) is **REFUTED**: decoding the same failed
  artifact with `without_timestamps=True` made it 2.5× WORSE (CER
  0.75→1.90, insertions 0.56→1.85, probes 116→66 on the 30-clip
  subset). The adapter damaged sequence termination in BOTH decode
  modes. The whisper-small LoRA r32/q+v family is dead on three
  independently tested axes (schedule, checkpoint, decode mode); the
  fine-tuning pause is now a measured conclusion — evidence:
  [e1c-results.json](../../research/experiments/15e-qwen3-adapter/e1c-results.json)

**Consequence for priorities:** Milestone 16 should be the Hindi
switching test + Qwen3 productization plan (vendored binary,
concurrency ladder, segment-granularity decision). Whisper remains the
serving incumbent until that test rules; nothing changed in production.

---

---

## Milestone 16 — Hindi switching test + production-readiness validation (appended 2026-08-12)

Full report: [2026-08-12-qwen3-hindi-switching.md](2026-08-12-qwen3-hindi-switching.md).
Validation milestone: no accuracy re-litigation, no promotion — the
operational half of the switching decision, measured.

**Qwen3-ASR 0.6B (same identity as the 15E entry: ggml-org @ 928ab958, pins bca25981/41a342b5; runtime NOW ALSO PINNED — llama.cpp b10344 (7a20b417f), six binaries hashed, verify-at-load)**
- 2026-08-12 — **measured STRONG CANDIDATE → switching_validated
  (READY FOR LOCAL CANARY)** *(evidence; promotion still NOT granted)* —
  **[EVIDENCE]** Switching mechanism proven: `research:intelliai-stt-switch`
  (hi→challenger, en/default→incumbent) through ONE multi-slot process
  reproduced **CER 0.1457 / WER 0.2851 bit-identically** with 0 probes
  and 0 failures while English stayed on whisper-small at WER 0.0 in
  the same process. Concurrency ladder (median frozen clip 6.88 s,
  pool 2/8): stable at c=1/5/10 with 0 errors, **saturation 2.28–2.34
  rps ≈ 16× real-time aggregate vs whisper's 0.65–0.68 rps (3.4×)**;
  c=20 sheds exactly at the admission boundary as clean 503s; peak RSS
  1,538.5 MiB; CPU ~70% at saturation. **[DRILL]** Child-process death
  → bounded 500 in ~2.1 s, incumbent slot UNAFFECTED, restart clean,
  0 orphans; drill caught an engine-name leak in the timeout message —
  fixed same-day, regression-tested. Findings that gate a production
  canary: `/info` readiness is not slot-truthful after child death;
  supervised child restart absent; Linux runtime build needs its own
  pin table. Fallback decision: NO per-request fallback (double-compute
  and double-metering hazards); rollback = registry route revert,
  precondition (slot isolation) drilled. Hindi segment decision:
  single-span output satisfies the public contract (no word-timestamp
  promise exists); the verbose_json segment-count delta is disclosed
  for the founder's decision — evidence:
  [switch hi](../../ml/evaluation/stt/results/2026-08-12-research-intelliai-stt-switch-hi-16.json) ·
  [switch en](../../ml/evaluation/stt/results/2026-08-12-research-intelliai-stt-switch-en-16.json) ·
  [qwen3 ladder](../../ml/evaluation/stt/benchmarks/2026-08-12-qwen3-asr-0.6b-cpu-ladder.json) ·
  [whisper ladder](../../ml/evaluation/stt/benchmarks/2026-08-12-whisper-small-cpu-ladder.json) ·
  [drills + canary sim](../../research/experiments/16-qwen3-switching/)

**Consequence for priorities:** Milestone 17 = production canary
preparation (slot-truthful readiness, supervised child restart,
vendored Linux runtime layer re-laddered on VPS hardware, long-audio
check, the catalog commit prepared for founder review). The founder's
switching decision now has its complete evidence file: accuracy (15E),
operations (16), rollback (drilled), and the one disclosed behavior
delta (hi segment count under verbose_json).

---

---

## Milestone 17 — production canary preparation (appended 2026-08-12)

Full report: [2026-08-12-qwen3-production-canary-prep.md](2026-08-12-qwen3-production-canary-prep.md).
Operational hardening + Linux validation; no accuracy re-litigation,
no promotion.

**Qwen3-ASR 0.6B (identity unchanged; runtime now pinned per-platform: win32 AND linux b10344 @ 7a20b417f, six hashes each, verify-at-load)**
- 2026-08-12 — **switching_validated → canary_ready** *(evidence;
  promotion still NOT granted — it is a prepared diff awaiting the
  founder)* — **[EVIDENCE]** The pinned LINUX build (ubuntu-x64, GNU
  11.4.0) reproduced the frozen primary at **CER 0.14594** (Windows:
  0.1457/0.1446 — within 0.0003), 0 probes, 0 failures, ladder plateau
  2.27 rps ≈ the Windows envelope. **[DRILL, live ×2]** Slot-truthful
  readiness (unready in 0.76 s; degraded-vs-dead-default semantics) +
  supervised bounded restart (total outage 9.8–9.9 s; refusals 0.04 s,
  `not_ready`, no leak) + **zero orphans including the forced
  mid-spawn stop window** (an orphan defect this milestone's own drill
  found and fixed same-day). **Long-audio finding [DRILL→FIX]:** at
  ctx 4096 the 600 s product ceiling is NOT supportable — 120 s
  complete, **300 s silently truncated to 8 % with a 200**, 600 s
  errored, RSS to 6.5 GiB; the engine now refuses >120 s with a clean
  400 (re-verified live). **Catalog prepared [FACT]:** the promotion
  is a validated, unreachable diff (proposals.py) with the quality
  baseline riding ON the route and a PENDING-approval sentinel a test
  refuses to ever see live; rollback route pinned verbatim. Honest
  caveat: Linux validation ran on WSL2 Ubuntu on the dev laptop — real
  kernel, real pinned binaries, NOT VPS hardware; the session scripts
  are committed for the VPS re-run — evidence:
  [linux eval](../../ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-hi-17-linux.json) ·
  [linux ladder](../../ml/evaluation/stt/benchmarks/2026-08-12-qwen3-asr-0.6b-linux-wsl2-ladder.json) ·
  [drills + long-audio + scripts](../../research/experiments/17-canary-prep/)

**Consequence for priorities:** next milestone = production canary
(vendored runtime layer → VPS re-validation with the committed
scripts → founder decisions: the switch, the segment disclosure, the
promotion commit). Engineering evidence is complete; the remaining
inputs are hardware access and one human decision.

---

---

## Milestone 18 — local production-path integration (appended 2026-08-12)

Full report: [2026-08-12-local-qwen-production-path.md](2026-08-12-local-qwen-production-path.md).
No quality re-litigation; the CUSTOMER PIPELINE half of the canary
story, proven locally.

**Qwen3-ASR 0.6B (identity unchanged)**
- 2026-08-12 — **canary_ready → local_product_path_proven** *(evidence;
  promotion still NOT granted; production still resolves hi→whisper,
  guard-tested)* — **[EVIDENCE]** Through a REAL gateway process
  (staging registry profile — the prepared proposal running under a
  flag that production refuses by validator): auth → per-language
  routing (runtime logs attribute 7 requests to the candidate, 3 to
  the incumbent, matching the plan one-for-one) → transcript → usage
  ledger (**22 succeeded/389.0 s billed; 1 failed/0 billed; refusals
  bill nothing; zero duplicates**) → consent-gated collection (17
  samples; contribution-off honored) → correction (original immutable).
  **Web verified in a real browser** driving the real Studio
  (screenshots committed; zero internal names in the rendered UI or
  raw responses). **Android verified at contract level** — every
  branch of the shipped keyboard client's request/parse contract
  replayed byte-faithfully against the live gateway, all passing; NOT
  a device run (no SDK/emulator on this machine), said plainly. The
  120 s ceiling behaves end-to-end (119/120→200, 121→400 named limit,
  unbilled, uncollected; both clients surface it usefully). Child
  death under live traffic: 503 in 0.16 s, incumbent unaffected, no
  fallback fired, recovery clean, 0 orphans. 12 new full-stack tests +
  4 guards pin all of it — evidence:
  [drills + screenshots](../../research/experiments/18-local-product-path/) ·
  [staging profile](../../apps/api/src/intelliai_api/registry/proposals.py)

**Consequence for priorities:** the Hostinger milestone now has
exactly four inputs left: the vendored Linux runtime layer, VPS
re-validation (scripts committed), a real Android device pass, and
the founder's promotion decision. Every other question is answered
with committed evidence.

## Milestone 19 — hybrid long-audio implementation (appended 2026-08-16)

Full report:
[2026-08-12-qwen3-long-audio-implementation.md](2026-08-12-qwen3-long-audio-implementation.md).
The approved Hybrid C strategy, implemented and proven; the product
ceiling raised **120 → 600 s** after (and only after) the battery.

**Qwen3-ASR 0.6B (identity unchanged; serving shape extended)**
- 2026-08-16 — **local_product_path_proven → long_audio_ready_600s**
  *(evidence; promotion still NOT granted; production still resolves
  hi→whisper, guard-tested)* — **[EVIDENCE]** Chunking lives entirely
  inside `Qwen3AsrEngine.transcribe()` (100 s windows, 5 s overlap,
  seams snapped to a deterministic energy argmin — A/B-measured better
  than fixed seams on spontaneous speech in every cell); ≤120 s stays
  the byte-identical direct pass. Complete-or-fail law held in every
  proof: sandbox through the engine (23/23 windows across
  120/180/300/600 × repeats; 300 s CER 0.2084 vs prototype 0.2092;
  600 s CER 0.184, completeness 1.005), staging product path (300 s in
  79.6 s and 600 s in 180.8 s through the real gateway; one usage
  event at the exact duration; one sample only when contributed;
  correction lifecycle; zero leaks), Web in a real browser (300+600 s,
  UI responsive mid-decode, segments join == text in the Studio's own
  pane), kill-mid-window drills (**the drill caught a real defect** —
  raw mid-response disconnects bypassed the retry contract; fixed,
  pinned by tests, re-drilled: a child killed 35 s or 100 s into a
  600 s request now recovers invisibly to a complete transcript),
  short-ladder regression (admission contract identical to M16; no
  material regression), long-audio concurrency (5×300 s all complete;
  tail 422 s ≈ the honest concurrent ceiling; RSS plateaus ~3.4 GiB).
  Deadlines sized to measurement, not estimates: gateway 120→450,
  lease 180→540. Android unchanged: long audio on mobile is formally
  unsupported until a deliberate client re-timing (recorded
  limitation). — evidence:
  [engine-proof + seam-probe + drills](../../research/experiments/19-long-audio-strategy/)

**Consequence for priorities:** unchanged Hostinger inputs, plus one
capacity decision before any long-audio production promise: concurrent
long-request admission (~4–5 × 300 s per single-decoder deployment,
measured) and the ~4 GiB steady-state slot memory, both re-measured on
VPS hardware.

## Milestone 21 — Qwen3 Hindi fine-tuning experiment E1 (appended 2026-08-17)

Full report:
[2026-08-17-qwen3-hindi-finetuning.md](2026-08-17-qwen3-hindi-finetuning.md).
The program's first fine-tune of an ADOPTED lineage — and its first
fine-tune to beat its own baseline.

**qwen3-asr-0.6b-hi-ft-e1 (NEW research candidate; identity in report §24)**
- 2026-08-17 — **created → hi_ft_candidate (B. MODEST IMPROVEMENT)**
  *(research only; NOT promoted; production Hindi still whisper-small;
  the M18 promotion proposal still names the incumbent qwen artifact)* —
  **[EVIDENCE]** SFT of the official recipe on `hi-public-train@v1`
  (10 h IndicVoices+Kathbath, eval-disjoint by content hash), audio
  tower frozen, 604 steps / 31 min on the RTX 5070 (peak 5.3 GiB).
  On the frozen `stt-hi-public-eval@v1` THROUGH the real adapter on the
  pinned b10344 runtime: **CER 0.1457 → 0.12477 (−14.4% rel, ~11× the
  replicate band; replicate spread 0.0006), WER 0.2851 → 0.26642, 0
  hallucinated probes, RTF 0.237, English WER 0.0 byte-perfect, M19
  chunked long-audio intact.** Export by TEMPLATE REWRITE onto the
  official GGUF structure — the pipeline reproduced the official base
  artifact **byte-for-byte** from base weights (sha `bca259818b50…`),
  so conversion provably adds nothing. Recorded regression, mitigated
  structurally: called WITHOUT the pipeline VAD, the candidate emits a
  repeated token on pure silence where the base emits nothing (10 h of
  speech-only supervision); unreachable through the product path (VAD
  short-circuits, verified adapter-side), zero empties on the
  benchmark. Next arm should fix data first (strip verbatim markup,
  add silence/noise negatives, scale 10→25-40 h) before any
  hyperparameter sweep.

**Consequence for priorities:** Hindi now has an in-house candidate
BETTER than the adopted incumbent on the frozen primary. Promotion
remains a founder decision with the switching/canary battery to re-run
on whichever artifact is proposed; the deployment story is unchanged
(same runtime, same mmproj, same serving shape, same size).

## Milestone 22 — Hindi fine-tuning E2: data quality + scale (appended 2026-08-18)

Full report:
[2026-08-17-qwen3-hindi-finetuning-e2.md](2026-08-17-qwen3-hindi-finetuning-e2.md).
One variable moved — the data — and it answered the question.

**qwen3-asr-0.6b-hi-ft-e2 (NEW research candidate; ck1200 of qwen-e2-hi-sft)**
- 2026-08-18 — **created → hi_ft_e2_best_hindi_NOT_promotable
  (B. MODEST IMPROVEMENT over E1; English gate FAILED)** *(research
  only; production Hindi still whisper-small; the M18 proposal still
  names the incumbent)* — **[EVIDENCE]** Corpus `qwen-hi-public-train@v2`
  (27.27 h cleaned: markup dropped with reasons, eval roster + content
  hashes enforced, 0.5% no-speech negatives whose target is the base's
  own `language None<asr_text>` emission), E1's exact configuration.
  On the frozen primary THROUGH the real adapter: **CER 0.12477 →
  0.11044 (replicate 0.10871), WER 0.26642 → 0.22805, 0 hallucinated
  probes, RTF 0.262, RSS 1,652 MiB — the program's best Hindi numbers**,
  every E2 checkpoint beating E1's best. **The E1 silence regression
  is FIXED** (silence → empty at every checkpoint, HF and quantized
  paths; 0.5% negatives sufficed, landing by step 30). **Recorded
  cost: English is GONE** — ck300/600 answer English with silence,
  ck900+ TRANSLATE it into Hindi; E1's 10 h kept English, so the
  monolingual retention threshold sits between 10 h and 27 h. Second
  recorded edge: **very short speech (1 s) now suppresses to empty**
  (the 2 s corpus floor left it unsupervised and the negatives taught
  "when unsure, silence") — E2's no-speech robustness meanwhile
  extends past digital silence to real noise at −50/−40 dBFS where E1
  voices text. Same byte-exact export pipeline (control unchanged);
  long-audio chunked path intact at 300 s and 600 s.

**Consequence for priorities:** data remains the binding axis. The
stated E3 arm is a COMPOSITION FIX (v2 corpus + ~5–8% approved open
English, e.g. FLEURS en, + a bounded 0.5–2 s short-speech slice; all
else frozen) to close both recorded regressions while keeping the
Hindi gain — only if that fails does optimizer work earn a turn. No
promotion proposal changes until a candidate passes every gate.

---

## Milestone 23 — Hindi fine-tuning E3: the retention mix (appended 2026-08-18)

Full report:
[2026-08-18-qwen3-hindi-finetuning-e3.md](2026-08-18-qwen3-hindi-finetuning-e3.md).
One variable moved again — the COMPOSITION — and both E2 regressions
closed.

- **`qwen3-asr-0.6b-hi-ft-e3@v1`** — REGISTERED (research-only), and
  the program's first **A. PROMOTION CANDIDATE**: all eight gates
  pass; production untouched pending a switching/promotion milestone —
  **[EVIDENCE]** Corpus `qwen-hi-public-train@v3` (30.11 h, sha
  `6cfc585d…` = v2 verbatim, containment proven row-for-row, + 5.92%
  FLEURS-en rows under a merge-enforced 8% ceiling + 800 REAL
  [0.5 s, 2.0 s) IndicVoices utterances + the 68 negatives carried),
  E2's exact configuration, 1,840 steps / 3.30 h / 5,096 MiB peak. On
  the frozen primary THROUGH the real adapter: **CER 0.11612
  (replicate 0.11750), WER 0.24064, 0 hallucinated probes — −20.3% vs
  base, a priced +5.1% relative giveback vs E2's gate-failed best.**
  **English RESTORED: safety record WER 0.0 / CER 0.0** (E2: 1.0) —
  and retained at EVERY checkpoint depth (JFK 0.0 across ck600–ck1840;
  the 5.92% slice held what 27 h of pure Hindi erased). **Short speech
  RESTORED**: the served artifact transcribes the full 0.5–2.5 s
  ladder and real held-out sub-2 s utterances (E2: empty at 1 s).
  **Silence/noise safety PRESERVED** (silence, −50, −40 dBFS all
  empty; transitions transcribe). Long-audio intact (300 s → 4
  segments, 600 s → 7, join==text at real offsets). RSS 1,559 MiB,
  RTF 0.16–0.218, sizes identical; same byte-exact export pipeline.
  Data-plane laws added for the mix: a bounded short-speech admission
  window exclusive at the standard floor, row-count freeze budgets,
  and a pin-reverified `merge-train` with language-share ceilings.

**Consequence for priorities:** the experiment arc E1→E2→E3 is
closed: pipeline proven, data proven binding, composition proven the
fix. The next Qwen-Hindi decision is PROMOTION, not training — an
M16-style switching battery against this artifact plus a proposal
update, founder-gated. Optimizer work never earned its turn.

---

## Milestone 24 — E3 promotion & switching validation (appended 2026-08-18)

Full report:
[2026-08-18-qwen3-hi-e3-promotion-readiness.md](2026-08-18-qwen3-hi-e3-promotion-readiness.md).
The question changed from "is it better?" to "can it safely replace
the incumbent?" — and every gate a laptop can prove says yes.

- **`qwen3-asr-0.6b-hi-ft-e3@v1` — classified A. READY FOR PRODUCTION
  CANARY (local/staging evidence); the promotion proposal is PREPARED
  and PENDING; production unchanged and test-pinned** — **[EVIDENCE]**
  Against a FRESH same-day incumbent baseline (whisper-small CER
  0.37617, inside the 15C band): **−69% relative CER, −64% relative
  WER, ~15× the noise band**, through the same multi-slot runtime.
  Safety battery matches-or-beats the incumbent row by row (E3
  transcribes 0.5 s where whisper is empty; both clean-400 malformed
  inputs; zero leaks). Product path drilled end to end on the real
  gateway: metering exact (+300.0/+600.0; 602 s refused, billed 0),
  one sample under consent, contribution-off honored, correction
  immutable-original, verbose_json segment law held at every length.
  Ladders: E3 c=10 p50 6.5 s vs incumbent 21.0 s (falls behind live
  speech); both shed cleanly at the admission boundary. Long-audio
  concurrency matches M19 (5×300 all clean; RSS 3.56 GiB sustained).
  Failure drills: readiness truthful in ~1.2 s, supervised recovery
  <4 s twice, incumbent never blinked, zero orphans. Canary sims
  400/400 clean across 10/25/50/75% shares. Rollback drilled as a
  pure configuration flip back to whisper-small. The proposal module
  now names E3 SPECIFICALLY (superseding the never-approved M17
  base-qwen proposal) with the PENDING sentinel; the staging overlay
  pins the E3 slot by guard test.

**Consequence for priorities:** the evidence file for the founder's
switching decision is complete. Remaining before real traffic: the
founder decision itself, VPS access (M20 runbook), and the Linux
re-pin + re-ladder on VPS hardware. Nothing further is learnable from
this laptop.

---

## Milestone 26 — Hindi promotion APPROVED and activated in the repository (appended 2026-08-19)

Full report:
[../milestones/26-qwen-e3-production-promotion.md](../milestones/26-qwen-e3-production-promotion.md).

- **`qwen3-asr-0.6b-hi-ft-e3@v1`** — **APPROVED HINDI PRODUCTION
  ARTIFACT (repository state; NOT yet deployed, NO live traffic)** —
  **[FACT]** The founder approved the promotion on 2026-08-19 on the
  M23→M24→M25 evidence chain (all eight research gates; −69% relative
  CER vs the whisper-small incumbent through the real product path;
  production-shaped Docker stack verified by real founder-driven Web
  and Android sessions through a live Cloudflare tunnel). The M26
  promotion commit moved the live catalog route `hi →
  qwen3-asr-0.6b-hi-ft-e3` with the approval record riding on the
  route evidence, declared the exact artifact in the prod compose
  slots, updated the guards to pin the NEW posture, and retired the
  pending-proposal state (no proposal is now pending). Weights
  distribute by seeding (deliberately non-downloadable; store
  hash-verify at load; preflight-enforced). **Rollback**: git revert
  of the promotion commit → `hi → whisper-small`
  (`ROLLBACK_HINDI_ROUTE`, test-pinned; drilled in M25). E1/E2/base
  artifacts preserved as research history and comparison anchors.

**Consequence for priorities:** the Hindi program's model decision is
made. What remains is DEPLOYMENT: Hostinger VPS + domain + secrets,
E3 seeding on the box, Linux re-ladder on VPS hardware, and the real
production canary — a separate milestone with its own gates.

---

## Milestone 29A — Hindi punctuation evaluation v1 + baselines (appended 2026-08-19)

Full report:
[2026-08-19-hindi-punctuation-evaluation-v1.md](2026-08-19-hindi-punctuation-evaluation-v1.md).
New capability lens: punctuation restoration as backend text
post-processing (M28 architecture research → M29A frozen benchmark
`hi-punct-eval@v1`, 265 rows, FLEURS hi_in test raw_transcription,
`punct_slots@v1` ruler, word-preservation invariant as a HARD GATE).

- **punct_cap_seg_47_language (1-800-BAD-CODE)** — **Researching**
  *(Gate 0 intake + first benchmark)* — **[EVIDENCE]** Apache-2.0
  (source, 2026-08-19), revision `1b9d51fc7989…`, ONNX+sentencepiece,
  ~233 MB, CPU. IDENTITY CORRECTION: the `punctuators` alias
  `pcs_47lang` resolves to THIS repo — the M28 document's attribution
  to `xlm-roberta_punctuation_fullstop_truecase` was wrong; every M28
  measured number was produced by this model. M29A measured, on
  hi-punct-eval@v1: micro punctuation F1 0.2421, sentence-boundary F1
  0.7497, comma F1 0.3467, invariant pass rate 96.23% (10/265 rows
  destroy Latin acronyms as `<unk>` — the pipeline's detokenizer, not
  the classifier heads). On the multi-sentence probe (3-sentence
  paragraphs): boundary recall 0.9435 vs the rules baseline's 0.2687
  — the model finds the mid-text boundaries the product actually
  needs. On 151 real E3 outputs: invariant 151/151 PASS. Latency
  0.08–0.31 s per 5–600 s tier, RSS peak 616 MiB (dev box).
  Integration precondition defined by M29A: a word-copy decoder
  (input words verbatim + predicted marks only) making the invariant
  structural — evidence:
  [29a evidence](../../research/experiments/29a-hindi-punctuation-eval/),
  [license checks](../../research/experiments/29a-hindi-punctuation-eval/license-access-checks.json)
- **Cadence-Fast (AI4Bharat)** — **Researching — benchmark BLOCKED**
  *(license)* — **[FACT]** Model card claims MIT, but the base model
  is Gemma-3-270M and Google's Gemma Terms of Use assert flow-down
  conditions on derivatives; no relicensing statement or maintainer
  clarification exists (community tab empty, checked 2026-08-19).
  Per the M29A rule, NOT downloaded, NOT benchmarked. Unblocking
  requires legal review or upstream clarification — evidence:
  [license checks](../../research/experiments/29a-hindi-punctuation-eval/license-access-checks.json)

**Consequence for priorities:** classification **B — evaluation
promising, needs better data**. Before any runtime integration
(M29B): benchmark v2 with multi-sentence and spontaneous punctuated
references, and the word-copy decoder as the integration contract.
Production remains untouched; Hindi still serves unpunctuated.

---

## Milestone 29B-DATA — punctuation evaluation v2 + word-copy decoder (appended 2026-08-19)

Full report:
[2026-08-19-hindi-punctuation-evaluation-v2.md](2026-08-19-hindi-punctuation-evaluation-v2.md).
New frozen benchmark `hi-punct-eval@v2` (148 rows: 88 deterministic
3-sentence read paragraphs reconstructible from pinned v1 members + 60
spontaneous IndicVoices references punctuated per the committed
annotation-style-guide-v1 — single annotator, AI, text-only,
**PROVISIONAL pending founder native-speaker review**). Question probe
set (30 questions + 12 statement controls) and edge probe set (22
corruption probes) committed as research probes.

- **punct_cap_seg_47_language (1-800-BAD-CODE)** — *status unchanged
  (Researching)* — **[EVIDENCE]** The M29A `<unk>` word-destruction
  defect is CLOSED by construction: a research-only word-copy decoder
  (model predicts marks; ORIGINAL input words copied verbatim via the
  evaluation plane's `apply_marks`) measured invariant **100%** on
  every surface (v1 265/265 vs old pipeline 96.23%; paragraphs 88/88
  vs 88.64%; spontaneous 60/60; edge probes **0/22 corrupted vs the
  old pipeline's 13/22**), with identical-or-better quality (v1 F1
  0.242, paragraphs 0.2606, comma 0.389) and better operations (~10×
  faster batch, warm load 0.88 s, RSS peak 428 MiB, 600 s tier
  0.451 s with decoder cost 0.0006 s). First spontaneous-Hindi
  measurement: micro F1 **0.5747**, boundary F1 0.7248 (P 0.7182 /
  R 0.7315), comma F1 0.4462, question F1 0.5 — against PROVISIONAL
  references. Questions: 21/30 (70%) overall, **21/23 (91.3%) on
  lexically-cued questions**, 0/12 false positives; the 9 misses are
  dominated by intonation-only questions no text system can recover.
  M29A-proposed gates as measured: invariant/comma/latency/RAM PASS;
  boundary F1 0.7441 (paragraphs) and question 70% sit just under the
  proposed bars — revised gate framing is PROPOSED and awaits founder
  decision — evidence:
  [29b evidence](../../research/experiments/29b-hindi-punctuation-eval/)

**Consequence for priorities:** classification **B — promising; the
smallest next step is a FOUNDER REVIEW, not more code**: (1) ratify or
amend the 60 spontaneous annotations (24 carry uncertainty flags) and
the style guide; (2) ratify the revised gate set. If both ratify with
gates passing, M29B-runtime (the M28 architecture behind the full test
battery) is the next implementation milestone. Production remains
untouched; Hindi still serves unpunctuated.

---

## Milestone 29C — founder review applied; ratified gate assessment (appended 2026-08-19)

Full report:
[2026-08-19-hindi-punctuation-ratification-m29c.md](2026-08-19-hindi-punctuation-ratification-m29c.md).
The founder-supplied text-only review of the 60 spontaneous annotations
(49 APPROVE / 2 comma-only REVISE / 9 AUDIO_REVIEW_REQUIRED) is applied
as **`hi-punct-eval@v3`** (v2 frozen as the pre-review record; inputs
byte-identical, so the committed predictions re-score deterministically).

- **punct_cap_seg_47_language (1-800-BAD-CODE)** — *status unchanged
  (Researching)* — **[EVIDENCE]** On the text-ratified 51-row slice:
  micro F1 0.5695, boundary F1 0.7363 (P 0.7204 / R 0.7528), comma F1
  0.4333, invariant 100%. Gate verdicts: M29A-as-written — invariant/
  comma/latency/RAM PASS; boundary F1/recall/precision and question-80%
  FAIL by small margins. M29B revised-proposed gates — BOTH PASS
  (questions 91.3% lexically-cued + 0 false positives; boundary F1
  0.7441 ≥ 0.70 and ≥ rules + 0.25). The audio-flagged 9 rows score
  lower on boundaries (0.667) than the ratified 51 (0.736) —
  validating their exclusion. **The remaining decision is the
  founder's gate choice**: approve the revised gates → M29B-runtime
  unblocked; hold the original bars → a new model-improvement research
  cycle. Open items: audio/native review of the 9 flagged rows; final
  native-speaker confirmation (the review itself is text-only) —
  evidence:
  [gate assessment](../../research/experiments/29b-hindi-punctuation-eval/gate-assessment-v3.json)

---

## Milestone 30 — Hindi punctuation runtime IMPLEMENTED and STAGED (appended 2026-08-19)

Full report:
[../milestones/30-hindi-punctuation-runtime.md](../milestones/30-hindi-punctuation-runtime.md).
Dossier (framework §11, first non-transcription entry):
[models/punct-cap-seg-dossier.md](models/punct-cap-seg-dossier.md).

- **punct_cap_seg_47_language (1-800-BAD-CODE)** — **Approved for
  Adoption (capability implemented; PRODUCTION ACTIVATION PENDING)** —
  **[FACT]** The founder approved the M29C revised gates; M30 shipped
  the stage on the approved architecture: vendored ONNX wrapper +
  word-copy decoder in the STT runtime (`punct-cap-seg-47@v1`, seeded,
  hash-verified, fail-open, hi-route gating, post-chunk-merge, one
  shared session), additive contract field `raw_text`, provenance
  raw → punctuated → corrected with billing untouched. **[EVIDENCE]**
  Phase-20 HARD gate PASS: frozen-eval accuracy metrics byte-identical
  OFF vs ON (CER 0.11612 / WER 0.24064), 153/153 word streams equal,
  440 v1 marks added on 150 clips. All six approved gates PASS through
  the SHIPPING wrapper (invariant 100%, cued questions 91.3% + 0 FP,
  boundary F1 0.7441/0.7222, comma 0.389/0.433, edges 0/22). Staging
  battery through the production-shaped stack 22/22 incl. long-audio
  join law with punctuation, silence safety, contribution ON/OFF,
  correction, three client contract shapes, restart recovery, and the
  live disable/rollback drill. Perf (dev box): 600 s → 0.267 s, RSS
  peak 436.8 MiB, warm load 0.58 s. Production remains OFF
  (`INTELLIAI_STT_PUNCTUATION_ENABLED: "false"` pinned + guard-tested);
  activation is a separate promotion decision (deploy-box re-ladder,
  audio-flagged-row review, reviewed flag flip) — evidence:
  [30 evidence](../../research/experiments/30-punctuation-runtime/)

**Consequence for priorities:** the punctuation program is
implementation-complete and staged. Hindi's remaining path to users is
DEPLOYMENT: the Hostinger milestone now carries both the E3 promotion
(M26) and the punctuation flag decision, each with its own gates.

---

## Milestone 49 — English punctuation model selection (appended 2026-08-28)

Full report: [2026-08-28-english-punctuation-model-selection.md](2026-08-28-english-punctuation-model-selection.md).
New frozen benchmark: `en-punct-eval@v1` (120 rows; LJSpeech read speech + authored probes + the M48 boss-DRAFT spontaneous slice), scored with the UNCHANGED `punct_slots@v1` ruler. Word-copy invariant: zero failures across every candidate, row, and ladder rung. Production untouched (STT 205 + evaluation 677 suites green).

- **kredor/punctuate-all** (XLM-RoBERTa-base, rev `0fe37019…`, weights sha `9aec7aa5…`) — **Approved for Benchmark → M49 SELECTION (decision A)** — **[MEASURED]** micro F1 0.674, **boundary F1 0.827** (the best measured), comma 0.557, question 0.824-0.857, spontaneous 0.639/0.727; 10-min transcript in **0.83 s** CPU (~1.6 % of STT p50 — the proposed ≤10 % latency gate passes with margin); peak RSS 1489 MiB fp32 (the proposed ≤700 MiB gate FAILS as-fp32 for every candidate — the M50 int8/ONNX export is the named lever, M30 precedent 437 MiB). License MIT, Europarl-trained, 12 languages. Boundary recall 0.841 — a narrow miss of the proposed 0.85 on this set (3-row DRAFT spontaneous slice); the gate stays PROPOSED and re-measures through the shipped stage. **Recommended M50: English punctuation runtime stage** (int8 ONNX + artifact pinning + the shipped M30 word-copy wrapper with en gating, flag OFF, founder listening before any flip). NOT promoted — M50 is the implementation gate.
- **oliverguhr/fullstop-punctuation-multilang-large** (XLM-R-large, rev `345e80ad…`, sha `270f27d7…`, MIT) — **Researching (quality ceiling/backup)** — [MEASURED] best micro 0.695 / comma 0.601 / spontaneous 0.732, but 2.3 GiB RSS and 5.37 s per 10-min transcript (10.3 % of STT p50 — borderline on the proposed gate). Falls back into play only if M50's export measurably degrades kredor.
- **felflare/bert-restore-punctuation** (bert-base, rev `954108a1…`, MIT) — **Rejected — domain mismatch** — [MEASURED] micro 0.420 / boundary 0.422 despite being English-only (Yelp training does not transfer to speech transcripts).
- **vendored punct-cap-seg-47 + EN label map** — [MEASURED, EXPERIMENTAL] clean-sentence specialist (probe boundary 0.941, question 1.0) but spontaneous 0.444 — confirms M48: the shipped Hindi v1 model is not the English answer alone; it remains the Hindi stage only.
- **Silero TE** — **Rejected — license** (CC BY-NC-SA; not downloaded). **NVIDIA NeMo punctuation_en_\*** — REVIEW REQUIRED (NVIDIA Open Model License); deferred, not measured.

---

## Milestone 50 — English punctuation runtime implementation (appended 2026-08-27)

Full report: [../milestones/50-english-punctuation-runtime.md](../milestones/50-english-punctuation-runtime.md).
Evidence: [50 evidence](../../research/experiments/50-english-punctuation-runtime/).

- **kredor/punctuate-all** (rev `0fe37019…`, fp32 weights sha `9aec7aa5…`, MIT) — **M49 selection → STAGING CANDIDATE (M50 classification A)** — **[MEASURED]** Converted reproducibly to **ONNX INT8** (torch 2.11 export opset 17 → `quantize_dynamic` QInt8 weight-only, no calibration; torch 2.11.0/transformers 4.57.3/onnxruntime 1.29.0/py 3.12.3): derived artifact **`punct-en-kredor@v1`** — `model.int8.onnx` sha `b0d8d68c…` (277,964,353 B), pinned xlm-roberta-base SPM sha `cfc8146a…`, provenance.json sha `bb74cc24…` (label table travels inside the hash-verified artifact). Tokenizer fairseq id law (`hf_id = spm_id + 1`) proven: 0 mismatches / 1218 eval words. Conversion control: 80/120 frozen-eval rows byte-identical to fp32. **Shipped stage** (`engines/punctuation_en.py`, M30 word-copy core imported, en/en-US/en-IN route gating, fail-open, `INTELLIAI_STT_PUNCTUATION_EN_ENABLED` default FALSE): frozen en-punct-eval@v1 through the SHIPPING wrapper — micro F1 **0.6814** (fp32 0.6745), boundary **0.8142** (fp32 0.8270), comma 0.5674, question 0.8889, invariant **0 failures**; identical to standalone INT8, i.e. integration changed nothing. **Memory gate PASS**: peak RSS 568.5 MiB ≤ 700 (fp32 was ~1489). **Latency**: 2000 words p95 0.373 s; real 102 s boss clip stage cost **45.2 ms = 0.56 %** of same-request STT inference (proposed ≤10 % gate passes ~14×). Long text 1500 w in 261 ms, zero word changes; concurrency c=1..8 no leak/fail-open; service-level proofs on real whisper-small instances: flag OFF `text` byte-identical to flag-ON `raw_text` (instant rollback), `language=hi` never runs the stage, forced-timeout instance returns 200 + raw. Sarvam remains QUALITATIVE ONLY (M48 directive) — no Sarvam metrics; the M48 "one unbroken run-on" readability gap is closed in kind on the boss clip. **Production remains OFF**; promotion (incl. live-browser E2E after the demo freeze) is the next milestone's decision, not this one's.

---

## Milestone 51 — English punctuation staging promotion + real web E2E (appended 2026-08-27)

Full report: [../milestones/51-english-punctuation-staging.md](../milestones/51-english-punctuation-staging.md).
Evidence: [51 evidence](../../research/experiments/51-english-punctuation-staging/).

- **kredor/punctuate-all → `punct-en-kredor@v1`** — **STAGING CANDIDATE → STAGING VERIFIED (M51 classification A)** — **[MEASURED]** Flag `INTELLIAI_STT_PUNCTUATION_EN_ENABLED` turned ON in the local production-shaped stack ONLY (`local-prod.yml`; `prod.yml` pins `"false"` + new guard test + preflight/smoke extensions). Real-browser E2E (Playwright Chromium against the Caddy HTTPS edge, the actual `/console/playground`): boss clip punctuated end to end, Share clipboard == displayed transcript, real correction (`droughts → drafts`) saved through the live endpoint, Hindi run untouched by the English stage, mobile/tablet usable, DOM + response bodies leak-clean. **The browser battery caught a real defect M50's evidence could not see**: Whisper fully punctuates clean READ speech and the stage doubled marks ("Sumit..") — fixed with the token-final **engine-already-punctuated stand-down law** (intra-word `2.5`/`example.com` never count; 4 new tests, suite 228 green). Complementarity recorded: Whisper punctuates clean speech, spontaneous arrives bare — the stage now fires exactly on the M48 readability gap. Live drills: forced 0.001 ms timeout → 200 + raw, no user-visible error; flag OFF → raw **byte-identical** to the fail-open capture; flag back ON → punctuated again. Long audio 30 s→595 s: stage 36→611 ms, invariant TRUE, zero truncation. Staging container latency: boss ×5 `punctuation_en` p50 196.4 ms = 2.87% of inference (≤10% gate passes; host M50 measurement was 45.2 ms). **Production remains OFF; the production promotion is the next founder-gated milestone.**

---

## Milestone 52 — Realtime STT streaming feasibility (appended 2026-08-27)

Full report: [2026-08-28-realtime-stt-feasibility.md](2026-08-28-realtime-stt-feasibility.md).
Evidence: [52 evidence](../../research/experiments/52-realtime-stt/). Research only — no model status changes, no production change.

- **whisper-small (current EN production artifact)** — **[MEASURED] realtime-capable by window re-decode** (no incremental API exists; none needed): Linux CPU decode 0.5 s → ~0.9 s / 30 s → ~2.6 s (RTF ~0.09-0.12) gives a continuous ~1.5 s-cadence partial stream whose FINAL text matched the offline decode byte-for-byte on the boss clip (WER 0.0) and stayed repeat-free/bounded through a 10-minute rolling session (commit-seam WER 2.4-4.2% — VAD-aligned commits are the named fix). Raw partials churn (stable-token 0.45-0.74); the **LocalAgreement-2 display law** measured monotonic (zero flicker, ~6-word lag, 71-75% live coverage). Silence: the bare model hallucinates ("You"); the production EnergyVad gates it to zero inference — VAD-gated windows are law. **GPU (RTX 5070, CT2 fp16): 0.5 s window 71 ms, partials p50 446 ms, final 974 ms — every proposed gate passes.** Windows-native CT2 measured ~3× slower than Linux — Linux/container numbers are the only honest ones.
- **qwen3-asr-0.6b-hi-ft-e3** — **[MEASURED] realtime-BLOCKED on CPU** (status unchanged; batch Hindi production unaffected): llama.cpp serving keeps no audio state, so every partial is a full re-inference, and the cost curve (1 s → 1307 ms, 2 s → 1614 ms, 19.9 s → 7546 ms) decodes NOTHING inside a 1 s update budget. GPU E3 via CUDA llama.cpp: UNMEASURED — the M53+ question for Hindi realtime. Hinglish probes (n=1, synthetic): hi-route drops English and loops, en-route drops Hindi — **no mixed-language support claimed**.
- **Transport/contract** — [MEASURED via isolated prototype] WebSocket session model (started/partial/final/completed + degraded) held up through real transport: auth-before-audio enforced, sessions isolated across restart (no stale text), 8× flood produced a LOUD degraded event and a complete lagged final (nothing silently dropped), finalization 286 ms with rolling commits. **Decision B — feasible with architectural changes** (WS session layer, rolling/VAD-aligned commits, LA2 display, optional GPU serving for sub-second UX); proposed next milestone: M53 realtime ENGLISH web implementation, founder-gated.

---

## Milestone 52H — Hindi Qwen E3 GPU realtime feasibility (appended 2026-08-27)

Full report: [2026-08-28-hindi-qwen-e3-gpu-realtime.md](2026-08-28-hindi-qwen-e3-gpu-realtime.md).
Evidence: [52h evidence](../../research/experiments/52h-hindi-qwen-gpu/). Research only — weights, routing, production all unchanged.

- **qwen3-asr-0.6b-hi-ft-e3 (unchanged GGUF pins) + RTX 5070 Laptop** — **[MEASURED] realtime-CAPABLE on GPU; decision B (feasible with minor architectural work)** — GPU runtime = llama.cpp **b10344 (7a20b417f) win-cuda-13.3** (the SAME commit as the production CPU pin; release zips SHA-recorded), `-ngl 99`, offload proven by behavior (1 s Hindi -> **64 ms** vs 874-1307 ms CPU same day; VRAM 2118 MiB, GPU util 63%). Ladder: RTF flat **~0.055** through 19.9 s (CPU 0.27-0.49+); every realtime window from 250 ms decodes faster than its own duration; the CPU-only 3 s-prefix generation loop does NOT reproduce on GPU. Streaming sims on REAL IndicVoices Hindi (VAD-snapped rolling commits): **FPT 490-660 ms**, update p50 524-880 ms (<=2 min sessions) / 1.2-1.8 s (5-10 min — decode scheduling, not compute, is the fix; a 15 s window cap measured as NOT helping), finals 1.0-1.7 s sim upper bound, LA2 monotonic with 98.5-99.4% live coverage, zero repeats, word counts within 0.6% of truth. Quality: 30 real clips offline — GPU 15.60%/7.77% vs CPU 15.28%/7.29% WER/CER, **25/30 transcripts byte-identical**; long sessions vs ground truth: streamed 15.88/23.89/17.60% vs per-clip offline baseline 15.88/23.17/15.53% (streaming penalty 0/+0.7/+2.1 pt). Silence: bare GPU model outputs EMPTY (VAD gate stays law); c=8 zero failures (~18 rps on 2 s windows); VRAM flat over 50 requests. **GPU is the Hindi realtime deployment requirement.** **OPEN FINDING (out of scope, own investigation needed): the CURRENT production service path returned unstable truncated Hindi on a 31.8 s real multi-speaker clip (7 runs, 2-96 words) while direct child calls were stable-complete on all three backends — recorded in `evidence/service-anomaly.json`; it predates M52H and touches the batch path.** Nothing promoted; proposed next = M53 realtime web implementation (English-first, Hindi GPU phase behind the same session contract), founder-gated.

---

## Milestone 53 — Realtime STT web implementation, staging (appended 2026-08-28)

Full report: [../milestones/53-realtime-stt-web.md](../milestones/53-realtime-stt-web.md).
Evidence: [53 evidence](../../research/experiments/53-realtime-stt/). Flags OFF everywhere by default; production pins the gateway URL empty; batch path untouched (byte-identical double-run on the live staging stack).

- **whisper-small (realtime serving role, GPU)** — **[MEASURED] staging realtime engine for en/en-US/en-IN** — a DEDICATED faster-whisper instance (never the batch slot) at `device=cuda` on the staging host (CT2 + declarative `cuda` extra: nvidia cu12 wheels + the measured PATH/add_dll_directory bootstrap), greedy partials / beam-5 finals. End-to-end through the gateway: FPT 1.11 s, partial cadence p50 0.54-0.57 s from 30 s to 10 min (966 partials, no degradation), finalization 0.29-1.2 s (one 4.0 s 5-min outlier recorded), final vs batch text WER 2.08%, silence sessions decode nothing and store nothing.
- **qwen3-asr-0.6b-hi-ft-e3 (realtime serving role, GPU)** — **[MEASURED] staging realtime engine for hi/hi-IN** — the UNCHANGED E3 GGUF through llama.cpp b10344-CUDA (`llama-server.exe` byte-identical to the production pin; `ggml-cuda.dll` pinned; launcher refuses drift). FPT 0.66-0.76 s on real IndicVoices speech; partial p50 0.82-0.99 s (≤2 min) / 1.5 s (10 min); finals 1.2-3.2 s — **recorded miss** vs the ≤1 s proposal (hardening item); quality vs ground truth 10.9% WER at 30 s (equals the direct-child quality) and +0-2.3 pt vs the M52H offline baselines on 5/10 min (2-min slice +6.6 pt, seam tuning continues). **[FINDING]** one qwen generation loop inflated a 2-min session ~180 words → duration-scaled max_tokens + repetition observability shipped; retry/trim guard named for promotion.
- **The session layer** — [MEASURED via real browser] fake-microphone Chromium through Caddy: live monotonic LA2 text from ~2.6-2.9 s in BOTH languages, Stop → punctuated final → Share == final → correction saved through the real endpoint, sample id via `session.completed`; flood 8x → loud degraded + complete final; rollback drilled (URL emptied → refused handshake + friendly UI + batch intact → restored). Browser E2E caught and fixed: LA2 display shrink, mic-after-Stop, and a completed-event transport-flush race (ordered shutdown). Next (founder-gated): staging hardening + promotion readiness. Nothing promoted.

---

## Milestone 54 — Realtime STT staging hardening + promotion readiness (appended 2026-09-01)

Full report: [../milestones/54-realtime-stt-hardening.md](../milestones/54-realtime-stt-hardening.md).
Evidence: [54 evidence](../../research/experiments/54-realtime-stt-hardening/). Baseline REPRODUCED same-day before any change (the environment ran slower than the M53 recording — deltas are against measurements, never memory). Production stays OFF; batch double-runs byte-identical.

- **whisper-small (realtime serving role, GPU)** — **[MEASURED] hardened staging engine, en/en-US/en-IN** — same artifact/runtime (CT2 fp16, dedicated instance, RTX 5070 Laptop). Commit-landing at final removed the ~4 s outlier CLASS (5-run finalization max 1.33 s vs baseline 1.85 s); silence-tail fast path finals in 41-60 ms (shorts/pauses); long-session finals 0.25-0.29 s; cadence p50 0.51-0.59 s at every length; final vs batch WER 2.08% with one run byte-equal. FPT p50 1.22 s — the ≤1 s target stays narrowly missed; telemetry attributes the p95 tail (2-12 s decode stalls, max gap 7.6-12.1 s) to individual slow decodes on the shared laptop GPU, not scheduling (hot-lane queue p95 ≤0.7 ms). **[MEASURED, negative]** a 0.3 s first-decode window WORSENS English FPT (whisper returns empty on short windows) — recorded, reverted for EN.
- **qwen3-asr-0.6b-hi-ft-e3 (realtime serving role, GPU)** — **[MEASURED] hardened staging engine, hi/hi-IN** — unchanged GGUF + pinned b10344-CUDA server. Finalization 3.3-4.0 s → **0.67-0.90 s** (30 s), 0.64 s (2 min), 1.4 s (5 min); 10-min finals 6.5 s with ~3.0 s of that the PUNCTUATION stage on 1,800 words (newly measured superlinear cost, named for the punctuation stage). Hindi-only 0.3 s first step: FPT **0.33-0.41 s** (from 0.75-1.06). Cadence p50 0.60-0.86 s at every length (≤1 s target met), p95 1.2-1.5 s. Quality vs ground truth within ±1.8 pt of baseline at every length (30 s identical at 16.81%); words 107±1 across every run. **[MEASURED, counterfactual]** a 12 s/3 s window-commit variant helps nothing and worsens finals — the 25 s/5 s defaults stand. Repetition guard (detect → retry → trim-to-2 + seam-collapse; legit "हाँ हाँ" unit-pinned untouchable) shipped; zero events in the wild this milestone.
- **The service layer** — GPU capacity/sharing [MEASURED]: both engines resident at 2.9-3.2 GiB VRAM flat, util ≤78% at c=4+loud-neighbor, zero OOM; fairness round-robin by construction (loud 10-min neighbor starves nobody); target UX to ~2 concurrent sessions per 5070-class GPU (laptop numbers — production-GPU re-run required). Cold start → ready 12.4 s (warm 6.8 s), everything SHA-verified. Readiness gained `degraded` (dead Hindi backend can no longer report a false ready). Rollback re-drilled live (flag-off / runtime-down / restore). **Hindi BATCH service anomaly (M52H open finding) ANSWERED: reproducible (real30s 2-94 words over 5 runs; NEW: also unstable at 60 s), worse under contention, GPU direct byte-stable (117×3, 225×3), realtime path unaffected — an existing CPU-batch defect, promotion checklist item for a founder decision.** Decision **H** — realtime gates pass or are recorded; promotion blocked on that decision + production-GPU verification. Proposed next: M55 production GPU serving readiness. Nothing promoted.

---

## Milestone 55 — Production GPU serving readiness (appended 2026-09-01)

Full report: [../milestones/55-production-gpu-serving-readiness.md](../milestones/55-production-gpu-serving-readiness.md).
Evidence: [55 evidence](../../research/experiments/55-production-gpu-readiness/). Classification **PRODUCTION-LIKE-GPU-VERIFIED** (RTX 5070 Laptop 8GB — no designated production GPU box exists yet; provisioning it + re-running the ladder/stall/edge checks there is the enablement condition). Production stays OFF; committed compose stays CPU-batch.

- **whisper-small (realtime serving role, GPU)** — **[MEASURED] production-like validated** — 20 consecutive boss30 sessions on the warm GPU: FPT p50 1.10 s (max 1.39), finalization p50 203 ms (max 358 — fast path landing consistently), cadence p50 0.53 s, **zero stalls (max gap 1.74 s)** — the M54 stalls are intermittent thermal-state behavior, alert-armed, production-GPU re-check required. c-ladder p50: 0.53/0.67/1.05/2.1 s at c=1/2/4/8, zero errors at every c.
- **qwen3-asr-0.6b-hi-ft-e3 (realtime serving role, GPU)** — **[MEASURED] production-like validated** — FPT 0.33-0.42 s; cadence p50 0.62-0.79 s at every length; **finalization ≤1.43 s at every length on the warm GPU** (the M54 10-min 6.5 s event did not reproduce; punctuation sub-second incl. 1,812 words). Quality vs frozen truth inside the seam-variance band (2 min −3.6 pt BETTER, 30 s +0.9…+3.4 pt over 3 runs, no directional regression).
- **qwen3-asr-0.6b-hi-ft-e3 (BATCH serving role, GPU) — NEW** — **[MEASURED] the M52H/M54 CPU batch anomaly is MITIGATED BY GPU SERVING**: an additive, flag-gated external-server engine mode (`INTELLIAI_STT_QWEN3_SERVER_URL`, default empty = unchanged CPU child; slot-truthful external health monitor, fail-loud load probe) through the REAL gateway route on its own pinned llama instance: real30s **117 words ×5 byte-deterministic** (WER 10.92% — direct-child quality) where the CPU service scattered 2-94; 60 s and 2 min stable; 13-call hammer under live realtime all 117. **Batch decision A: GPU batch is production-required for Hindi**; CPU remains a documented degraded fallback.
- **The service layer** — both engines + the batch instance coexist on one 8 GiB card (VRAM 2.9→5.3 GiB flat, ~2.8 GiB headroom, zero OOM across ~50 sessions); **RECOMMENDED SAFE CAPACITY 2 realtime sessions/GPU (4 = degraded burst)**; continuous batch hammering costs realtime ~2× cadence (policy: cap batch on realtime GPUs or separate cards). Alerts became a runnable checker (five forced conditions fire, cancellation never does, two fired LIVE in failure drills); failure/recovery and every rollback leg drilled live. Decision **A — PRODUCTION GPU READY (production-like)**; next: founder-gated realtime production promotion. Nothing enabled.

---

## Milestone 56 — Smart transcript correction: research + model selection (appended 2026-09-01)

Full report: [2026-09-01-smart-transcript-correction.md](2026-09-01-smart-transcript-correction.md).
Evidence: [56 evidence](../../research/experiments/56-smart-correction/). RESEARCH ONLY — nothing integrated, production/Playground/pipelines/billing untouched; every request stayed on this machine (loopback llama-server; zero external API tokens). New frozen benchmark: **smart-correction-en-hi@v1** (300 AUTHORED rows, 150 EN + 150 HI, STT-noise style, sha-pinned manifest; flag classes: 37 already-correct, 23 meaning-trap, 21 ambiguous).

- **Qwen3-4B-Instruct-2507 (Apache-2.0; Q4_K_M GGUF via pinned llama.cpp b10344 CUDA, research port)** — **[MEASURED] task = STT transcript correction, EN+HI+Hinglish — SELECTED PRIMARY, decision A** — the decisive experiment was the PROMPT: a combined contract caused cross-language flips (EN→HI translation on Indian names; Roman-Hindi answered in Latin); **language-scoped prompt pair (session language comes from the pipeline) removed flips entirely (12%→0%)**. Canonical v3 full-benchmark: EN — meaning-traps 100%, entity violations 0, flips 0, unchanged-correct 100%, additions 1.3%, WER-vs-gold 16.9% vs identity-baseline 34.4% (~half), exact 60.7%, row p50 **201 ms** GPU; HI — traps 100%, flips 0, violations 1 format case (एक→१), unchanged-correct 77% (**over-correction is the recorded HI edge**), WER 21.2%, row p50 432 ms. Human read (author evaluation, 25+25, not MOS): EN 4.80-4.96, HI 4.40-4.56 with four named failure classes (Roman homograph der→डर meaning flip; loanword mangling busy→बसी; ONE invented clause on an ambiguous fragment in 50 rows; occasional tense breaks). Latency by length: EN 0.3→2.6 s (20→250 w), HI 0.9→9.2 s (Devanagari output token-heavy); **CPU verdict: EN marginal, HI FAILS (15-38 s) — GPU-preferred layer**; VRAM ~3 GB. Blind chunking measurably breaks tense/pronoun coherence — whole-transcript (or sentence-boundary-with-overlap, PROPOSED) is the path. Punctuation interaction measured (11/12 word-identical from raw vs pre-punctuated): keep the existing word-copy punctuation stage as the guaranteed layer; correction runs after, flag-gated, MAY rewrite punctuation — two contracts documented.
- **Qwen3-1.7B (Apache-2.0)** — [MEASURED] FALLBACK tier: perfectly safe (0 violations, unchanged 100%/95%) but a weak corrector (exact 8-9%); CPU EN marginal (0.9-1.7 s), CPU HI unusable.
- **Qwen2.5-1.5B-Instruct (Apache-2.0)** — [MEASURED, subset] REJECTED: HI WER 37%, additions 35%.
- **License audit [WEB-RESEARCHED]** — grammarly/coedit-large CC-BY-NC-4.0 and vennify/t5-GEC CC-BY-NC-SA: REJECT (every usable out-of-box GEC specialist found is non-commercial); **Qwen2.5-3B is Qwen-Research-licensed while its 1.5B/7B siblings and ALL Qwen3 are Apache** (trap caught); Gemma-3 custom+gated (not measured); ai4bharat/IndicXlit MIT (transliteration component only); mT5 Apache but needs training. Proposed next (ONE, founder-gated): **Smart Correction Runtime (staging only)** — post-final flag-gated stage, raw→punctuated→AI-corrected→user-corrected provenance, ambiguity review-flag UX, HI long-final latency strategy. Nothing promoted, nothing enabled.

---

## Milestone 57 — Smart Correction Runtime, staging (appended 2026-09-02)

Full report: [../milestones/57-smart-correction-runtime.md](../milestones/57-smart-correction-runtime.md).
Evidence: [57 evidence](../../research/experiments/57-smart-correction-runtime/). **STAGING IMPLEMENTED — PRODUCTION OFF** (flag pinned false + empty URL in prod.yml, ops-guard-tested; flag-off batch double-run byte-identical).

- **Qwen3-4B-Instruct-2507 Q4_K_M (Apache-2.0) — task: Smart Transcript Correction, EN+HI — STAGING SERVING ROLE** — GGUF sha-pinned (`3605803b…`) behind a drift-refusing launcher on the pinned llama.cpp b10344 CUDA build, its OWN instance (:8802). Product shape: POST-FINAL and USER-TRIGGERED (✨ Improve in the Playground; partials never corrected), language-scoped M56 prompts in code, and a mechanical OUTPUT VALIDATION gate (length ratio, script/flip rejection both ways, digit/email/URL survival, repetition guard reuse, prompt-leak rejection) — a failed validation serves the punctuated transcript, never the LLM. Provenance: `ai_correction_suggested` is its own append-only sample event; `current_transcript` moves only on a HUMAN save — machine and human corrections permanently distinguishable (DB-integration-tested). [MEASURED live through the real gateway] every spec EN case correct incl. unchanged already-correct and unchanged hallucination-bait (145-400 ms); HI Roman→Devanagari verbatim on the spec's own example, Hinglish natural, ONE recorded under-correction (gender case); all ten protected entities preserved; full-stack p50 EN 0.32-2.4 s / HI 0.97-8.9 s (20→250 words); VRAM 5.9 GB total with the realtime stack on the 8 GB card; worst-case continuous-correction hammer degrades realtime ~1.7× (policy proposed: cap concurrent corrections). Browser E2E EN+HI: improve/toggle/Share-carries-displayed/STALE-EDIT-drill (user's edit always wins) all green, leak scan clean, mobile clean. Fail-open + backend-kill + flag-off rollback drilled live (readiness `disabled|ready|degraded` all observed). Decision **A — ready for staging**; next: staging hardening + founder review. Nothing promoted, production untouched.

---

*This file grows by appended entries only. Do not edit prior entries — including their mistakes.*
