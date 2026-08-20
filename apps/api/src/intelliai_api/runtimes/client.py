"""The transport-agnostic seam between gateway and runtimes.

The Protocol speaks ONLY contract vocabulary: bytes in, envelope out,
contract-shaped failures. No URLs, no headers, no status codes — an HTTP
client, a gRPC client, and an in-process runtime can all implement it
without the Protocol changing. M8 streaming arrives as an ADDITIVE method
(e.g. a stream variant yielding incremental results), never by mutating
`transcribe` — the same append-only discipline as the contract itself.
"""

from collections.abc import AsyncIterator
from typing import Protocol

from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeResponse,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
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

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        """Send synthesis params, return (audio bytes, contract envelope).

        The audio travels as transport payload and the envelope as
        operational metadata (ADR-0020) — this seam returns both without
        knowing how they traveled. Added ADDITIVELY (the module's own
        evolution rule); same failure vocabulary as `transcribe`."""
        ...

    async def synthesize_stream(
        self, request: SpeechSynthesisRequest
    ) -> tuple[AsyncIterator[bytes], RuntimeResponse[SpeechSynthesisResult]]:
        """The progressive form (M36, additive): the envelope up front
        (pre-flight identity; duration 0.0 by contract), then audio bytes
        as the runtime produces them. Pre-stream failures raise exactly
        like `synthesize`; a mid-stream failure ends the iterator early.
        The caller MUST exhaust or close the iterator."""
        ...

    async def close(self) -> None:
        """Release transport resources. Called once, at app shutdown."""
        ...
