# ADR-0005: Only commercially-clear model licenses; the registry enforces it

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0003, ADR-0011

## Context

IntelliAI is a commercial SaaS reselling model inference. Open-source model
licenses vary from fully permissive (MIT, Apache-2.0) to research-only
(CC-BY-NC) to bespoke restrictions (Coqui CPML). A license violation in a
revenue-generating product is an existential legal risk, and swapping a
banned model out after customers depend on its quality is a product crisis.

## Problem

Which models are allowed into the platform, and how is the rule enforced so
it survives beyond anyone's memory?

## Decision

We will serve only models whose licenses clearly permit commercial
inference-as-a-service: MIT, Apache-2.0, BSD, CC-BY, or equivalent. Every
model registry entry records `license` and a `commercial_ok` verdict; entry
without them is impossible by schema. Piper voices are audited individually
(voice models inherit training-data licenses). Currently banned: Coqui XTTS
(CPML non-commercial; vendor defunct, no license purchasable), NVIDIA
Canary (CC-BY-NC). Every model recommendation must state license,
commercial usability, performance, hardware requirements, and rationale.

## Alternatives considered

- **Use now, resolve later** — rejected: retroactive license violations
  compound with revenue; the cheapest moment to comply is before launch.
- **Negotiate commercial licenses for restricted models** — rejected today:
  disproportionate effort pre-revenue; Coqui no longer exists to negotiate
  with. Explicitly the first thing to revisit with scale.
- **Only self-trained models** — rejected for Phase 1: years of work before
  a single API call.

## Trade-offs

- Some state-of-the-art models are off-limits; in some domains our quality
  ceiling is lower than competitors willing to take licensing risk.

## Consequences

- License review is a standing step in model adoption.
- The registry is the enforcement point — policy as data, not memory.
- Voice-catalog growth (Piper) is slowed by per-voice audits.

## Future review criteria

- Revenue plus legal counsel could justify negotiated licenses for
  restricted models that benchmark meaningfully better.
- If a banned model's license changes (or weights are relicensed), re-audit.
