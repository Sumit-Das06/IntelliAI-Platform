# Kyutai STT — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Kyutai STT — the speech-recognition component of Kyutai's real-time
speech stack (the lab behind the Moshi full-duplex speech model). Built
on **delayed-streams modelling**: a streaming-first formulation rather
than an offline model adapted to stream.

## Repository
`github.com/kyutai-labs/delayed-streams-modeling`; checkpoints on
HuggingFace under `kyutai`.

## Organization
Kyutai — a French non-profit research lab with a consistent open-release
practice.

## License (claimed at intake)
CC-BY-4.0 (claimed, 2026-07-31 sweep). **Not verified at source in this
intake.** CC-BY permits commercial use with attribution; as with the
NVIDIA candidates, the **attribution obligation versus our
engine-hiding product design** is a real Gate 1 question.

## Model family / sizes
Streaming STT checkpoints at small-to-moderate sizes; released alongside
the lab's broader real-time speech work.

## Supported languages (claimed)
English and French only. **No Hindi. No Arabic.**

## Streaming support (claimed)
**Yes — this is the lineage's entire reason for existing.** Designed for
genuine full-duplex, low-latency conversational use with explicit
latency/quality trade-off controls, rather than chunked batch inference.

## Hardware expectations
Real-time operation is the design target; GPU-oriented in published usage,
CPU feasibility unestablished.

## Maintenance activity
Active research lab with a sustained real-time speech agenda.

## Commercial concerns
Attribution obligations under CC-BY; small non-profit means lower
long-term product-continuity assurance than a corporate lab, though the
licence remains irrevocable for released weights.

## Known limitations
Two languages only — it cannot serve our product languages beyond
English; research-grade tooling; narrower ecosystem.

## Why this lineage deserves investigation
Not as a likely engine, but as the **architectural reference for
streaming ASR**. The M8 streaming question is a standing platform
decision, and this lineage represents the strongest open expression of
"streaming as a first-class design" rather than "batch model plus
chunking" — which is what our current pipeline does. Understanding what
delayed-streams modelling buys, and what it costs, informs the streaming
decision regardless of whether we ever adopt this model.
