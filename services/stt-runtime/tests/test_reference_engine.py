"""ReferenceEngine: deterministic, contract-honest, thin.

Engines receive canonical DecodedAudio directly — no pipeline, no ffmpeg:
engine tests must prove the engine, not the ingestion.
"""

from helpers import make_audio
from intelliai_runtime_contract import TranscriptionRequest
from intelliai_stt_runtime.engines.reference import ReferenceEngine

ENGINE = ReferenceEngine()


def test_silence_transcribes_to_nothing() -> None:
    audio = make_audio(duration_seconds=1.0, tone_hz=None)
    result = ENGINE.transcribe(audio, TranscriptionRequest())
    assert result.text == ""
    assert result.segments == ()
    assert result.language == "zxx"  # no linguistic content
    assert result.duration_seconds == 1.0


def test_deterministic_across_calls() -> None:
    audio = make_audio(duration_seconds=0.25)
    first = ENGINE.transcribe(audio, TranscriptionRequest())
    second = ENGINE.transcribe(audio, TranscriptionRequest())
    assert first == second
    assert first.text != ""


def test_different_audio_produces_different_text() -> None:
    request = TranscriptionRequest()
    a = ENGINE.transcribe(make_audio(tone_hz=440.0), request)
    b = ENGINE.transcribe(make_audio(tone_hz=880.0), request)
    assert a.text != b.text


def test_language_hint_is_respected() -> None:
    result = ENGINE.transcribe(make_audio(), TranscriptionRequest(language="hi"))
    assert result.language == "hi"


def test_segments_cover_the_audio() -> None:
    audio = make_audio(duration_seconds=0.5)
    result = ENGINE.transcribe(audio, TranscriptionRequest())
    (segment,) = result.segments
    assert segment.start_seconds == 0.0
    assert segment.end_seconds == audio.duration_seconds
    assert segment.text == result.text
