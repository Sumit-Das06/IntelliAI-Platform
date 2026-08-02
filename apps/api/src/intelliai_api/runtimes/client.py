"""The transport-agnostic seam between gateway and runtimes.

The Protocol speaks ONLY contract vocabulary: bytes in, envelope out,
contract-shaped failures. No URLs, no headers, no status codes — an HTTP
client, a gRPC client, and an in-process runtime can all implement it
without the Protocol changing. M8 streaming arrives as an ADDITIVE method
(e.g. a stream variant yielding incremental results), never by mutating
`transcribe` — the same append-only discipline as the contract itself.
"""

from typing import Protocol

from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeResponse,
    TranscriptionRequest,
    TranscriptionResult,
)


class RuntimeCallError(Exception):
    """The runtime answered, with a contract-shaped failure.

    Carries the full `RuntimeErrorResponse`; translating it into the
    public error contract is the caller's job (gateway policy), never
    this layer's."""

    def __init__(self, error: RuntimeErrorResponse) -> None:
        super().__init__(f"runtime error: {error.type}")
        self.error = error


class RuntimeUnavailableError(Exception):
    """The runtime could not be reached or spoke unintelligibly.

    Transport failure, timeout, or a malformed envelope — from the
    gateway's perspective all the same fact: no trustworthy answer."""


class RuntimeClient(Protocol):
    """What every runtime transport must provide."""

    async def transcribe(
        self, audio: bytes, request: TranscriptionRequest
    ) -> RuntimeResponse[TranscriptionResult]:
        """Send audio + params, return the contract envelope.

        Raises RuntimeCallError (runtime said no) or
        RuntimeUnavailableError (no answer at all)."""
        ...

    async def close(self) -> None:
        """Release transport resources. Called once, at app shutdown."""
        ...
