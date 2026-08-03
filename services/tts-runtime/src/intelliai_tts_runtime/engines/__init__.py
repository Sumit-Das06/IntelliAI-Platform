"""Engine adapters — the ONLY modules allowed to import foundation-model
libraries (CI-enforced by the isolation test suite).

An engine is a thin adapter around one foundation model: canonical text
and an engine voice reference in, canonical PCM out. Engines hold exactly
one piece of state — the loaded model — and know nothing about transport,
containers, filesystems, downloads, slots, or PUBLIC voice identities
(voice resolution happens before the engine; ModelManager owns the rest).
"""

from intelliai_tts_runtime.engines.base import SynthesisEngine, SynthesizedAudio

__all__ = ["SynthesisEngine", "SynthesizedAudio"]
