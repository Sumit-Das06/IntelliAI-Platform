# services/stt-runtime — Speech-to-Text Runtime

The transcription-capability runtime service. Arrives in Milestone 2 (v0.3).

**The service is named for the capability, never for a foundation model**
(Constitution P1/P2): Whisper is the *current* engine behind it, selected in
[FOUNDATION_MODELS.md](../../docs/FOUNDATION_MODELS.md); Qwen3-ASR is the
named successor lineage; future IntelliAI fine-tunes ride the same runtime.
Replacing an engine touches one adapter module, never this service's
identity.

Internal shape (M2 design, approved):

```
api/        contract layer — speaks packages/runtime-contract only
pipeline/   media ingestion: sniff → ffmpeg → 16 kHz mono → VAD (engine-neutral)
manager/    ModelManager — download, checksum verification, cache, slots
            (default/premium/experimental), lifecycle, warm-up
engines/    engine adapters — the ONLY modules allowed to import
            foundation-model libraries (CI-enforced)
```

CPU-first deployment (int8); hardware-agnostic architecture — GPU via
deployment config only (ADR-0015).
