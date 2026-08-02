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
from intelliai_stt_runtime.engines import TranscriptionEngine
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.identity import SERVICE_NAME, runtime_metadata
from intelliai_stt_runtime.manager import ModelManager
from intelliai_stt_runtime.pipeline import MediaPipeline, PipelineOutput
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


def _ingest_and_transcribe(
    pipeline: MediaPipeline,
    engine: TranscriptionEngine,
    payload: bytes,
    request: TranscriptionRequest,
) -> tuple[PipelineOutput, TranscriptionResult, float]:
    """Stages 1-5 plus handoff, as one blocking unit on a pool slot.

    The handoff stage's short-circuit: when VAD found no speech, the
    correct transcript is empty and NO engine runs — silence can never
    reach a model and come back as hallucinated words.
    """
    output = pipeline.process(payload)
    inference_started = time.perf_counter()
    if output.speech.has_speech:
        result = engine.transcribe(output.audio, request)
    else:
        result = TranscriptionResult(
            text="",
            language=request.language or "zxx",
            duration_seconds=output.audio.duration_seconds,
        )
    inference_ms = (time.perf_counter() - inference_started) * 1000.0
    return output, result, inference_ms


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
    pipeline: MediaPipeline = request.app.state.pipeline
    pool: WorkerPool = request.app.state.pool
    loaded = manager.lookup(transcription_request.model)

    payload = await file.read()
    # Admission happens BEFORE any expensive work: pipeline decode and
    # inference share one bounded slot, so ffmpeg concurrency is capped
    # by the same honest limit as the engines.
    output, result, inference_ms = await pool.run(
        partial(_ingest_and_transcribe, pipeline, loaded.engine, payload, transcription_request)
    )

    envelope = RuntimeResponse[TranscriptionResult](
        output=result,
        model=loaded.artifact,
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=output.audio.duration_seconds),),
        timing=RuntimeTiming(
            total_ms=(time.perf_counter() - started) * 1000.0,
            stages={**output.timings_ms, "inference": inference_ms},
        ),
        runtime=runtime_metadata(),
    )
    logger.info(
        "transcription_completed",
        artifact=loaded.artifact,
        media_format=str(output.media_format),
        audio_seconds=round(output.audio.duration_seconds, 3),
        speech_seconds=round(output.speech.speech_seconds, 3),
        total_ms=round(envelope.timing.total_ms, 1),
    )
    return Response(
        content=envelope.model_dump_json(),
        media_type="application/json",
        headers=_CONTRACT_HEADERS,
    )
