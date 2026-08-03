"""Local real-model tier: the actual Kokoro-82M, end to end, espeak-free.

Opt-in (INTELLIAI_RUN_LOCAL_MODEL_TESTS=1): downloads/verifies ~330 MB of
weights + voice packs and needs the `kokoro` extra installed. CI never
runs this — CI proves the architecture with the ReferenceSynthesisEngine;
THIS tier proves the foundation model, on demand, on real hardware — and
proves the license firewall at runtime: after a full load and synthesis,
no GPL espeak/phonemizer module exists in the process.
"""

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("INTELLIAI_RUN_LOCAL_MODEL_TESTS") != "1",
    reason="local model tier: set INTELLIAI_RUN_LOCAL_MODEL_TESTS=1 (downloads weights)",
)


def _peak_amplitude(pcm: bytes, sample_limit: int = 240_000) -> int:
    window = pcm[: sample_limit * 2]
    return max(
        abs(int.from_bytes(window[i : i + 2], "little", signed=True))
        for i in range(0, len(window), 2)
    )


def test_kokoro_synthesizes_real_speech_with_the_firewall_holding() -> None:
    # The hub must never be needed: everything loads from OUR verified store.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    from intelliai_runtime_core import ArtifactStore
    from intelliai_tts_runtime.engines.kokoro import KOKORO_FILES, load_kokoro

    store = ArtifactStore(Path("models"))
    local_dir = store.ensure(KOKORO_FILES)  # SHA-256-verified before load
    engine = load_kokoro(local_dir)
    try:
        natural = engine.synthesize(
            "Hello! This is the IntelliAI speech platform speaking.", "af_heart", None
        )
        faster = engine.synthesize(
            "Hello! This is the IntelliAI speech platform speaking.", "af_heart", 1.4
        )
        other_voice = engine.synthesize("Hello from a different voice.", "am_michael", None)
    finally:
        engine.close()

    assert natural.sample_rate_hz == 24_000
    assert 1.0 < natural.duration_seconds < 15.0
    assert _peak_amplitude(natural.pcm) > 3000  # audible speech, not silence
    assert faster.duration_seconds < natural.duration_seconds  # speed is honored
    assert _peak_amplitude(other_voice.pcm) > 3000

    # The license firewall, proven at runtime: the poison stub is in place
    # and no REAL GPL wrapper module ever entered the process.
    stub = sys.modules.get("misaki.espeak")
    assert stub is not None
    with pytest.raises(RuntimeError, match="license"):
        _ = stub.EspeakFallback
    loaded_gpl = [
        name
        for name in sys.modules
        if ("phonemizer" in name.lower() or "espeak" in name.lower()) and name != "misaki.espeak"
    ]
    assert not loaded_gpl, f"GPL modules entered the process: {loaded_gpl}"
