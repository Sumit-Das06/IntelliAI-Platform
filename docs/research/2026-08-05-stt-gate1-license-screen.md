# Gate 1 — License & Commercial Screening: Speech-to-Text Universe

| | |
|---|---|
| **Gate** | 1 — License & commercial screening ([RESEARCH_FRAMEWORK.md §5](RESEARCH_FRAMEWORK.md)) |
| **Date** | 2026-08-05 (every licence fact below read at source on this date) |
| **Scope** | All 16 transcription lineages that survived Gate 0 intake |
| **Out of scope** | Quality, accuracy, benchmarks, WER, latency, hardware performance. None are discussed here. Hardware appears only where it creates a *commercial* dependency. |
| **Deliverable** | A commercially-clean research universe. No adoption recommendation is made or implied. |
| **Result** | **12 PASS · 4 BLOCKED · 0 REJECTED** |

**Verdict definitions.** `PASS` — commercially eligible to continue to Gate 2.
`BLOCKED` — additional legal or provenance clarification required before
research continues. `REJECTED` — permanent exit on licensing or commercial
incompatibility.

**Evidence rule.** Only statements read at source on 2026-08-05 are recorded as
Facts. Where a document could not be reached or a term was absent, that absence
is recorded as absence — never as permission. Verdicts bind to the **artifact
version** named, never to the organisation.

---

## 1. Verdict table

| # | Lineage | Licence (verified at source) | Gated | Remote code | Verdict |
|---|---|---|---|:-:|:-:|---|
| 1 | Whisper (OpenAI) | MIT — code **and weights** | No | No | **PASS** |
| 2 | Qwen3-ASR 1.7B / 0.6B | apache-2.0 | No | No | **PASS** |
| 3 | Granite Speech 4.1 2B (IBM) | apache-2.0 | No | No | **PASS** |
| 4 | Omnilingual ASR (Meta) | apache-2.0 | No | Not indicated | **PASS** |
| 5 | Parakeet TDT 0.6B v3 (NVIDIA) | CC-BY-4.0 | No | No | **PASS** ⚠ attribution |
| 6 | Canary-Qwen 2.5B (NVIDIA) | CC-BY-4.0 | No | No | **PASS** ⚠ attribution |
| 7 | Kyutai STT 1b-en_fr | cc-by-4.0 | No | No | **PASS** ⚠ attribution |
| 8 | Moonshine | mit | No | No | **PASS** ⚠ pin repo |
| 9 | Cohere Transcribe Arabic 07-2026 | apache-2.0 | **Yes** | **Yes** | **PASS** ⚠ access |
| 10 | Cohere Transcribe 03-2026 | apache-2.0 | **Yes** | **Yes** | **PASS** ⚠ access |
| 11 | Voxtral-Mini-3B-2507 (Mistral) | apache-2.0 | **Yes** | Not indicated | **PASS** ⚠ access |
| 12 | IndicConformer-600M (AI4Bharat) | mit | No | **Yes** | **PASS** ⚠ code licence |
| 13 | IndicWhisper (AI4Bharat) | MIT *(repo only)* | No | n/a | **BLOCKED** |
| 14 | Zipformer / sherpa-onnx | Apache-2.0 *(toolkit only)* | No | No | **BLOCKED** |
| 15 | MOSS-Transcribe-preview-2B | apache-2.0 *(base chain undeclared)* | No | **Yes** | **BLOCKED** |
| 16 | ARK-ASR-3B (Audio8) | apache-2.0 *(remote-code chain unverified)* | No | **Yes** | **BLOCKED** |

---

## 2. PASS — evidence and reasoning

### 1. Whisper (OpenAI) — PASS
- **Source:** `github.com/openai/whisper` README, read 2026-08-05.
- **Evidence (verbatim):** "Whisper's code and model weights are released under the MIT License."
- **Transitive chain verified the same day:** `github.com/SYSTRAN/faster-whisper` — MIT; `github.com/OpenNMT/CTranslate2` — MIT. Both actively maintained.
- **Restrictions:** none found — no gating, no acceptable-use policy, no attribution beyond MIT's notice requirement, no field-of-use, MAU, or export terms.
- **Reasoning:** The weights are *explicitly* covered by the same licence as the code — the single most important sentence in this screen, because most publishers leave weight licensing to a metadata tag. The entire serving chain we actually deploy is MIT end to end.
- **Verdict:** **PASS.** The cleanest lineage in the universe.

