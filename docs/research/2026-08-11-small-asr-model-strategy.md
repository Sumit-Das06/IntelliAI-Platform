# Small-Model / Modular Multilingual STT Strategy — Research & Decision Document

| | |
|---|---|
| **Status** | RESEARCH REPORT — awaiting founder decision (no code, no training, no production change) |
| **Date** | 2026-08-11 (all licenses and landscape claims read at source this date unless another date shown; repo facts verified 2026-08-10) |
| **Trigger** | Management directive: broaden from "whisper-small + Hindi fine-tune" to a small-model / modular multilingual STT investigation across EN · HI · AR · TA · ML · ZH, optimizing for parallel call-center-class serving |
| **Governed by** | [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) · [ADR-0005](../adr/0005-permissive-model-licensing-policy.md) · [FOUNDATION_MODELS.md §1](../FOUNDATION_MODELS.md) · [FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md) · [stt-execution-roadmap.md](stt-execution-roadmap.md) · [stt-target-architecture.md](stt-target-architecture.md) |
| **Supersedes / extends** | Extends [2026-08-10-first-finetuning-experiment.md](2026-08-10-first-finetuning-experiment.md) (EN/HI/AR screens remain valid, dated 2026-08-10). Does **not** supersede the execution roadmap — it feeds it. |

Labels: **[FACT]** read at primary source, dated · **[EVIDENCE]** our own
evaluation-plane records · **[CLAIM]** publisher/third-party, unverified
by us · **[INFERENCE]** reasoning · **Unknown / not documented** where a
value could not be established. **All concurrency numbers in §16 are
ESTIMATES, clearly marked — none are production benchmarks.**

---

## 1. Executive summary

**Management's small-model instinct is correct, and the evidence makes
it structural, not aesthetic: no single permissive model — small or
large — serves all six languages well.** The recommended architecture
is the **hybrid pool** the platform already designed for
([stt-target-architecture.md](stt-target-architecture.md)): one small
multilingual default engine plus per-language specialist slots, each
slot filled only by measured evidence. Our registry already routes per
(public model, language) with zero gateway work.

The seven load-bearing findings:

1. **The six-language coverage problem has no single-engine answer.**
   Qwen3-ASR 0.6B — management's named candidate — is excellent for
   4/6 (FLEURS: zh 2.88 · hi 19.12 · ar 25.51; LID 96.8%) but **has no
   Tamil and no Malayalam** [FACT, official list read 2026-08-11].
   Whisper-small nominally covers all six but is weak at Hindi
   (63.5 zero-shot CV11) and **effectively broken for Malayalam at
   every size (~100+ WER, OpenAI's own tables)** [FACT]. Omnilingual
   ASR covers all six permissively but caps audio at 40 s against our
   600 s product ceiling and has no documented CPU path [FACT].
2. **Small permissive specialists exist exactly where the generalists
   fail.** AI4Bharat ships per-language **IndicConformer ta and ml
   checkpoints at ~120M, MIT** [FACT]; measured on the IndicVoices
   spontaneous benchmark (their paper): ta 31.2 / ml 40.5 WER vs
   Whisper's ta 78.4 / ml 148.6 [FACT — publisher's numbers].
   Malayalam is the cleanest possible demonstration that the modular
   strategy is *necessary*, not optional.
3. **Chinese has a standout permissive small engine and a licensing
   minefield around it.** Qwen3-ASR 0.6B (Apache-2.0) posts FLEURS-zh
   2.88 vs whisper-small's 20.8 — ~7× better [FACT both]. Nearly every
   other Chinese option fails the license gate: SenseVoice-Small and
   Paraformer weights sit under the FunASR Model License (no express
   commercial grant), TeleSpeech needs written approval, and all
   WeNet/icefall/sherpa-onnx zh checkpoints are trained on
   non-commercial corpora [FACT].
4. **Routing is mostly free for us.** Our API already takes a language
   parameter and the registry already resolves per-language routes —
   declaration-first is the in-force law. An acoustic LID is needed
   only for undeclared traffic; the best permissive component is
   **SpeechBrain ECAPA VoxLingua107 (Apache-2.0, all six languages,
   6.7% dev error, CPU-cheap)** [FACT]. Code-switching literature says
   the router must pick a code-switch-tolerant backend per call, never
   flip mid-utterance [RESEARCH FINDING].
5. **CPU concurrency favors small models arithmetically.** Our measured
   incumbent: RTF 0.162 (~6× real-time) at ~800 MiB [EVIDENCE].
   faster-whisper's own benchmark: small int8 = 1,477 MB RAM at ~7.6×
   real-time sequential, 3,608 MB at ~15× batched [FACT]. A pool of
   small engines is resident-RAM-cheap (§16); cores, not memory, are
   the binding constraint.
