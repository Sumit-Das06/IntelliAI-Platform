"""The engine seam: what every foundation-model adapter must look like."""

from typing import Protocol

from intelliai_runtime_contract import TranscriptionRequest, TranscriptionResult
from intelliai_runtime_core import EngineDescription
from intelliai_stt_runtime.pipeline import DecodedAudio


class TranscriptionEngine(Protocol):
    """A loaded model behind a uniform face.

    ``transcribe`` is synchronous and may block — callers run it on the
    worker pool, never on the event loop. Implementations must be safe to
    call concurrently from pool threads (the loaded model is their only
    state, and it is read-only after load).
    """

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        """Turn decoded audio into a contract result. Pure computation."""
        ...

    def describe(self) -> EngineDescription:
        """State how this engine is configured to decode.

        Part of the seam because only the adapter knows: the build it was
        loaded under, what granularity it emits, and the decode
        configuration actually in force — including the values its library
        chose that nobody passed. A harness measuring this runtime over
        HTTP cannot see any of it, and a benchmark that had to be *told*
        would be recording an operator's memory rather than the system.

        Must be constant for the engine's lifetime. Anything that varies
        per request belongs in the response, not here.
        """
        ...

    def close(self) -> None:
        """Release the loaded model. Called once, by the ModelManager."""
        ...