### 2. Qwen3-ASR 1.7B / 0.6B — PASS
- **Source:** `huggingface.co/Qwen/Qwen3-ASR-1.7B` card, read 2026-08-05.
- **Evidence:** licence tag `apache-2.0`. Not gated. No `trust_remote_code` requirement indicated. No separate LICENSE file referenced (unlike several Qwen text models, which do ship custom LICENSE files — the absence here is itself the finding).
- **Restrictions:** none found.
- **Reasoning:** Apache-2.0 with a patent grant, no gate, no in-process vendor code. Note for the record: sibling Qwen *text* repositories do carry custom LICENSE files, so this verdict must not be generalised across the Qwen family.
- **Verdict:** **PASS.**

### 3. Granite Speech 4.1 2B (IBM) — PASS
- **Source:** `huggingface.co/ibm-granite/granite-speech-4.1-2b` card, read 2026-08-05.
- **Evidence:** "License: apache-2.0", linking to `apache.org/licenses/LICENSE-2.0`. Not gated. Usage examples use standard `AutoProcessor` / `AutoModelForSpeechSeq2Seq` — **no `trust_remote_code`**. No formal AUP document referenced; guidance is advisory only ("IBM recommends using this model for automatic speech recognition and translation tasks").
- **Restrictions:** none found.
- **Reasoning:** Permissive licence, open access, and no vendor code executing in our process. Of the twelve new entrants, this is the only one with none of the three recurring risks.
- **Verdict:** **PASS.** Commercially the cleanest of the 2026-generation entrants.

### 4. Omnilingual ASR (Meta) — PASS
- **Source:** `huggingface.co/facebook/omniASR-LLM-300M/raw/main/README.md` — raw YAML frontmatter read directly, 2026-08-05.
- **Evidence (verbatim frontmatter):** `license: apache-2.0`; `datasets: - facebook/omnilingual-asr-corpus`. **No `extra_gated` fields present.** Canonical code repository: `github.com/facebookresearch/omnilingual-asr`.
- **Restrictions:** none found on the model. The associated *corpus* is a separate asset reported under CC-BY-4.0 — relevant to dataset research (§12), not to serving these weights.
- **Reasoning:** I read the raw frontmatter rather than a rendered summary specifically because this organisation ships CC-BY-NC weights elsewhere (SeamlessM4T v2, rejected at Gate 0 the same day). The Apache-2.0 claim held under direct inspection.
- **Verdict:** **PASS.** The Gate 0 note that Meta's Apache claim "cannot be inherited from a sibling" is now discharged by direct verification.

### 5. Parakeet TDT 0.6B v3 (NVIDIA) — PASS ⚠ attribution
- **Source:** `huggingface.co/nvidia/parakeet-tdt-0.6b-v3` card, read 2026-08-05.
- **Evidence (verbatim):** "Use of this model is governed by the CC-BY-4.0 license." Not gated. No remote code (NeMo-native loading).
- **Obligation:** CC-BY-4.0 requires **appropriate credit**. This is a live product-design question, not a formality: our public API deliberately does not disclose engines.
- **Reasoning:** Commercial use is permitted; the obligation is attribution, which is satisfiable through a third-party notices page without naming engines per request. Recorded as a condition to resolve before adoption, not a bar to research.
- **Verdict:** **PASS**, attribution obligation recorded.

### 6. Canary-Qwen 2.5B (NVIDIA) — PASS ⚠ attribution
- **Source:** `huggingface.co/nvidia/canary-qwen-2.5b` card, read 2026-08-05.
- **Evidence:** licence CC-BY-4.0; card states the model **"is ready for commercial use"**; "Deployment Geography: Global"; not gated; loaded via NeMo `SALM.from_pretrained()` with no remote-code requirement.
- **Reasoning:** This is the artifact the Gate 0 ledger flagged as distinct from the CC-BY-**NC** `Canary 1B` already rejected. Direct verification confirms the split: same family name, opposite commercial terms. An organisation-level or family-level verdict would have discarded a usable model — the per-artifact-version law paid for itself here.
- **Verdict:** **PASS**, attribution obligation recorded.

### 7. Kyutai STT (stt-1b-en_fr) — PASS ⚠ attribution
- **Source:** `huggingface.co/kyutai/stt-1b-en_fr/raw/main/README.md` — raw frontmatter read directly, 2026-08-05.
- **Evidence (verbatim frontmatter):** `license: cc-by-4.0`, `library_name: moshi`. Body states the weights are "licensed under CC-BY 4.0" and names nine authors.
- **Obligation:** CC-BY attribution, with a specific author list published on the card.
- **Reasoning:** Commercially usable with credit. Dependency on the `moshi` library is noted for later transitive review, not screened here.
- **Verdict:** **PASS**, attribution obligation recorded.

