# IndicConformer (AI4Bharat) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-04 (ledger seed) · intake record created 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
IndicConformer — Conformer-architecture ASR models purpose-built for
Indian languages by AI4Bharat, a research lab at IIT Madras. Sibling
lineages from the same lab: IndicWhisper (Whisper-based, see
[indicwhisper-dossier.md](indicwhisper-dossier.md)) and IndicWav2Vec.

## Repository
`huggingface.co/ai4bharat/indic-conformer-600m-multilingual`;
`github.com/AI4Bharat/IndicConformerASR`.

## Organization
AI4Bharat (IIT Madras) — publicly funded Indic-language research lab.
Different institutional risk profile from a corporate lab: strong
language-specific depth, funding-dependent continuity.

## License (claimed at intake)
MIT — recorded in the 2026-07-31 sweep and restated in the Aug 2026
landscape material. Not re-verified at source in this intake; Gate 1 must
verify weights, code, and any dataset-derived restrictions per version.

## Model family / sizes
600M multilingual checkpoint; per-language variants exist across the lab's
model suite.

## Supported languages (claimed)
All 22 scheduled Indian languages, **Hindi included**. No English-first
claim and **no Arabic**. This is a specialist, not a generalist.

## Streaming support (claimed)
Not established at intake. Conformer/CTC architectures are commonly
streamable in principle; whether these released checkpoints ship a
streaming path is a Gate 2 question.

## Hardware expectations
600M is materially smaller than audio-LLM entrants and plausibly
CPU-servable; unmeasured.

## Maintenance activity
Active lab with a sustained Indic publication record.

## Commercial concerns
MIT is clean if confirmed. The genuine question is **training-data
provenance** for publicly funded Indic corpora — recorded as a risk note
to examine, not a gate.

## Known limitations
No English competitiveness claim; no Arabic; ecosystem and serving
tooling are smaller than Whisper's, so operational knowledge would not
transfer from our incumbent.

## Why this lineage deserves investigation
It is the leading candidate for a **dedicated Hindi engine** and,
independently, a valuable **evaluation baseline**: even if we never serve
it, measuring it tells us how much Hindi headroom exists above Whisper —
which is precisely the evidence §9 needs to choose between fine-tuning the
incumbent and adopting a specialist. Our architecture already permits
per-language engines behind one public model, so adoption would not
require redesign.
