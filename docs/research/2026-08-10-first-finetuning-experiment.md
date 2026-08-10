# First Fine-Tuning Experiment — Model & Dataset Research, Recommendation, and Experiment Design

| | |
|---|---|
| **Status** | RESEARCH REPORT — awaiting founder decision (no status changes, no code, no training run) |
| **Date** | 2026-08-10 (every license and landscape claim in this document was read at source on this date unless another date is shown) |
| **Trigger** | Founder directive: research and recommend the pretrained ASR base for IntelliAI's first fine-tuning experiment, and design a public-data experiment that proves fine-tuning improves the selected base for our target languages — *before* any implementation |
| **Governed by** | [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) (gates, append-only ledger law) · [FOUNDATION_MODELS.md §1](../FOUNDATION_MODELS.md) (the permanent scoring instrument) · [ADR-0005](../adr/0005-permissive-model-licensing-policy.md) (permissive-only licensing) · [FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md) (the ladder; Part 10 training law) · [stt-execution-roadmap.md](stt-execution-roadmap.md) (IN FORCE, 2026-08-06) |
| **What this is not** | Not a benchmark result (nothing was measured), not a status change (all ledger statuses unchanged), not an adoption recommendation (no serving decision is proposed) |

Labels per framework §2: **[FACT]** read at primary source, dated ·
**[EVIDENCE]** our own evaluation-plane records · **[CLAIM]**
publisher/third-party, unverified by us · **[INFERENCE]** reasoning ·
**[OPEN]** known unknown.

---

## 1. Executive summary

**Recommended base for the first experiment: `whisper-small` — the
incumbent lineage — fine-tuned for Hindi with LoRA on public,
commercially-clean data.** Second choice: **Qwen3-ASR 0.6B**. The
experiment's job is to prove, with a before/after measurement on the
same held-out corpus, that fine-tuning on public data improves the model
we actually serve — Ladder Stage 0 → 1 (FINE_TUNING_STRATEGY Part 2),
the "first adapter experiment proving the training loop end-to-end"
that Part 9 assigns to Year 1.

The five load-bearing findings:

1. **The published proof your question asks for already exists,
   in-lineage.** Hugging Face's canonical recipe fine-tunes
   *whisper-small on ~8 h of Common Voice Hindi*: WER **63.5% → 32.0%**
   [FACT, hf.co/blog/fine-tune-whisper]. AI4Bharat's IndicWhisper
   (whisper-**medium** fine-tuned on 2,150 h Hindi) averages **13.6 WER**
   across seven Hindi benchmarks, beating Google and Azure STT [FACT,
   arXiv:2305.15386 Table 3]. For Arabic, full fine-tuning of large-v2
   cut MGB-2 WER **34.7 → 15.5**, and even 4 h recovered most of the
   Common Voice gain [FACT, arXiv:2306.02902]. Fine-tuning Whisper for
   our languages is not a hypothesis; the open question is only what it
   does on *our* distributions.
2. **No new candidate displaces the incumbent lineage as the
   fine-tuning base.** The two Meta SSL encoders newly screened here
   (XLS-R Apache-2.0, w2v-BERT 2.0 MIT) are license-clean but
   structurally regressive for our product: per-language CTC vocab, no
   punctuation, no casing, no timestamps — colliding with the
   `verbose_json` contract — and the best documented XLS-R Hindi WERs
   (0.34–0.46) sit far above the Whisper fine-tune evidence. MMS and
   SeamlessM4T v2 are CC-BY-NC hard fails (both re-verified at source
   today).
3. **One Gate 2 finding is now amended: Qwen3-ASR covers all three
   product languages.** The official repo (read 2026-08-10) lists 52
   languages/dialects including **both Hindi and Arabic**, Apache-2.0,
   with a **published fine-tuning framework** — resolving two open
   questions in its dossier. It is the only permissive lineage besides
   Whisper claiming EN+HI+AR, and it publishes first-party tuning
   support. It stays second choice, not first, because every published
   operating point is GPU/bfloat16, timestamps require a second model
   covering 11 languages, and none of it is measured on our corpus.
