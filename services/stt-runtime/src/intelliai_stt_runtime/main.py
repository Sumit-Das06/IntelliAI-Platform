"""App factory: wiring, lifecycle, and nothing else.

The lifespan is the lifecycle refinement made executable: the ModelManager
loads every engine BEFORE the server accepts traffic, engines live for the
whole process, and shutdown unloads them exactly once. Requests only ever
look up what startup created.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response

from intelliai_runtime_contract import TranscriptionRequest
from intelliai_runtime_core import (
    ArtifactStore,
    ModelManager,
    WorkerPool,
    configure_logging,
)
from intelliai_stt_runtime import __version__
from intelliai_stt_runtime.api.binding import HEADER_REQUEST_ID
from intelliai_stt_runtime.api.errors import register_error_handlers
from intelliai_stt_runtime.api.routes import router
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.engines import TranscriptionEngine
from intelliai_stt_runtime.identity import SERVICE_NAME
from intelliai_stt_runtime.pipeline import EnergyVad, FfmpegDecoder, MediaPipeline, canonical_audio
from intelliai_stt_runtime.slots import build_slot_specs

# Half a second of gentle deterministic non-silence: enough to push a real
# model through its full encode/decode path once, engine-agnostic.
_WARM_UP_PCM = bytes(
    byte for i in range(8000) for byte in ((i % 64) * 8).to_bytes(2, "little", signed=True)
)


def transcription_warm_up(engine: TranscriptionEngine) -> None:
    """This runtime's capability-defined warm-up probe (ADR-0019).

    The lifecycle machinery guarantees the probe runs once per engine
    before serving; what probing MEANS is transcription's business: one
    engine-agnostic inference over deterministic canonical audio, so lazy
    initialization is paid at startup, never by the first request."""
    engine.transcribe(canonical_audio(_WARM_UP_PCM), TranscriptionRequest())


def build_manager(settings: Settings) -> ModelManager[TranscriptionEngine]:
    """Settings-driven slot configuration.

    The deployment declares the artifacts it hosts (``slots.py`` owns the
    engine catalog and the declaration rules); the manager hosts them.
    One artifact or five is a configuration difference, not a code one.
    """
    return ModelManager(
        slots=build_slot_specs(settings),
        store=ArtifactStore(settings.model_dir),
        warm_up=transcription_warm_up,
    )


def build_pipeline(settings: Settings) -> MediaPipeline:
    """Ingestion wiring: sandboxed ffmpeg + deterministic VAD + limits."""
    return MediaPipeline(
        FfmpegDecoder(settings.ffmpeg_path, settings.decode_timeout_seconds),
        EnergyVad(),
        max_upload_bytes=settings.max_upload_bytes,
        max_audio_seconds=settings.max_audio_seconds,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(
        service=SERVICE_NAME,
        service_version=__version__,
        log_level=settings.log_level,
        console_logs=settings.console_logs,
    )
    manager = build_manager(settings)
    pipeline = build_pipeline(settings)
    pool = WorkerPool(max_concurrency=settings.max_concurrency, max_queue=settings.max_queue)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Decoder first: a runtime that cannot ingest must fail the deploy
        # before it loads models or accepts traffic.
        await asyncio.to_thread(pipeline.verify)
        await manager.startup()
        yield
        await manager.shutdown()
        pool.shutdown()

    app = FastAPI(title="IntelliAI STT Runtime", lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager
    app.state.pipeline = pipeline
    app.state.pool = pool

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(HEADER_REQUEST_ID)
        structlog.contextvars.clear_contextvars()
        if request_id:
            structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        if request_id:
            response.headers[HEADER_REQUEST_ID] = request_id
        return response

    app.include_router(router)
    register_error_handlers(app)
    return app
