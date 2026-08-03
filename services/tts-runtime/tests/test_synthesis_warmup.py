"""The synthesis warm-up probe — the capability content of startup.

The lifecycle machinery (runtime-core) guarantees the probe runs exactly
once per engine before serving; those guarantees are pinned in the
runtime-core suite. THIS test pins what probing MEANS for synthesis: one
short fixed sentence through the default voice at natural pace.
"""

from intelliai_tts_runtime.engines import SynthesizedAudio
from intelliai_tts_runtime.main import make_synthesis_warm_up
from intelliai_tts_runtime.voices import KOKORO_VOICES, REFERENCE_VOICES


class RecordingEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float | None]] = []

    def synthesize(self, text: str, voice: str, speed: float | None) -> SynthesizedAudio:
        self.calls.append((text, voice, speed))
        return SynthesizedAudio(pcm=b"\x00\x00", sample_rate_hz=24_000)

    def close(self) -> None:
        return None


def test_probe_is_one_fixed_sentence_through_the_default_voice() -> None:
    engine = RecordingEngine()
    make_synthesis_warm_up(REFERENCE_VOICES)(engine)
    assert len(engine.calls) == 1
    text, voice, speed = engine.calls[0]
    assert text  # a real sentence pushes the engine through its full path
    assert voice == REFERENCE_VOICES.resolve(None)[1]  # the default ENGINE reference
    assert speed is None  # natural pace


def test_probe_follows_the_engine_bound_voice_map() -> None:
    # The probe is capability-defined AND deployment-aware: a kokoro
    # deployment warms through kokoro's default binding.
    engine = RecordingEngine()
    make_synthesis_warm_up(KOKORO_VOICES)(engine)
    assert engine.calls[0][1] == "af_heart"
