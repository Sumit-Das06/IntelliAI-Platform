# services/tts-runtime — Speech Synthesis Runtime

Capability-named speech synthesis service; second instantiation of the
runtime serving architecture (ADR-0018) with a text pipeline and the
binary audio binding (ADR-0020). Built on `packages/runtime-core`
(ADR-0019). Arrives in Milestone 3 (v0.4) — design:
[3-tts-design.md](../../docs/milestones/3-tts-design.md).

First artifact: Kokoro-82M (Apache-2.0), English voices at launch; Hindi
is gated on a license-clean phonemization path (design review §8). Voices
are individually license-audited before catalog entry; public voice ids
never expose engine names.

> Directory renamed from `tts-kokoro` at M3 Step 0: services are named by
> capability, never by engine — engines are replaceable artifacts behind
> the registry. (The engine itself changed once already: Piper was dropped
> at Milestone 1.5 when its successor fork went GPL-3.0 — see
> [FOUNDATION_MODELS.md §3](../../docs/FOUNDATION_MODELS.md).) Voice-cloning
> work (Phase 2) targets the Chatterbox lineage, not this service.