4. **The dataset asymmetry decides the experiment order.** Hindi has an
   unusually strong commercially-safe public supply (IndicVoices
   CC-BY-4.0, Kathbath CC0, Common Voice CC0, MUCS SLR104 CC-BY-SA for
   Hinglish; Lahaja and Svarah as low-contamination evals). Dialectal
   Arabic is a licensing desert: SADA, Casablanca, QASR, and MGB-2 are
   all non-commercial; what remains commercially clean is MSA-leaning
   (Common Voice, FLEURS) plus MASC's conditional CC-BY. English is
   closed by our own evidence (Stage 2, WER 0.000, "do not reopen
   without new evidence").
5. **The platform can already feed the pipeline.** The dataset
   preparation artifact is a valid Hugging Face `load_dataset("json")`
   input today (five fields, deterministic bytes, SHA-256-pinned). The
   gap is a thin loader plus S3 access — not schema surgery — with four
   small additive manifest-v2 fields recommended (speaker id, mime type,
   sample rate, corrected flag) and a derived split rule. Nothing
   model-specific enters the core Dataset model.

**Therefore the first experiment is Hindi-only, on the incumbent, on
public data** — not the three-language balanced mixture the directive
sketched. English has nothing measurable to improve; Arabic error is not
yet computable (`profile_for("ar")` refuses by design until the
enumerated fold table exists). A balanced mixture today would train what
we cannot measure, violating Part 10 law 1 ("measure before you
improve") and law 3 ("no evaluation → no deployment"). Arabic enters as
Experiment E2 the moment its ruler exists — and the fold-table
commissioning that unblocks it is the single longest-lead item on the
Stage 4 path, so it should start now, in parallel.

---

## 2. Current IntelliAI ML architecture (context, all [FACT] from repo inspection 2026-08-10)

```
Web / STT Studio ─┐                                   ┌─ Return transcript
Android Keyboard ─┴→ POST /v1/audio/transcriptions ───┤
                     auth → validation → STT runtime  └─ Optional collection (consent-gated)
                     (faster-whisper whisper-small,          ↓
                      CTranslate2 int8, CPU,            SpeechSample → Correction
                      device="cpu", ~800 MiB,                ↓
                      RTF 0.162 EN)                     Dataset → immutable DatasetVersion
                                                             ↓
                                                        DatasetPreparation (JSONL manifest,
                                                        sha256-pinned, 5 fields/line)
```

- Serving: `whisper-small` int8 via CTranslate2; artifacts pinned by
  URL + SHA-256 in `ArtifactStore`; engine imports confined to
  `engines/` by an AST-enforced test that denylists `torch`/
  `transformers` everywhere else. `ml/training/` exists as an empty
  stub package — the sanctioned home for training code.
- Registry: `intelliai-stt` → `en` SUPPORTED, `hi` AVAILABLE, `ar`
  AVAILABLE, all routed to `whisper-small`. The resolution manifest
  already routes per language — hybrid routing needs zero gateway work.
- Evaluation plane: `wer_unicode` and `cer_unicode` are implemented,
  registered, and wired (`accuracy.py`, `runner.py`), with
  `unicode_generic@v2` bound for `en` and `hi`. **The 2026-08-05
  prerequisite register is stale on this point** — item 4.1
  (`cer_unicode` "implemented nowhere") has since been discharged.
  `profile_for("ar")` still refuses, deliberately, pending the
  enumerated Arabic fold table (PR-1.2).
- Evidence holdings: English WER 0.000 / RTF 0.162 baselines committed;
  the whisper *family* measured (Stage 1: 7 records — large-v3 breaches
  CPU real-time and deterministically hallucinates on VAD-passed
  non-speech); zero Hindi natural-speech corpus at C2 scale; zero
  Arabic clips of any kind.

## 3. Candidate models

The 2026-08-05 intake already registered 16 STT lineages (12 license-PASS
with Gate 2 dossiers, 4 BLOCKED). This research adds four Meta-lineage
candidates the directive named, verifies three landscape updates, and
evaluates everything *for the specific role of fine-tuning base* — a
different question from "serving engine", which the roadmap governs.

**New screens performed 2026-08-10 (all licenses read at source that day):**

| Candidate | License [FACT] | Verdict for this role |
|---|---|---|
| XLS-R 300m / 1b / 2b (Meta) | `apache-2.0` on all three HF cards | Screens clean; registered `Researching`. Weak base for us (see §4) |
| w2v-BERT 2.0 (Meta) | `mit` on HF card | Screens clean; registered `Researching`. Strongest permissive SSL encoder (4.5M h, 143 langs, hi+ar in pretraining); same CTC product regressions |
| MMS 1b-all / 1b-fl102 (Meta) | `cc-by-nc-4.0` on both cards | **Rejected at intake** — non-commercial fails ADR-0005, regardless of its 1,162-language coverage |
| SeamlessM4T v2 | `cc-by-nc-4.0` (unchanged from 2026-08-05) | Rejection re-confirmed |

**Landscape updates to already-registered candidates:**

- **Whisper license correction [FACT].** The HF cards we pin artifacts
  from read `apache-2.0` for `openai/whisper-small`, `-medium`, and
  `-large-v3`; `-large-v3-turbo` reads `mit`; the OpenAI GitHub repo is
  MIT. Our ledger carries "MIT" from the repo/faster-whisper chain read.
  All permissive — no verdict changes — but per-artifact license law
  requires the record corrected (ledger entry appended today).
- **Qwen3-ASR Arabic confirmed [FACT].** github.com/QwenLM/Qwen3-ASR
  (read 2026-08-10): 52 languages/dialects including Hindi **and
  Arabic**; Apache-2.0; an official fine-tuning path is published
  ("Please refer to [Qwen3-ASR-Finetuning] for detailed instructions"),
  and the technical report describes an open-sourced "comprehensive
  inference and finetuning framework". This discharges two dossier open
  questions and amends the Gate 2 structural finding: **one permissive
  candidate besides Whisper now claims EN+HI+AR.** Coverage is a claim
  about counts, not quality; nothing is measured.
- **Parakeet-RNNT-1.1B-multilingual [FACT].** NVIDIA's NGC collection
  lists `hi-IN` and `ar-AR` among 25 languages — but under the "AI
  Foundation Models Community License", not CC-BY-4.0. [INFERENCE]
  Fails ADR-0005's permissive-only rule; the permissive Parakeet
  (`tdt-0.6b-v3`, CC-BY-4.0) remains European-only. No change to the
  Parakeet ledger row.
- **distil-whisper [FACT].** MIT, English-only checkpoints, but the
  distillation *training code* is multilingual-capable — relevant to
  Ladder Stage 4 later, not to this experiment.

## 4. Detailed comparison — decision matrix

Directive columns first (compressed; per-language detail in §§6–8):

| Model | Params | English | Hindi | Arabic | Fine-tune | Streaming | CPU | GPU | License | Production fit |
|---|---|---|---|---|---|---|---|---|---|---|
| **whisper-small** (incumbent) | 244M | **EVIDENCE**: WER 0.000, RTF 0.162 | usable; 1 anecdotal matra error; FT proof 63.5→32.0 (CV11) | claimed; unevaluated; weak-base evidence for AR FT | **best ecosystem in ASR**; official recipe; LoRA/PEFT; CT2 conversion of fine-tunes official | no native; chunk+VAD (ours) | **proven (ours)** | optional | Apache-2.0 (HF card) / MIT (repo) | **serving now** |
| whisper-medium | 769M | strong [CLAIM] | IndicWhisper base: 13.6 avg WER [FACT] | FT'd small < zero-shot large-v2 ⇒ medium the floor AR base [INFERENCE] | same as small | same | **[OPEN]** likely breaches CPU class | fits 16–24 GB FT | Apache-2.0 | candidate for E2/E3 bases |
| whisper-large-v3 | 1.55B | **EVIDENCE: breaches CPU real-time; hallucinates on VAD-passed non-speech** (Stage 1) | best zero-shot in family [CLAIM] | best zero-shot in family [CLAIM] | same; LoRA <8 GB documented | same | **no (measured)** | yes | Apache-2.0 | not our serving class |
| whisper-large-v3-turbo | 809M | ≈large-v2 [CLAIM] | 4-layer decoder; degradation on some low-resource langs noted by OpenAI [FACT] | same concern | fine-tunable [FACT]; weaker base capacity [INFERENCE] | same | [OPEN] | yes | MIT | not first base |
| **Qwen3-ASR 0.6B** | 0.6B | claimed strong | claimed (52 langs) | **claimed (confirmed in list 2026-08-10)** | **official FT framework [FACT]**; toolchain young for speech | no native; aligner = 2nd model, 11 langs | [OPEN] — unmeasured | published points GPU/bf16 | Apache-2.0 | second lineage |
| XLS-R 300m | 300M+CTC head | fine [CLAIM] | community FT: WER 0.34–0.46 [FACT] | community FT: WER 0.43 [FACT] | official CTC recipe; per-language vocab | CTC chunk-streamable | plausible | 16 GB class | Apache-2.0 | **no punctuation/casing/timestamps** |
| w2v-BERT 2.0 | ~600M | [OPEN] | in pretraining set; no documented FT | existence-proof FT only | official CTC recipe; 14 h → 32% WER (Mongolian, 16 GB V100) [FACT] | CTC | heavier; **no ONNX path [FACT]** | 16 GB | MIT | same CTC regressions |
| IndicConformer-600M | 600M | none | claimed, 22 Indic | none | **no adapter precedent** [dossier]; `trust_remote_code` | frame-sync | intended [INFERENCE] | optional | MIT | Hindi serving challenger, not FT base |
| Omnilingual ASR (CTC 325M–LLM 7.8B) | 325M–7.8B | not competitive [CLAIM] | `hin_Deva` in list [FACT] | `arb_Arab` + ~25 dialect codes [FACT] | official **fairseq2** recipe; Meta reference = 32 GPUs for 300M [FACT] | no | [OPEN], conversion ours | yes | Apache-2.0 | ecosystem friction |
| Parakeet TDT 0.6b-v3 | 600M | strong [CLAIM] | **none** | **none** | NeMo stack | native | [OPEN] | yes | CC-BY-4.0 | fails language coverage |
| MMS / SeamlessM4T v2 | — | — | — | — | — | — | — | — | **CC-BY-NC-4.0** | **rejected** |

**Scoring.** The directive proposed ad-hoc weights (coverage 20%,
fine-tuning 15%, accuracy 20%, …). The framework forbids redefining the
permanent instrument, and FOUNDATION_MODELS §1's weights (License 20% ·
Fine-tuning ecosystem 20% · Quality 15% · Multilingual/Indic 10% ·
Serving maturity 10% · Hardware flexibility 10% · Momentum 10% ·
Openness 5%) are the *better* ruler for this decision: choosing a
fine-tuning base is precisely the decision §1's weights were built for
— license freedom and tuning ecosystem outweigh today's leaderboard
position, because we are buying the lineage, not the checkpoint. Scores
below are §1 judgment calls on the data above (1–10 per criterion,
weighted total):

| Candidate (as FT base) | Lic | FT | Qual | Multi | Serve | HW | Mom | Open | **Weighted** |
|---|---|---|---|---|---|---|---|---|---|
| **Whisper (small/medium bases)** | 10 | 10 | 8 | 9 | 10 | 10 | 6 | 4 | **8.9** |
| **Qwen3-ASR 0.6B** | 9 | 8 | 7 | 9 | 5 | 5 | 9 | 5 | **7.5** |
| XLS-R 300m | 10 | 8 | 4 | 7 | 7 | 8 | 3 | 6 | 6.9 |
| w2v-BERT 2.0 | 10 | 7 | 6 | 8 | 4 | 6 | 4 | 5 | 6.7 |
| Omnilingual ASR | 9 | 5 | 5 | 9 | 3 | 5 | 7 | 8 | 6.2 |
| IndicConformer-600M | 8 | 4 | 5 | 8 | 6 | 7 | 6 | 6 | 6.1 |
| large-v3-turbo (as base) | 10 | 7 | 6 | 6 | 8 | 7 | 5 | 4 | 6.9 |

Consistent with the 2026-07-31 sweep (Whisper 8.6, Qwen3-ASR 8.1); the
deltas are explained by role: as a *fine-tuning base* Whisper gains
(the CT2 conversion path for fine-tunes is verified official; the Hindi
FT literature is directly on-point) and Qwen3-ASR loses on serving/
hardware (every published operating point is GPU/bf16, and its verified
FT support is younger than its text-model tooling reputation — the
dossier's warning that audio-tower tuning "should not be assumed" to
inherit text tooling stands).

## 5. Licensing comparison (all read at source 2026-08-10)

| Model | Weights license | Commercial | Derivatives/fine-tunes | Attribution | COMMERCIAL LICENSE RISK |
|---|---|---|---|---|---|
| whisper-small/medium/large-v3 | Apache-2.0 (HF cards) · repo MIT | yes | yes | notice preservation | **LOW** (cleanest chain: faster-whisper MIT, CTranslate2 MIT — verified 2026-08-05) |
| whisper-large-v3-turbo | MIT | yes | yes | notice | LOW |
| Qwen3-ASR 0.6B/1.7B | Apache-2.0 | yes | yes | notice | **LOW** (does not generalize to other Qwen repos) |
| XLS-R (all 3 sizes) | Apache-2.0 | yes | yes | notice | LOW |
| w2v-BERT 2.0 | MIT | yes | yes | notice | LOW |
| Omnilingual ASR | Apache-2.0 (repo + card) | yes | yes | notice | LOW (tooling risk is the real cost) |
| distil-whisper (code) | MIT | yes | yes | notice | LOW |
| Parakeet-RNNT-1.1B-multilingual | NVIDIA "AI Foundation Models Community License" | **unverified** | — | — | **HIGH/UNKNOWN — treat as fail** |
| MMS 1b-all / fl102 | CC-BY-NC-4.0 | **no** | — | — | **HIGH — rejected** |
| SeamlessM4T v2 | CC-BY-NC-4.0 | **no** | — | — | **HIGH — rejected (re-confirmed)** |

Framework note: verdicts bind per artifact version. The Whisper
Apache/MIT split across distributions is recorded in the ledger today;
either grant is permissive and derivative-friendly, so the experiment is
unaffected.

## 6. Hindi analysis

- **Zero-shot Whisper Hindi is genuinely weak** [FACT]: 63.5% WER
  (whisper-small, CV11, HF blog) — consistent with our single anecdotal
  matra error, and with Vistaar's judgment that vanilla Whisper's
  Indian-language performance "is significantly poor".
- **Fine-tuning closes most of the gap** [FACT]: 32.0% after 4,000
  steps on ~8 h (same blog, same corpus); IndicWhisper (medium, 2,150 h
  Hindi) reaches 10.3 (Kathbath) / 11.4 (FLEURS) / 15.0 (CV) — average
  13.6 across seven benchmarks, beating Google STT (23.9) and Azure
  (20.0) [FACT, arXiv:2305.15386 Table 3].
- **In-lineage is the cheapest Hindi path and it is currently frozen at
  Gate 1** (IndicWhisper checkpoints BLOCKED on unlicensed third-party
  distribution) — but that block binds *their checkpoints*, not the
  recipe: we can run the same shape of fine-tune ourselves on clean
  data, which is exactly what E1 does.
- Hinglish: MUCS SLR104 (CC-BY-SA-4.0, 89.86 h train) is the one
  commercially-viable code-switch corpus; IndicVoices conversational
  slices are naturally code-mixed [INFERENCE]. Evaluation keeps
  code-mixed as its own slice, never blended (corpus law).
- Ruler status: **live** (`unicode_generic@v2` binds `hi`;
  `cer_unicode` implemented and registered; `RulerFailureError` guards
  the empty-reference path).

## 7. Arabic analysis

- **Supply** [FACT]: one purpose-built permissive candidate (Cohere
  Transcribe Arabic, Apache-2.0, gated + remote-code conditions);
  Qwen3-ASR now confirms Arabic in scope; Omnilingual lists `arb_Arab`
  + ~25 dialect codes; Whisper claims Arabic, unevaluated by us.
- **Fine-tuning evidence** [FACT, arXiv:2306.02902]: large-v2 full FT:
  CV11 19.4→13.3, MGB-2 34.7→15.5; 4 h of data recovers most of the CV
  gain. Two hard warnings: **fine-tuned whisper-small is worse than
  zero-shot large-v2 on every Arabic test set** (small is a weak Arabic
  base), and **MSA fine-tuning degraded dialect performance below
  zero-shot** (MGB-3: 55.3 FT vs 31.4 zero-shot) — the catastrophic-
  forgetting risk in its most concrete published form.
- **Data desert** [FACT]: SADA (CC-BY-NC-SA), Casablanca (CC-BY-NC-ND),
  QASR ("Non-Commercial Purpose ONLY!"), MGB-2 (research agreement) —
  every serious dialectal corpus is commercially dead. Clean supply is
  MSA-leaning: CV ar (CC0, 92 validated h), FLEURS ar_eg (CC-BY-4.0,
  ~10 h), MASC (CC-BY via IEEE DataPort platform terms; YouTube
  provenance risk flagged for counsel).
- **Our ruler does not exist yet, by design**: `profile_for("ar")`
  refuses pending the enumerated fold table (tashkeel/alef/tatweel) and
  a dialect-competent verifier — the category-M trap ("a profile that
  strips category M to de-diacritise Arabic destroys Hindi") is why
  this cannot be rushed.
- **Consequence:** Arabic fine-tuning is E2, gated on the ruler; the
  fold-table commissioning should start now (longest human lead). Base
  choice for E2 is an open question (small is evidence-weak; medium+
  breaches CPU class; Qwen3-ASR unmeasured) — E2's design decision, not
  today's.

## 8. English analysis

Closed by our own evidence: Stage 2 verdict "whisper-small remains the
English production engine" (WER 0.000 at corpus ceiling, ~9× latency
headroom, zero hallucinated words) with recorded reopen triggers. No
English training is proposed. English appears in E1 only as a
**no-regression guard**: the adapter serves the `hi` route exclusively,
so English serving is structurally untouched; the English eval suite is
still run against the merged artifact as a paranoia check before any
future serving decision.

## 9. Production / deployment analysis

- **Serving path for a fine-tuned Whisper is proven and official**
  [FACT]: `ct2-transformers-converter` explicitly supports "user
  fine-tuned models"; LoRA must be merged into base weights first
  [INFERENCE, standard]; output loads in faster-whisper with
  `compute_type=int8` exactly like today's artifact. A tuned checkpoint
  is a new pinned artifact (SHA-256) behind the same engine — zero
  gateway, contract, or Android changes.
- **Adapter-on-route topology kills the regression risk**: hybrid
  routing (stt-target-architecture §2) means the Hindi artifact serves
  only `hi`; `en`/`ar` keep stock weights. Catastrophic forgetting
  cannot reach another language's traffic by construction.
- **Known serving hazards from the FT literature, with mitigations**:
  timestamp-token degradation when tuned without timestamped data
  (breaks faster-whisper long-form) → include timestamped samples or
  verify long-form on probes before packaging [FACT, ivrit.ai
  postmortem]; silence-hallucination worsening after LoRA [FACT,
  arXiv:2606.07608] → our silence/tone probes are mandatory gates and
  our VAD short-circuit contains engine-level regressions.
- **GPU**: training only, single card — the founder's local RTX 5070
  Laptop GPU (8 GB) covers the recommended LoRA arm (§16); rental is a
  fallback, not a requirement. No GPU serving tier is proposed
  (roadmap: "does not run on our CPU" is a recordable result, not a
  criterion).

## 10. Public dataset comparison (licenses read at source 2026-08-10)

| Dataset | Langs | Hours (relevant) | License [FACT unless noted] | Commercial | Speaker IDs | Splits | Character | Suitability |
|---|---|---|---|---|---|---|---|---|
| Common Voice Scripted 26.0 | 294 | EN 2,785 val · HI 54 val (1,278 recorded!) · AR 92 val | CC0 + MDC terms ("no re-hosting") | YES (internal) | client_id, speaker-disjoint splits | ✓ | read prompts; AR≈MSA | TRAIN all 3; eval = contaminated |
| FLEURS | 102 | ~12/lang (hi_in, ar_eg) | CC-BY-4.0 | YES | no per-speaker IDs | ✓ | read, news-domain | EVAL (comparability only) |
| LibriSpeech | EN | 960 | CC-BY-4.0 | YES | yes | ✓ | US audiobooks | small TRAIN slice at most |
| VoxPopuli | 23 EU | EN 543 | data CC0 | YES | — | ✓ | EU-accented oratory | optional EN TRAIN |
| People's Speech | EN | 30,000+ | CC-BY subset | YES | — | ✓ | noisy real-world; alignment noise | TRAIN (filtered) |
| GigaSpeech | EN | 10,000 | agreement unreadable (gated) | **UNKNOWN → NO** | — | ✓ | YouTube provenance | NEITHER |
| **IndicVoices** | 22 Indic | 11,200 transcribed total; HI figure [OPEN, at download] | **CC-BY-4.0** | YES | speaker/district metadata | partial | 76% extempore, 15% conversational — our domain | **TRAIN backbone + held-out EVAL** |
| Shrutilipi | 12 Indic | ~6,400 total | CC-BY-4.0 | YES | none (broadcast-mined) | per-lang | newsreader register; alignment-mined noise | TRAIN bulk (filtered); never eval |
| Kathbath / IndicSUPERB | 12 Indic | 1,684 total | **CC0** (explicit waiver) | YES | yes (1,218 speakers) | ✓ (unseen-speaker test) | clean read, smartphone | TRAIN + secondary EVAL |
| **Svarah** | Indian EN | 9.6 | CC-BY-4.0 | YES | 117 speakers | — | purpose-built Indian-English benchmark | **EVAL (accents)** |
| **Lahaja** | HI dialects | 12.5 | CC-BY-4.0 | YES | 132 speakers | — | dialect-stratified | **EVAL (primary HI)** |
| MUCS SLR103 | HI | 95 + 5.5 | license URL dead (MSR) | **UNKNOWN → NO** | — | ✓ | read stories | NEITHER (license risk) |
| MUCS SLR104 | HI-EN code-switch | 89.9 + 5.2 | CC-BY-SA-4.0 | CONDITIONAL (SA; counsel) | — | ✓ | technical lectures | TRAIN Hinglish + its test as EVAL |
| MASC | AR multi-dialect | 1,000 | CC-BY (DataPort platform terms) | CONDITIONAL (YouTube provenance) | channel-level only | clean/noisy, dev/test | caption-quality bulk; verified clean subset | TRAIN (filtered) + clean-test EVAL |
| SADA | AR Saudi+ | 667 | CC-BY-**NC**-SA | **NO** | — | ✓ | broadcast dialects | NEITHER |
| QASR | AR | 2,000 | CC-BY-**NC**-2.0 ("Non-Commercial ONLY!") | **NO** | yes | ✓ | Al Jazeera | NEITHER |
| MGB-2 | AR | 1,200 | research agreement; text unobtainable | **NO (assumed)** | — | ✓ | Al Jazeera | NEITHER |
| Casablanca | AR 8 dialects | ~48 | CC-BY-**NC-ND** | **NO** | — | — | best dialect eval design, dead to us | NEITHER |

## 11. Dataset licensing analysis — the rules this experiment obeys

1. **Downloadable ≠ usable.** Six of the seventeen datasets screened
   fail commercially (MMS-class NC pattern repeats in data).
2. **Per-source license records** enter the report and, at collection
   time, the provenance record (framework §12 discipline; the dataset
   ledger is created at the first *Collected* entry, not before).
3. **CC-BY-SA (MUCS 104)**: SA binds redistributed/adapted *data*;
   whether a trained model is an adaptation is unsettled — counsel
   review before it enters any training mixture. E1 can proceed without
   it (Hinglish slice is evaluation-first anyway).
4. **Common Voice MDC overlay**: CC0 audio, but "you agree not to
   rehost this dataset" — fine for internal training; we never ship
   data.
5. **MASC**: platform-level CC-BY does not launder upstream YouTube
   rights [INFERENCE] — counsel item before E2 relies on it.
6. **Contamination is a license-adjacent axis**: CV and FLEURS
   train+test are inside virtually every public multilingual model
   [INFERENCE]; gated/recent sets (IndicVoices, Lahaja, Svarah, MASC)
   are the least crawled. Public eval slices get
   `contamination_risk` recorded honestly, per corpus law.

## 12. Recommended training dataset (E1 — Hindi)

**Target: 10 h curated** for the first run (see §20 for why 10 and not
5/25/50), assembled as:

| Slice | Source | Share | Why |
|---|---|---|---|
| Spontaneous/extempore Hindi | IndicVoices (CC-BY-4.0) | ~60% | our domain: real, conversational, dialect-diverse, consent-collected |
| Read Hindi | Kathbath (CC0) | ~20% | clean references, speaker IDs, smartphone channel |
| Read Hindi, crowd | Common Voice hi 26.0 validated (CC0) | ~15% | replicates the known-good recipe's data class |
| Hinglish | mined from IndicVoices conversational | ~5% | code-mix exposure without the SA question |

Shrutilipi is held in reserve for E3 scale-up (bulk, but alignment-mined
noise and newsreader register — filter by alignment score first).
All audio → 16 kHz mono WAV at ingestion; transcripts verbatim,
Devanagari, script-follows-word for code-mix; no digits (numerals as
spoken) — matching the platform's own transcription convention.

## 13. Recommended evaluation dataset (E1)

Held out **before** training data is assembled (Part 3 law: evaluation
before training counterparts):

| Slice | Source | Size | Role |
|---|---|---|---|
| **Primary** | IndicVoices held-out, **speaker-disjoint** (speakers never in any train slice) | ≥1 h, ≥100 clips, ≥10 speakers | the before/after ruler |
| Dialect stress | Lahaja (CC-BY-4.0, 2024, low crawl exposure) | full 12.5 h or a fixed slice | dialect robustness read |
| Comparability | FLEURS hi_in test · CV hi test | as published | numbers other papers can be compared against — **never the headline** (contaminated) |
| Probes | silence · tone · noise-only (byte-identical to platform probe set) | 5 | hallucination gate |
| No-regression | existing English `stt-eval-v1` + long-form timestamp probe | as committed | serving-safety gate |

Metrics: `cer_unicode` (primary, Hindi law) + `wer_unicode`
(co-primary), profile `unicode_generic@v2`, S/I/D decomposition,
`hallucinated_words` on probes. Speaker-disjoint splitting is mandatory
because voice identity leaks even when clips differ (corpus law §6);
random utterance splits put the same speaker on both sides and inflate
the measured gain. Datasets without speaker IDs (Shrutilipi, MASC bulk)
are train-only, never eval. **The public eval slice answers "did
fine-tuning improve the model"; it does not answer "should this serve"
— that remains the private `stt-hi-eval` C2 corpus and the Stage 3
gate, exactly as the roadmap orders.**

## 14. Baseline evaluation plan (mandatory, before any training)

```
stt-hi-public-eval@v1 (frozen, sha256-pinned manifest)
        ↓
  whisper-small int8 (the artifact we serve, via the research route)
        ↓
  EvalRun: cer_unicode · wer_unicode · S/I/D · probes · RTF
        ↓
  committed to ml/evaluation append-only records  = THE BASELINE
```

Same corpus, same ruler, same hardware class for the post-training run;
the comparison is invalid on any other terms (framework §6.1). Bonus
read at near-zero cost: the same run on `whisper-large-v3` gives the
lineage-ceiling number Stage 3 wants anyway (in-stack, ~1 day).
Prerequisite: `EvalClip` local-path source (~1 day, already the named
Stage 3 engineering item) — public clips are local files, not hosted
URLs.

## 15. Fine-tuning plan per top candidate — shapes and trade-offs

**Whisper (recommended):**
```
audio 16 kHz → WhisperFeatureExtractor (log-Mel)
transcript   → WhisperTokenizer (language="hi", task="transcribe")
     → Seq2SeqTrainer (transformers) + LoRA via PEFT
       (r=32, α=64, q_proj+v_proj, dropout 0.05 — documented config)
     → adapter (~tens of MB) → merge into base → ct2-transformers-converter
     → int8 CT2 artifact → SHA-256 pin → candidate
```
Trade-offs: largest ecosystem, exact recipes public, serving conversion
official; decoder is autoregressive (punctuation/casing preserved);
timestamp health must be guarded (train data slice with timestamps, or
verify long-form probes post-merge).

**Qwen3-ASR 0.6B (second):** official Qwen3-ASR-Finetuning framework
[FACT]; LoRA support standard in the Qwen toolchain [CLAIM for the
speech variant]. Trade-offs: new serving stack (no CT2 path), published
operating points GPU/bf16, timestamps need the companion aligner (11
languages, Hindi membership unverified), and our evaluation/serving
capital does not transfer. Right shape for a *bake-off* once E1
machinery exists, not for the first proof.

**XLS-R / w2v-BERT (CTC shape, for the record):**
```
audio 16 kHz → feature extractor → Wav2Vec2ForCTC / Wav2Vec2BertForCTC
             + per-language character vocab (built from OUR transcripts)
     → CTC loss fine-tune → checkpoint (+ optional n-gram LM)
```
Trade-offs: cheapest compute, official recipes, data-efficient
(14 h → 32% WER Mongolian on 16 GB V100 [FACT]) — but output is
lowercase, unpunctuated, vocab-bound; timestamps only via frame
alignment; an external LM is needed to approach parity (0.46→0.34 with
LM on Hindi [FACT]); and serving would be a second stack. Product
regressions rule them out as our base; they remain the reference CTC
shape if a tiny specialized model is ever wanted.

**Omnilingual ASR:** official fairseq2 recipe exists [FACT] but the
reference configs are 32-GPU class and the stack sits outside
transformers/ONNX — watch-list for the long-tail asset, not a first
base.

## 16. GPU / resource requirements (E1)

**Local hardware finding [FACT, measured 2026-08-10 via `nvidia-smi` on
the founder's machine]:** NVIDIA GeForce RTX 5070 Laptop GPU, **8 GB
VRAM** (8,151 MiB, idle), driver 591.91, CUDA 13.1 — alongside the
Intel UHD iGPU that handles the display, leaving the RTX free for
compute.

| Item | Requirement | Fits local 8 GB? | Source |
|---|---|---|---|
| **E1 LoRA arm (whisper-small, fp16, batch 16)** | ~3–5 GB [INFERENCE] | **YES — runs locally, zero rental cost** | LoRA on whisper-large-v2 (6× our base) documented <8 GB [FACT] |
| Optional full-FT comparison arm (small) | ~7–9 GB at batch 16 [INFERENCE] | Borderline — batch 4–8 + grad checkpointing + accumulation, or rent | small full-FT ran in a Colab (~16 GB class) at batch 16 [FACT] |
| Future medium LoRA (E2/E3 base candidate) | ~5–7 GB [INFERENCE]; QLoRA halves the frozen base if tight | Likely | PEFT int8 workflow [FACT] |
| Future medium/large full-FT | 16–24 GB+ | **No — rented 24 GB card, decided after E1 results** | large-v2 full-FT ~24 GB [FACT] |
| Est. wall clock | ~4,000–5,000 steps ≈ 5–10 GPU-hours per arm [INFERENCE — pilot will measure]; laptop thermal throttling may stretch, not break, the run | overnight job | blog trains 4k steps in a Colab session |
| Storage | ~15 GB (data + checkpoints) | — | [INFERENCE] |
| Serving | **unchanged** — CPU int8, same runtime | — | §9 |

Two local-run conditions [FACT]: RTX 50-series (Blackwell, sm_120)
requires a PyTorch build for CUDA 12.8+ — the training environment must
pin a current torch; and multi-hour runs at the 115 W laptop power cap
want mains power and airflow (throttling costs wall clock only).

Gradient accumulation preserves the effective batch at any per-device
size, so the smaller card never compromises the result — only the
speed. **Consequence for 15D: no GPU spend is required for the
recommended experiment.** No GPU infrastructure is added; rental
re-enters only if the optional full-FT arm is wanted or a later
experiment moves to a medium+ base.

## 17. Recommended model for the first experiment — ONE

**`whisper-small` (LoRA, Hindi).** Why, in the disclosure format:

- **License**: Apache-2.0 (HF card, read 2026-08-10; repo MIT;
  faster-whisper/CTranslate2 MIT) — cleanest chain in the universe,
  commercial use and derivatives unrestricted. RISK: LOW.
- **Commercial usability**: proven — it is the engine in production;
  a tuned checkpoint rides the identical serving path.
- **Performance**: our own evidence for EN (WER 0.000, RTF 0.162 CPU
  int8, ~800 MiB); Hindi zero-shot is weak (63.5% CV11) which is
  precisely what makes the experiment measurable; the published
  fine-tune delta on exactly this model and language is −31.5 WER
  points [FACT].
- **Hardware**: trains on one rented 16 GB GPU in hours; serves on the
  CPU we already run.
- **Why best**: it is the only candidate where the experiment answers
  the business question directly — *can training improve what we
  serve?* The switching test (Part 4) measures challengers against the
  **tuned incumbent**, so tuning capital spent here compounds; spent
  anywhere else, it evaporates if that lineage is never adopted. Every
  layer of our stack (artifact pinning, int8 CT2 serving, eval rulers,
  VAD probes) already speaks Whisper.

## 18. Second-choice model

**Qwen3-ASR 0.6B** — Apache-2.0, the only other permissive EN+HI+AR
lineage, first-party fine-tuning framework, CPU-plausible size, fastest
momentum. It becomes the *named challenger* the moment E1's machinery
exists and Stage 3's gate justifies a challenger round — entering
through the ordinary switching test. What keeps it second today:
unmeasured on our corpus, GPU-published operating points, second-model
timestamp story, new serving stack, and zero of our accumulated capital.

## 19. Models we should NOT start with

| Model | Reason (one line) |
|---|---|
| SeamlessM4T v2, MMS | CC-BY-NC-4.0 — commercially dead [FACT, re-verified today] |
| Parakeet TDT v3 / RNNT-multilingual | permissive artifact lacks HI+AR; the HI+AR artifact lacks a permissive license |
| whisper-large-v3 (as serving target) | our own Stage 1 evidence: breaches CPU real-time, hallucinates on VAD-passed non-speech |
| whisper-large-v3-turbo (as base) | 4-layer decoder; OpenAI notes degradation on some low-resource languages; unproven base for Indic [INFERENCE] |
| XLS-R / w2v-BERT 2.0 | CTC product regressions (no punctuation/casing/timestamps, per-language vocab); Hindi evidence an order weaker than Whisper FT |
| Omnilingual ASR | fairseq2-only training and serving; 32-GPU reference configs |
| IndicConformer-600M | no documented adapter path; `trust_remote_code`; it is a Stage 3 *serving* challenger, not a tuning base |
| IndicWhisper checkpoints | Gate 1 BLOCKED (unlicensed checkpoint distribution) — we replicate the recipe on clean data instead |

## 20. Proposed experiment — E1 in full

**Hypothesis (falsifiable, both directions):** *LoRA fine-tuning
whisper-small on ≤10 h of commercially-clean public Hindi speech
reduces `cer_unicode` on a speaker-disjoint held-out public Hindi
corpus by ≥30% relative vs the zero-shot baseline, without degrading
the silence/tone probes or the English suite on the merged artifact.*
(Failure modes that would falsify: gain <30%, probe regressions,
timestamp/long-form breakage.)

| # | Element | Decision |
|---|---|---|
| 1 | Model | `openai/whisper-small` (the incumbent's weights) |
| 2 | Datasets | IndicVoices + Kathbath + Common Voice hi (train); IndicVoices held-out + Lahaja + FLEURS/CV tests (eval) |
| 3 | Sizes | **10 h train** · ≥1 h/≥100-clip primary eval. Why 10: the recipe's proven operating point is ~8 h (63.5→32.0); Arabic evidence shows 4 h recovers most of the CV gain; 5 h risks an ambiguous result, 25–50 h doubles cost without changing the *answer* to "does the machinery work" — scale-up is E3's job if E1 passes |
| 4 | Preprocessing | ffmpeg → 16 kHz mono WAV; reject clips <2 s />30 s for training; dedup vs eval by content hash |
| 5 | Audio format | WAV PCM16, 16 kHz mono (canonical, matches serving pipeline) |
| 6 | Sampling rate | 16,000 Hz |
| 7 | Transcript normalization | verbatim Devanagari; script-follows-word for code-mix; numerals as spoken; punctuation retained in training text (Whisper is punctuation-capable); *evaluation* normalization only via `unicode_generic@v2` at scoring |
| 8 | Split | speaker-disjoint by speaker metadata (client_id / speaker id); datasets lacking speaker IDs are train-only; eval slice frozen and hash-pinned **first** |
| 9 | Framework | transformers `Seq2SeqTrainer` + PEFT LoRA (r=32, α=64, q/v_proj, dropout 0.05); language="hi", task="transcribe" tokens forced |
| 10 | GPU | founder's local RTX 5070 Laptop (8 GB) for the LoRA arms; rented 16–24 GB only if the optional full-FT arm is added (§16) |
| 11 | Epochs/steps | ~4,000–5,000 steps, eval every 500, early-stop on eval CER |
| 12 | Batch | effective 32 via per-device 16 × grad-accum 2, fp16 (halve on OOM — documented guidance) |
| 13 | LR | LoRA 1e-3 vs 5e-4 micro-sweep (2 runs); full-FT comparison arm optional at 1e-5 if budget allows — exact hyperparameters cannot be responsibly fixed pre-pilot, so this small sweep IS the plan |
| 14 | Metrics | `cer_unicode` (primary), `wer_unicode`, S/I/D rates, `hallucinated_words` on probes, long-form timestamp probe, recognition RTF post-conversion |
| 15 | Expected runtime | 5–10 GPU-hours per arm [INFERENCE — measured by the pilot] |
| 16 | Output | adapter + merged fp32 checkpoint → `ct2-transformers-converter` → int8 CT2 dir → `sha256` → candidate artifact `whisper-small-hi-lora-e1` (identity = base + dataset manifest hash + recipe tag) |
| 17 | Reproducibility | frozen JSONL data manifest (platform 5-field format + sidecar provenance: source/license/URL/date/speaker/split), pinned library versions, committed training config, fixed seed, run log — a run that cannot register its output did not succeed (Part 5) |

**What E1 proves / does not prove.** Proves: the training loop
end-to-end (data → train → merge → convert → evaluate → package), and
whether public-data tuning moves Hindi on a clean ruler. Does **not**
prove: that the artifact should serve. Serving still requires the
private `stt-hi-eval` C2 corpus, the Stage 3 gate, and the switching
test — this experiment feeds that gate a ready remedy instead of a
research project, which is exactly the roadmap's dormant-LoRA trigger
("then it is a first-line remedy, not research").

## 21. Proposed milestone breakdown

| Milestone | Content | Gate to next |
|---|---|---|
| **15A** (this document) | Research, screening, recommendation, experiment design | founder approval of base + datasets (GPU budget: none — E1 runs on the local RTX 5070, §16) |
| **15B** | Public dataset ingestion: download, license/provenance records (framework §12 intake), filtering, 16 kHz normalization, frozen train/eval manifests (eval frozen first), dedup + contamination declarations | manifests hash-pinned; dataset ledger seeded with first *Collected* entries |
| **15C** | Baseline: `EvalClip` local-path source (~1 day, shared with Stage 3), zero-shot whisper-small on `stt-hi-public-eval@v1` (+ optional large-v3 ceiling read), committed EvalRuns | baseline records committed |
| **15D** | The E1 run: local RTX 5070 (8 GB), LoRA sweep (2 arms), checkpoints registered — no rental needed for the recommended arms (§16) | training complete, artifacts registered |
| **15E** | Post-training evaluation on the identical corpus/ruler/hardware; before/after comparison; probe + English no-regression + long-form checks; verdict vs the falsifiable hypothesis | founder review of results |
| **15F** | IntelliAI dataset adapter: manifest v2 additive fields (`speaker_id`, `mime_type`, `sample_rate`, `corrected`), deterministic derived split rule, thin `ml/training/` loader consuming platform manifests — the bridge from public-data machinery to the consented flywheel | adapter consumes a real platform preparation in a dry run |
| **15G** | Candidate packaging: merge → CT2 → int8 → pinned artifact; promotion-pipeline dry run to *Candidate* status only — **no route change, no production exposure** | founder decision on next step (E2 Arabic prep / E3 scale-up / Stage 3 alignment) |

Parallel, non-blocking, start now: **Arabic fold-table commissioning +
dialect-verifier recruitment** (Stage 4's longest lead), so E2 is not
gated on it later.

## 22. Risks

| Risk | Mitigation |
|---|---|
| Eval contamination inflates/deflates deltas | primary eval = gated, recent, speaker-disjoint IndicVoices slice; CV/FLEURS demoted to comparability; `contamination_risk` recorded |
| Speaker leakage inflates gains | speaker-disjoint splits mandatory; no-speaker-ID sets train-only |
| Timestamp/long-form breakage post-tune | timestamped/long-form probes gate packaging; include timestamped data if probes fail |
| Silence hallucination worsens after LoRA | probe gates + pipeline VAD short-circuit contains engine-level regressions |
| Dialect forgetting (Arabic precedent) | E1 is additive-adapter on a frozen base, route-scoped; Lahaja dialect read reported separately |
| Transcript-convention mismatch across corpora | single conversion pass to our convention at ingestion; convention recorded in the manifest sidecar |
| MUCS SA / MASC provenance questions | counsel items; E1 does not depend on either |
| GPU spend without decision value | fixed 2-arm sweep, 10 h data, hours-class budget; hypothesis falsifiable in both directions |
| Solo-founder capacity | E1 is deliberately the smallest useful shape; 15B/15C reuse Stage 3 engineering (local-path source) |

## 23. Open questions (tracked, not blocking E1)

1. Hindi hours inside IndicVoices/Kathbath/Shrutilipi — obtainable at
   download (15B intake records them).
2. whisper-medium CPU viability (int8 RTF/memory) — decides whether the
   E3 base can be medium; one in-stack measurement.
3. Arabic base for E2 — small is evidence-weak; medium+ vs Qwen3-ASR vs
   Cohere-AR is E2's decision, after the ruler exists.
4. Qwen3-ASR 0.6B CPU viability and Hindi timestamp coverage in its
   aligner — pre-bake-off questions.
5. Whether IndicVoices ships per-clip timestamps (affects the
   timestamp-health training slice).
6. MDC terms overlay vs CC0 — internal-use reading is safe; re-check if
   we ever redistribute data.

## 24. Exact next implementation step

**None until the founder decides.** On approval of this report's
recommendation, the first command of 15B is: create the dataset intake
records (framework §12) for IndicVoices, Kathbath, Common Voice hi,
Lahaja, Svarah, FLEURS — provenance, license verdict, date, URL — then
download and freeze `stt-hi-public-eval@v1` **before** assembling any
training data. The first *code* is the ~1-day `EvalClip` local-path
source, which Stage 3 needs regardless of this experiment.

---

*Research recommends; the founder decides; engineering adopts. This
report changes no ledger status and touches no production system.*