6. **Fine-tuning support diverges sharply.** Whisper: LoRA/PEFT mature,
   fits our 8 GB RTX 5070, serving conversion official. Qwen3-ASR:
   official recipe but **full fine-tuning only — no LoRA documented**
   [FACT], VRAM needs undocumented — an 0.6B full FT on 8 GB is
   borderline [INFERENCE]. IndicConformer: NeMo-fork training, no
   adapter precedent [FACT].
7. **Tamil/Malayalam/Chinese are not yet product languages.** Core
   Speech Language Policy v1 names EN/HI/AR. Extending it is a founder
   decision this report requires before any ta/ml/zh work is funded
   (§25) — and each new language needs a ruler binding and a corpus
   before it can be measured at all.

**Recommended first experiment (§18):** one milestone, two arms, both
on existing hardware — **Arm 1:** the already-designed Hindi LoRA on
whisper-small (E1, unchanged, local RTX 5070). **Arm 2 (new, cheaper):**
a **zero-shot small-model bracket** on the same frozen Hindi public
eval — whisper-small vs Qwen3-ASR 0.6B (GGUF, CPU) vs IndicConformer —
plus a Chinese CPU-viability baseline for Qwen3-ASR 0.6B on the fresh
Common Voice 26.0 zh test. Arm 1 proves the training loop; Arm 2
produces the first measured routing evidence. Together they answer
management's question with numbers instead of cards.

## 2. Management requirement (restated)

Prefer the smallest model that delivers acceptable quality per
language, so many calls can be processed in parallel without loading
several huge models. Investigate small ASR models, HF models/datasets,
six languages, Qwen small models, language routing, call-center
concurrency. Direction, not mandate: evidence decides. This aligns with
three standing laws: CPU-first serving, the switching test, and
"per-language engines are a legitimate outcome" (framework §7.3).

## 3. Current IntelliAI STT architecture ([FACT], repo, 2026-08-10)

One backend pipeline for all clients (Web, Android, future):
`POST /v1/audio/transcriptions → auth → validation → runtime
(ffmpeg → 16 kHz mono → pipeline VAD → engine) → transcript + segments
→ consent-gated collection → SpeechSample → correction → Dataset →
immutable DatasetVersion → sha256-pinned JSONL training artifact`.
Engine imports confined to `engines/` (AST-enforced; `torch`/
`transformers` denylisted elsewhere). `ml/training/` is an empty stub —
the sanctioned home for training code. **No second pipeline will be
created for Android.**

## 4. Current model ([EVIDENCE] unless noted)

- `whisper-small` via faster-whisper/CTranslate2, **int8 at load**,
  `device="cpu"`; artifacts URL+SHA-256-pinned, re-verified at boot.
- Measured: EN WER 0.000 (corpus ceiling), RTF 0.162, ~800 MiB steady,
  p95 PASS ~9× headroom, 0 hallucinated words (VAD short-circuit).
- Registry: `en` SUPPORTED · `hi` AVAILABLE · `ar` AVAILABLE — all to
  the same artifact; per-language routes already exist as a mechanism.
- Known engine quirks: explicit `hi` declaration costs ~9.4× on
  non-speech input [EVIDENCE]; `whisper-large-v3` breaches CPU
  real-time and hallucinates on VAD-passed non-speech [EVIDENCE,
  Stage 1, 7 records].

## 5. Small-model strategy — size categories (defined for this report)

| Category | Params | Examples here |
|---|---|---|
| **Tiny** | < 100M | whisper-tiny 39M, whisper-base 74M, TeleSpeech-base 90M |
| **Small** | 100M – 400M | **whisper-small 244M**, **IndicConformer ta/ml 120M**, Omnilingual CTC 325M, Dolphin-small 372M, OWSM small 367M, SenseVoice ~234M, Paraformer 220M |
| **Medium** | 400M – 1.5B | IndicConformer-600M, **Qwen3-ASR 0.6B**, Parakeet 600M, whisper-medium 769M, turbo 809M, OWSM 1B, FireRedASR-AED 1.1B |
| **Large** | > 1.5B | whisper-large-v3 1.55B, Qwen3-ASR 1.7B, Voxtral 3B+, Canary-Qwen 2.5B |

The strategy target: the **smallest engine per language that clears the
product bar** — measured, per the improvement ladder, never assumed.
Note Qwen3-ASR "0.6B" is our Medium class boundary-rider: its GGUF Q8
artifact is 805 MB [FACT], comparable to whisper-small's runtime
footprint.

## 6. Candidate model landscape (licenses read at source; date shown)

