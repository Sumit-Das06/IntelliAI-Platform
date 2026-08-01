# IntelliAI Foundation Model Strategy — CTO Recommendation

| | |
|---|---|
| **Status** | APPROVED (Milestone 1.5, Deliverable 3, 2026-07-31) |
| **Version** | 0.2 (close-out: permanent/dated split marked) |
| **Research date** | 2026-07-31 (licenses verified at source on this date; verification URLs in the research record) |
| **Role of this document** | The recommendation of record for which open foundation model lineages IntelliAI builds on — and invests fine-tuning capital in — per primitive capability of [CAPABILITIES.md](CAPABILITIES.md), evaluated under [AI_STRATEGY.md](AI_STRATEGY.md)'s constitution. Model *adoption* still requires the per-artifact license gate (Constitution P4) at implementation time. |
| **Method** | Eight parallel research sweeps across all model domains; every load-bearing license verified on the HuggingFace card or repository LICENSE on 2026-07-31, not assumed from reputation. Items that could not be verified are explicitly flagged and quarantined from recommendations. |

---

## ⚠ How to read this document — two documents in one

This file contains a **permanent framework** and a **time-sensitive
research snapshot**. Know which half you are citing:

| Part | Sections | Nature |
|---|---|---|
| **PERMANENT** — cite freely, any year | §1 (scoring framework & weights) · §14's concentration-risk *protocol* · §15.1 (per-artifact license rule) | Constitution-derived method; survives every model in this file |
| **DATED EVIDENCE** — decays from 2026-07-31 | §0, §2–§13, the named models in §14–§15 | Verified on one date and aging since. **Re-verify licenses and landscape at the source before acting on any verdict here.** The flagged-unverified list (§15.3) decays fastest. |

A future revision re-runs the DATED half through the PERMANENT half; the
frameworks are the asset, the verdicts are their output for one moment
in time.

---

## 0. Executive summary  *(DATED EVIDENCE — snapshot of 2026-07-31)*

**The recommendation in one table** (per primitive capability: the lineage to
build on and fine-tune, plus a fallback from a different organization):

| Capability | Primary lineage | Backup lineage | Wedge/special |
|---|---|---|---|
| `transcription` | **OpenAI Whisper** (large-v3-turbo / large-v3, MIT) | **Qwen3-ASR** (Apache-2.0) | Meta Omnilingual ASR (Apache) for long-tail Indic; AI4Bharat IndicConformer (MIT) |
| `speech_synthesis` | **Kokoro-82M** (Apache) to serve · **Chatterbox** (MIT) to own | **Qwen3-TTS** (Apache) | **IndicF5** (MIT, 11 Indic langs) — the wedge lineage |
| `diarization` | **pyannote** (community-1 CC-BY-4.0 / 3.1 MIT) | **NVIDIA streaming Sortformer v2** (CC-BY-4.0) | Silero VAD v6 (MIT) as the universal VAD |
| `speech_translation` | **Composite** (our STT → our MT → our TTS) | — (no commercially-clean native S2ST exists) | watch: Canary-1b-v2 (CC-BY, EN↔EU only) |
| `chat` | **Qwen3 / Qwen3.5** (Apache, full size ladder) | **Mistral** open line (Apache; Sarvam-M proves Indic FT) | Gemma 4 pending license verification; Sarvam 30B/105B (Apache) as Indic reference |
| `embedding` | **Qwen3-Embedding** (Apache, 0.6B–8B) | **BGE-m3** (MIT) | EmbeddingGemma (Gemma terms) for edge only |
| `rerank` | **Qwen3-Reranker** (Apache) | **bge-reranker-v2-m3** (Apache) | — |
| `translation` | **IndicTrans2** (MIT, 22 Indic langs) + **Qwen-LLM MT** for high-resource | **MADLAD-400** (Apache, 400+ langs long-tail) | TranslateGemma & Hunyuan-MT: quality leaders, license caveats — watch |
| `moderation` | **Qwen3Guard** (Apache, 119 langs, streaming variant) | **Granite Guardian 4.1** (Apache, widest scope) | — |
| `ocr` | **PaddleOCR-VL** (Apache, 109 langs incl. Indic) | **GLM-OCR** (MIT) / **dots.ocr** (MIT, Indic strength) | Granite-Docling-258M (Apache) for the CPU-tiny tier; olmOCR-2 recipes as the FT playbook |
| `image_understanding` | **Qwen3-VL** (Apache, 2B–235B) | **InternVL3.5** (Apache) or **GLM-4.6V** (MIT) | Molmo2 (Ai2) for grounding + open-data reproducibility |

