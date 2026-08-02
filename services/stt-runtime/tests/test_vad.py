"""EnergyVad: deterministic speech-activity facts over canonical audio."""

from helpers import make_audio, pcm_bytes
from intelliai_stt_runtime.pipeline import EnergyVad, canonical_audio

VAD = EnergyVad()


def test_digital_silence_has_no_speech() -> None:
    analysis = VAD.analyze(make_audio(duration_seconds=2.0, tone_hz=None))
    assert analysis.has_speech is False
    assert analysis.speech_seconds == 0.0
    assert analysis.regions == ()
    assert analysis.speech_ratio == 0.0


def test_tone_counts_as_activity() -> None:
    # Erring toward "speech": energy present -> the engine decides.
    analysis = VAD.analyze(make_audio(duration_seconds=1.0, tone_hz=440.0))
    assert analysis.has_speech is True
    assert analysis.speech_seconds > 0.9


def test_activity_regions_are_located_in_time() -> None:
    silence = pcm_bytes(duration_seconds=1.0, tone_hz=None)
    tone = pcm_bytes(duration_seconds=1.0, tone_hz=440.0)
    analysis = VAD.analyze(canonical_audio(silence + tone + silence))
    assert analysis.has_speech is True
    (region,) = analysis.regions
    assert 0.8 <= region.start_seconds <= 1.2
    assert 1.8 <= region.end_seconds <= 2.2
    assert 0.25 <= analysis.speech_ratio <= 0.45


def test_faint_hum_stays_below_the_absolute_floor() -> None:
    # Scale a tone to ~0.3% of full scale: audible artifact, not speech.
    loud = pcm_bytes(duration_seconds=1.0, tone_hz=50.0)
    scaled = bytearray()
    for i in range(0, len(loud), 2):
        value = int.from_bytes(loud[i : i + 2], "little", signed=True)
        scaled += (value // 100).to_bytes(2, "little", signed=True)
    analysis = VAD.analyze(canonical_audio(bytes(scaled)))
    assert analysis.has_speech is False


def test_deterministic() -> None:
    audio = make_audio(duration_seconds=1.5)
    assert VAD.analyze(audio) == VAD.analyze(audio)


def test_empty_audio() -> None:
    analysis = VAD.analyze(canonical_audio(b""))
    assert analysis.has_speech is False
    assert analysis.total_seconds == 0.0