**Screened and viable (permissive):**
whisper family (Apache-2.0/MIT, 2026-08-10) · Qwen3-ASR 0.6B/1.7B
(Apache-2.0, 2026-08-11) · IndicConformer-600M + per-language ta/ml
120M (MIT, 2026-08-11) · Omnilingual ASR (Apache-2.0, 2026-08-10/11) ·
Dolphin base/small (Apache-2.0, 2026-08-11) · OWSM v3.1/v4
(CC-BY-4.0, 2026-08-11) · FireRedASR-AED-L (Apache-2.0, 2026-08-11;
1.1B — size-flagged) · XLS-R / w2v-BERT 2.0 (Apache-2.0/MIT,
2026-08-10; CTC product regressions) · Moonshine (MIT; EN-only) ·
Granite Speech (Apache-2.0; EN+EU only) · Cohere Transcribe Arabic
(Apache-2.0; gated + remote code) · Vakyansh ta/ml (MIT; stale 2022,
weak).

**Fail the license gate (verbatim reasons in §9):**
SenseVoice-Small weights · Paraformer official weights · TeleSpeech ·
MMS · MMS-LID · SeamlessM4T v2 · Parakeet-RNNT-1.1B-multilingual ·
all WeNet/icefall/sherpa-onnx zh checkpoints (provenance) ·
vasista22 whisper-tamil fine-tunes (weights Apache but trained on
research-only MSR + LDC Babel — the IndicWhisper taint pattern; usable
as an eval reference, never as our base).

## 7. Detailed model comparison (the serious candidates)

| Model | Params | Arch | Six-lang coverage | License | FT support | CPU | Timestamps | Punct | Streaming | Key numbers [source] |
|---|---|---|---|---|---|---|---|---|---|---|
| whisper-small | 244M | enc-dec seq2seq | 6/6 nominal; ml broken | Apache-2.0 (card) | **LoRA/PEFT mature; official recipe; CT2 conversion official** | **proven [EVIDENCE]** | native segments | native | chunk+VAD | EN 0.000 [EVIDENCE]; hi CV11 63.5→32.0 FT [FACT]; ta FLEURS 35.2 / CV9 28.7 [FACT]; **ml ~101 (broken)** [FACT]; zh FLEURS 20.8 [FACT] |
| Qwen3-ASR 0.6B | ~0.6B (+LM) | audio-LLM | **4/6 — no ta, no ml** | Apache-2.0 | official recipe, **full-FT only, no LoRA** [FACT]; VRAM undoc | GGUF Q8 805 MB official; RTF unmeasured | separate aligner, 11 langs, **no hi/ar/ta** | Unknown / not documented | vLLM streaming | zh 2.88 · hi 19.12 · ar 25.51 (FLEURS) · LID 96.8% [FACT, tech report] |
| IndicConformer ta / ml | **120M each** | Conformer hybrid CTC+RNNT | 1/6 each (specialists) | MIT | NeMo-fork training; no adapter precedent | CTC branch CPU-tractable [INFERENCE]; ONNX undocumented | frame-sync CTC (exposure unverified) | Unknown / not documented | no | ta 31.2 / ml 40.5 WER on IndicVoices bench (600M sibling) vs Whisper 78.4/148.6 [FACT, paper] |
| IndicConformer-600M | 600M | same | 3/6 (hi/ta/ml) | MIT | same | intended [INFERENCE]; onnxruntime pinned | same | Unknown | no | hi 13.2 on Vaani bench [CLAIM, card] |
| Omnilingual CTC-325M | 325M | wav2vec2 + CTC head | **6/6** | Apache-2.0 | fairseq2 recipe (32-GPU reference) [FACT] | undocumented; conversion ours | frame-sync (unverified) | no (char CTC) | no | **40 s audio cap** [FACT]; per-lang CER for our six: Unknown / not documented |
| Dolphin-small / base | 372M / 140M | CTC-attention (E-Branchformer) | zh (+40 Eastern langs; no ar) | Apache-2.0 (code+weights) [FACT] | scripts present | plausible [INFERENCE] | Unknown | Unknown | 2026 streaming variants | avg 25.2 WER mixed suite; zh-specific: Unknown / not documented |
| OWSM v4 base/small | 102M/370M | enc-dec (ESPnet) | zh yes; our six unenumerated | CC-BY-4.0 | ESPnet training | plausible [INFERENCE] | yes (Whisper-style) | yes | no | per-lang numbers: Unknown / not documented |
| FireRedASR-AED-L | 1.1B | AED | zh(+en) | Apache-2.0 | none documented | none documented; ≤60 s cap | none documented | Unknown | no | AISHELL-1 CER 0.55 [FACT] — near-SOTA, but Medium+ size, no serving story |

## 8. Language coverage matrix (permissive models only)

| Lang | Generalist option | Specialist option | Coverage verdict |
|---|---|---|---|
| EN | whisper-small [EVIDENCE: at ceiling] | (closed — Stage 2) | **solved** |
| HI | whisper-small+LoRA (proof exists) · Qwen3 0.6B (19.12) | IndicConformer (13.2 claim) | strong, needs our measurement |
| AR | Qwen3 0.6B (25.51) · whisper (unevaluated) | Cohere-AR 2B (gated/remote-code) | candidates exist; **ruler missing** |
| TA | whisper-small (28–35, tunable) | **IndicConformer-ta 120M MIT** | good |
| ML | **none — Whisper broken (~100 WER)** | **IndicConformer-ml 120M MIT — effectively the only option** | specialist forced |
| ZH | **Qwen3 0.6B (2.88)** | Dolphin 140/372M backup | strong |

