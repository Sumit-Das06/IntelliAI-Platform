"""RuntimeClient seam: HTTP implementation and binding consistency."""

import json

import httpx
import pytest
import structlog

from intelliai_api.runtimes import RuntimeCallError, RuntimeUnavailableError
from intelliai_api.runtimes import http as gateway_binding
from intelliai_api.runtimes.http import HTTPRuntimeClient
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionRequest,
    TranscriptionResult,
    Usage,
    UsageUnit,
)

pytestmark = pytest.mark.anyio

META = RuntimeMetadata(
    service="stt-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
)


def envelope_json(text: str = "hello") -> str:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(text=text, language="en", duration_seconds=1.0),
        model="whisper-small",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=1.0),),
        timing=RuntimeTiming(total_ms=10.0, stages={"inference": 8.0}),
        runtime=META,
    ).model_dump_json()


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, status: int, body: str) -> None:
        self.requests: list[httpx.Request] = []
        self._status = status
        self._body = body

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        await request.aread()
        return httpx.Response(self._status, content=self._body)


def make_client(transport: httpx.AsyncBaseTransport) -> HTTPRuntimeClient:
    return HTTPRuntimeClient(
        base_url="http://runtime.test",
        timeout_seconds=5,
        client=httpx.AsyncClient(transport=transport, base_url="http://runtime.test"),
    )


async def test_success_returns_parsed_envelope_and_sends_artifact() -> None:
    transport = RecordingTransport(200, envelope_json("ask not"))
    client = make_client(transport)
    envelope = await client.transcribe(
        b"audio-bytes", TranscriptionRequest(language="en", model="whisper-small")
    )
    assert envelope.output.text == "ask not"
    assert envelope.model == "whisper-small"
    body = transport.requests[0].content.decode("utf-8", errors="replace")
    assert '"model":"whisper-small"' in body.replace(" ", "")
    await client.close()


async def test_request_id_propagates_across_planes() -> None:
    transport = RecordingTransport(200, envelope_json())
    client = make_client(transport)
    structlog.contextvars.bind_contextvars(request_id="req_crossplane")
    try:
        await client.transcribe(b"x", TranscriptionRequest())
    finally:
        structlog.contextvars.clear_contextvars()
    assert transport.requests[0].headers[gateway_binding.HEADER_REQUEST_ID] == "req_crossplane"
    await client.close()


async def test_runtime_error_becomes_typed_call_error() -> None:
    error_body = RuntimeErrorResponse(
        type=RuntimeErrorType.INVALID_INPUT,
        message="audio file is empty",
        param="file",
        runtime=META,
    ).model_dump_json()
    client = make_client(RecordingTransport(400, error_body))
    with pytest.raises(RuntimeCallError) as exc_info:
        await client.transcribe(b"", TranscriptionRequest())
    assert exc_info.value.error.type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.error.param == "file"
    await client.close()


async def test_transport_failure_is_unavailable() -> None:
    class ExplodingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    client = make_client(ExplodingTransport())
    with pytest.raises(RuntimeUnavailableError):
        await client.transcribe(b"x", TranscriptionRequest())
    await client.close()


async def test_malformed_bodies_are_unavailable_never_crashes() -> None:
    for status, body in ((200, "not json"), (500, "<html>gateway timeout</html>")):
        client = make_client(RecordingTransport(status, body))
        with pytest.raises(RuntimeUnavailableError):
            await client.transcribe(b"x", TranscriptionRequest())
        await client.close()


def test_binding_constants_match_the_runtime_exactly() -> None:
    """CI-enforced cross-pin (deferred decision from steps 1/3, resolved):
    each side owns its constants; THIS TEST is the single source of truth
    for their equality. Test-only import of the runtime service package —
    production gateway code never imports it."""
    from intelliai_stt_runtime.api import binding as runtime_binding

    assert gateway_binding.HEADER_REQUEST_ID == runtime_binding.HEADER_REQUEST_ID
    assert gateway_binding.HEADER_CONTRACT_VERSION == runtime_binding.HEADER_CONTRACT_VERSION
    assert gateway_binding.ROUTE_TRANSCRIBE == runtime_binding.ROUTE_TRANSCRIBE
    assert gateway_binding.PART_FILE == runtime_binding.PART_FILE
    assert gateway_binding.PART_PARAMS == runtime_binding.PART_PARAMS


def test_params_part_is_valid_contract_json() -> None:
    request = TranscriptionRequest(language="hi", model="whisper-small")
    parsed = json.loads(request.model_dump_json())
    assert parsed["language"] == "hi"
    assert parsed["model"] == "whisper-small"