**Five strategic findings that outrank any individual model choice:**

1. **Piper is dead as a strategy.** Our planned M3 TTS engine was archived
   in October 2025; the successor fork is GPL-3.0 with an unfilled
   maintainer vacancy. The M3 plan changes: **Kokoro-82M replaces Piper**
   as the launch TTS engine (Apache-2.0, Hindi included, CPU real-time,
   the highest-momentum permissive TTS in existence). This finding alone
   pays for Milestone 1.5.
2. **One family can back six capabilities.** Qwen (Alibaba) offers
   Apache-2.0, actively-maintained, top-tier models for chat, vision,
   embedding, rerank, moderation, ASR and TTS — the largest coherent
   permissive stack ever available. We should exploit it — with the
   concentration-risk protocol of §14, not naively.
3. **Licenses move under you — in both directions.** In 18 months:
   Meta went NC→Apache (Omnilingual ASR) while retreating from open LLMs;
   Google went Gemma-terms→Apache (Gemma 4, pending verification);
   NVIDIA went CC-BY→custom license on its newest checkpoints; Spark-TTS,
   MiniMax and Fish Audio silently hardened to non-commercial. Consequence
   for Registry v2: **the license verdict attaches to the artifact
   version, never to the family name.**
4. **The "open" leaderboard is a licensing minefield.** The #1 multilingual
   embedder (NVIDIA), the best rerankers (Jina), the broadest MT model
   (NLLB-200), the best diarizer (DiariZen), and several top TTS models
   (F5, XTTS, Voxtral-TTS) are all non-commercial. Roughly a third of
   "open model" search results are unusable for us — which is exactly why
   this research verified everything at the source.
5. **The Indic wedge is unusually well-armed in open weights** — AI4Bharat
   (IndicConformer MIT, IndicTrans2 MIT, IndicF5 MIT, Indic Parler
   Apache) plus Sarvam's Apache-2.0 30B/105B LLMs (IndiaAI-funded) mean
   the wedge is buildable entirely on permissive lineages. Sarvam
   releasing open weights is simultaneously competitive validation and a
   usable resource; we treat their models as reference baselines to beat
   on *our* benchmarks, not as our base (differentiation demands it).

---

## 1. Scoring framework  *(PERMANENT)*

Weights encode the constitution: for a company that intends to *own*
models, fine-tunability and license freedom outweigh today's benchmark
position. A model we cannot legally build on at scale scores zero no
matter its quality; a model we cannot fine-tune is a rented engine.