**This matrix is the architecture argument**: EN wants the incumbent,
ML forces a specialist, ZH strongly prefers Qwen3, HI/AR/TA are
measurable contests. One engine cannot win all six; a pool can.

## 9. License matrix

**Commercially safe** [FACT, read at source, dates in §6]:
whisper (all sizes) · Qwen3-ASR 0.6B/1.7B + ForcedAligner ·
IndicConformer 600M + ta/ml 120M · Omnilingual ASR · Dolphin ·
OWSM (CC-BY, attribution) · FireRedASR-AED · XLS-R · w2v-BERT 2.0 ·
Moonshine · SpeechBrain ECAPA LID · faster-whisper (MIT) ·
Vakyansh (MIT, stale).

**Needs legal review**: Paraformer (HF mirror tagged `apache-2.0`, but
origin ModelScope distribution binds the FunASR Model License —
contradictory) · MASC dataset (platform CC-BY vs YouTube provenance) ·
MUCS SLR104 (CC-BY-SA share-alike on a trained model) · SPRING-INX
(no license metadata; paper says "public domain" — one email resolves
~470 h of ta+ml data).

**Non-commercial / unsuitable** [FACT, verbatim reasons]:
SenseVoice-Small weights (FunASR Model License: "provided for reference
and learning purposes only", no express commercial grant, unilateral
revision, conduct-clause forfeiture) · TeleSpeech ("obtaining written
approval" required for commercial use) · MMS + MMS-LID (CC-BY-NC-4.0) ·
SeamlessM4T v2 (CC-BY-NC-4.0) · Parakeet-RNNT-1.1B-multilingual
(NVIDIA community license) · WeNet/icefall/sherpa-onnx zh checkpoints
(trained on WenetSpeech "non-commercial", KeSpeech NC, MagicData
NC-ND, AISHELL-2 research-only — split verdict, weights tainted) ·
vasista22 whisper-tamil (MSR research-only + Babel in training data).

## 10. Fine-tuning capability

| Model | LoRA | QLoRA | Full FT | PEFT | Official scripts | Fits RTX 5070 8 GB? |
|---|---|---|---|---|---|---|
| whisper-small | ✅ documented | ✅ | ✅ (Colab-class) | ✅ | HF blog + PEFT example [FACT] | **LoRA yes (~3–5 GB est.); full FT borderline** |
| whisper-medium | ✅ | ✅ | 16 GB+ | ✅ | same | LoRA likely (~5–7 GB est.); full FT no |
| Qwen3-ASR 0.6B | **not documented** | not documented | ✅ official | not documented | QwenLM/Qwen3-ASR/finetuning [FACT] | **Unknown — VRAM undocumented; full FT of 0.6B on 8 GB borderline [INFERENCE]** |
| IndicConformer ta/ml 120M | no precedent | no | ✅ (NeMo fork) | no | AI4Bharat NeMo fork, nemo-v2 branch [FACT] | plausible at 120M [INFERENCE]; unverified stack |
| Omnilingual | no precedent | no | ✅ fairseq2 | no | official recipe (32-GPU reference) [FACT] | 325M CTC maybe with grad-accum [INFERENCE] |
| XLS-R/w2v-BERT | n/a (full CTC head) | — | ✅ 16 GB class | — | HF blogs [FACT] | yes (documented 16 GB V100 / Colab) |

**Recommendation stands: LoRA/PEFT first, on Whisper** — the only
lineage where adapter tuning is documented, cheap, and serving-
compatible. Everything else trains full-model on unverified stacks.

## 11. Hardware / VRAM comparison (training + inference)

Training: §10. Inference footprints (documented only):
whisper-small int8 **1,477 MB RAM** sequential / 3,608 MB batched
[FACT, faster-whisper README] — our own container measures ~800 MiB
steady [EVIDENCE, different workload shape]; Qwen3-ASR 0.6B GGUF
weights 805 MB (Q8) / 1.51 GB (BF16) [FACT — weights floor, runtime
RAM Unknown / not documented]; Omnilingual CTC-325M ~2 GiB VRAM (GPU
figures) [FACT]; IndicConformer 120M ≈ 0.5 GB fp32 weights
[INFERENCE]; ECAPA LID: params Unknown / not documented, ~tens of MB
class [INFERENCE]. Everything else: Unknown / not documented.

## 12. CPU / production considerations

- **Only one CPU measurement exists in the entire universe — ours.**
  Every other CPU claim is inference or absent. Any slot decision
  requires our own CPU RTF/memory measurement first (this is the
  cheapest kind of session: no training, in-stack, ~1 day each).
- Serving-stack costs differ sharply [INFERENCE from verified stack
  facts]: whisper = zero new stack; Qwen3 GGUF = llama.cpp-class
  runtime (new, but small and dependency-light); IndicConformer =
  AI4Bharat NeMo fork + `trust_remote_code` (needs the security-review
  process, prerequisite 5.3) or an ONNX export spike (undocumented);
  Omnilingual = fairseq2 (heavy); OWSM = ESPnet (heavy).
- Timestamps: our `verbose_json` contract returns segments. Whisper
  native; Qwen3 needs its aligner — **which excludes hi/ar/ta**
  [FACT], so Qwen3 slots would ship without word timestamps for
  exactly the languages we'd use it for (zh is covered). IndicConformer
  CTC timestamps unexposed/undocumented. This is a real contract
  question for non-Whisper slots (§24).
- Android/on-device: **out of scope by architecture** — the keyboard
  calls the same HTTPS API; no on-device model is proposed. (Moonshine
  remains the future edge candidate if that ever changes.)

## 13. Dataset landscape (commercially safe assemblies per language)

EN/HI/AR: unchanged from [2026-08-10 report §§10–13] — EN closed; HI
backbone IndicVoices+Kathbath+CV (10 h curated for E1, scale-up
available); AR = MSA-leaning CV/FLEURS + MASC (conditional), dialect
corpora all NC.

**New screens (2026-08-11):**

| Lang | TRAIN (safe) | Assemblable | EVAL (least contaminated) |
|---|---|---|---|
| **TA** | Shrutilipi ~790 h (CC-BY) + Kathbath 185 h (CC0) + CV26 235 h validated (CC0) + IISc-MILE SLR127 150 h (CC-BY-2.0) + IndicVoices ~106 h (CC-BY) | **~1,450 h** (+226 h if SPRING-INX confirms) | IndicVoices ta test 5 h (spontaneous) · Kathbath test-unknown · FLEURS ta test |
| **ML** | Shrutilipi ~360 h + Kathbath 147 h + IndicVoices ~66 h + CV26 4 h | **~575 h** (+245 h SPRING-INX pending) | IndicVoices ml test 5 h · Kathbath ml tests · FLEURS ml test |
| **ZH** | AISHELL-1 ~150 h train (Apache-2.0) + THCHS-30 ~30 h (Apache-2.0) + CV26 zh-CN 239.6 h validated (CC0) + Emilia-YODAS ~300 h (CC-BY, mined labels) | **~750–900 h** | **CV 26.0 zh-CN test (cut 2026-06-12 — post-dates most model training)** · FLEURS zh secondary |

Excluded (NC/unusable): WenetSpeech, KeSpeech, MagicData-RAMC,
AISHELL-2, Emilia main split, SADA, Casablanca, QASR, MGB-2, Microsoft
Indian corpus, MUCS SLR103 (dead license URL), OpenSLR 63/65 (BY-SA),
IMaSC (BY-SA). Vaani: CC-BY-4.0 but only ~6.5% transcribed — SSL
audio, not a labeled source yet.

## 14. Dataset license matrix (six languages, one view)

| Verdict | Datasets |
|---|---|
| **Safe (CC0/CC-BY/Apache)** | Common Voice 26.0 (all langs; no re-hosting) · FLEURS · IndicVoices · Kathbath · Shrutilipi · Lahaja · Svarah · IISc-MILE ta · AISHELL-1 · THCHS-30 · Emilia-YODAS · LibriSpeech · People's Speech (CC-BY subset) · VoxPopuli data |
| **Conditional / legal review** | MASC (YouTube provenance) · MUCS SLR104 (BY-SA) · SPRING-INX (license unpublished — email SPRING Lab) |
| **Excluded (NC/research/unknown)** | WenetSpeech · KeSpeech · MagicData · AISHELL-2 · Emilia main · SADA · Casablanca · QASR · MGB-2 · MSR Indian · GigaSpeech (agreement unreadable) · MUCS SLR103 |

## 15. Language router architectures (Options A–D compared)

Reference point [FACT]: our API takes `language` as a form field;
declaration-first routing is in-force law; the registry resolves per
(model, language); the gateway does no acoustic LID today.

| Option | Shape | Latency | Memory | Accuracy risk | Complexity | Verdict |
|---|---|---|---|---|---|---|
| **A. LID → per-language STT** for all traffic | acoustic LID on every request | +LID hop always | +LID model | LID errors compound into STT errors; code-switch flips | new mandatory component in hot path | over-engineered: most traffic declares language |
| **B. One small multilingual STT** with language-aware decoding | no router | none | one engine | ml broken, zh weak (Whisper) or ta/ml absent (Qwen3) — **coverage fails (§8)** | lowest | impossible at quality, today |
| **C. LID → router → specialists** (no default engine) | every language needs a dedicated slot | +hop | N engines resident | undeclared + unsupported language = hard fail | high (N stacks) | brittle; no fallback |
| **D. Hybrid: default multilingual + specialist slots + LID only for undeclared** | declared traffic routes free; undeclared → LID → route; unsupported → default engine | ~zero added for declared traffic | default + only evidence-justified specialists | fallback always exists; code-switch handled by routing to tolerant backend | incremental — each slot is one registry entry | **RECOMMENDED — and already our designed target architecture** |

LID component when needed [FACT]: SpeechBrain ECAPA VoxLingua107
(Apache-2.0, our six covered, 6.7% VoxLingua dev error, utterance-
level); fallback whisper-tiny `detect_language` (39M, MIT; Whisper LID
80.3% FLEURS for the *best* model — tiny undocumented). MMS-LID is NC
— excluded. Code-switch law: pick a tolerant backend per call; never
re-route mid-utterance [RESEARCH FINDING + corpus law].

## 16. Call-center concurrency analysis — 10 simultaneous calls

**⚠ ALL NUMBERS BELOW ARE CONCEPTUAL ESTIMATES** built from: our one
measured point (whisper-small int8: RTF 0.162, ~800 MiB [EVIDENCE]),
faster-whisper's published table (1,477 MB sequential / 3,608 MB
batched ~15× RT [FACT]), and artifact sizes. **None of this is a
production benchmark**; §18's experiment produces the first real
numbers. Scenario: hi×2, ta×2, ar×2, en×2, ml×1, zh×1, streaming-ish
call audio, CPU server unless stated.

