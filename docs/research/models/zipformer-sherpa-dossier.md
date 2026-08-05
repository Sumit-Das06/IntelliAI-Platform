# Zipformer / Next-gen Kaldi (k2, icefall, sherpa-onnx) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 intake · **Gate 1 verdict: BLOCKED as a serving candidate (2026-08-05)** |
| **Gate 1** | Toolkit verified Apache-2.0 and clean — the **training-stack path (§12/§15) is unobstructed**. But pretrained checkpoints ship separately via GitHub Releases with **no per-checkpoint licence**, and training-corpus terms may bind derived weights. **No checkpoint may enter Gate 2 until its own licence and corpus terms are verified.** [Screening record](../2026-08-05-stt-gate1-license-screen.md) |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Next-gen Kaldi — the `k2` / `icefall` / `sherpa` ecosystem, whose current
flagship encoder is **Zipformer**, typically trained with
pruned-transducer or CTC objectives and deployed via `sherpa-onnx`. This
is a **toolkit lineage**, not a single released checkpoint: recipes plus
per-language models.

## Repository
`github.com/k2-fsa/icefall` (recipes/training),
`github.com/k2-fsa/sherpa-onnx` (deployment), with pretrained checkpoints
published per recipe.

## Organization
Next-gen Kaldi community (Xiaomi-affiliated maintainers plus the wider
Kaldi research community). Community-governed rather than
corporate-owned.

## License (claimed at intake)
Apache-2.0 across the k2/icefall/sherpa stack (claimed). **Not verified
at source in this intake.** Per-checkpoint licences may differ from the
toolkit's, and some recipes are trained on corpora with their own terms —
an unusually important Gate 1 nuance for this lineage, since here the
*dataset* licence can bind the *checkpoint*.

## Model family / sizes
Zipformer encoders across a wide size range, commonly tens to low
hundreds of millions of parameters — **the smallest class in this
intake**, by design.

## Supported languages (claimed)
Whatever a recipe has been trained for; community checkpoints exist for
many languages, with quality varying sharply by recipe and corpus. Hindi
and Arabic checkpoints exist in the community but their provenance and
quality are entirely unestablished.

## Streaming support (claimed)
**Yes — streaming is a first-class design goal**, not an add-on.
Pruned-transducer streaming recipes and `sherpa-onnx` streaming servers
are the ecosystem's core competency.

## Hardware expectations
**The most CPU-native lineage in this intake.** ONNX deployment, small
footprints, and real-time streaming on modest CPUs are the explicit
targets — directly aligned with our CPU-first constitution.

## Maintenance activity
Sustained, active community development over many years.

## Commercial concerns
Toolkit licence appears permissive; the real diligence is per-checkpoint
and per-training-corpus. If we ever *train* on this stack, corpus terms
become our terms.

## Known limitations
Quality tier for a given language depends on the training corpus
available, so out-of-the-box multilingual quality is unlikely to match
large pretrained models; operating it means owning recipes rather than
consuming checkpoints; documentation is research-grade.

## Why this lineage deserves investigation
Two distinct reasons, both structural rather than about today's accuracy.
First, it is the **CPU-streaming reference**: if the M8 streaming
question ever demands genuinely low-latency CPU transcription, this
ecosystem is where that has been solved. Second — and more strategically
— it is a **training stack, not just a serving stack**, which makes it
directly relevant to the training-program connection (§15) and to any
future IntelliAI-native model built on our own datasets (§12). It is the
one candidate here that could eventually serve the *own* side of the
serve/own split rather than the *serve* side.