| Criterion | Weight | What it measures (constitution link) |
|---|---|---|
| License & commercial freedom | 20% | Verified license; derivative rights; no MAU/revenue traps; synthetic-data rights (P4) |
| Fine-tuning ecosystem & ownership path | 20% | Recipes, LoRA maturity, community fine-tune precedent — can this lineage become `intelliai-*`? (flywheel) |
| Model quality (current tier) | 15% | Accuracy/naturalness tier — not decimal leaderboard positions |
| Multilingual & Indic fit | 10% | Wedge alignment (PRD positioning #4) |
| Serving & deployment maturity | 10% | Engines (vLLM/ONNX/GGUF/CT2), serving-class fit per CAPABILITIES §4 |
| Hardware flexibility | 10% | CPU-viability today, GPU path tomorrow, quantization (P10) |
| Momentum & org commitment | 10% | Release cadence, org strategy toward open weights |
| Openness & reproducibility | 5% | Training data/recipes published (P7) |

Scores below are 1–10 per criterion, shown as the weighted total. They are
judgment calls made on verified data — recorded so future revisions argue
with the scores, not with ghosts.

---

## 2. `transcription`  *(§2–§13: DATED EVIDENCE — verified 2026-07-31, re-verify before adoption)*

| Candidate | License (verified) | Weighted score | One-line verdict |
|---|---|---|---|
| **Whisper large-v3(-turbo)** | MIT | **8.6** | Not the leaderboard leader — the *ownership* leader |
| **Qwen3-ASR 0.6B/1.7B** (Jan 2026) | Apache-2.0 | **8.1** | Fastest-rising; Hindi; the second lineage |
| Granite Speech 4.1-2b | Apache-2.0 | 7.3 | Top English WER + official GGUF; zero Indic |
| Parakeet TDT 0.6B v2/v3 | CC-BY-4.0 | 7.2 | Best speed/cost EN/EU; zero Indic; newest checkpoints moved to custom NVIDIA license |
| Cohere Transcribe 2B | Apache-2.0 | 6.9 | Strong newcomer; no Indic, no FT culture yet |
| Omnilingual ASR (Meta) | Apache-2.0 | 6.8 | 1,600+ languages — the Indic long-tail asset; fairseq2 friction; EN not competitive |
| Canary-qwen-2.5b | CC-BY-4.0 | 6.4 | Long-time #1 English WER; English-only, GPU-bound |
| Moonshine streaming | MIT | 6.0 | Best edge streaming; English-centric, young |
| Kyutai STT | CC-BY-4.0 | 5.8 | Best streaming architecture; en/fr only |

**Primary: Whisper.** The top of today's leaderboard (Granite, Cohere,
Canary-qwen) sits within one WER point of each other — but none of them
matches Whisper's decisive strategic properties: MIT with zero conditions;
99 languages; the largest fine-tuning ecosystem in ASR history including a
mature *Indic fine-tune community* (exactly the flywheel we intend to
run); and CPU serving proven at scale through faster-whisper int8 —
matching our launch economics. The known weaknesses (hallucination on
silence, 30s window, no native streaming) are engineering-managed
(VAD-gating with Silero, chunking) and — decisively — **the model being
frozen matters less to a company whose plan is to fine-tune it.** We are
buying the lineage, not the checkpoint. **M2 proceeds unchanged on
faster-whisper.**

**Backup: Qwen3-ASR.** Apache-2.0, Hindi in-scope, a 0.6B CPU-plausible
size, timestamp companion model, 2M downloads/month within six months, and
an org (Alibaba/Qwen) currently outshipping everyone. If Whisper's age
starts losing evaluations in our wedge, this is the successor lineage —
and it rides the same Qwen serving stack as §6–§12.

**Wedge assets:** Omnilingual ASR (Apache) for long-tail Indic coverage no
one else has; IndicConformer-600M (MIT, 22 scheduled languages) as a
dedicated Indic engine and evaluation baseline. Both enter the registry as
routing candidates behind `intelliai-stt`, not as public names.

## 3. `speech_synthesis`

| Candidate | License (verified) | Weighted score | One-line verdict |
|---|---|---|---|
| **Kokoro-82M** | Apache-2.0 | **8.2** | Serve it: quality/cost champion, Hindi, CPU real-time |
| **Chatterbox (+Turbo)** | MIT | **8.0** | Own it: cloning + 23 langs incl. Hindi + corporate cadence |
| **Qwen3-TTS** | Apache-2.0 | 7.7 | Fastest riser; FT-supported; no Indic yet |
| IndicF5 | MIT | 7.2 | The wedge: 11 Indic languages, consent-collected data |
| CosyVoice2 | Apache-2.0 | 6.8 | Solid; zh-centric; v3.0 license unverified |
| Supertonic 3 | MIT | 6.6 | 2026 CPU-speed champion; preset voices only |
| Piper (fork) | GPL-3.0 | 3.5 | Archived → GPL fork, maintainer vacancy — **exit** |
| F5-TTS / XTTS-v2 / Fish | NC | 0 | Quality-tier leaders, commercially dead to us |

