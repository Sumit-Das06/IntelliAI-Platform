# ADR-0015: Hardware-agnostic architecture; CPU-first deployment posture

- **Status:** Accepted
- **Date:** 2026-07-31
- **Supersedes:** ADR-0004
- **Related:** ADR-0002, ADR-0003, [AI_STRATEGY.md §6](../AI_STRATEGY.md), [MODEL_IDENTITY.md §5–6](../MODEL_IDENTITY.md)

## Context

ADR-0004 established "CPU-first serving; GPU adoption is deployment
configuration only." Its *mechanics* were always right: device as
environment configuration, single resolution point per service, CUDA via
base-image argument and compose overlay, and the acceptance test that
moving a service to GPU touches nothing under `services/*/src`.

Milestone 1.5's research exposed a cost in its *framing*. "CPU-first" read
as platform philosophy had begun to leak into strategy: it would have
vetoed GPU-native model lineages during foundation-model selection
(FOUNDATION_MODELS.md) before serving cost could be weighed as the
economic trade-off it actually is. Meanwhile the model-identity work
formalized where hardware truly lives: precision, format, and placement
are attributes of **builds** and **deployments** — never of architecture,
contracts, or model identity.

## Problem

Is "CPU-first" an architectural identity of the platform, or a deployment
posture of the current era?

## Decision

We adopt the principle: **hardware-agnostic architecture, CPU-first
deployment (today).**

- **Architecture is hardware-blind.** Runtime contracts, registry
  identity, public APIs, and capability schemas may never assume a device,
  precision, or accelerator. The same logical model may ship as many
  builds (CPU, GPU, future accelerator, hosted-provider adapter, edge),
  each separately evaluated and separately costed.
- **Model selection is hardware-open.** No candidate lineage is excluded
  because its natural engine wants specific hardware; serving cost enters
  scoring as a weighted economic criterion, never as a categorical veto.
- **Deployment is CPU-first as a posture, not a promise.** Today's
  economics (efficient small models, int8-class quantization, commodity
  hardware) make CPU the default deployment tier and the basis of
  free-tier economics. That default is re-decided per service, per tier,
  per era — by measurement.
- **All ADR-0004 mechanics are carried forward unchanged:** device as
  env configuration, one resolution point per service, hardware variants
  via build/deploy artifacts, and the generalized acceptance test —
  **adopting any new hardware target touches deployment configuration
  and (at most) adds a build; never the contract, the identity, or the
  public API.**

## Alternatives considered

- **Keep "CPU-first" as platform philosophy** — rejected: it had already
  begun functioning as a hidden architectural constraint on model
  strategy, which is exactly the kind of coupling ADR-0004's own
  mechanics were designed to prevent.
- **Go hardware-neutral in deployment too (no stated posture)** —
  rejected: the CPU-first posture is a real economic discipline (unit
  costs, free tier, commodity dev machines) and deserves to stay the
  stated default until measurements retire it.
- **Full GPU shift now** — rejected for the same reasons as in ADR-0004:
  cost before revenue, and the current small-model frontier keeps CPU
  serving competitive for Phase 1 targets.

## Trade-offs

- A posture is easier to erode than a philosophy: without the old
  absolutist framing, GPU spend must now be argued against *numbers*
  (unit economics per tier), which requires those numbers to exist —
  metering and evaluation carry more weight.
- Two-word nuance ("architecture" vs "deployment") must be maintained in
  docs and reviews; sloppy shorthand will recreate the old framing.

## Consequences

- Foundation-model scoring weighs serving cost economically; GPU-native
  lineages are eligible platform citizens (this unblocked several
  Milestone 1.5 recommendations).
- Hardware, precision, and placement live exclusively in build and
  deployment records (MODEL_IDENTITY.md §5–6); registry identity remains
  hardware-blind.
- The GPU era (expected with the Language phase) arrives as deployment
  configuration plus new builds — no code, contract, or API changes —
  exactly as ADR-0004's mechanics always intended.
- ADR-0004 is superseded in framing; every mechanical rule it introduced
  remains in force through this ADR.

## Future review criteria

- First sustained GPU deployment tier: verify the acceptance test held
  (no `services/*/src` changes) and record actual unit-economics deltas.
- If a future accelerator class (non-CPU/GPU) is adopted: this ADR holds
  if adoption was deployment-config + builds only; anything more means
  the architecture leaked hardware assumptions and this ADR failed.
- If free-tier economics stop depending on CPU serving, re-examine
  whether "CPU-first deployment" remains the stated default posture.
