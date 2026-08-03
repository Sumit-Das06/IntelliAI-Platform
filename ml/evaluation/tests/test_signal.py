"""Signal sanity metrics over synthetic, deterministic waveforms."""

import io
import math
import struct
import wave

import pytest

from intelliai_evaluation.signal import analyze_wav, duration_plausibility

RATE = 16000


def wav_of(pcm: bytes, rate: int = RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(pcm)
    return buffer.getvalue()


def tone(seconds: float, amplitude: float = 0.3, hz: float = 440.0) -> bytes:
    peak = int(amplitude * 32767)
    return b"".join(
        struct.pack("<h", int(peak * math.sin(2 * math.pi * hz * i / RATE)))
        for i in range(int(seconds * RATE))
    )


class TestAnalyzeWav:
    def test_clean_tone_is_clean(self) -> None:
        analysis = analyze_wav(wav_of(tone(1.0)))
        assert analysis.clipping_ratio == 0.0
        assert analysis.silence_ratio == 0.0
        assert analysis.is_digital_silence is False
        assert abs(analysis.duration_seconds - 1.0) < 0.01

    def test_clipped_audio_is_measured(self) -> None:
        # Overdriven sine (1.8x full scale, pinned at the rails): the
        # waveform a broken vocoder actually produces.
        overdriven = b"".join(
            struct.pack(
                "<h",
                max(-32768, min(32767, int(1.8 * 32767 * math.sin(2 * math.pi * 440 * i / RATE)))),
            )
            for i in range(RATE // 2)
        )
        analysis = analyze_wav(wav_of(overdriven))
        assert analysis.clipping_ratio > 0.3

    def test_full_scale_sine_barely_clips(self) -> None:
        # A loud-but-honest sine only grazes the threshold at its peaks —
        # the metric distinguishes loud from broken.
        analysis = analyze_wav(wav_of(tone(0.5, amplitude=1.0)))
        assert 0.0 < analysis.clipping_ratio < 0.1

    def test_digital_silence(self) -> None:
        analysis = analyze_wav(wav_of(b"\x00\x00" * RATE))
        assert analysis.is_digital_silence is True
        assert analysis.silence_ratio == 1.0

    def test_half_silence_half_tone(self) -> None:
        analysis = analyze_wav(wav_of(b"\x00\x00" * RATE + tone(1.0)))
        assert 0.4 <= analysis.silence_ratio <= 0.6

    def test_empty_wav_is_total_silence(self) -> None:
        analysis = analyze_wav(wav_of(b""))
        assert analysis.is_digital_silence is True
        assert analysis.duration_seconds == 0.0

    def test_non_16bit_refused(self) -> None:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(1)
            writer.setframerate(RATE)
            writer.writeframes(b"\x80" * RATE)
        with pytest.raises(ValueError, match="16-bit"):
            analyze_wav(buffer.getvalue())

    def test_deterministic(self) -> None:
        payload = wav_of(tone(0.7))
        assert analyze_wav(payload) == analyze_wav(payload)


class TestDurationPlausibility:
    def test_plausible_rate_scores_one(self) -> None:
        # 40 speakable chars in 3 seconds ≈ 13 chars/sec: human.
        text = "this sentence has about forty characters"
        assert duration_plausibility(text, 3.0) == 1.0

    def test_runaway_and_truncated_score_zero(self) -> None:
        text = "short text"
        assert duration_plausibility(text, 60.0) == 0.0  # 60s for 9 chars
        assert duration_plausibility("a very long paragraph " * 20, 0.5) == 0.0

    def test_degenerate_inputs_score_zero(self) -> None:
        assert duration_plausibility("", 1.0) == 0.0
        assert duration_plausibility("text", 0.0) == 0.0
