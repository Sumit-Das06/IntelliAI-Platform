# IndicWhisper (AI4Bharat) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
IndicWhisper — AI4Bharat's **fine-tunes of OpenAI Whisper** on Indian
languages, published alongside the *Vistaar* Indic ASR benchmark. It is a
derivative of our incumbent lineage, not an independent architecture.

## Repository
`ai4bharat.iitm.ac.in/areas/model/ASR/IndicWhisper`; training and
evaluation code plus checkpoints published by AI4Bharat. Third-party
re-uploads exist on HuggingFace — provenance must be pinned to the
lab's own distribution at Gate 1.

## Organization
AI4Bharat (IIT Madras). Same lab as
[indicconformer-dossier.md](indicconformer-dossier.md).

## License (claimed at intake)
MIT — the lab states MIT covers the repository's fine-tuned language
models and the Vistaar benchmark (landscape material, 2026-08-05).
**Not verified at source in this intake.** Two things need Gate 1
attention: the licence on the *checkpoints themselves* (as distinct from
the code), and confirmation that the Whisper base's MIT terms flow through
cleanly (they should — MIT on MIT).

## Model family / sizes
Whisper-architecture checkpoints at the base model's sizes; per-language
and multilingual Indic variants.

## Supported languages (claimed)
Indian languages, **Hindi prominently included**. No English-improvement
claim; no Arabic.

## Streaming support (claimed)
None — inherits Whisper's 30-second window and non-streaming design.

## Hardware expectations
**Identical to our incumbent's** at equal size. This is the lineage's
defining practical advantage: it can run on the serving stack we already
operate (faster-whisper / CTranslate2), subject to conversion.

## Maintenance activity
Tied to the lab's Indic programme; less continuously maintained than
corporate lines.

## Commercial concerns
MIT if confirmed. Training-data provenance for Indic corpora is a risk
note to examine, as with the lab's other models.

## Known limitations
Inherits every Whisper limitation (window, no streaming, hallucination
surface); Indic-only; unclear whether checkpoints exist in a
CTranslate2-convertible form; benchmark claims are on Vistaar, not on our
corpus.

## Why this lineage deserves investigation
It is the **cheapest possible answer to research priority #2**. If Hindi
quality can be materially improved *inside the Whisper lineage*, then our
accumulated operational knowledge, serving stack, and evaluation tooling
all transfer unchanged — precisely the "fine-tuning capital compounds
within a lineage" argument in FINE_TUNING_STRATEGY Part 4. It also serves
as a reference point for what a Hindi fine-tune of Whisper can achieve,
which is the natural comparison for §9 rung 3 (adapters) before rung 5
(new engine) is ever funded.
