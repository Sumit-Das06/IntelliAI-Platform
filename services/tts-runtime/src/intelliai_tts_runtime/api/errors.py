"""Failure -> HTTP response: the binding's half of the error contract.

Errors are ALWAYS JSON (ADR-0020): a non-2xx response from this runtime
is parseable without sniffing content types, no matter that success
responses are binary audio.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from intelliai_runtime_contract import RuntimeErrorResponse, RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_tts_runtime.api.binding import HEADER_CONTRACT_VERSION, STATUS_BY_ERROR_TYPE
from intelliai_tts_runtime.identity import runtime_metadata

logger = structlog.get_logger(__name__)


def _render(failure: RuntimeServiceError) -> JSONResponse:
    body = RuntimeErrorResponse(
        type=failure.error_type,
        message=failure.message,
        param=failure.param,
        runtime=runtime_metadata(),
    )
    return JSONResponse(
        status_code=STATUS_BY_ERROR_TYPE[failure.error_type],
        content=body.model_dump(mode="json"),
        headers={HEADER_CONTRACT_VERSION: str(runtime_metadata().contract_version)},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RuntimeServiceError)
    async def on_runtime_failure(_: Request, failure: RuntimeServiceError) -> JSONResponse:
        logger.info(
            "request_failed",
            error_type=str(failure.error_type),
            param=failure.param,
        )
        return _render(failure)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # A misshapen body — the binding's own validation. The message names
        # the schema, never the payload (text is customer-owned content).
        return _render(
            RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                "request body must be a JSON SpeechSynthesisRequest with non-empty text",
            )
        )

    @app.exception_handler(Exception)
    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Details stay in runtime logs; the wire gets an opaque internal.
        logger.exception("unhandled_error")
        return _render(RuntimeServiceError(RuntimeErrorType.INTERNAL, "internal runtime error"))