### 8. Moonshine — PASS ⚠ pin the repository
- **Source:** `huggingface.co/moonshine-ai/moonshine-base` card, read 2026-08-05.
- **Evidence:** "License: mit". Not gated. No remote-code requirement indicated.
- **Provenance finding:** the model is published under the **`moonshine-ai`** organisation while code examples and paper attribution still reference **`UsefulSensors`**. Both namespaces exist. This reads as an organisation migration rather than a competing fork, and both carry MIT.
- **Reasoning:** No licence ambiguity — MIT either way. The obligation is operational: the canonical repository must be pinned explicitly before any artifact is fetched, so that a future rename cannot silently redirect an unpinned reference.
- **Verdict:** **PASS**, canonical-repository pinning recorded as a condition.

### 9. Cohere Transcribe Arabic 07-2026 — PASS ⚠ gated access + remote code
- **Source:** `huggingface.co/CohereLabs/cohere-transcribe-arabic-07-2026` card, read 2026-08-05.
- **Evidence (verbatim):** licence Apache 2.0; Terms of Use section states — "We hope that the release of this model will make community-based research efforts into Arabic speech more accessible. **This model is governed by an Apache 2.0 license.**"
- **Gating (verbatim):** "You need to agree to share your contact information to access this model."
- **Remote code:** required — `vllm serve CohereLabs/cohere-transcribe-arabic-07-2026 --trust-remote-code`.
- **Reasoning on the research/commercial ambiguity:** the Terms of Use paragraph opens with research-flavoured language, which in isolation could suggest a research-only intent. It does not: the same sentence explicitly names Apache 2.0 as the governing licence, and Apache 2.0 permits commercial use unconditionally. Stated intent does not narrow a granted licence. **Commercial use is genuinely permitted.**
- **Reasoning on gating:** contact-sharing is an *access* condition, not a licence term. Once obtained, Apache-2.0 rights are irrevocable. It nonetheless binds our artifact pipeline, which fetches from pinned URLs at container start — a credentialled fetch is an operational dependency to design for.
- **Reasoning on remote code:** vendor code executing inside our runtime process is the exact vector by which GPL entered our TTS stack. Here the code ships inside an Apache-2.0 repository, so the licence covers it; the residual concern is security review, which belongs to engineering, not to this gate.
- **Verdict:** **PASS**, with gated access and remote-code execution recorded as conditions.

### 10. Cohere Transcribe 03-2026 (general) — PASS ⚠ gated access + remote code
- **Source:** `huggingface.co/CohereLabs/cohere-transcribe-03-2026` card, read 2026-08-05. (The `/raw/` frontmatter endpoint returned **HTTP 401** — consistent with, and the first signal of, the gate.)
- **Evidence:** licence Apache 2.0. Gated — "You need to agree to share your contact information to access this model". `trust_remote_code=True` required for both Transformers and vLLM paths. Contact: `labs@cohere.com`.
- **Languages recorded as a commercial-scope fact** (not a quality claim): 14 languages — English, French, German, Italian, Spanish, Portuguese, Greek, Dutch, Polish, Chinese, Japanese, Korean, Vietnamese, **Arabic**. **Hindi is absent.**
- **Reasoning:** identical to its Arabic sibling — permissive licence, access gate, in-process vendor code. The Terms-of-Use paragraph here does not repeat the "governed by an Apache 2.0 license" sentence, but the licence field is unambiguous and no conflicting term was found.
- **Verdict:** **PASS**, with the same two conditions.

### 11. Voxtral-Mini-3B-2507 (Mistral) — PASS ⚠ gated access, per-variant verification pending
- **Source:** `huggingface.co/mistralai/Voxtral-Mini-3B-2507` card, read 2026-08-05.
- **Evidence:** licence field `apache-2.0`. Distribution carries an `extra_gated_description` referencing Mistral's privacy policy — i.e. gated access with a privacy notice rather than a licence condition.
- **Scope limit:** this verdict covers **`Voxtral-Mini-3B-2507` only**. `Voxtral-Small-24B-2507` and the realtime/transcribe variants are reported Apache-2.0 but were **not individually verified at source today**; each requires its own verdict before use.
- **Reasoning:** Apache-2.0 permits commercial use; a privacy-policy gate is an access mechanism, not a restriction on the grant.
- **Verdict:** **PASS** for the Mini artifact; other variants remain unverified.

