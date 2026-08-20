"""The engine seam: what every synthesis adapter must look like."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SynthesizedAudio:
    """Canonical engine output: mono 16-bit signed little-endian PCM plus
    its rate. Engines produce PCM and facts; containerization (WAV) is the
    HTTP binding's job — the mirror image of 'engines never see MP3s'."""

    pcm: bytes
    sample_rate_hz: int
    #: Milliseconds from synthesize() start until the FIRST audio chunk
    #: existed (M35). Operational telemetry for the streaming decision:
    #: it measures what a chunked transport COULD deliver while the HTTP
    #: response stays whole-body. None when an engine renders in one shot.
    first_chunk_ms: float | None = None

    @property
    def duration_seconds(self) -> float:
        return (len(self.pcm) // 2) / self.sample_rate_hz


class SynthesisEngine(Protocol):
    """A loaded model behind a uniform face.

    ``synthesize`` is synchronous and may block — callers run it on the
    worker pool, never on the event loop. Implementations must be safe to
    call concurrently from pool threads (the loaded model is their only
    state, and it is read-only after load). ``voice`` is an ENGINE voice
    reference, already resolved from the public id — engines never see
    public identities.
    """

    def synthesize(self, text: str, voice: str, speed: float | None) -> SynthesizedAudio:
        """Turn canonical text into canonical PCM. Pure computation."""
        ...

    def close(self) -> None:
        """Release the loaded model. Called once, by the ModelManager."""
        ...
