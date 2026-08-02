"""Failure -> HTTP response: the binding's half of the error contract."""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from intelliai_runtime_contract import RuntimeErrorResponse, RuntimeErrorType
from intelliai_stt_runtime.api.binding import HEADER_CONTRACT_VERSION, STATUS_BY_ERROR_TYPE
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.identity import runtime_metadata

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
        # Missing/misshapen multipart parts — the binding's own validation.
        return _render(
            RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                "request must be multipart with a 'file' part and optional 'params' JSON",
            )
        )

    @app.exception_handler(Exception)
    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Details stay in runtime logs; the wire gets an opaque internal.
        logger.exception("unhandled_error")
        return _render(RuntimeServiceError(RuntimeErrorType.INTERNAL, "internal runtime error"))