### 12. IndicConformer-600M (AI4Bharat) — PASS ⚠ remote-code licence
- **Source:** `huggingface.co/ai4bharat/indic-conformer-600m-multilingual` card, read 2026-08-05.
- **Evidence:** licence `mit`. Not gated. **`trust_remote_code=True` required** — the card's own example is `AutoModel.from_pretrained("ai4bharat/indic-conformer-600m-multilingual", trust_remote_code=True)`. Dependencies pinned to `onnxruntime==1.20.1` / `onnx==1.20.1`. No dataset-derived restrictions stated on the card.
- **Reasoning:** MIT covers the repository, and the remote code is served from that same MIT repository, so the executing code is licensed. Recorded as a condition because in-process vendor code always warrants explicit verification rather than inference.
- **Verdict:** **PASS**, remote-code execution recorded.

---

## 3. BLOCKED — evidence and reasoning

*Work on these four lineages stops here. No Gate 2 dossier is created for any of
them until the named clarification is obtained.*

### 13. IndicWhisper (AI4Bharat) — BLOCKED
- **Source:** `github.com/AI4Bharat/vistaar`, read 2026-08-05.
- **Evidence (verbatim):** "Vistaar is MIT-licensed. The license applies to all the fine-tuned language models."
- **The blocking fact:** the checkpoints are **not hosted in the MIT-licensed repository**. They are distributed from third-party object storage — e.g. `https://indicwhisper.objectstore.e2enetworks.net/hindi_models.zip` — and **no separate licence statement accompanies the checkpoint files**. Additionally, the HuggingFace copies discoverable today (`parthiv11/indic_whisper_*`) are **third-party re-uploads, not an AI4Bharat distribution**. Repository shows 54 commits with no visible recent activity.
- **Reasoning:** Gate 1 requires checkpoint licensing to be verified *separately* from repository licensing wherever the two are distributed separately. A README sentence in repo A is a statement of intent about artifacts hosted at location B; it is not a licence attached to those artifacts. Adopting weights whose only licence evidence is a third-party sentence, pulled from unauthenticated object storage, is precisely the exposure this gate exists to prevent. This is a documentation gap, very likely resolvable — but it is not resolvable by assumption.
- **Clarification required:** a licence statement attached to the checkpoint distribution itself, or an AI4Bharat-published HuggingFace repository with an explicit licence field.
- **Verdict:** **BLOCKED.**

### 14. Zipformer / sherpa-onnx (Next-gen Kaldi) — BLOCKED
- **Source:** `github.com/k2-fsa/sherpa-onnx`, read 2026-08-05.
- **Evidence:** repository licensed **Apache-2.0**; actively maintained (2,272 commits, 14k+ stars). Pretrained models are distributed **separately via GitHub Releases** under tags such as `asr-models`. **No statement was found that individual checkpoints carry the repository's licence.**
- **Reasoning:** This lineage has two separable commercial identities and they do not share a verdict. The **toolkit** is verified Apache-2.0 and is commercially clean for its strategic purpose — training our own models (§15) — where the licences that would bind us are those of *our* training data, not of any released checkpoint. The **pretrained checkpoints** are a different matter: each is trained on a specific corpus whose terms may bind derived weights, and none carries a verified licence today. Because no *specific commercially-clean checkpoint* can be named, the lineage cannot enter Gate 2 as a serving candidate.
- **Clarification required:** per-checkpoint licence and training-corpus terms for any specific checkpoint proposed for adoption. The toolkit-as-training-stack path needs no further clearance.
- **Verdict:** **BLOCKED** as a serving candidate; the toolkit path is unobstructed.

### 15. MOSS-Transcribe-preview-2B (OpenMOSS) — BLOCKED
- **Source:** `huggingface.co/OpenMOSS-Team/MOSS-Transcribe-preview-2B` card, read 2026-08-05.
- **Evidence:** licence field `apache-2.0`; not gated; **`trust_remote_code=True` required**; built on **Qwen3-1.7B-base** and a **Qwen3-Omni-MoE audio encoder**, and — the blocking fact — **"No licenses are stated for these base models"** on the card.
- **Reasoning:** A derivative cannot grant more than its bases allow. An Apache-2.0 tag on a model assembled from two undeclared upstreams is an unverified claim about a chain, not a verified licence. Qwen bases are *typically* Apache-2.0, but "typically" is precisely the reasoning this framework forbids — and the Qwen family is documented as carrying custom LICENSE files on some repositories.
- **Clarification required:** verified licences for `Qwen3-1.7B-base` and the `Qwen3-Omni-MoE` encoder, confirming both permit the Apache-2.0 redistribution asserted here.
- **Verdict:** **BLOCKED.**

