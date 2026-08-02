"""Deterministic audio builders: raw canonical PCM and WAV containers."""

import io
import math
import struct
import wave

from intelliai_stt_runtime.pipeline import DecodedAudio, canonical_audio

SAMPLE_RATE_HZ = 16000


def pcm_bytes(
    *,
    duration_seconds: float = 0.5,
    tone_hz: float | None = 440.0,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> bytes:
    """16-bit mono PCM: a sine tone, or digital silence when tone_hz=None."""
    frame_count = int(duration_seconds * sample_rate_hz)
    if tone_hz is None:
        return b"\x00\x00" * frame_count
    amplitude = int(0.3 * 32767)
    return b"".join(
        struct.pack(
            "<h",
            int(amplitude * math.sin(2 * math.pi * tone_hz * i / sample_rate_hz)),
        )
        for i in range(frame_count)
    )


def make_audio(*, duration_seconds: float = 0.5, tone_hz: float | None = 440.0) -> DecodedAudio:
    """Canonical DecodedAudio without touching the pipeline (engine tests)."""
    return canonical_audio(pcm_bytes(duration_seconds=duration_seconds, tone_hz=tone_hz))


def wav_bytes(
    *,
    duration_seconds: float = 0.5,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    channels: int = 1,
    tone_hz: float | None = 440.0,
) -> bytes:
    """A WAV container around deterministic PCM (HTTP/pipeline tests)."""
    mono = pcm_bytes(
        duration_seconds=duration_seconds, tone_hz=tone_hz, sample_rate_hz=sample_rate_hz
    )
    if channels == 1:
        pcm = mono
    else:
        frames = [mono[i : i + 2] for i in range(0, len(mono), 2)]
        pcm = b"".join(frame * channels for frame in frames)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate_hz)
        writer.writeframes(pcm)
    return buffer.getvalue()