| Architecture | Resident memory (est.) | Concurrency behavior (est.) | Cold start | Ops complexity | Verdict |
|---|---|---|---|---|---|
| **A. One large multilingual (large-v3 1.55B)** | ~3–4 GB int8 RAM, or GPU | **fails before concurrency**: breaches real-time on our CPU at 1 stream [EVIDENCE]; GPU serving = new tier + KV/batch memory per stream | 10s of seconds | one stack, but GPU fleet | eliminated by measurement + policy |
| **B. One medium multilingual (Qwen3 1.7B / OWSM 1B)** | ~2–4 GB | CPU RTF unmeasured; audio-LLM decode likely sub-real-time on CPU [INFERENCE]; and ta/ml uncovered anyway | moderate | one stack | coverage fails; GPU pressure |
| **C. Six small specialists, no default** | 6 engines ≈ 0.5–1.5 GB each ≈ **4–7 GB total** | each stream independent; per-worker ~6× RT means ~4–6 streams/core-set [INFERENCE from RTF 0.162] | small per engine | **6 serving stacks** (CT2 + llama.cpp + NeMo-fork + …) — the real cost | memory fine; ops heavy |
| **D. Router + specialists** | C + LID (~tens of MB) | as C; +LID hop (~small) only on undeclared calls | as C | C + router component | as C, plus fallback gap |
| **E. Hybrid pool (recommended)** | whisper-small (en/hi/fallback) ~1.5 GB + Qwen3-0.6B GGUF (zh, later ar) ~1–1.5 GB + IndicConformer ta+ml ~1 GB ≈ **3.5–4.5 GB resident total** | 10 calls spread over 3–4 resident engines; whisper handles en+hi+undeclared batched (~15× RT batched [FACT]); specialists take their languages; **cores are the constraint, not RAM** — a 16-core box ≈ 12–20 real-time streams [INFERENCE] | each engine warm-restarts in seconds (ours: 2.4 s [EVIDENCE]) | 2–3 stacks, each added only when a slot is won by evidence | **recommended** |