**This is the one capability where "serve" and "own" diverge, and the
recommendation is explicitly two-track.** **Serve Kokoro** at launch
(M3): Apache-2.0, Hindi voice pack, ONNX CPU real-time, beats XTTS-class
models in blind tests at 82M parameters — it is Piper's replacement and an
upgrade. But Kokoro cannot be our ownership lineage: no cloning, no
released training pipeline, single-maintainer risk. **Own Chatterbox**:
MIT end-to-end, zero-shot cloning (the P2-roadmap voice-cloning capability
needs exactly this), Hindi in its 23 languages, a company (Resemble)
shipping quarterly, and a built-in watermarker that aligns with our
consent-gated cloning policy. **The wedge lineage is IndicF5** (MIT, 11
Indic languages, and — rare in TTS — *consent-collected training data*,
which our own data constitution should reward). Backup for all three
roles: Qwen3-TTS (Apache, cloning, explicit fine-tune support; watch its
language expansion). PRD/M3 scope updates at M1.5 close.

## 4. `diarization`

| Candidate | License (verified) | Weighted score | Verdict |
|---|---|---|---|
| **pyannote community-1 / 3.1** | CC-BY-4.0 / MIT | **8.3** | Default; unbounded speakers; fine-tunable; CPU-viable |
| **Streaming Sortformer v2** | CC-BY-4.0 | 6.9 | The streaming tier; ≤4 speakers; GPU-oriented |
| DiariZen | CC-BY-NC | 0 | Best open DER — non-commercial, excluded |
| Reverb (Rev.com) | custom NC | 0 | Excluded |

**Primary: pyannote** — the only fine-tunable, permissive, unlimited-
speaker pipeline with real momentum (VC-funded steward, open-model
commitment in writing). Deployment note that must reach M-implementation:
pyannote models are HF-gated (contact-info gate, not a license term) — CI
and deploys need a token, or we use sherpa-onnx's redistributed ONNX
conversions (Apache engine) for a fully ungated CPU path. **Backup /
streaming tier: NVIDIA streaming Sortformer v2** — the *only* NVIDIA
diarizer that is commercially licensed; its ≤4-speaker cap fits the
realtime meeting/call use-cases it would serve. **Silero VAD v6 (MIT)**
becomes the platform-wide VAD (it also gates Whisper hallucination).
DiariZen's exclusion despite the best DER is the constitution working as
intended: no license verdict, no traffic.

## 5. `speech_translation`

