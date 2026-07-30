"""Request-scoped middleware: correlation ID and access logging.

The request ID minted here is the platform-wide correlation ID: bound to the
logging context for every line emitted while handling the request, returned
to the client in ``X-Request-ID``, and (from M2) propagated on outbound calls
to inference services so one ID traces a request across every process it
touches.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_CLIENT_ID_LENGTH = 128

logger = structlog.get_logger("intelliai_api.access")


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
        return response
