"""The runtime's endpoints: one capability route plus operational surface."""

import time
from functools import partial
from typing import Annotated, Any, Final

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
from intelliai_runtime_core import (
    DEFAULT_SLOT,
    ModelManager,
    RuntimeServiceError,
    WorkerPool,
    host_environment,
    interpreter_identity,
    package_versions,
)
from intelliai_stt_runtime import __version__
from intelliai_stt_runtime.api.binding import HEADER_CONTRACT_VERSION, ROUTE_TRANSCRIBE
from intelliai_stt_runtime.engines import TranscriptionEngine
from intelliai_stt_runtime.engines.punctuation import PunctuationRestorer
from intelliai_stt_runtime.identity import SERVICE_NAME, runtime_metadata
from intelliai_stt_runtime.pipeline import MediaPipeline, PipelineOutput

logger = structlog.get_logger(__name__)
router = APIRouter()

_CONTRACT_HEADERS = {HEADER_CONTRACT_VERSION: str(CONTRACT_VERSION)}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    """Slot-truthful readiness (Milestone 17).

    Engines MAY expose ``slot_state() -> str`` (`ready`/`restarting`/
    `failed`); an engine without it is in-process and ready by virtue of
    having loaded. The DEFAULT slot decides the status code, because it
    answers requests that pin nothing — the deployment's core promise.
    A dead specialist beside a healthy default degrades the body, never
    the code: flipping 503 for it would invite the orchestrator to
    restart a process that is still serving customers (the same
    reasoning the compose healthchecks document).
    """
    manager: ModelManager[TranscriptionEngine] = request.app.state.manager
    if not manager.started:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    slots: dict[str, str] = {}
    default_state = "ready"
    degraded = False
    for loaded in manager.loaded_models():
        state = getattr(loaded.engine, "slot_state", lambda: "ready")()
        slots[loaded.artifact] = state
        if loaded.slot == DEFAULT_SLOT:
            default_state = state
        elif state != "ready":
            degraded = True
    if default_state != "ready":
        return JSONResponse({"status": "not_ready", "slots": slots}, status_code=503)
    return JSONResponse({"status": "degraded" if degraded else "ready", "slots": slots})


@router.get("/info")
async def info(request: Request) -> dict[str, Any]:
    """Operational identity and runtime self-description — never payload.

    **The lifetime law.** Every field here is true for the whole life of
    this process. Anything that changes per request is telemetry and
    belongs somewhere else. The rule exists because this endpoint has two
    kinds of consumer with incompatible needs: a benchmark record quotes
    it and needs a value that never moves, while monitoring wants one that
    always does. Let both live here and the second wins by accretion —
    every new counter individually reasonable, the endpoint no longer
    quotable in permanent evidence. A CI test enforces this by calling
    `/info`, running traffic, and calling it again.

    **One grandfathered exception: `pool.admitted`.** It is a live gauge
    and it predates this law. It stays only because `bench` polls it to
    observe saturation, and breaking a benchmark consumer to tidy a schema
    is the wrong trade. It is a documented debt, **not a precedent**: no
    further live counters are admitted here.

    **Why self-description belongs on the runtime.** A harness measures
    this service from another process and usually another container, so
    the build, the decode configuration, the VAD owner and the host are
    all invisible to it. Reporting them here is what stops a benchmark
    from *declaring* values the system already knows — Procedure §2's
    low-friction rule, whose point is that a hand-typed value the system
    could have supplied is a transcription error waiting to be committed.

    ADR-0016 governs `RuntimeMetadata` in the contract package and is not
    amended by anything below: this is a service endpoint, additive, and
    it carries no payload and no business data.
    """
    manager: ModelManager[TranscriptionEngine] = request.app.state.manager
    pool: WorkerPool = request.app.state.pool
    pipeline: MediaPipeline = request.app.state.pipeline
    settings = request.app.state.settings
    return {
        "pool": {
            # LEGACY EXCEPTION to the lifetime law — see the docstring.
            "admitted": pool.admitted,
            "max_concurrency": settings.max_concurrency,
            "max_queue": settings.max_queue,
        },
        "service": SERVICE_NAME,
        "service_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "capability": str(Capability.TRANSCRIPTION),
        # Who decided there was speech. Process-level: the pipeline's VAD
        # runs before any engine and therefore owns the decision.
        "vad_owner": pipeline.vad_owner,
        # The machine, as only this process can honestly describe it: the
        # harness's own environment describes the harness's host, which is
        # the right answer only when the runtime is local and native.
        "environment": _environment(),
        "models": [
            {
                "slot": loaded.slot,
                "artifact": loaded.artifact,
                "load_ms": round(loaded.load_ms, 1),
                "warmup_ms": round(loaded.warmup_ms, 1),
                # Per artifact, not per process: a multi-slot deployment
                # can host two artifacts under different builds, and one
                # description covering both would describe neither.
                **loaded.engine.describe().as_dict(),
            }
            for loaded in manager.loaded_models()
        ],
    }


#: The engine libraries this service can host, plus the numeric stack they
#: run on. A declared short list rather than every installed distribution:
#: `/info` is an evidence surface, and a full dependency dump would make
#: it a debugging endpoint by accretion.
_REPORTED_PACKAGES: Final = ("faster-whisper", "ctranslate2", "numpy")


def _environment() -> dict[str, Any]:
    return {
        **host_environment(),
        "interpreter": interpreter_identity(),
        "package_versions": package_versions(_REPORTED_PACKAGES),
    }


def _ingest_and_transcribe(
    pipeline: MediaPipeline,
    engine: TranscriptionEngine,
    payload: bytes,
    request: TranscriptionRequest,
    punctuator: PunctuationRestorer | None,
) -> tuple[PipelineOutput, TranscriptionResult, float, float | None]:
    """Stages 1-5 plus handoff, as one blocking unit on a pool slot.

    The handoff stage's short-circuit: when VAD found no speech, the
    correct transcript is empty and NO engine runs — silence can never
    reach a model and come back as hallucinated words.

    The punctuation stage (M30) rides the SAME pool slot after the final
    transcript exists (post chunk-merge for long audio): fail-open, gated
    on the route-resolved language, words copied verbatim by contract.
    Silence short-circuits before it, so empty text never meets the model.
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
    punctuation_ms: float | None = None
    if punctuator is not None and result.text:
        stage = punctuator.restore_safely(result, request.language)
        result = stage.result
        punctuation_ms = stage.elapsed_ms
    return output, result, inference_ms, punctuation_ms


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

    manager: ModelManager[TranscriptionEngine] = request.app.state.manager
    pipeline: MediaPipeline = request.app.state.pipeline
    pool: WorkerPool = request.app.state.pool
    punctuator: PunctuationRestorer | None = request.app.state.punctuator
    loaded = manager.lookup(transcription_request.model)

    payload = await file.read()
    # Admission happens BEFORE any expensive work: pipeline decode and
    # inference share one bounded slot, so ffmpeg concurrency is capped
    # by the same honest limit as the engines.
    output, result, inference_ms, punctuation_ms = await pool.run(
        partial(
            _ingest_and_transcribe,
            pipeline,
            loaded.engine,
            payload,
            transcription_request,
            punctuator,
        )
    )

    stages = {**output.timings_ms, "inference": inference_ms}
    if punctuation_ms is not None:
        stages["punctuation"] = punctuation_ms
    envelope = RuntimeResponse[TranscriptionResult](
        output=result,
        model=loaded.artifact,
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=output.audio.duration_seconds),),
        timing=RuntimeTiming(
            total_ms=(time.perf_counter() - started) * 1000.0,
            stages=stages,
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