**Recommendation: stay composite — and this is now evidence-backed, not
just architecturally convenient.** Verified reality: *no commercially
usable open native speech-translation model exists.* SeamlessM4T and every
derivative (including AI4Bharat's IndicSeamless) inherit CC-BY-NC;
Canary-1b-v2 (CC-BY) covers only English↔European; OWSM v4 (CC-BY) is
below quality bar. The D2 design — `speech_translation` as a
composite-backed primitive (our STT → our MT → optionally our TTS) — is
therefore the *only* clean implementation today, and the contract already
guarantees we can swap in a native model the day one appears under a
usable license. Wedge note: BhasaAnuvaad (CC-BY-4.0, largest open Indic
speech-translation *dataset*) means we can eventually train our own —
the dataset is clean even though the reference model isn't.

## 6. `chat`

| Candidate | License (verified) | Weighted score | Verdict |
|---|---|---|---|
| **Qwen3 / Qwen3.5** | Apache-2.0 (all open sizes) | **9.0** | The lineage: full ladder, hybrid thinking, best FT ecosystem, 119+ langs |
| **Mistral open line** | Apache-2.0 | **7.9** | Backup: EU-based, Sarvam-M proved it as an Indic FT base |
| Gemma 3 → 4 | Gemma ToU → Apache (4, unverified) | 7.6* | Strong Indic + edge; *score rises ~0.4 if Gemma 4 Apache confirms |
| GLM-4.5→5.2 | MIT | 7.4 | Agentic/reasoning high tier; flagship-heavy, thin small-model ladder |
| DeepSeek V3.x/V4 | MIT | 7.0 | Frontier reasoning; no small models — serve-only tier, not an FT lineage |
| Llama 3.3/4 | Community license | 5.5 | Naming+MAU conditions, EU vision carve-outs, org retreating from open — declining |
| gpt-oss | Apache-2.0 | 6.2 | Good one-off; no cadence commitment; English-centric |
| OLMo 3 | Apache-2.0 + full data | 6.5 | The reproducibility reference (P7); quality tier below leaders |
| Kimi K3 / MiniMax M2.7 | bespoke / NC-ish | excluded | License tightening mid-family — exactly the volatility we refuse |

**Primary: Qwen3/3.5.** The scoring is not close. Apache-2.0 across every
open size; a genuine size ladder (0.6B CPU → A3B MoEs on a single 24GB
GPU → frontier MoE) that maps 1:1 onto our serving classes and pricing
tiers; hybrid thinking (which is how CAPABILITIES.md models "reasoning" —
a tier, not a capability); the largest derivative/fine-tune ecosystem on
HuggingFace (>200K derivatives — deepest recipe pool to learn from); and
the best Indic quality of any non-Indian major lineage. **Backup:
Mistral's Apache line** — organizationally independent (EU), proven as an
Indic fine-tuning base by Sarvam-M itself, and the natural fallback if
Qwen concentration risk (§14) ever fires. Gemma 4 becomes a serious
contender *if* its reported Apache relicensing verifies on the actual
model cards — verification is a step-0 task at adoption time. DeepSeek/GLM
enter as *served* high-end reasoning tiers later, not as fine-tuning
lineages (no small models to own). OLMo is the standing reference for
what P7-grade reproducibility looks like — we study its model flow even
where we don't deploy it.

## 7. `embedding`

**Primary: Qwen3-Embedding** (Apache; 0.6B CPU-viable to 8B leaderboard
tier; matryoshka dims; 32K context; 100+ languages; vLLM/TEI/GGUF all
native; a multimodal sibling already exists for future doc-image
retrieval). **Backup: BGE-m3** (MIT; dense+sparse+ColBERT in one model —
architecture diversity that pure dense embedders can't replicate; the
industry workhorse with FlagEmbedding fine-tune recipes). NC traps
verified and blacklisted: the entire Jina line, NVIDIA's
leaderboard-topping embedders, SFR, Linq. EmbeddingGemma only for a future
edge story (Gemma terms). Embeddings are also the *cheapest fine-tuning
flywheel we own* — domain embedding tunes (sentence-transformers) are
weekend-scale work with immediate retrieval-quality payoff; this is where
the fine-tuning muscle gets its first reps before speech models.

## 8. `rerank`

**Primary: Qwen3-Reranker** (Apache; 0.6B–8B; instruction-aware; same
serving stack as the embedder — one operational surface for the whole
retrieval pair). **Backup: bge-reranker-v2-m3** (Apache; the most-deployed
open reranker; CPU-viable). Watch: zerank (relicensed to Apache, built on
Qwen3 — evidence the ecosystem consolidates on the same base we chose).
Excluded: Jina v3 (NC — the quality leader, unusable), ContextualAI (NC).

## 9. `translation`

**Recommendation: routing-first, exactly as the AI_STRATEGY §3 example
predicted.** No single open MT lineage wins all three segments:

- **Indic pairs (the wedge): IndicTrans2** — MIT, all 22 scheduled
  languages, CPU-viable via CTranslate2, actively maintained under
  government backing. This is the wedge's translation backbone and a
  fine-tuning lineage we can own. (IndicTrans3-beta: CC-BY-4.0 but
  Gemma-3-based — license flow-down question flagged; adopt only after
  legal read at GA.)
- **High-resource pairs: LLM-backed** via the chat lineage (Qwen3
  serving already in place — zero extra infrastructure; WMT-validated
  approach). TranslateGemma (Jan 2026, 55 languages, SOTA open tier) is
  the strongest dedicated alternative but carries Gemma terms;
  Hunyuan-MT-7B won 30/31 WMT25 pairs but has *no license tag on its
  card* and Tencent's historical MAU/territory clauses — both are
  watch-list, not build-list, until verified.
- **Long-tail: MADLAD-400** (Apache, 400+ languages, CT2 CPU path) as the
  coverage fallback.
- **Blacklisted with emphasis: NLLB-200** — CC-BY-NC despite ~2M monthly
  downloads (an industry-wide compliance blind spot we will not join).
- Seed-X (ByteDance, OpenMDW permissive) is the credible dedicated-MT
  backup if the LLM path underperforms on quality-per-cost.

## 10. `moderation`

**Primary: Qwen3Guard** — Apache-2.0 and **the only guard model with real
multilingual coverage (119 languages)**, which for an Indic-wedge platform
is disqualifying for the alternatives by itself; a streaming variant
(token-level) fits realtime voice later. **Backup: Granite Guardian 4.1**
(Apache; the widest scope — harm plus RAG groundedness plus agentic
function-call validation — which becomes valuable exactly when composites
and agents arrive; bring-your-own-criteria fits policy-as-data).
gpt-oss-safeguard's policy-as-prompt approach is the architectural
direction moderation is heading — worth studying, too heavy to serve as
the default. Llama Guard (Llama conditions) and ShieldGemma (Gemma ToU)
lose on license cleanliness.

## 11. `ocr`

**Primary: PaddleOCR-VL** (Apache-2.0 verified; 109 languages *including
Devanagari/Tamil/Telugu* — the strongest Indic story in open OCR;
SOTA-tier OmniDocBench; full layout/tables/reading-order pipeline; 0.9B
CPU-plausible, vLLM-servable) with the classic PP-OCR pipeline as the
cheap-CPU tier behind the same contract. **Backups: GLM-OCR** (MIT, 0.9B,
#1 OmniDocBench v1.5 at release, Indic coverage unverified) and
**dots.ocr** (MIT, 1.7B, explicit low-resource/Indic strength, single-
model layout+content JSON — but single-release cadence risk).
**Fine-tuning playbook: olmOCR-2** — Apache with *complete* training
code, data, and GRPO recipes; when we fine-tune document models for
customer domains, this is the published recipe we follow. CPU-tiny tier:
Granite-Docling-258M (Apache, DocTags). **Blocked by license, explicitly:**
Surya/Marker/Chandra (Datalab OpenRAIL revenue caps — a trap for a funded
company), MinerU (AGPL VLM weights), MonkeyOCR (NC clause under an Apache
badge — the single best example this research found of why we verify).

## 12. `image_understanding`

**Primary: Qwen3-VL** — Apache-2.0 at every size (2B→235B MoE; verified at
both ends), best-in-class open OCR-in-VLM and 2D grounding, day-0
vLLM/SGLang, and the size ladder again maps onto serving tiers. Also the
base most OCR specialists (olmOCR, Chandra) chose — when we fine-tune
document intelligence, the substrate is already our VLM lineage.
**Backups: InternVL3.5** (Apache at verified sizes; the benchmark rival;
use 3.5+ only — older generations have per-size license mess) and
**GLM-4.6V** (MIT, incl. a 9B Flash for the cheap tier). **Molmo2** (Ai2)
earns a watch slot for fully-open training data and pointing/grounding
skills relevant to future document/GUI work. Traps verified: Qwen2.5-VL-3B
(research-only — size-level trap inside an otherwise-permissive family),
Llama vision (EU carve-out), MiniCPM (registration + scale caps), Pixtral
Large (NC).

---

## 13. Weighted-criteria note on what did NOT win

Applying "do not optimize for today's benchmark leader" concretely — the
strongest models this research *rejected*, and the single reason each
lost: Canary-qwen-2.5b (best English WER; English-only + GPU decoder),
NVIDIA llama-embed-nemotron-8b (#1 multilingual embedder; research-only
license), Jina reranker v3 (top reranker; NC), DiariZen (best DER; NC),
NLLB-200 (broadest MT; NC), F5-TTS (top cloning quality; NC weights),
Chandra (best handwriting OCR; revenue-capped), Hunyuan-MT (WMT25 winner;
unverifiable license), Llama 4 (largest install base; conditional license
+ retreating org). A benchmark summary would have recommended eight of
those nine.

## 14. The Qwen question — family reuse and concentration risk

**The reuse opportunity is real and we should take it.** Qwen backs the
primary or backup for seven capabilities (chat, VLM, embedding, rerank,
moderation, ASR-backup, TTS-backup). Concretely that buys: one serving
stack (vLLM/SGLang tuned once per serving class), one tokenizer family,
one fine-tuning toolchain (LLaMA-Factory/Unsloth/ms-swift), transferable
LoRA expertise between capabilities, and a single vendor-watch instead of
seven. For a solo-founder company, concentrating operational learning is
not a nice-to-have — it is the difference between shipping P3 and
drowning in it.

**The concentration risk is equally real; the protocol:**

1. **Apache-2.0 is irrevocable for released weights** — the downside is
   capped at "no future versions," never "lose what we built on." Pin
   artifacts (P8 makes rollback structural).
2. **Every Qwen-primary capability keeps a non-Qwen backup warm in the
   registry** (Mistral chat, BGE embedding/rerank, Granite Guardian,
   InternVL/GLM vision) — a real routing target we periodically evaluate,
   not a name in a document. The registry makes the swap a lifecycle
   event; that is the whole point of the architecture.
3. **Watch triggers, reviewed each milestone close:** a Qwen release
   under a non-Apache license (precedent: Qwen3.7 went proprietary);
   geopolitical/export-control action affecting Chinese open weights in
   our operating markets; cadence stall > 2 quarters.
4. **Our fine-tunes hedge us further**: as `intelliai-*` artifacts
   accumulate on top of pinned bases, the dependency shifts from "Qwen's
   future" to "our lineage's future" — which is precisely the model-
   company transition the strategy intends.

## 15. Cross-cutting consequences for Registry v2 and the roadmap

1. **License verdicts are per-artifact-version facts** (§0 finding 3) —
   Registry v2's license gate must record verdict + verification date +
   source URL per artifact, and a *family-level* trust assumption is
   forbidden. (Verified examples of one family spanning permissive→NC:
   Qwen2.5-VL sizes, Canary versions, BGE variants, Mistral open/MRL.)
2. **Roadmap deltas at M1.5 close:** M2 unchanged (faster-whisper
   validated); **M3 = Kokoro, not Piper** (PRD v0.4 table and
   ARCHITECTURE forward map update); voice-cloning capability (P2 phase)
   pre-assigned to the Chatterbox lineage; `/v1/models` metadata gains
   nothing new — the registry v1 schema already fits these entries.
3. **Re-verify before adoption** (flagged UNVERIFIED in research):
   Gemma 4's Apache claim on actual HF cards; Qwen3.5 per-repo licenses;
   Fun-CosyVoice 3.0; Moonshine language variants; Hunyuan-MT license
   file; Supertonic 3 language list; IndicTrans3 GA terms. None of these
   blocks a current recommendation; all are recorded as adoption-time
   gates.
4. **Datasets got the same audit as models** and the same rule applies:
   BhasaAnuvaad/IndicVoices (CC-BY-4.0, usable) vs Emilia-trained model
   weights (NC-contaminated) is the clearest proof that **data licensing
   is model licensing one step earlier** — Constitution P4's extension to
   datasets (AI_STRATEGY §2) is confirmed necessary.

---

*Change log:*
- *2026-07-31 — v0.1: initial recommendation (M1.5 D3): 11 capabilities,
  8 verified research sweeps, primary+backup lineages, Qwen concentration
  protocol, Piper exit / Kokoro adoption, per-artifact license-gate
  requirement for Registry v2. Pending approval.*