### 16. ARK-ASR-3B (Audio8) — BLOCKED
- **Source:** `huggingface.co/Audio8/ARK-ASR-3B` and `huggingface.co/AutoArk-AI/ARK-ASR-3B` cards, read 2026-08-05.
- **Provenance — resolved:** the Gate 0 ambiguity is settled. **Audio8** is the publishing organisation; **AutoArk** is the research origin, with code at `github.com/AutoArk/open-audio-opd`. The card identifies itself as the canonical ARK-ASR-3B and does not present a competing authority. Attribution: Lin, Wang, Cai, Zeng (2026), arXiv:2605.28139.
- **Evidence:** licence field `apache-2.0`. Not gated. **Remote code mandatory** — card states the model "should be loaded with `trust_remote_code=True`".
- **The blocking fact:** the mandatory remote code originates from a **separate repository whose licence was not verified**, and the card states the work **builds upon `THUNLP/OPD` and `volcengine/verl`** — neither upstream's licence is stated on the card or verified here.
- **Reasoning:** The weights' Apache-2.0 tag does not automatically cover custom code that ships from, or derives from, other repositories and then **executes inside our runtime process**. This is structurally the same failure mode as the espeak-ng incident: an Apache-licensed model whose default execution path pulled in differently-licensed code. Provenance is now clear; the licence chain is not.
- **Clarification required:** verified licences for `AutoArk/open-audio-opd`, `THUNLP/OPD`, and `volcengine/verl`, plus confirmation that the shipped `arkasr` remote code is covered by the repository's Apache-2.0 grant.
- **Verdict:** **BLOCKED.**

---

## 4. REJECTED — none at this gate

**Zero lineages were rejected at Gate 1.**

This is a result of gate ordering, not of leniency. Gate 0's licence-first
screen had already removed the two non-commercial lineages the same day —
**ArTST** (`cc-by-nc-4.0`, verified at source) and **SeamlessM4T v2**
(`cc-by-nc-4.0`, verified at source). Both remain permanently rejected; neither
received a dossier. Every candidate that reached Gate 1 therefore arrived with a
licence already believed to be in our permitted class, and direct verification
confirmed that belief in all 16 cases.

The finding worth recording is that **no candidate's headline licence claim was
false**. Every problem found at this gate was structural — access mechanics,
in-process code, or an unverifiable chain — not a mislabelled licence.

---

## 5. Recurring commercial risks

| Risk | Lineages affected | Why it matters |
|---|---|---|
| **Mandatory remote code** | 5 of 16 — Cohere ×2, IndicConformer, MOSS, ARK | Vendor code executing inside our runtime process. This is the exact vector by which GPL entered the TTS stack. The weights' licence does not automatically cover it. |
| **Gated distribution** | 3 of 16 — Cohere ×2, Voxtral | Apache-2.0 grants the rights, but access requires accepting contact-sharing or a privacy notice. Our artifact pipeline fetches from pinned URLs at container start; a credentialled fetch is an operational dependency, and gates can be changed or withdrawn by the publisher. |
| **CC-BY attribution** | 3 of 16 — Parakeet, Canary-Qwen, Kyutai | Commercial use permitted *with credit*, against a public API designed never to disclose engines. Solvable with a notices page, but it is a product decision nobody has made yet. |
| **Checkpoint ≠ repository licence** | 2 of 16 — IndicWhisper, sherpa-onnx | A licence sentence in a code repository does not attach to weights hosted elsewhere. Both blocked cases share this root cause. |
| **Undeclared base-model chain** | 2 of 16 — MOSS, ARK | Audio-LLM derivatives assembled from upstream components whose licences the card never states. A derivative cannot grant more than its bases allow. |

The two structural risks — remote code and undeclared chains — are both
**consequences of the 2026 architectural shift toward audio-LLMs**: models
assembled from other models, shipped with bespoke loading code. Classical ASR
encoders (Whisper, Granite, Parakeet, Canary-Qwen) exhibit neither.

