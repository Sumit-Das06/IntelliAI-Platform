# Parakeet TDT (NVIDIA) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Parakeet — NVIDIA's efficient ASR line (FastConformer encoders with
Token-and-Duration Transducer decoding), distributed through the NeMo
ecosystem. Current multilingual member at intake: **parakeet-tdt-0.6b-v3**.

## Repository
`huggingface.co/nvidia/parakeet-tdt-0.6b-v3` (verified to exist).

## Organization
NVIDIA. Prolific speech-model publisher — with a **licensing record that
varies by artifact**, which is the central caution for this lineage.

## License (claimed at intake)
**`CC-BY-4.0` — verified at source on the v3 card, 2026-08-05**
("Use of this model is governed by the CC-BY-4.0 license"). CC-BY permits
commercial use with attribution and is inside our policy class.

**Critical per-version caution:** the same org publishes Canary 1B under
**CC-BY-NC** (already Rejected in our ledger) and has moved some newer
checkpoints to a custom NVIDIA licence. This lineage is the clearest live
proof of the law that verdicts attach to artifact versions, never to
organisations.

## Model family / sizes
0.6B (v2 English-centric; v3 multilingual). Small by 2026 standards and
deliberately throughput-oriented.

## Supported languages (claimed)
25 European languages with automatic language identification (Bulgarian,
Croatian, Czech, Danish, Dutch, English, Estonian, Finnish, French,
German, Greek, Hungarian, Italian, Latvian, Lithuanian, Maltese, Polish,
Portuguese, Romanian, Slovak, Slovenian, Spanish, Swedish, Russian,
Ukrainian). **No Hindi. No Arabic.**

## Streaming support (claimed)
**Yes — verified on the card:** a dedicated streaming inference script
with configurable context windows and chunk sizes. Transducer
architectures are natively streaming-friendly.

## Hardware expectations
Throughput claims are GPU-referenced (reported RTFx in the thousands on
an A100, up to ~24 minutes of audio in a single pass on 80GB). CPU
behaviour is unestablished; NeMo/transducer stacks are less CPU-mature
than CTranslate2, which is what our incumbent enjoys.

## Maintenance activity
Very active line with successive versions (v2 → v3).

## Commercial concerns
CC-BY-4.0 requires **attribution**, which is an operational obligation
our product surfaces would need to satisfy — worth noting because our
public API deliberately hides engines. Attribution compatibility with a
white-labelled `intelliai-stt` is a genuine Gate 1 question, not a
formality. Plus the per-version licence drift noted above.

## Known limitations
No Indic or Arabic coverage; GPU-oriented performance story; NeMo serving
stack is a different operational world from our current runtime;
attribution obligations interact awkwardly with engine-hiding.

## Why this lineage deserves investigation
It is the **efficiency/throughput reference** for this generation and a
genuinely streaming-native architecture under a commercially usable
licence. Research priority #1 is English STT improvement, where cost per
hour is as legitimate a lever as accuracy; and the M8 streaming question
benefits from understanding a transducer-based streaming design even if we
never adopt it.
