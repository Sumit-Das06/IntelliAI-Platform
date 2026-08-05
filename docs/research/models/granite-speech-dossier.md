# Granite Speech (IBM) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
IBM Granite Speech — the speech member of IBM's Granite open-model
family, coupling a speech encoder to a Granite LLM backbone. Current
generation at intake: **Granite Speech 4.1 2B**.

## Repository
`huggingface.co/ibm-granite/granite-speech-4.1-2b` (verified to exist).

## Organization
IBM. Enterprise-oriented governance: IBM publishes provenance and
indemnification positions for Granite models, which is unusual among open
weights and materially relevant to a commercial platform.

## License (claimed at intake)
**`apache-2.0` — verified at source on the model card, 2026-08-05.**
Transitive dependencies and per-version verdicts remain Gate 1 work.

## Model family / sizes
2B. Architecture per card: 16-block conformer speech encoder with
dual-head CTC → speech projector / temporal downsampler (window query
transformer) → Granite 4.0 1B LLM backbone with 128k context.

## Supported languages (claimed)
English, French, German, Spanish, Portuguese, Japanese.
**No Hindi. No Arabic.** This is an English-and-European model and cannot
serve two of our three product languages.

## Streaming support (claimed)
Not stated on the card. The dual-head CTC component is architecturally
suggestive of a streaming path, but nothing is claimed — treat as absent.

## Hardware expectations
2B with an LLM backbone; heavier than classical ASR encoders. CPU
viability unknown; the 128k-context LLM component implies memory
overheads that our ~800MiB incumbent does not carry.

## Maintenance activity
Active, with a versioned release train (4.0 → 4.1) and enterprise support
expectations.

## Commercial concerns
Among the cleanest in this intake: permissive licence plus explicit
enterprise governance. The concern is scope, not law — adopting it would
mean an English-only engine, and our language policy requires the other
two languages to be served *somehow*.

## Known limitations
No Indic or Arabic coverage; LLM-coupled memory profile; no streaming
claim; quality tier is a leaderboard claim we have not measured.

## Why this lineage deserves investigation
It is a credible **English-specialist** candidate with an unusually clean
commercial posture, from a vendor whose provenance practices align with
our licensing constitution. Our architecture explicitly permits
per-language engines behind one public model, so an English-only engine is
a legitimate shape — and research priority #1 is English STT improvement.
It is also a useful reference point for how much a 2B LLM-coupled model
costs relative to our 244M incumbent.
