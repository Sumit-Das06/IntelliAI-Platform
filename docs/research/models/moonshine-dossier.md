# Moonshine — Dossier

| | |
|---|---|
| **Stage** | Gate 2 complete (desk research, 2026-08-05) |
| **Gate 1** | **PASS** — `mit` verified at source; not gated; no remote code. ⚠ Canonical repository must be pinned (`moonshine-ai` vs `UsefulSensors` namespaces both exist). |
| **Status** | Researching |
| **Capability** | transcription |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence. No scoring, ranking, comparison, or adoption
> recommendation appears here.

## 1. Identity

Moonshine — a compact encoder-decoder ASR family for edge and low-latency use, developed by
**Useful Sensors** and now published under the **`moonshine-ai`** organisation **[FACT]**.
Repository: `github.com/moonshine-ai/moonshine` **[FACT]**. A follow-on line of specialised
tiny models is published as *"Flavors of Moonshine"* (arXiv:2509.02523) **[CLAIM]**.

## 2. Architecture

- **Design** **[CLAIM]**: compact Transformer encoder-decoder, Whisper-like in family but
  materially smaller.
- **The distinguishing property** **[CLAIM — publisher]**: **variable-length audio without
  padding to a fixed window**. Processing cost scales with *actual* audio length.
  **[INFERENCE]** This is the sharpest architectural contrast with our incumbent, whose
  fixed 30-second window means a 3-second utterance costs the same as a 30-second one. For
  any workload dominated by short utterances, that difference is structural, not marginal.
- **Sizes** **[FACT]**: **Tiny ~27M parameters**, plus a base tier. These are by a wide
  margin the smallest models in the PASS set — roughly a ninth of our incumbent's 244M.
- **Decoding** **[INFERENCE]**: autoregressive encoder-decoder.
- **Timestamps** **[INFERENCE — open question]**: not documented in material reviewed.
- **Tokenizer** **[INFERENCE — open question]**: unverified.
- **Streaming** **[CLAIM]**: designed for low-latency and streaming-style edge use; the
  variable-length design is what makes short-segment latency competitive. The project
  positions itself for "voice agents and interfaces".
- **Multilingual strategy** **[INFERENCE]**: English-centric core, with the *Flavors*
  line taking a **per-language specialised tiny model** approach rather than one
  multilingual model **[CLAIM]**. That is a distinct strategy worth noting: many small
  specialists instead of one generalist.

## 3. Languages

**[FACT]** English-centric. **[CLAIM]** Later specialised tiny models extend to other
languages, but Hindi and Arabic coverage should be **assumed absent until established**.

**[FACT]** Addresses at most one of our three product languages.

## 4. Licensing (Gate 1, verified 2026-08-05)

`mit` **[FACT]**. Not gated; no remote code indicated **[FACT]**.

⚠ **Provenance note** **[FACT]**: published under `moonshine-ai` while code examples and
paper attribution still reference `UsefulSensors`; both namespaces exist and both carry
MIT. Reads as an organisation migration rather than a competing fork **[INFERENCE]** — but
the canonical repository must be pinned explicitly so a future rename cannot silently
redirect an unpinned reference.

## 5. Runtime and deployment profile

- **Serving stack** **[FACT]**: **ONNX Runtime is the primary path** — this is an
  ONNX-first project, not a PyTorch project with an export afterthought.
- **Quantization** **[FACT]**: **8-bit weights across the board and 8-bit computation for
  heavy operations such as MatMul**, produced by **post-training quantization** using ONNX
  Runtime tooling plus the *Onnx Shrink Ray* utility. Quantization is the shipped default,
  not an experiment.
- **[INFERENCE]** Of every candidate in the PASS set, this has the most mature and
  first-party CPU/quantization story. It is the only one where int8 CPU deployment is the
  design centre rather than a possible port.
- **CTranslate2** **[FACT — absent]**; ONNX Runtime is the route.
- **Remote code** **[FACT]**: none indicated.
- **CPU friendliness** **[INFERENCE]**: highest in the set, by design — 27M parameters at
  int8 targets embedded and edge hardware.
- **GPU expectations** **[INFERENCE]**: unnecessary.
- **Cold start** **[INFERENCE]**: a 27M int8 artifact implies a small download and fast
  load — likely the fastest cold start available, relevant given our measured 46 s first
  boot dominated by a 483 MB download.
- **Batching** **[INFERENCE]**: less relevant at this scale; the design targets single-stream
  low-latency use.
