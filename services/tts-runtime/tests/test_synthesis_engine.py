"""ReferenceSynthesisEngine: deterministic, text/voice/speed-dependent."""

from intelliai_tts_runtime.engines.reference import SAMPLE_RATE_HZ, ReferenceSynthesisEngine

ALTO = "tone:440"
BASS = "tone:220"


def test_same_input_same_bytes_forever() -> None:
    first = ReferenceSynthesisEngine().synthesize("hello world", ALTO, None)
    second = ReferenceSynthesisEngine().synthesize("hello world", ALTO, None)
    assert first.pcm == second.pcm  # determinism across instances
    assert first.sample_rate_hz == SAMPLE_RATE_HZ


def test_text_changes_the_audio() -> None:
    engine = ReferenceSynthesisEngine()
    assert engine.synthesize("hello", ALTO, None).pcm != engine.synthesize("world", ALTO, None).pcm


def test_voice_changes_the_audio() -> None:
    engine = ReferenceSynthesisEngine()
    assert engine.synthesize("hello", ALTO, None).pcm != engine.synthesize("hello", BASS, None).pcm


def test_duration_is_proportional_to_text_length() -> None:
    engine = ReferenceSynthesisEngine()
    short = engine.synthesize("ab", ALTO, None)
    long = engine.synthesize("abcd", ALTO, None)
    assert long.duration_seconds == 2 * short.duration_seconds
    assert short.duration_seconds > 0


def test_speed_scales_duration_inversely() -> None:
    engine = ReferenceSynthesisEngine()
    natural = engine.synthesize("hello", ALTO, None)
    double = engine.synthesize("hello", ALTO, 2.0)
    assert double.duration_seconds == natural.duration_seconds / 2


def test_pcm_is_canonical_16_bit_mono() -> None:
    audio = ReferenceSynthesisEngine().synthesize("x", ALTO, None)
    assert len(audio.pcm) % 2 == 0  # whole 16-bit samples
    assert audio.duration_seconds == (len(audio.pcm) // 2) / SAMPLE_RATE_HZ
