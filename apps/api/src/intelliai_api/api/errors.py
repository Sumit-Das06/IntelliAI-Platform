"""HTTP rendering of the platform error contract.

Four handlers cover every way a request can fail:

1. ``IntelliAIError``          — deliberately raised platform errors
2. ``RequestValidationError``  — bad input caught by Pydantic (rendered 400,
                                 not FastAPI's nonstandard 422 shape)
3. ``StarletteHTTPException``  — framework-raised HTTP errors (404 no route,
                                 405 wrong method, …)
4. ``Exception``               — anything unexpected: logged with stack
                                 trace, rendered as an opaque internal_error.
                                 Details NEVER cross the API boundary.

Deliberate exception to the envelope: ``/health/*`` keeps its own report
shape — orchestrators and uptime probes expect it.
"""

from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from intelliai_api.core.errors import ErrorType, IntelliAIError

logger = structlog.get_logger("intelliai_api.errors")

_STATUS_TO_TYPE: dict[int, ErrorType] = {
    400: ErrorType.INVALID_REQUEST,
    401: ErrorType.AUTHENTICATION,
    403: ErrorType.AUTHORIZATION,
    404: ErrorType.NOT_FOUND,
    405: ErrorType.INVALID_REQUEST,
    409: ErrorType.CONFLICT,
    429: ErrorType.RATE_LIMIT,
    503: ErrorType.SERVICE_UNAVAILABLE,
}

_INTERNAL_ERROR_MESSAGE = (
    "An internal error occurred. The failure has been logged; quote the "
    "request_id when contacting support."
)


def _envelope(
    request: Request,
    *,
    error_type: ErrorType,
    message: str,
    status_code: int,
    code: str | None = None,
    param: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "error": {
                "type": error_type.value,
                "code": code,
                "message": message,
                "param": param,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


async def _handle_platform_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(IntelliAIError, exc)  # registration guarantees the type
    headers: dict[str, str] = {}
    retry_after = getattr(error, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    if error.status_code == 401:
        # RFC 6750: a 401 must tell the client which auth scheme to use.
        headers["WWW-Authenticate"] = "Bearer"
    return _envelope(
        request,
        error_type=error.error_type,
        code=error.code,
        message=error.message,
        param=error.param,
        status_code=error.status_code,
        headers=headers or None,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    first: dict[str, Any] = errors[0] if errors else {}
    location = [str(part) for part in first.get("loc", [])]
    # Drop the transport prefix ("body", "query", "path", "header") — the
    # client cares about the field name, not our parsing internals.
    if location and location[0] in {"body", "query", "path", "header"}:
        location = location[1:]
    return _envelope(
        request,
        error_type=ErrorType.INVALID_REQUEST,
        code="validation_error",
        message=str(first.get("msg", "Invalid request.")),
        param=".".join(location) or None,
        status_code=400,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    default = ErrorType.INTERNAL if error.status_code >= 500 else ErrorType.INVALID_REQUEST
    return _envelope(
        request,
        error_type=_STATUS_TO_TYPE.get(error.status_code, default),
        message=str(error.detail),
        status_code=error.status_code,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error_class=type(exc).__name__)
    return _envelope(
        request,
        error_type=ErrorType.INTERNAL,
        message=_INTERNAL_ERROR_MESSAGE,
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntelliAIError, _handle_platform_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
