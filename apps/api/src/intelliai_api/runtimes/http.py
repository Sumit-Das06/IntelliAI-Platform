"""HTTPRuntimeClient — the HTTP realization of the runtime contract.

Everything wire-specific lives HERE and only here: the binding constants
(multipart part names, header names, route), status handling, and payload
parsing. The constants mirror the runtime's `api/binding.py`; a dedicated
cross-pin test imports both sides and fails CI on any drift — one source
of truth per side, machine-checked equality between them.
"""

from collections.abc import AsyncIterator
from typing import Final

import httpx
import pydantic
import structlog

from intelliai_api.runtimes.client import RuntimeCallError, RuntimeUnavailableError
from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeResponse,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    TranscriptionRequest,
    TranscriptionResult,
)

logger = structlog.get_logger(__name__)

# HTTP binding of runtime-contract v1 (ADR-0016; cross-pinned by test).
HEADER_REQUEST_ID: Final = "X-Request-ID"
HEADER_CONTRACT_VERSION: Final = "X-Runtime-Contract-Version"
ROUTE_TRANSCRIBE: Final = "/v1/transcribe"
PART_FILE: Final = "file"
PART_PARAMS: Final = "params"

# Binary audio binding (ADR-0020; cross-pinned by test): WAV bytes as the
# body, the success envelope riding this header. Errors are always JSON.
ROUTE_SYNTHESIZE: Final = "/v1/synthesize"
HEADER_RUNTIME_ENVELOPE: Final = "X-Runtime-Envelope"


class HTTPRuntimeClient:
    """One pooled async client per runtime service, closed at app shutdown."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def transcribe(
        self, audio: bytes, request: TranscriptionRequest
    ) -> RuntimeResponse[TranscriptionResult]:
        headers = {}
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if isinstance(request_id, str):
            headers[HEADER_REQUEST_ID] = request_id  # correlation crosses planes
        try:
            response = await self._client.post(
                ROUTE_TRANSCRIBE,
                files={PART_FILE: ("audio", audio, "application/octet-stream")},
                data={PART_PARAMS: request.model_dump_json()},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.info("runtime_unreachable", detail=type(exc).__name__)
            raise RuntimeUnavailableError(str(exc)) from exc

        if response.status_code == 200:
            try:
                return RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            except pydantic.ValidationError as exc:
                logger.info("runtime_envelope_malformed")
                raise RuntimeUnavailableError("malformed runtime envelope") from exc
        try:
            error = RuntimeErrorResponse.model_validate_json(response.text)
        except pydantic.ValidationError as exc:
            logger.info("runtime_error_malformed", status=response.status_code)
            raise RuntimeUnavailableError("malformed runtime error") from exc
        raise RuntimeCallError(error)

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        headers = {}
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if isinstance(request_id, str):
            headers[HEADER_REQUEST_ID] = request_id  # correlation crosses planes
        try:
            response = await self._client.post(
                ROUTE_SYNTHESIZE,
                json=request.model_dump(mode="json"),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.info("runtime_unreachable", detail=type(exc).__name__)
            raise RuntimeUnavailableError(str(exc)) from exc

        if response.status_code == 200:
            envelope_header = response.headers.get(HEADER_RUNTIME_ENVELOPE)
            if envelope_header is None:
                logger.info("runtime_envelope_missing")
                raise RuntimeUnavailableError("missing runtime envelope")
            try:
                envelope = RuntimeResponse[SpeechSynthesisResult].model_validate_json(
                    envelope_header
                )
            except pydantic.ValidationError as exc:
                logger.info("runtime_envelope_malformed")
                raise RuntimeUnavailableError("malformed runtime envelope") from exc
            return response.content, envelope
        try:
            error = RuntimeErrorResponse.model_validate_json(response.text)
        except pydantic.ValidationError as exc:
            logger.info("runtime_error_malformed", status=response.status_code)
            raise RuntimeUnavailableError("malformed runtime error") from exc
        raise RuntimeCallError(error)

    async def synthesize_stream(
        self, request: SpeechSynthesisRequest
    ) -> tuple[AsyncIterator[bytes], RuntimeResponse[SpeechSynthesisResult]]:
        """The progressive form (M36): headers first, audio as it lands.

        The envelope arrives on the SAME header as whole-body — in
        streaming mode it carries pre-flight identity (voice, characters;
        duration 0.0 by contract, measured downstream from delivered
        bytes). Errors before the stream begins parse exactly like the
        whole-body path; a failure mid-stream surfaces as the byte
        iterator ending early (the caller decides what that means).
        """
        headers = {}
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if isinstance(request_id, str):
            headers[HEADER_REQUEST_ID] = request_id  # correlation crosses planes
        stream_request = self._client.build_request(
            "POST",
            ROUTE_SYNTHESIZE,
            json=request.model_dump(mode="json"),
            headers=headers,
        )
        try:
            response = await self._client.send(stream_request, stream=True)
        except httpx.HTTPError as exc:
            logger.info("runtime_unreachable", detail=type(exc).__name__)
            raise RuntimeUnavailableError(str(exc)) from exc

        if response.status_code != 200:
            body = await response.aread()
            await response.aclose()
            try:
                error = RuntimeErrorResponse.model_validate_json(body)
            except pydantic.ValidationError as exc:
                logger.info("runtime_error_malformed", status=response.status_code)
                raise RuntimeUnavailableError("malformed runtime error") from exc
            raise RuntimeCallError(error)

        envelope_header = response.headers.get(HEADER_RUNTIME_ENVELOPE)
        if envelope_header is None:
            await response.aclose()
            logger.info("runtime_envelope_missing")
            raise RuntimeUnavailableError("missing runtime envelope")
        try:
            envelope = RuntimeResponse[SpeechSynthesisResult].model_validate_json(envelope_header)
        except pydantic.ValidationError as exc:
            await response.aclose()
            logger.info("runtime_envelope_malformed")
            raise RuntimeUnavailableError("malformed runtime envelope") from exc

        async def body_iter() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        return body_iter(), envelope

    async def close(self) -> None:
        await self._client.aclose()
