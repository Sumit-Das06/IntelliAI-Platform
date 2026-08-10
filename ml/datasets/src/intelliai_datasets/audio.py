"""Audio probing and hashing for ingested clips.

Ingestion stores ORIGINAL bytes exactly as received (the same law the
platform applies to collected speech) and records what those bytes are.
The probe is a minimal RIFF/WAVE header reader: integer PCM (format 1)
and IEEE float (format 3, what FLEURS parquet ships) are accepted —
anything else is refused rather than guessed. The serving pipeline's
ffmpeg canonicalizes either encoding identically.
"""

from __future__ import annotations

import hashlib
import struct

from pydantic import BaseModel, ConfigDict

_PCM = 1
_IEEE_FLOAT = 3
_EXTENSIBLE = 0xFFFE
_ACCEPTED_FORMATS = {_PCM, _IEEE_FLOAT}


class AudioProbe(BaseModel):
    """What the bytes actually are — measured, never assumed."""

    model_config = ConfigDict(frozen=True)

    container: str  # "wav" is the only accepted container today
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    sha256: str


class UnreadableAudioError(RuntimeError):
    """The bytes are not a decodable PCM/float WAV file."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probe_wav(data: bytes) -> AudioProbe:
    """Probe WAV bytes (PCM or IEEE float); refuse anything else."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise UnreadableAudioError("not a RIFF/WAVE container")

    fmt: tuple[int, int, int, int] | None = None  # format, channels, rate, bits
    data_size: int | None = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (chunk_size,) = struct.unpack_from("<I", data, offset + 4)
        body = offset + 8
        if chunk_id == b"fmt " and chunk_size >= 16:
            audio_format, channels, rate = struct.unpack_from("<HHI", data, body)
            (bits,) = struct.unpack_from("<H", data, body + 14)
            if audio_format == _EXTENSIBLE and chunk_size >= 40:
                # WAVE_FORMAT_EXTENSIBLE: the real format is the first two
                # bytes of the SubFormat GUID at offset 24 of the chunk.
                (audio_format,) = struct.unpack_from("<H", data, body + 24)
            fmt = (audio_format, channels, rate, bits)
        elif chunk_id == b"data":
            data_size = min(chunk_size, len(data) - body)
        # Chunks are word-aligned: odd sizes carry a pad byte.
        offset = body + chunk_size + (chunk_size & 1)

    if fmt is None or data_size is None:
        raise UnreadableAudioError("missing fmt or data chunk")
    audio_format, channels, rate, bits = fmt
    if audio_format not in _ACCEPTED_FORMATS:
        msg = f"unsupported WAV format code {audio_format} (accepted: PCM=1, IEEE float=3)"
        raise UnreadableAudioError(msg)
    if channels <= 0 or rate <= 0 or bits <= 0:
        raise UnreadableAudioError("WAV fmt chunk reports impossible geometry")
    bytes_per_frame = channels * (bits // 8)
    if bytes_per_frame == 0 or data_size < bytes_per_frame:
        raise UnreadableAudioError("WAV data chunk holds no complete frame")

    return AudioProbe(
        container="wav",
        duration_seconds=data_size / (rate * bytes_per_frame),
        sample_rate_hz=rate,
        channels=channels,
        sha256=sha256_bytes(data),
    )
