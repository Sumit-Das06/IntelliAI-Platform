"""The runtime's endpoints: one capability route plus operational surface."""

import time
from functools import partial
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    Capability,
    RuntimeErrorType,
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionRequest,
    TranscriptionResult,
    Usage,
    UsageUnit,
)
from intelliai_stt_runtime import __version__
from intelliai_stt_runtime.api.binding import HEADER_CONTRACT_VERSION, ROUTE_TRANSCRIBE
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.identity import SERVICE_NAME, runtime_metadata
from intelliai_stt_runtime.manager import ModelManager
from intelliai_stt_runtime.pipeline import decode_wav
from intelliai_stt_runtime.pool import WorkerPool

logger = structlog.get_logger(__name__)
router = APIRouter()

_CONTRACT_HEADERS = {HEADER_CONTRACT_VERSION: str(CONTRACT_VERSION)}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    manager: ModelManager = request.app.state.manager
    if manager.started:
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "not_ready"}, status_code=503)


@router.get("/info")
async def info(request: Request) -> dict[str, Any]:
    """Operational identity only — never payload (ADR-0016)."""
    manager: ModelManager = request.app.state.manager
    return {
        "service": SERVICE_NAME,
        "service_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "capability": str(Capability.TRANSCRIPTION),
        "models": [
            {"slot": loaded.slot, "artifact": loaded.artifact} for loaded in manager.loaded_models()
        ],
    }


@router.post(ROUTE_TRANSCRIBE)
async def transcribe(
    request: Request,
    file: Annotated[UploadFile, File()],
    params: Annotated[str, Form()] = "{}",
) -> Response:
    started = time.perf_counter()
    try:
        transcription_request = TranscriptionRequest.model_validate_json(params)
    except ValidationError as exc:
        raise RuntimeServiceError(
            RuntimeErrorType.INVALID_INPUT,
            "params must be a JSON-encoded TranscriptionRequest",
            param="params",
        ) from exc

    manager: ModelManager = request.app.state.manager
    pool: WorkerPool = request.app.state.pool
    loaded = manager.lookup(transcription_request.model)

    payload = await file.read()
    decoded = decode_wav(payload)
    decode_ms = (time.perf_counter() - started) * 1000.0

    inference_started = time.perf_counter()
    result = await pool.run(partial(loaded.engine.transcribe, decoded, transcription_request))
    inference_ms = (time.perf_counter() - inference_started) * 1000.0

    envelope = RuntimeResponse[TranscriptionResult](
        output=result,
        model=loaded.artifact,
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=decoded.duration_seconds),),
        timing=RuntimeTiming(
            total_ms=(time.perf_counter() - started) * 1000.0,
            stages={"decode": decode_ms, "inference": inference_ms},
        ),
        runtime=runtime_metadata(),
    )
    logger.info(
        "transcription_completed",
        artifact=loaded.artifact,
        audio_seconds=round(decoded.duration_seconds, 3),
        total_ms=round(envelope.timing.total_ms, 1),
    )
    return Response(
        content=envelope.model_dump_json(),
        media_type="application/json",
        headers=_CONTRACT_HEADERS,
    )
