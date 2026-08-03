"""The synthesis warm-up probe — the capability content of startup.

The lifecycle machinery (runtime-core) guarantees the probe runs exactly
once per engine before serving; those guarantees are pinned in the
runtime-core suite. THIS test pins what probing MEANS for synthesis: one
short fixed sentence through the default voice at natural pace.
"""

from intelliai_tts_runtime.engines import SynthesizedAudio
from intelliai_tts_runtime.main import synthesis_warm_up
from intelliai_tts_runtime.voices import resolve


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
    synthesis_warm_up(engine)
    assert len(engine.calls) == 1
    text, voice, speed = engine.calls[0]
    assert text  # a real sentence pushes the engine through its full path
    assert voice == resolve(None)[1]  # the default voice's ENGINE reference
    assert speed is None  # natural pace
