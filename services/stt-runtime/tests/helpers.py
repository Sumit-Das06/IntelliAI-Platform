"""Deterministic in-memory WAV builders (stdlib, mirrors the eval seed)."""

import io
import math
import struct
import wave


def wav_bytes(
    *,
    duration_seconds: float = 0.5,
    sample_rate_hz: int = 16000,
    tone_hz: float | None = 440.0,
) -> bytes:
    """A 16-bit mono WAV: a sine tone, or digital silence when tone_hz=None."""
    frame_count = int(duration_seconds * sample_rate_hz)
    if tone_hz is None:
        pcm = b"\x00\x00" * frame_count
    else:
        amplitude = int(0.3 * 32767)
        pcm = b"".join(
            struct.pack(
                "<h",
                int(amplitude * math.sin(2 * math.pi * tone_hz * i / sample_rate_hz)),
            )
            for i in range(frame_count)
        )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate_hz)
        writer.writeframes(pcm)
    return buffer.getvalue()
