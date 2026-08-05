# Cohere Transcribe Arabic — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Cohere Transcribe — Cohere's open-weight ASR line. This is its
**Arabic-specialised** member, released 2026-07-07, sibling to the
general multilingual model (see
[cohere-transcribe-dossier.md](cohere-transcribe-dossier.md)).

## Repository
`huggingface.co/CohereLabs/cohere-transcribe-arabic-07-2026`.

## Organization
Cohere / Cohere Labs.

## License (claimed at intake)
**`apache-2.0` — verified at source on the model card, 2026-08-05.**

This verification mattered enough to perform at intake: Cohere Labs has
historically released flagship weights (Aya, Command) under **CC-BY-NC**,
which would have made the model commercially impossible for us. The
transcribe line does not follow that pattern. Gate 1 must still confirm
the **transitive** picture (inference code, any tokenizer/feature
dependencies) and re-verify per artifact version — a family-level trust
assumption is forbidden, and this org is a live example of why.

## Model family / sizes
2B parameters. FastConformer encoder + lightweight autoregressive
Transformer decoder (encoder-decoder, not an audio-LLM).

## Supported languages (claimed)
**Arabic, Arabic dialects, English, and Arabic-English code-switched
speech.** The card presents dialect breadth and code-switching as
deliberate design targets, with training data resampled across dialect
groups.

## Streaming support (claimed)
Not stated on the card. Assume none until established.

## Hardware expectations
2B encoder-decoder; heavier than our 244M incumbent but far lighter than
24B audio-LLMs. CPU viability at our latency targets is unknown and is a
first-order Gate 2 question given CPU-first economics.

## Maintenance activity
Newly released (July 2026) by an active commercial lab that shipped the
general transcribe model in March 2026 — a cadence, not a one-off.

## Commercial concerns
Licence verified permissive at the card level. Watch trigger: this org's
licensing has diverged by product line before, so **every new version
requires its own verdict**.

## Known limitations
Arabic ASR is objectively hard — the vendor's own reported leaderboard
figure is a high absolute WER by English standards, which reflects the
task, not necessarily the model. No comparison is drawn here; that is
Gate 4 work. Beyond that: no streaming claim, no Hindi, and a single
released version with no track record.

## Why this lineage deserves investigation
**It is the first serious candidate for a language slot that has had
none.** Arabic is a first-class product language under Core Speech
Language Policy v1, yet the ledger has carried it as an open slot with no
corpus, no baseline, and no candidate. This model is purpose-built for the
two properties that make Arabic genuinely hard — dialect variation and
Arabic-English code-switching — under a licence that appears commercially
usable. Its arrival is the strongest argument for opening the Arabic
research thread now rather than later.