Key structural point: resident engine memory is paid **per pool, not
per call** — 10 concurrent calls do not load 10 models. The pool grows
one evidence-justified engine at a time, and the default engine is the
universal fallback. This is why small models compound operationally:
three small stacks ≈ the RAM of one large model, with per-language
independence and CPU-only economics.

## 17. Recommended architecture

**Option E — the hybrid pool, which is the in-force target architecture
used at full width** ([stt-target-architecture.md](stt-target-architecture.md)):

```
Client → gateway (auth/metering, public model intelliai-stt)
       → registry resolution per declared language
           en → default engine (whisper-small int8, today)
           hi → default today; tuned-adapter artifact when E1 wins the gate
           ar → default today; slot contested later (Qwen3 / Cohere-AR / tuned whisper)
           ta → specialist slot (IndicConformer-ta candidate) — AFTER policy + ruler + corpus
           ml → specialist slot (IndicConformer-ml candidate) — same gates
           zh → specialist slot (Qwen3-ASR 0.6B candidate) — same gates
           undeclared → default engine auto-detect today;
                        ECAPA LID + routing IF undeclared traffic justifies it
```

No gateway change, no API change, no Android change. Every slot fill is
a registry entry backed by a switching-test record. LID enters only
when measured undeclared-traffic volume justifies a component
(declaration-first law stands).

