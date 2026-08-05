# Voxtral (Mistral AI) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Voxtral — Mistral's audio/speech line. Unlike classical ASR encoders, the
main variants are **audio-LLMs** (audio encoder + language-model
backbone), with a dedicated realtime variant and a transcription-focused
member reported in the Aug 2026 landscape.

## Repository
`huggingface.co/mistralai/Voxtral-Mini-3B-2507` (verified to exist),
plus larger and realtime variants under the same org.

## Organization
Mistral AI — European commercial lab with a consistent Apache-2.0
open-weight track record and an active release cadence.

## License (claimed at intake)
**`apache-2.0` — verified at source on the `Voxtral-Mini-3B-2507` card,
2026-08-05.** Other Voxtral variants (24B, realtime, transcribe) must be
verified individually at Gate 1; this verdict covers the Mini card only.

## Model family / sizes
Mini ~3B (card also reports ~5B total including the audio encoder) ·
Small 24B · a realtime variant reported at ~4B (≈3.4B LM + ≈970M causal
audio encoder). Sizes above ~3B are relevant to us only if CPU economics
or a GPU exception permit.

## Supported languages (claimed)
Eight primary languages with automatic detection: English, Spanish,
French, Portuguese, **Hindi**, German, Dutch, Italian. The realtime
variant is reported at 13 languages. **No Arabic in the primary list.**

## Streaming support (claimed)
**Yes — and architecturally, not as a wrapper.** The realtime variant is
described with a causal audio encoder trained from scratch and
sliding-window attention enabling effectively unbounded streaming, with
day-0 vLLM Realtime API support. All vendor claims; none verified by us.

## Hardware expectations
Vendor claims the realtime variant runs on a single 16GB GPU. That is a
**GPU-shaped claim** and says nothing about CPU viability, which is the
economics that matter for us today. Establishing CPU feasibility (or
formally treating this as a GPU-tier candidate) is the first Gate 2
question.

## Maintenance activity
Active; Mistral ships frequently and keeps Apache-2.0 as its default
posture for open weights.

## Commercial concerns
Apache-2.0 verified on the Mini card. Audio-LLM architectures pull in
LLM-scale dependencies; the transitive picture deserves real scrutiny at
Gate 1 (our GPL-by-transitivity lesson generalises).

## Known limitations
Larger than dedicated ASR encoders for the same task; no Arabic in the
primary language set; CPU story unproven; audio-LLMs can be more prone to
instruction-following artifacts and hallucination-style failure than
classical CTC/encoder-decoder ASR — a robustness question, unmeasured.

## Why this lineage deserves investigation
It is the **only lineage in this intake that claims Apache-2.0, Hindi, and
native streaming simultaneously** — touching research priority #2 (Hindi
STT) and the standing M8 streaming question with one candidate. If its
CPU economics are workable, it is strategically interesting; if they are
not, it becomes the clearest test case for whether IntelliAI ever wants a
GPU serving tier. Either answer is worth having.
