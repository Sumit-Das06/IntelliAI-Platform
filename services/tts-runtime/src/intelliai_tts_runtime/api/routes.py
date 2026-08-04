"""The runtime's endpoints: one capability route plus operational surface.

The synthesis route realizes ADR-0020: JSON request in, raw WAV bytes as
the response body, the success envelope riding ``X-Runtime-Envelope`` as
operational metadata. Errors never reach this shape — they are always
JSON (api/errors.py).
"""

import time
from functools import partial
from typing import Any

import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    Capability,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)
from intelliai_runtime_core import ModelManager, WorkerPool
from intelliai_tts_runtime import __version__
from intelliai_tts_runtime.api.binding import (
    HEADER_CONTRACT_VERSION,
    HEADER_RUNTIME_ENVELOPE,
    MEDIA_TYPE_WAV,
    ROUTE_SYNTHESIZE,
)
from intelliai_tts_runtime.api.wav import encode_wav
from intelliai_tts_runtime.engines import SynthesisEngine, SynthesizedAudio
from intelliai_tts_runtime.identity import SERVICE_NAME, runtime_metadata
from intelliai_tts_runtime.pipeline import TextPipeline
from intelliai_tts_runtime.voices import VoiceCatalog

logger = structlog.get_logger(__name__)
router = APIRouter()

_CONTRACT_HEADERS = {HEADER_CONTRACT_VERSION: str(CONTRACT_VERSION)}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    manager: ModelManager[SynthesisEngine] = request.app.state.manager
    if manager.started:
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "not_ready"}, status_code=503)


@router.get("/info")
async def info(request: Request) -> dict[str, Any]:
    """Operational identity only — never payload (ADR-0016).

    ``models`` is the deployment's catalog: every hosted artifact, with
    the voices that artifact can render. The top-level ``voices`` list is
    the union across slots — what this deployment can render at all,
    regardless of which artifact does it.
    """
    manager: ModelManager[SynthesisEngine] = request.app.state.manager
    pool: WorkerPool = request.app.state.pool
    settings = request.app.state.settings
    catalog: VoiceCatalog = request.app.state.voices

    models: list[dict[str, Any]] = []
    served: list[str] = []
    for loaded in manager.loaded_models():
        voice_ids = catalog.voices_for(loaded.engine).voice_ids()
        served.extend(voice for voice in voice_ids if voice not in served)
        models.append(
            {
                "slot": loaded.slot,
                "artifact": loaded.artifact,
                "load_ms": round(loaded.load_ms, 1),
                "warmup_ms": round(loaded.warmup_ms, 1),
                "voices": list(voice_ids),
            }
        )
    return {
        "pool": {
            "admitted": pool.admitted,
            "max_concurrency": settings.max_concurrency,
            "max_queue": settings.max_queue,
        },
        "service": SERVICE_NAME,
        "service_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "capability": str(Capability.SPEECH_SYNTHESIS),
        "voices": served,
        "models": models,
    }


def _pipeline_and_synthesize(
    pipeline: TextPipeline,
    engine: SynthesisEngine,
    text: str,
    engine_voice: str,
    speed: float | None,
) -> tuple[dict[str, float], SynthesizedAudio, bytes]:
    """Validate/normalize, synthesize, containerize — one blocking unit on
    a pool slot, so text processing and encoding are capped by the same
    honest admission limit as inference."""
    output = pipeline.process(text)
    timings = dict(output.timings_ms)

    started = time.perf_counter()
    audio = engine.synthesize(output.text, engine_voice, speed)
    timings["synthesis"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    body = encode_wav(audio)
    timings["encode"] = (time.perf_counter() - started) * 1000.0
    return timings, audio, body


@router.post(ROUTE_SYNTHESIZE)
async def synthesize(request: Request, synthesis_request: SpeechSynthesisRequest) -> Response:
    started = time.perf_counter()
    manager: ModelManager[SynthesisEngine] = request.app.state.manager
    pipeline: TextPipeline = request.app.state.pipeline
    pool: WorkerPool = request.app.state.pool
    catalog: VoiceCatalog = request.app.state.voices

    # Slot selection first, voice resolution second — and unbypassably so,
    # because the selected engine is the catalog's key. A voice is an
    # artifact-specific asset; asking "which voice?" before "which
    # artifact?" is a question with no answer in a multi-slot runtime.
    loaded = manager.lookup(synthesis_request.model)

    resolution_started = time.perf_counter()
    public_voice, engine_voice = catalog.voices_for(loaded.engine).resolve(synthesis_request.voice)
    resolution_ms = (time.perf_counter() - resolution_started) * 1000.0

    # Admission happens BEFORE any expensive work: validation, synthesis,
    # and containerization share one bounded slot.
    timings, audio, body = await pool.run(
        partial(
            _pipeline_and_synthesize,
            pipeline,
            loaded.engine,
            synthesis_request.text,
            engine_voice,
            synthesis_request.speed,
        )
    )

    characters = len(synthesis_request.text)
    envelope = RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=audio.duration_seconds,
            sample_rate_hz=audio.sample_rate_hz,
            voice=public_voice,
            characters=characters,
        ),
        model=loaded.artifact,
        usage=(Usage(unit=UsageUnit.CHARACTERS, amount=characters),),
        timing=RuntimeTiming(
            total_ms=(time.perf_counter() - started) * 1000.0,
            stages={"voice_resolution": resolution_ms, **timings},
        ),
        runtime=runtime_metadata(),
    )
    # The customer's text is customer-owned content: only measurements of
    # it (characters, duration) may appear in logs or metadata.
    logger.info(
        "synthesis_completed",
        artifact=loaded.artifact,
        voice=public_voice,
        characters=characters,
        audio_seconds=round(audio.duration_seconds, 3),
        total_ms=round(envelope.timing.total_ms, 1),
    )
    return Response(
        content=body,
        media_type=MEDIA_TYPE_WAV,
        headers={**_CONTRACT_HEADERS, HEADER_RUNTIME_ENVELOPE: envelope.model_dump_json()},
    )
