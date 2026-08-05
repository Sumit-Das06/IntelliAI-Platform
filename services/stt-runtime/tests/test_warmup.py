"""The STT warm-up probe — the capability content of startup.

The lifecycle machinery (runtime-core) guarantees the probe runs exactly
once per engine before serving; those guarantees are pinned in the
runtime-core suite. THIS test pins what probing MEANS for transcription:
one default-parameter inference over deterministic canonical audio.
"""

from intelliai_runtime_contract import TranscriptionRequest, TranscriptionResult
from intelliai_runtime_core import EngineDescription
from intelliai_stt_runtime.main import transcription_warm_up
from intelliai_stt_runtime.pipeline import DecodedAudio


class RecordingEngine:
    def __init__(self) -> None:
        self.audio: list[DecodedAudio] = []
        self.requests: list[TranscriptionRequest] = []

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        self.audio.append(audio)
        self.requests.append(request)
        return TranscriptionResult(text="", language="und", duration_seconds=audio.duration_seconds)

    def describe(self) -> EngineDescription:
        # Part of the seam now: an engine that cannot say how it decodes
        # cannot be measured, so a double that omits it is not a stand-in
        # for one.
        return EngineDescription(compute_type="recording", emitted_unit="word")

    def close(self) -> None:
        return None


def test_probe_is_one_default_inference_over_canonical_nonsilent_audio() -> None:
    engine = RecordingEngine()
    transcription_warm_up(engine)
    assert len(engine.audio) == 1
    audio = engine.audio[0]
    assert audio.sample_rate_hz == 16_000  # canonical format, exactly
    assert audio.channels == 1
    assert audio.sample_width_bytes == 2
    assert audio.duration_seconds == 0.5
    # Real non-silence: the probe pushes a model through its full
    # encode/decode path, not through a silence short-circuit.
    assert not audio.is_silence
    assert engine.requests == [TranscriptionRequest()]