- **Operational maturity** **[FACT]**: shipped SDKs and demo applications for edge
  deployment; independent academic benchmarking of its quantization exists
  (`Edge-ASR`, arXiv:2507.07877) **[CLAIM]**.

## 6. Quality evidence

**None from IntelliAI.** Publisher and third-party accuracy comparisons are excluded at
this gate.

## 7. Latency and memory expectations

Unmeasured by us **[FACT]**. **[INFERENCE]** Architecture and size together imply the
lowest memory and lowest short-utterance latency of any candidate; the variable-length
property means its advantage would be *largest* on short audio and smallest on long audio —
a shape our benchmark should deliberately probe rather than average away.

## 8. Fine-tuning ecosystem

- **[INFERENCE — open question]** No LoRA/PEFT precedent identified; at 27M parameters,
  adapters are largely beside the point — full fine-tuning is cheap.
- **[CLAIM]** The *Flavors of Moonshine* line demonstrates that the team itself trains
  language-specialised variants, which implies a working training recipe exists.
- **[INFERENCE]** For a model this small, **training a language variant ourselves** is a
  more plausible proposition than for any other candidate here — which connects it to §15
  more than to adapter tuning.

## 9. Training support

**[CLAIM]** Papers published for both the base models and the specialised line; the
project is open-source with an active repository. Training data and full recipes not
verified as released **[FACT — unverified]**.

## 10. Ecosystem and research maturity

- **Publication** **[CLAIM]**: multiple papers, plus independent quantization benchmarking
  by third parties — a healthier evidence trail than most small projects.
- **Maintenance** **[FACT]**: active repository; the project has broadened from ASR into
  intent recognition and TTS for voice agents.
- **Documentation** **[INFERENCE]**: adequate; edge-deployment oriented.
- **Ecosystem** **[INFERENCE]**: small but focused on on-device use.
- **Organisational risk** **[FACT]**: the smallest publisher in the PASS set; single-vendor
  continuity risk, mitigated by MIT and by the model's small size (retrainable).

## 11. Known strengths

Smallest models in the set (27M tiny); **int8 quantization as the shipped default**;
ONNX-first design; variable-length processing without fixed-window padding; MIT; fast cold
start; independent quantization research; plausible in-house retraining at this scale.

## 12. Known weaknesses

**[FACT]** English-centric — no Hindi, no Arabic. **[INFERENCE]** Small models carry a
quality ceiling no serving optimisation removes. **[FACT]** Smallest publisher, single-team
continuity risk. **[INFERENCE]** Timestamps and tokenizer undocumented; limited
fine-tuning precedent; namespace migration requires careful pinning.

## 13. Integration risks

- **[INFERENCE]** Lowest integration risk of any candidate: ONNX Runtime is a
  well-understood dependency, there is no remote code, no gate, and no GPU assumption.
- **[FACT]** Namespace pinning must be explicit.
- **[INFERENCE]** It would serve at most an English tier, so adopting it implies a
  multi-engine topology.
- **[INFERENCE]** If used for short-utterance traffic specifically, that implies
  **routing by audio length** — a routing capability our gateway does not have and which
  would be a new concept in the registry.

## 14. Open questions carried to Gate 3

Quality ceiling at 27M on our corpus · timestamp support · behaviour on long-form audio
(where the variable-length advantage disappears) · hallucination behaviour · whether the
*Flavors* line covers any of our languages · cold-start and memory measurements ·
tokenizer behaviour.

## 15. Strategic value to IntelliAI

- **CPU-first candidate — the purest one.** It is the only candidate whose design centre
  is exactly our deployment constitution: small, int8, ONNX, CPU, no GPU assumption.
- **Cost-frontier reference** — defines the lower bound of what transcription can cost,
  which is a useful number for pricing and capacity planning independent of adoption.
- **Offline / on-device candidate** — the only realistic option if an offline product
  ever enters the roadmap.
- **Training-program candidate** — at 27M, training our own language variant is
  economically conceivable, unlike every other lineage here.

## 16. Benchmark hypothesis *(to test at Gate 3+, not a prediction)*

> **H-MOONSHINE:** *On short utterances Moonshine's variable-length processing will deliver
> lower latency and memory than whisper-small at a quality cost that is acceptable for some
> traffic but not all — meaning its real question for IntelliAI is whether we ever want
> length-based routing between engines, not whether it can replace the incumbent.*

Falsifiable: the quality gap may be unacceptable across the board, or negligible — either
result settles the routing question without further work.
