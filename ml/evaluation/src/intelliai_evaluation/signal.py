"""Signal sanity — what the WAV itself proves, stdlib-only and deterministic.

Catches catastrophic generation failures (clipped output, dead air,
digital silence, runaway or truncated duration) without any model in the
loop. Thresholds are frozen constants: changing one changes the metric,
which means a NEW metric name — never a silent edit.
"""

from __future__ import annotations

import io
import wave
from array import array
from dataclasses import dataclass
from typing import Final

CLIP_THRESHOLD: Final = 32700  # |sample| at or beyond ≈ digital full scale
SILENCE_RMS_FLOOR: Final = 330.0  # ~1% of int16 full scale (matches runtime VAD floor)
FRAME_SECONDS: Final = 0.03
# Plausible speaking-rate band, non-space characters per second, generous
# across languages and scripts. A coarse gate by design (confidence: medium).
MIN_CHARS_PER_SECOND: Final = 4.0
MAX_CHARS_PER_SECOND: Final = 40.0


@dataclass(frozen=True)
class SignalAnalysis:
    """Deterministic facts about one generated waveform."""

    duration_seconds: float
    sample_rate_hz: int
    clipping_ratio: float
    silence_ratio: float
    is_digital_silence: bool


def analyze_wav(wav_bytes: bytes) -> SignalAnalysis:
    """Decode a 16-bit PCM WAV and measure its signal-sanity facts."""
    with wave.open(io.BytesIO(wav_bytes)) as reader:
        if reader.getsampwidth() != 2:
            msg = "signal analysis expects 16-bit PCM WAV"
            raise ValueError(msg)
        sample_rate = reader.getframerate()
        frames = reader.readframes(reader.getnframes())

    samples = array("h")
    samples.frombytes(frames[: len(frames) - (len(frames) % 2)])
    if not samples or sample_rate <= 0:
        return SignalAnalysis(
            duration_seconds=0.0,
            sample_rate_hz=max(sample_rate, 0),
            clipping_ratio=0.0,
            silence_ratio=1.0,
            is_digital_silence=True,
        )

    duration = len(samples) / sample_rate
    clipped = sum(1 for sample in samples if abs(sample) >= CLIP_THRESHOLD)

    frame_length = max(1, int(sample_rate * FRAME_SECONDS))
    silent_frames = 0
    frame_count = 0
    for start in range(0, len(samples), frame_length):
        frame = samples[start : start + frame_length]
        frame_count += 1
        mean_square = sum(sample * sample for sample in frame) / len(frame)
        if mean_square**0.5 < SILENCE_RMS_FLOOR:
            silent_frames += 1

    return SignalAnalysis(
        duration_seconds=duration,
        sample_rate_hz=sample_rate,
        clipping_ratio=clipped / len(samples),
        silence_ratio=silent_frames / frame_count,
        is_digital_silence=all(sample == 0 for sample in samples),
    )


def duration_plausibility(text: str, duration_seconds: float) -> float:
    """1.0 when the speaking rate is humanly plausible for the text, else 0.0.

    Deliberately binary: a coarse gate against runaway/truncated synthesis,
    not a quality score (SPEECH_EVALUATION.md: confidence medium)."""
    speakable = len("".join(text.split()))
    if speakable == 0 or duration_seconds <= 0:
        return 0.0
    chars_per_second = speakable / duration_seconds
    return 1.0 if MIN_CHARS_PER_SECOND <= chars_per_second <= MAX_CHARS_PER_SECOND else 0.0
