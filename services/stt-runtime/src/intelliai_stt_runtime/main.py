"""App factory: wiring, lifecycle, and nothing else.

The lifespan is the lifecycle refinement made executable: the ModelManager
loads every engine BEFORE the server accepts traffic, engines live for the
whole process, and shutdown unloads them exactly once. Requests only ever
look up what startup created.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial

import structlog
from fastapi import FastAPI, Request, Response

from intelliai_stt_runtime.api.binding import HEADER_REQUEST_ID
from intelliai_stt_runtime.api.errors import register_error_handlers
from intelliai_stt_runtime.api.routes import router
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.engines import reference, whisper
from intelliai_stt_runtime.logging import configure_logging
from intelliai_stt_runtime.manager import ArtifactStore, ModelManager, SlotSpec
from intelliai_stt_runtime.pipeline import EnergyVad, FfmpegDecoder, MediaPipeline
from intelliai_stt_runtime.pool import WorkerPool


def build_manager(settings: Settings) -> ModelManager:
    """Settings-driven slot configuration.

    The default slot binds whichever engine deployment chose; the engines
    module owns everything model-specific (files, hashes, library import).
    Adding an engine here = one SlotSpec line, nothing else on the platform.
    """
    if settings.default_engine == "whisper":
        slots = (
            SlotSpec(
                slot="default",
                artifact=whisper.ARTIFACT_ID,
                load=partial(
                    whisper.load_faster_whisper, compute_type=settings.whisper_compute_type
                ),
                files=whisper.WHISPER_SMALL_FILES,
            ),
        )
    else:
        slots = (
            SlotSpec(
                slot="default",
                artifact=reference.ARTIFACT_ID,
                load=lambda _: reference.load_reference_engine(),
            ),
        )
    return ModelManager(slots=slots, store=ArtifactStore(settings.model_dir))


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
    configure_logging(settings)
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
