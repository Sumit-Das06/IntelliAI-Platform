# Canary-Qwen 2.5B (NVIDIA) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Canary — NVIDIA's accuracy-oriented ASR line. **Canary-Qwen 2.5B** is a
Speech-Augmented Language Model (SALM): a Canary-family speech encoder
coupled to a Qwen LLM decoder.

**This artifact is not the rejected one.** Our ledger already carries
`Canary 1B` as **Rejected** on a CC-BY-NC licence. Canary-Qwen 2.5B is a
separate artifact reported under CC-BY-4.0. Registering it separately is
the per-artifact-version law working as designed — a family-level
rejection would have silently discarded a usable model.

## Repository
`huggingface.co/nvidia/canary-qwen-2.5b` (to be pinned and verified at
Gate 1).

## Organization
NVIDIA — see the licence-variance caution in
[parakeet-tdt-dossier.md](parakeet-tdt-dossier.md).

## License (claimed at intake)
CC-BY-4.0 (claimed, 2026-07-31 sweep). **Not verified at source in this
intake.** Given that a sibling artifact in the same family is CC-BY-NC,
source verification here is high-value and must precede any other work on
this lineage.

## Model family / sizes
2.5B (SALM: speech encoder + Qwen LLM decoder).

## Supported languages (claimed)
English only. **No Hindi. No Arabic.**

## Streaming support (claimed)
None identified at intake; LLM-decoder architectures are generally not
streaming-native.

## Hardware expectations
2.5B with an LLM decoder — GPU-bound in practice per the 2026-07-31
assessment. Least aligned of this intake with CPU-first economics.

## Maintenance activity
Active line; it held the top leaderboard position for an extended period
before the 2026 wave of entrants.

## Commercial concerns
CC-BY attribution obligations (as with Parakeet) plus the family's
licence variance. Also inherits a Qwen component, so Qwen concentration
considerations partially apply.

## Known limitations
English-only; GPU-bound; large relative to the task; the SALM approach
couples ASR quality to LLM behaviour, which adds hallucination surface
that a CTC/transducer model does not have.

## Why this lineage deserves investigation
It is the reference implementation of the **SALM architecture** — the
design pattern that several 2026 entrants (ARK, MOSS, Voxtral) now share.
Understanding it once explains a whole class of candidates, which is
efficient research even though this specific artifact is poorly matched to
our deployment constraints.
