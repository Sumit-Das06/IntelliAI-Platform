# Milestone 3 Review — Text-to-Speech as a Product (v0.4)

**Closed:** 2026-08-03 · 9 review-gated steps (0–8), each founder-approved ·
Reference design: [3-tts-design.md](3-tts-design.md) (approved with two
refinement rounds; every step was reviewed against it).

**What shipped:** IntelliAI speaks. `POST /v1/audio/speech` and
`GET /v1/audio/voices` are live behind API keys; public model
**`intelliai-tts`** serves raw playable WAV through the same gateway,
registry, and error contract as transcription — with the engine
(Kokoro-82M, Apache-2.0, verified 2026-08-03) invisible to customers, as
designed. The founder completed the customer flow personally: key →
catalog → voices → audible audio in both launch voices.

| Step | Delivered |
|---|---|
| 0 Governance | Design doc committed; ADR-0019 (runtime-core) + ADR-0020 (binary binding); `tts-kokoro → tts-runtime` rename; license verdicts (EN approved espeak-free; **Hindi gated**) |
| 1 Extraction | `packages/runtime-core` — ArtifactStore/WorkerPool/generic ModelManager/failures, **empty behavioral diff proven** (unchanged stt suite; ModelManager logic diff = imports/typing only; baseline re-run at parity) |
| 2 Contract | `SPEECH_SYNTHESIS` + `CHARACTERS` + synthesis schemas, all additive (CONTRACT_VERSION still 1); the M2-promised registry capability-mismatch test finally constructible, landed; capability-independence proof (alien engine shapes through unchanged lifecycle) |
| 3 Skeleton | tts-runtime with `ReferenceSynthesisEngine` — binary binding proven with no model; envelope header ceiling pinned adversarially; isolation suite live from day one |
| 4 Kokoro | Hash-pinned artifacts (HF LFS oids at source) through the verified store; **license firewall** (poison stub keeps the GPL espeak chain out of the process, proven at runtime); voice assets as artifact files; placeholder public voices preserved; first real `SpeechEvalRun` (EN round-trip WER **0.072**) |
| 5 Gateway | Public API + `intelliai-tts` catalog row + product-plane voice validation + `speech.completed` + leak-guards extended + engine-replacement demonstrated at the API level |
| 6 Evaluation | `speech-eval` CLI (reproducibility metadata from live `/info`; refuses mismatched artifacts); live baseline **reproduction** committed (quality metrics reproduce; moment-metrics vary); capability-extension demo (future-TTS/cloning/S2S shapes through the unchanged runner) |
| 7 Production | GPL-free image (build fails if espeak importable), compose topology, [permanent benchmark](../../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md), PRD verdict incl. the milestone's **first honest FAIL**, customer-flow + engine-swap demos, three real defects caught |
| 8 Close | This review; PRD v0.7; ARCHITECTURE v0.4; Language Policy v1 + capabilities-permanent principle recorded; Pronunciation Manager registered; version 0.4.0 |

430 tests across 6 workspace packages; CI green at every step; zero
engine names in any customer-facing surface (CI-enforced).

## 1. Architectural assumptions — validated by evidence

1. **The runtime architecture is capability-independent** (the milestone's
   central claim): proven three ways — the extraction produced an *empty
   behavioral diff* for STT; alien-shaped fake engines ran the unchanged
   lifecycle; and tts-runtime instantiated the ADR-0018 template with only
   capability content (pipeline, engines, binding) written new.
2. **Binary responses fit the contract discipline** (ADR-0020): raw WAV +
   bounded operational-only envelope header worked end-to-end from the
   ReferenceSynthesisEngine through production; errors stayed JSON
   everywhere; gateway overhead 2.0 % of inference — ADR-0002's isolation
   bet holds for the payload-out shape too.
3. **Engines are replaceable cargo**: swapping Kokoro requires the engine
   module + one registry row — demonstrated at the API level (byte-identical
   customer responses over a fake successor artifact) and at the deployment
   level, where a half-done swap (env flip without the registry edit)
   **failed loudly on artifact mismatch** — registry↔runtime coherence is
   enforced, not hoped for.
4. **Evaluation-first pays immediately**: M2.5's framework needed one
   ~30-line adapter to judge its first real defendant; the day-one baseline
   existed before the public API did.
5. **Admission control generalizes**: at c=20 the pool capped at exactly
   its capacity (10), refused 38 requests fast, and kept accepted latency
   bounded — the same measured behavior as STT, on a different capability.
6. **The license gate works under pressure**: the espeak risk identified at
   Step 0 materialized exactly as predicted at Step 4 and was contained by
   design (KPipeline bypass + firewall) rather than by luck; the deployment
   image is now GPL-free *by construction* (build-time verified).

## 2. Assumptions still unvalidated

- **No human has scored quality**: round-trip WER 0.072 proves
  *intelligibility*, not *pleasantness*; the listening protocol has still
  never been executed (founder has the three audition WAVs).
- **Voice identities are placeholders**: the naming decision (and therefore
  the first *real* exercise of voice-id permanence) is pending.
- **Single-judge evidence**: every quality number flows through
  whisper-small; C2 (second-judge spot-audit) remains a scheduled gate.
