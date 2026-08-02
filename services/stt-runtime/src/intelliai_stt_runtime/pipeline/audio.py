"""Canonical audio — the one representation every engine receives.

16 kHz, mono, 16-bit signed little-endian PCM. Every supported input
format converges here BEFORE inference, so engines never learn what a
container or codec is, and swapping an engine never changes ingestion.
"""

from dataclasses import dataclass
from typing import Final

CANONICAL_SAMPLE_RATE_HZ: Final = 16_000
CANONICAL_CHANNELS: Final = 1
CANONICAL_SAMPLE_WIDTH_BYTES: Final = 2


@dataclass(frozen=True)
class DecodedAudio:
    """Normalized PCM plus the facts about it. What engines are written against."""

    pcm: bytes
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    duration_seconds: float

    @property
    def is_silence(self) -> bool:
        """True when every sample is digital zero."""
        return not self.pcm or all(byte == 0 for byte in self.pcm)


def canonical_audio(pcm: bytes) -> DecodedAudio:
    """Wrap canonical-format PCM with its derived facts."""
    frame_count = len(pcm) // CANONICAL_SAMPLE_WIDTH_BYTES
    return DecodedAudio(
        pcm=pcm,
        sample_rate_hz=CANONICAL_SAMPLE_RATE_HZ,
        channels=CANONICAL_CHANNELS,
        sample_width_bytes=CANONICAL_SAMPLE_WIDTH_BYTES,
        duration_seconds=frame_count / CANONICAL_SAMPLE_RATE_HZ,
    )
