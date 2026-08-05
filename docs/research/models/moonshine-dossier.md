# Moonshine (Useful Sensors) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Moonshine — a compact encoder-decoder ASR family designed for edge and
low-latency use. Its distinguishing design choice is handling
**variable-length audio without padding to a fixed window**, which is
what allows short utterances to be processed proportionally to their
actual length rather than at Whisper's fixed 30-second cost.

## Repository
`github.com/usefulsensors/moonshine`; checkpoints on HuggingFace under
`UsefulSensors`.

## Organization
Useful Sensors — a small company focused on on-device AI. **Smallest
organisational footprint in this intake**, which is a continuity risk to
record honestly.

## License (claimed at intake)
MIT (claimed). **Not verified at source in this intake**; Gate 1 must
confirm the licence on both code and checkpoints.

## Model family / sizes
Tiny and base tiers (tens of millions of parameters) — the smallest
models registered in this intake.

## Supported languages (claimed)
English-centric. Later multilingual work has been reported, but Hindi and
Arabic coverage should be assumed absent until established.
**Does not address two of our three product languages.**

## Streaming support (claimed)
Designed for low-latency and streaming-style edge use; the variable-length
design is what makes short-segment latency competitive.

## Hardware expectations
The lightest CPU profile among registered candidates; targets embedded and
edge hardware. Attractive against CPU-first economics, and the only
candidate plausibly relevant to a future **offline/on-device** product.

## Maintenance activity
Active but small-team; single-vendor continuity risk.

## Commercial concerns
MIT if confirmed — clean. The concern is organisational durability rather
than legal terms.

## Known limitations
English-centric; small models carry a quality ceiling that no amount of
serving optimisation removes; limited ecosystem and fine-tuning precedent
compared to Whisper.

## Why this lineage deserves investigation
It defines the **lower bound of the cost/latency frontier**. Research
priority #1 (English STT improvement) is not solely an accuracy question —
if a fraction of traffic is short utterances, a model whose cost scales
with actual audio length rather than a fixed window is architecturally
interesting. It is also the natural reference if an offline or on-device
deployment ever enters the product roadmap.