## 18. Recommended first experiment (one milestone, two arms)

**Arm 1 — E1 Hindi LoRA (unchanged from the 2026-08-10 design):**
whisper-small + LoRA, 10 h curated public Hindi, frozen speaker-
disjoint eval first, baseline → train (local RTX 5070, ~3–5 GB) →
re-measure. Proves the training loop and produces the Hindi remedy.

**Arm 2 — zero-shot small-model bracket (new; measurement only, no
training, CPU):** on the SAME frozen Hindi eval: whisper-small
[baseline] vs **Qwen3-ASR 0.6B (GGUF, llama.cpp, CPU)** vs
**IndicConformer** (600M CTC; the 120M-class question rides on the same
spike). Record `cer_unicode`/`wer_unicode`, RTF, peak RAM, probe
behavior. Plus one Chinese read: Qwen3-ASR 0.6B on **CV 26.0 zh-CN
test** — the CPU-viability + quality number that decides whether the
zh slot is real. (zh ruler binding: `cer_unicode` under
`unicode_generic@v2`, a one-line governance addition — §24.)

Why this shape: Arm 1 answers "does fine-tuning work for us end to
end"; Arm 2 converts the three biggest routing unknowns (Qwen3 CPU
RTF, Qwen3-vs-Whisper Hindi gap on our ruler, IndicConformer's real
behavior) from card-claims into committed records — for the cost of
inference only. Tamil/Malayalam baselines follow the same pattern
after the policy decision (§25) and ruler bindings; Arabic keeps its
existing track (fold table first).

## 19. Baseline protocol (mandatory order, both arms)

1. Freeze eval manifests (hash-pinned, speaker-disjoint,
   `contamination_risk` recorded) — **before** any training data
   assembly.
2. Per candidate: WER + CER (unicode rulers), S/I/D, latency
   percentiles, RTF, peak RAM, silence/tone/noise probes
   (hallucination), language-confusion note where LID is implicit.
3. Commit EvalRuns to the append-only ledger. Only then train.
4. Post-training: identical corpus, ruler, hardware. Before/after
   deltas cited from committed records only.

## 20. Fine-tuning protocol (Arm 1)

