# MOSS-Transcribe-preview-2B (OpenMOSS) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 intake · **Gate 1 verdict: BLOCKED (2026-08-05) — work halted** |
| **Gate 1** | Card claims `apache-2.0`, but the model is built on **Qwen3-1.7B-base** and a **Qwen3-Omni-MoE** encoder with **no licences stated for either base**. A derivative cannot grant more than its bases allow. **No Gate 2 dossier until both upstream licences are verified.** [Screening record](../2026-08-05-stt-gate1-license-screen.md) |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
MOSS-Transcribe — the ASR line of the OpenMOSS project: a
**Qwen3-1.7B-base** language-model backbone paired with a
**Qwen3-Omni-MoE** audio encoder. SALM-class, like ARK and Canary-Qwen.

## Repository
`huggingface.co/OpenMOSS-Team/MOSS-Transcribe-preview-2B`.

## Organization
OpenMOSS (academic-affiliated open-model project, Fudan University
lineage).

## License (claimed at intake)
Apache-2.0 (claimed, landscape material 2026-08-05). **Not verified at
source in this intake.**

## Model family / sizes
~2B total (1.7B LM backbone plus MoE audio encoder). Explicitly a
**preview** release, not a stable line.

## Supported languages (claimed)
English only, trained on public English ASR corpora.
**No Hindi. No Arabic.**

## Streaming support (claimed)
None stated.

## Hardware expectations
2B with an MoE audio encoder; MoE adds memory overhead disproportionate to
its nominal parameter count. GPU-oriented.

## Maintenance activity
Preview-stage; no stable release cadence to assess.

## Commercial concerns
Licence unverified. Built on Qwen components, so concentration
considerations partially apply.

## Known limitations
Beyond English-only and preview status, one property deserves explicit
recording: the model is described as **fine-tuned with reinforcement
learning on the Open ASR Leaderboard training splits**. Optimising
directly against a public benchmark's training data means its leaderboard
standing is not transferable evidence of general capability — an
independent-corpus effect our framework anticipates but which is rarely
stated this plainly by a publisher.

## Why this lineage deserves investigation
Two reasons, and the second is the stronger one. First, it is a current
top-of-leaderboard English entrant under a claimed permissive licence.
Second, it is a **clean worked example of why our benchmarking discipline
exists**: §6 permits comparisons only on our own corpus with our own
judge, precisely so that leaderboard-optimised models are measured on
ground they were not trained to win. This candidate should be carried
partly as a research lesson — if it performs on *our* corpus as it does on
the leaderboard, that is informative; if it does not, that is more
informative still.
