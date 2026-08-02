"""Engine adapters — the ONLY modules allowed to import foundation-model
libraries (CI-enforced by the isolation test suite).

An engine is a thin adapter around one foundation model: contract-shaped
audio and params in, contract-shaped result out. Engines hold exactly one
piece of state — the loaded model — and know nothing about transport,
filesystems, downloads, or slots (ModelManager's business).
"""

from intelliai_stt_runtime.engines.base import TranscriptionEngine

__all__ = ["TranscriptionEngine"]