---

## 6. Organisations with inconsistent licensing across model families

Four organisations demonstrably ship different commercial terms across their own
families — all four verified at source on the same day:

| Organisation | Permissive artifact | Non-commercial / divergent artifact |
|---|---|---|
| **Meta** | Omnilingual ASR — `apache-2.0` ✅ | SeamlessM4T v2 — `cc-by-nc-4.0` ❌ |
| **NVIDIA** | Canary-**Qwen** 2.5B — CC-BY-4.0, "ready for commercial use" ✅ · Parakeet TDT v3 — CC-BY-4.0 ✅ | Canary **1B** — CC-BY-NC ❌ |
| **Cohere Labs** | Transcribe line — `apache-2.0` ✅ | Aya / Command lines — CC-BY-NC historically ❌ |
| **Alibaba / Qwen** | Qwen3-ASR — `apache-2.0`, no LICENSE file ✅ | Several Qwen text repositories ship **custom LICENSE files** ⚠ |

NVIDIA is the sharpest case: **two artifacts sharing the name "Canary" carry
opposite commercial terms.** Had we screened by family or by organisation, we
would have discarded a commercially usable model on the strength of its
sibling's licence — or, worse, adopted a non-commercial one on the strength of
its sibling's permissiveness.

**The existing per-artifact-version law is not merely vindicated; it is
load-bearing.** Four of sixteen verdicts would have been wrong without it.

---

## 7. Does the licence policy require refinement?

**Yes — three gaps, none of them a flaw in what the policy says, all of them
dimensions it does not yet address.**

[ADR-0005](../adr/0005-permissive-model-licensing-policy.md) classifies
*licences* (MIT / Apache-2.0 / BSD / CC-BY) and records `license` +
`commercial_ok` per registry entry. Every candidate in this screen passed that
test. Yet four were blocked and eight carry conditions — because the risks that
actually appeared are not licence-class risks:

1. **Distribution access is unmodelled.** A gated Apache-2.0 model is
   commercially permitted but operationally conditional. The policy has no field
   for "can we fetch this artifact without credentials, and can that access be
   withdrawn?"
2. **Executing code is unmodelled.** `commercial_ok` describes weights. Five
   candidates require vendor code to run *inside our process* — the surface
   where our one real licensing incident actually occurred.
3. **Attribution obligations have no home.** CC-BY is in the permitted class,
   but nothing records that three candidates would oblige us to publish credit,
   nor how that reconciles with an engine-hiding public API.

These are **proposals for the founder's decision**, not changes. Research
recommends; it does not amend engineering policy. If accepted, the natural form
is an ADR superseding or extending ADR-0005 — written by an engineering session,
since the registry schema is theirs.

---

## 8. Proposed permanent research rules

Four rules, offered for ratification into [RESEARCH_FRAMEWORK.md §5](RESEARCH_FRAMEWORK.md).
Each is generalised from a fact found in this screen, not invented.

- **R1 — The executing chain is part of the licence.** Any candidate requiring
  `trust_remote_code` (or equivalent) has the **remote code's licence verified
  separately from the weights' licence** at Gate 1. *Origin: 5 of 16 candidates;
  the espeak-ng incident generalised.*
- **R2 — Checkpoints are licensed where they are hosted.** A licence statement
  in a code repository never covers weights distributed elsewhere. The
  checkpoint's own distribution must carry the licence. *Origin: IndicWhisper,
  sherpa-onnx — both blocked on exactly this.*
- **R3 — Undeclared bases block the derivative.** A derivative whose base-model
  licences are not stated is BLOCKED until the chain is verified; a permissive
  tag on an unverified chain is a claim, not a licence. *Origin: MOSS, ARK.*
- **R4 — Access is recorded as a fact distinct from the licence.** Gating,
  authentication requirements, and redistribution rights are recorded at Gate 1
  even when the licence is fully permissive, because they bind the artifact
  pipeline independently of the grant. *Origin: 3 of 16 gated candidates.*

---

## 9. Ledger updates applied

All verdicts appended to [MODEL_LEDGER.md](MODEL_LEDGER.md) as dated entries on
2026-08-05. **No prior entry was edited.** Gate 1 verdicts do **not** change any
model's status: all 16 remain `Researching`, since status transitions occur at
Gate 3 (§3). `BLOCKED` is a gate outcome, not a ledger status — no new status was
invented.

*This document is a research record. It recommends no model for adoption and
draws no quality comparison of any kind.*
