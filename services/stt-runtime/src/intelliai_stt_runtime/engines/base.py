"""The engine seam: what every foundation-model adapter must look like."""

from typing import Protocol

from intelliai_runtime_contract import TranscriptionRequest, TranscriptionResult
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

    def close(self) -> None:
        """Release the loaded model. Called once, by the ModelManager."""
        ...
