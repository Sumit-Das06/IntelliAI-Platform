"""Media detection — magic bytes, never file extensions or client claims.

A whitelist, deliberately: only containers we recognize reach the decoder
subprocess. Unrecognized bytes are refused here, cheaply, before any
external process sees them. Extending support = adding a signature +
tests, one place.
"""

from enum import StrEnum, unique

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError


@unique
class MediaFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"
    OGG = "ogg"  # ogg/opus/vorbis
    WEBM = "webm"  # webm/matroska
    MP4 = "mp4"  # mp4/m4a


def detect_format(payload: bytes) -> MediaFormat:
    """Identify the container from its leading bytes, or refuse."""
    if payload[:4] == b"RIFF" and payload[8:12] == b"WAVE":
        return MediaFormat.WAV
    if payload[:4] == b"fLaC":
        return MediaFormat.FLAC
    if payload[:3] == b"ID3" or (
        len(payload) >= 2 and payload[0] == 0xFF and (payload[1] & 0xE0) == 0xE0
    ):
        return MediaFormat.MP3
    if payload[:4] == b"OggS":
        return MediaFormat.OGG
    if payload[:4] == b"\x1a\x45\xdf\xa3":
        return MediaFormat.WEBM
    if len(payload) >= 12 and payload[4:8] == b"ftyp":
        return MediaFormat.MP4
    supported = ", ".join(sorted(member.value for member in MediaFormat))
    raise RuntimeServiceError(
        RuntimeErrorType.INVALID_INPUT,
        f"unrecognized audio format; supported containers: {supported}",
        param="file",
    )
