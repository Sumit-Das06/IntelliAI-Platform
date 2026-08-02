"""HTTPRuntimeClient — the HTTP realization of the runtime contract.

Everything wire-specific lives HERE and only here: the binding constants
(multipart part names, header names, route), status handling, and payload
parsing. The constants mirror the runtime's `api/binding.py`; a dedicated
cross-pin test imports both sides and fails CI on any drift — one source
of truth per side, machine-checked equality between them.
"""

from typing import Final

import httpx
import pydantic
import structlog

from intelliai_api.runtimes.client import RuntimeCallError, RuntimeUnavailableError
from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeResponse,
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

    async def close(self) -> None:
        await self._client.aclose()
