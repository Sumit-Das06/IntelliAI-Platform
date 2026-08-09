"""Request-scoped middleware: correlation ID, access logging, body ceiling.

The request ID minted here is the platform-wide correlation ID: bound to the
logging context for every line emitted while handling the request, returned
to the client in ``X-Request-ID``, and (from M2) propagated on outbound calls
to inference services so one ID traces a request across every process it
touches.
"""

import json
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_CLIENT_ID_LENGTH = 128

logger = structlog.get_logger("intelliai_api.access")


class RequestBodySizeLimitMiddleware:
    """Refuse request bodies over the transport ceiling — at READ time.

    Pure ASGI on purpose: the guard wraps ``receive`` so the limit is
    enforced exactly where the risk lives (the gateway buffering bytes
    into memory), not at routing time. A request whose handler never
    reads its body costs no memory and needs no refusal.

    Two lanes, one verdict:

    - a declared ``Content-Length`` over the cap is refused before the
      wrapped app runs at all — the honest majority case, free;
    - a chunked/streamed body is cut off the moment the running total
      crosses the cap: the middleware sends the refusal itself and then
      hands the app an ``http.disconnect``, discarding whatever late
      response the app still tries to write.

    The refusal is rendered HERE, not raised through the app, by
    necessity: FastAPI wraps form parsing in a catch-all that would
    translate any exception from ``receive`` into a generic 400,
    silently losing the 413 contract. Like ``/health``, this is a
    documented exception to "all envelopes come from the four error
    handlers" — the envelope shape is byte-compatible, and the request
    id comes from the same scope state the handlers read.

    Innermost middleware by design (added FIRST in the factory): the
    outer context middleware has already stamped the request id, and the
    refusal travels back through it to pick up ``X-Request-ID`` exactly
    like every other response.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        declared: int | None = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
                break

        limit = self._max_bytes
        if declared is not None and declared > limit:
            await self._refuse(scope, send, declared=declared)
            return

        received = 0
        refused = False
        response_started = False

        async def guarded_receive() -> Message:
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request" and not refused:
                received += len(message.get("body", b""))
                if received > limit:
                    refused = True
                    if not response_started:
                        await self._refuse(scope, send, declared=None)
                    # The app sees a disconnect and aborts its read; its
                    # late response, if any, is discarded below.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if refused:
                return  # the 413 is already on the wire
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self._app(scope, guarded_receive, guarded_send)

    async def _refuse(self, scope: Scope, send: Send, *, declared: int | None) -> None:
        """The platform envelope, rendered at the transport layer."""
        sized = f" of {declared} bytes" if declared is not None else ""
        body = json.dumps(
            {
                "error": {
                    "type": "invalid_request_error",
                    "code": "request_too_large",
                    "message": (
                        f"Request body{sized} exceeds the {self._max_bytes}-byte "
                        "limit. Audio uploads are capped separately at 25 MiB."
                    ),
                    "param": None,
                    "request_id": scope.get("state", {}).get("request_id"),
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _request_id(request: Request) -> str:
    """Honor a sane client-supplied ID (so callers can pre-correlate), else mint one."""
    supplied = request.headers.get(REQUEST_ID_HEADER, "")
    if 0 < len(supplied) <= _MAX_CLIENT_ID_LENGTH and supplied.isprintable():
        return supplied
    return f"req_{uuid.uuid4().hex}"


def _auth_fields(request: Request) -> dict[str, str]:
    """Identity set by the auth dependency, carried via request.state.

    Bound contextvars do not cross the BaseHTTPMiddleware task boundary
    (the downstream app runs in a child task), so the completion log reads
    them from request.state instead.
    """
    fields: dict[str, str] = {}
    for name in ("organization_id", "key_id"):
        value = getattr(request.state, name, None)
        if value is not None:
            fields[name] = value
    return fields


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id

        # Fresh context per request: bind once here, and every log line from
        # any code handling this request carries request_id automatically.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        logger.info("request_started", method=request.method, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            **_auth_fields(request),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        # Rate-limit headers ride out here rather than from each route, so
        # they appear on successes AND on the 429 the error handler
        # rendered — a client tuning its backoff needs them most on the
        # response that refused it.
        decision = getattr(request.state, "rate_limit", None)
        if decision is not None and not decision.degraded:
            response.headers.update(decision.headers)
        return response
