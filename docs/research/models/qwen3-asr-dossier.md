# Qwen3-ASR (Alibaba / Qwen) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-04 (ledger seed) · intake record created 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Qwen3-ASR — the speech-recognition line of Alibaba's Qwen family
(released Jan 2026). Shares tokenizer, serving stack, and fine-tuning
toolchain with the wider Qwen lineage.

## Repository
`huggingface.co/Qwen/Qwen3-ASR-*`; GitHub under `QwenLM`. Ships an
inference toolkit and a **separate forced-alignment model** for timestamps.

## Organization
Alibaba Cloud / Qwen team. Among the highest-cadence open-weight
publishers in the industry.

## License (claimed at intake)
Apache-2.0 — recorded in the 2026-07-31 sweep. **Not re-verified at
source in this intake**; per-version verification is mandatory at Gate 1,
and the Qwen family has precedent for licence divergence between sizes.

## Model family / sizes
0.6B and 1.7B (claimed) — deliberately small, unlike audio-LLM entrants.

## Supported languages (claimed)
52 languages and dialects claimed as of the Aug 2026 landscape (≈30
languages plus 22 Chinese dialects). **Hindi is claimed in scope.**
Arabic coverage and depth are unclear from the landscape material and
must be established at Gate 2. Timestamp alignment claimed for 11
languages only.

## Streaming support (claimed)
No native streaming identified at intake.

## Hardware expectations
0.6B is CPU-plausible on paper — attractive against our CPU-first
economics, and the main reason this lineage was named the backup. No CPU
measurement exists.

## Maintenance activity
Very active; the org currently outships most competitors.

## Commercial concerns
Apache-2.0 is irrevocable for released weights, so downside is capped at
"no future versions." The real concern is **concentration**: Qwen already
backs the primary or backup for several planned capabilities, and the
[FOUNDATION_MODELS §14](../../FOUNDATION_MODELS.md) protocol requires a
warm non-Qwen alternative wherever Qwen is primary. Geopolitical /
export-control exposure on Chinese open weights is a named watch trigger.

## Known limitations
Chinese-centric optimisation is likely (22 of the claimed dialects are
Chinese); Indic and Arabic depth unproven; timestamps require a second
model, which complicates our runtime contract.

## Why this lineage deserves investigation
It is the designated **successor lineage** for transcription: Apache-2.0,
Hindi in scope, CPU-plausible sizes, and an org shipping faster than
anyone. If Whisper's age begins losing our evaluations, this is the
pre-positioned answer — and it rides a serving stack we may already
operate for other capabilities.