- **Seed-scale corpus**: 25 cases; C3 requires ≥100 before any switching
  test.
- **The template is n=2**: two runtimes prove the pattern twice, not
  universally; the third capability (or streaming) is the next real test.

## 3. What changed our mind

- **PyPI torch on Linux is the CUDA build** — CPU-first needed an explicit
  CPU wheel index; "default = CPU" was a Windows-shaped assumption.
- **misaki pip-installs a spaCy model at first load** — a runtime internet
  fetch invisible on dev machines, fatal in the hardened image; now a
  hash-locked explicit dependency. Lesson re-learned from M2 ("containers
  are the honest dependency test"), one layer deeper.
- **The stt image could no longer rebuild** (predated the runtime-core
  extraction) — running containers hide broken builds; production
  validation exists precisely to find this.
- **Short text isn't automatically fast**: two short sentences cost two
  model passes (~500 ms fixed each) — 28 chars measured *slower* than 44.
  Chunking strategy, not model speed, governs short-utterance TTFB.
- **The espeak-free trade-off has a product face**: dictionary-only G2P
  drops out-of-vocabulary words — the platform couldn't say "IntelliAI"
  (founder-discovered). Registered as the **Pronunciation Manager**
  (platform component, §5), not a Kokoro bug.

## 4. PRD verdict — honest scoping (the milestone's first FAIL)

TTFB < 1 s: **PASS for single-sentence utterances** (814 ms via gateway);
**FAIL for longer text** (2237 ms @ 122 chars — unstreamed TTFB scales
with audio length). Recorded in PRD §10 with scope; consequences decided:
**streaming = GO for M8** (this was the deferred go/no-go evidence), chunk
merging registered as the nearer runtime lever. A measured FAIL with a
decision attached is the evaluation culture working as designed.

## 5. Debt register & conditions carried forward

| Item | Owner / trigger |
|---|---|
| **Pronunciation Manager** (platform lexicon, per-engine rendering; brand names first — "IntelliAI" case joins corpus v2) | Platform work, next runtime touch; design review §11 |
| Chunk merging in tts-runtime | Before any TTFB re-measurement |
| **Hindi TTS checkpoint** (subprocess-isolated espeak spike vs IndicF5 MIT lineage) | Now governed by Language Policy v1; decision before Hindi ships |
| **Arabic engine research** (no current candidate) | New, from Language Policy v1; enters the engine-research pipeline |
| C2: second-judge spot-audit | First promotion decision |
| C3: corpus ≥100 cases | Before any switching test |
| GPL wheels on dev-machine disk (unused, firewalled) | Cosmetic; image is clean — revisit only if policy tightens |
| Voice naming (founder listening session) | Whenever the founder decides; engineering does not wait |

ADR ledger: 0016 (contract) exercised additively twice, holds; 0017
(registry) gained voices + a second capability, holds; 0018 (runtime
template) instantiated twice with measured parity, holds; 0019
(runtime-core) proven by empty diff + second consumer, holds; 0020
(binary binding) proven through production incl. the bounded-envelope
invariant, holds. No ADR met its reopening criteria; ADR-0002's evidence
now covers both payload directions (0.86 % / 2.0 %).

## 6. Founder responsibilities (carried, aging)

Dataset v2 recordings (protocol in ml/evaluation/README.md) · customer
discovery conversations (still zero logged — now two shipped products to
demo) · M1 key rotation · voice naming (three audition WAVs delivered) ·
parked Dependabot PRs (#1 py3.14 ~M9; #2 + new postgres-18 PR ~M4).

## 7. Definition of Done (final)

✓ Public TTS API live behind keys, OpenAI-compatible, engine invisible
(leak-guard-enforced) — **officially released as v0.4** with honest scope
(EN-only, placeholder voices, single-sentence TTFB).
✓ Runtime architecture proven capability-independent (empty-diff
extraction + second template instantiation + alien-engine proofs).
✓ Contract evolved additively; version still 1.
✓ License discipline end-to-end: fresh verdicts, license firewall,
**GPL-free deployment image verified at build and in the container**.
✓ Evaluation wired: day-one baseline, live reproduction, reproducible
CLI workflow, capability-extension demonstrated.
✓ Production measured and permanent: [TTS baseline](../../ml/evaluation/tts/benchmarks/2026-08-03-kokoro-82m-cpu-baseline.md)
(cold ~38 s / warm restart 7 s / plateau 0.64 rps / flat ~2.0 GiB /
overhead 2.0 %); PRD verdict recorded honestly; streaming decided by
evidence.
✓ Founder directives recorded as law: three-planes causal chain,
knowledge-compounds principle, **Core Speech Language Policy v1
(EN/HI/AR)**, capabilities-permanent principle, Pronunciation Manager.
✓ PRD v0.7, ARCHITECTURE v0.4, version 0.4.0, CI green throughout.

## 8. Verdict

Milestone 3 is **closed**. The platform now serves two speech
capabilities through one identity system, one contract, one evaluation
discipline, and one deployment shape — and the first engine to be
retired, whenever that day comes, will change a module and a registry
row, not the product. Models depreciate; knowledge compounds — and this
milestone banked plenty of both.
