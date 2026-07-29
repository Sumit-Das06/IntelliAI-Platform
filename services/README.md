# services/ — Inference Services

One independently deployable service per model or external provider, each
implementing the shared runtime contract from `packages/runtime-contract`.
This is the ONLY layer allowed to be domain- or provider-specific.

Rules:
- May import `packages/runtime-contract` and nothing else internal.
- Know nothing about accounts, keys, billing, or other services.
- Device (CPU/GPU) is runtime configuration, never code (ADR-0004, forthcoming).
- External providers (e.g. Deepgram, Azure Speech) integrate as adapter services
  implementing this same contract — the gateway cannot tell them apart from our own.
