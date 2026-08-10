"""Audio probing and hashing for ingested clips.

Ingestion stores ORIGINAL bytes exactly as received (the same law the
platform applies to collected speech) and records what those bytes are.
Two containers are probed natively, header-only, stdlib-only:

- RIFF/WAVE — integer PCM (format 1) and IEEE float (format 3, what
  FLEURS parquet ships);
- FLAC — via the mandatory STREAMINFO block (what IndicVoices ships;
  the serving pipeline already decodes FLAC — the canonical `jfk-flac`
  evaluation clip exercises that path in production).

Anything else is refused rather than guessed, and every refusal is a
recorded problem.
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
    """The bytes are not a decodable WAV or FLAC file."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probe_audio(data: bytes) -> AudioProbe:
    """Sniff the container and probe it; refuse anything unrecognized."""
    if data[:4] == b"fLaC":
        return probe_flac(data)
    if data[:4] == b"RIFF":
        return probe_wav(data)
    raise UnreadableAudioError("unrecognized container (not RIFF/WAVE, not FLAC)")


def probe_flac(data: bytes) -> AudioProbe:
    """Read the mandatory STREAMINFO block (always the first metadata block).

    Layout after the 4-byte marker: 1 byte block header (last-flag +
    type, type 0 = STREAMINFO) + 3 bytes length, then 34 bytes:
    min/max block size (16+16), min/max frame size (24+24), then a
    packed field — sample rate (20 bits), channels-1 (3), bits-1 (5),
    total samples (36) — followed by the MD5.
    """
    if len(data) < 4 + 4 + 34:
        raise UnreadableAudioError("FLAC too short for a STREAMINFO block")
    block_type = data[4] & 0x7F
    (length,) = struct.unpack_from(">I", b"\x00" + data[5:8])
    if block_type != 0 or length < 34:
        raise UnreadableAudioError("FLAC does not start with a STREAMINFO block")
    info = data[8 : 8 + 34]
    sample_rate = (info[10] << 12) | (info[11] << 4) | (info[12] >> 4)
    channels = ((info[12] >> 1) & 0x07) + 1
    # 36-bit total_samples = low nibble of byte 13 (the high nibble is the
    # tail of bits-per-sample) followed by bytes 14-17.
    total_samples = ((info[13] & 0x0F) << 32) | int.from_bytes(info[14:18], "big")
    if sample_rate <= 0 or total_samples <= 0:
        raise UnreadableAudioError("FLAC STREAMINFO reports no audio")
    return AudioProbe(
        container="flac",
        duration_seconds=total_samples / sample_rate,
        sample_rate_hz=sample_rate,
        channels=channels,
        sha256=sha256_bytes(data),
    )


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
