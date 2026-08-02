# services/stt-runtime — Speech-to-Text Runtime

The transcription-capability runtime service. Arrives in Milestone 2 (v0.3).

**The service is named for the capability, never for a foundation model**
(Constitution P1/P2): Whisper is the *current* engine behind it, selected in
[FOUNDATION_MODELS.md](../../docs/FOUNDATION_MODELS.md); Qwen3-ASR is the
named successor lineage; future IntelliAI fine-tunes ride the same runtime.
Replacing an engine touches one adapter module, never this service's
identity.

Three independent responsibilities, three module groups (M2 step 3):

```
api/        HTTP binding — the ONLY transport-aware layer; realizes the
            runtime contract on the wire (multipart in, envelope JSON out)
pipeline/   media ingestion — a permanent, engine-independent subsystem.
            Six single-responsibility stages, each timed: validate (size
            caps) → detect (magic bytes, whitelist) → decode (sandboxed
            ffmpeg subprocess: fixed argv, stdin/stdout pipes, hard
            timeout, startup-verified) → normalize (canonical 16 kHz mono
            s16le PCM + duration cap) → VAD (Protocol; deterministic
            energy detector today, model-based slots in behind the same
            seam) → handoff. No speech after VAD is NOT an error: the
            engine is skipped and the correct empty transcript returns.
            Failure philosophy in pipeline/pipeline.py. Reusable as-is by
            future speech capabilities (translation, diarization, keyword
            spotting); extracts to a shared package at the second consumer.
manager/    model lifecycle — the long-lived ModelManager owns long-lived
            engine instances: loaded at startup, reused by every request,
            unloaded at shutdown; NO request constructs or destroys an
            engine. Slots (default/premium/experimental) each serve one
            artifact. Step 5 adds download/checksum/cache/warm-up.
engines/    inference execution — thin adapters around one foundation
            model each; stateless apart from the loaded model; the ONLY
            modules allowed to import foundation-model libraries
            (CI-enforced by tests/test_engine_isolation.py)
```

Inference runs on a bounded worker pool (`pool.py`): `max_concurrency`
threads + a small admission queue; beyond that the runtime answers
`overloaded` immediately. The `ReferenceEngine` (deterministic, weight-free)
proves the whole architecture and serves the test suite forever — CI never
loads model weights. Run locally: `make stt` (port 8001).

CPU-first deployment (int8); hardware-agnostic architecture — GPU via
deployment config only (ADR-0015). Precision/quantization are build
concerns owned by the ModelManager, never part of artifact identity.
