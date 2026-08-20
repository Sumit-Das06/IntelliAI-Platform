"""The synthesis warm-up probe — the capability content of startup.

The lifecycle machinery (runtime-core) guarantees the probe runs exactly
once per engine before serving; those guarantees are pinned in the
runtime-core suite. THIS test pins what probing MEANS for synthesis: one
short fixed sentence through the default voice — of the engine's OWN
bindings, which is what makes the probe correct in a multi-slot runtime.
"""

from collections.abc import Callable

from intelliai_tts_runtime.engines import SynthesizedAudio
from intelliai_tts_runtime.main import make_synthesis_warm_up
from intelliai_tts_runtime.voices import KOKORO_VOICES, REFERENCE_VOICES, VoiceCatalog


class RecordingEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float | None]] = []

    def synthesize(self, text: str, voice: str, speed: float | None) -> SynthesizedAudio:
        self.calls.append((text, voice, speed))
        return SynthesizedAudio(pcm=b"\x00\x00", sample_rate_hz=24_000)

    def synthesize_stream(
        self, text: str, voice: str, speed: float | None, emit: Callable[[bytes], None]
    ) -> None:
        emit(self.synthesize(text, voice, speed).pcm)

    def close(self) -> None:
        return None


def test_probe_is_one_fixed_sentence_through_the_default_voice() -> None:
    engine = RecordingEngine()
    catalog = VoiceCatalog()
    catalog.bind(engine, REFERENCE_VOICES)
    make_synthesis_warm_up(catalog)(engine)
    assert len(engine.calls) == 1
    text, voice, speed = engine.calls[0]
    assert text  # a real sentence pushes the engine through its full path
    assert voice == REFERENCE_VOICES.resolve(None)[1]  # the default ENGINE reference
    assert speed is None  # natural pace


def test_each_engine_is_warmed_through_its_own_bindings() -> None:
    # The probe is capability-defined AND slot-aware: two engines hosted
    # in one process warm through their own voice maps, never a global
    # one. A shared map would warm one engine with the other's tokens.
    reference_engine, kokoro_engine = RecordingEngine(), RecordingEngine()
    catalog = VoiceCatalog()
    catalog.bind(reference_engine, REFERENCE_VOICES)
    catalog.bind(kokoro_engine, KOKORO_VOICES)

    warm_up = make_synthesis_warm_up(catalog)
    warm_up(reference_engine)
    warm_up(kokoro_engine)

    assert reference_engine.calls[0][1] == "tone:440"
    assert kokoro_engine.calls[0][1] == "af_heart"