As specified in [2026-08-10 report §20]: transformers Seq2SeqTrainer +
PEFT LoRA (r=32, α=64, q/v_proj), language+task tokens forced, fp16,
effective batch 32, ~4–5 k steps, 2-arm LR micro-sweep (1e-3 / 5e-4),
early-stop on eval CER; merge → `ct2-transformers-converter` → int8 →
sha256-pinned candidate artifact. Timestamp-health and hallucination
probes gate packaging. QLoRA fallback if memory surprises. No Qwen3
fine-tuning this milestone (full-FT-only, VRAM undocumented — verify
before promising any run, per management's own instruction).

## 21. Evaluation metrics

`wer_unicode` (EN primary) · `cer_unicode` (HI/AR primary; also the
right primary for TA/ML matras and ZH characters [INFERENCE — binding
decisions per language required]) · S/I/D rates · `hallucinated_words`
+ `excess_word_ratio` on probes · `recognition_rtf`, latency
percentiles (≥20 samples per cited p95), `peak_memory_mib` ·
per-language, never averaged across languages or rulers (law).

## 22. Success / failure criteria

**Arm 1 (E1):** success = ≥30% relative `cer_unicode` reduction on the
frozen Hindi eval, probes no worse, English suite unchanged, long-form
timestamps intact. Failure = any of those violated — a recorded result
that redirects (data scale? full FT? different base?) without touching
production.

**Arm 2:** success = committed records answering three questions:
(1) does Qwen3-0.6B run ≥1× real-time on our CPU class at ≤~2 GB?
(2) does any candidate beat whisper-small on Hindi on our ruler by a
margin that would survive the switching test? (3) zh: does Qwen3 clear
~real-time CPU + plausible quality on the fresh CV26 test? "It does
not run on CPU" is itself a recordable, decision-grade result.

**Architecture decision rule:** a specialist slot is opened per
language only when a candidate beats the default engine on that
language's primary metric on our corpus, meets latency/memory on our
CPU class, under a clean license — the standing §5 decision rule of
[STT_EVALUATION_SUCCESS_CRITERIA.md](STT_EVALUATION_SUCCESS_CRITERIA.md).

## 23. Risks

| Risk | Mitigation |
|---|---|
| Language-scope creep: ta/ml/zh work before the policy decision | §25 gates all ta/ml/zh spend on the founder's policy call |
| Qwen3 CPU RTF disappoints → zh slot stalls | Dolphin-small (Apache) is the registered backup; whisper-zh is the (weak) floor; result is still decision-grade |
| IndicConformer remote-code + NeMo fork | security-review process (existing prerequisite 5.3) + ONNX-export spike before any adoption |
| Aligner gap: no word timestamps for hi/ar/ta on Qwen3 slots | contract review: segment-level may suffice; else Whisper keeps those slots |
| FunASR-license pattern spreading (HF mirror tags contradict origin licenses) | verdicts bind to the distribution we pin; mirrors never inherit trust |
| Multi-stack sprawl (the Option-C failure mode) | slots open one at a time, each through the switching test; portfolio review law |
| Concurrency estimates wrong | §16 marked estimates; Arm 2 + a batched-throughput session replace them with records before any capacity promise |
| Router LID on code-switched calls | declaration-first; LID only for undeclared; tolerant-backend routing; code-mixed slices reported separately forever |
| SPRING-INX/MASC/MUCS-104 license ambiguity | counsel/email items; no experiment depends on them |

## 24. Open questions

1. Founder: extend Core Speech Language Policy to ta/ml/zh? (§25)
2. Qwen3-ASR 0.6B CPU RTF/RAM (Arm 2 answers).
3. IndicConformer ONNX/CPU export path (spike; undocumented).
4. Ruler bindings for ta/ml/zh (`unicode_generic@v2` likely correct
   for ta/ml; zh needs a binding decision; ar fold table unchanged).
5. SPRING-INX license (one email ≈ 470 h of ta/ml data).
6. Qwen3 full-FT VRAM (before ever promising a Qwen3 tune).
7. Undeclared-language traffic share (decides whether LID is ever
   built) — measurable from existing request metadata.
8. Segment- vs word-timestamp contract requirements for non-Whisper
   slots.

## 25. Decision required (founder)

| # | Decision | Recommendation |
|---|---|---|
| 1 | Extend product languages to TA/ML/ZH? | Yes as **roadmap intent**, gated per-language on corpus+ruler+baseline (policy amendment + §16 priorities update); no serving promise until slots are won |
| 2 | Approve the two-arm first experiment (§18) | Yes — Arm 1 local GPU, Arm 2 CPU-only; zero rental, zero production risk |
| 3 | Approve Hindi dataset list (unchanged from 2026-08-10) + zh eval addition (CV26 zh test) | Yes |
| 4 | Start Arabic fold-table + SPRING-INX license email in parallel | Yes — both are long-lead, cheap now |

## 26. References

Primary sources with read dates are inline throughout §§4–16 and in
the three agent research records of 2026-08-11 (Qwen3-ASR card + repo +
tech report; Whisper paper Appendix D; omnilingual-asr lang_ids;
AI4Bharat cards + IndicVoices paper; FunASR MODEL_LICENSE; Dolphin,
FireRedASR, TeleSpeech, OWSM cards; SpeechBrain/Silero/MMS-LID cards;
faster-whisper source + README benchmarks; OpenSLR 18/33/63/65/123/127;
cv-dataset 26.0 stats JSON; WenetSpeech/KeSpeech/Emilia agreements;
IEEE DataPort terms; SPRING-INX paper). EN/HI/AR model and dataset
details: [2026-08-10-first-finetuning-experiment.md](2026-08-10-first-finetuning-experiment.md).

---

## Decision table (management summary)

| Decision | Recommendation | Reason |
|---|---|---|
| First model experiment | whisper-small + LoRA (Arm 1) **plus** zero-shot bracket: Qwen3-ASR 0.6B GGUF · IndicConformer · whisper-small (Arm 2) | proves training loop AND converts routing unknowns into measurements, in one milestone |
| First language | **Hindi** | ruler live, richest safe data, baseline exists, proof-of-recipe published |
| Second language | **Chinese (baseline-only)**, then Malayalam as the first specialist-adoption test | zh: strongest candidate + fresh uncontaminated eval, inference-only cost; ml: the language that *forces* the modular strategy |
| Fine-tuning method | **LoRA/PEFT on Whisper** | only documented adapter path; fits 8 GB; serving conversion official |
| Dataset (train) | IndicVoices + Kathbath + Common Voice hi (10 h curated) | commercially safe, spontaneous-heavy, speaker IDs |
| Evaluation dataset | frozen speaker-disjoint IndicVoices slice + Lahaja (hi) · CV 26.0 zh-CN test (zh) | least contaminated, hash-pinned before training |
| Local GPU | RTX 5070 8 GB | fits LoRA arm (~3–5 GB est.); full-FT arms stay borderline/rented |
| Production architecture | **Hybrid pool: small multilingual default + evidence-won specialist slots** | no single permissive model covers 6 languages well; registry already routes per language |
| Language routing | **Declaration-first (exists); ECAPA VoxLingua107 LID only if undeclared traffic justifies it** | zero added latency for declared traffic; Apache-2.0 component identified, not built |

*Research recommends; the founder decides; engineering adopts. Nothing
in this document ships anything.*
