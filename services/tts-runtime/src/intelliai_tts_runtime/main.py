"""App factory: wiring, lifecycle, and nothing else.

The lifespan is the lifecycle discipline made executable: the ModelManager
loads every engine BEFORE the server accepts traffic, engines live for the
whole process, and shutdown unloads them exactly once. Requests only ever
look up what startup created.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response

from intelliai_runtime_core import ModelManager, SlotSpec, WorkerPool, configure_logging
from intelliai_tts_runtime import __version__, voices
from intelliai_tts_runtime.api.binding import HEADER_REQUEST_ID
from intelliai_tts_runtime.api.errors import register_error_handlers
from intelliai_tts_runtime.api.routes import router
from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.engines import SynthesisEngine, reference
from intelliai_tts_runtime.identity import SERVICE_NAME
from intelliai_tts_runtime.pipeline import TextPipeline


def synthesis_warm_up(engine: SynthesisEngine) -> None:
    """This runtime's capability-defined warm-up probe (ADR-0019).

    The lifecycle machinery guarantees the probe runs once per engine
    before serving; what probing MEANS is synthesis's business: one
    inference of a short fixed sentence through the default voice, so
    lazy initialization is paid at startup, never by the first request."""
    _, engine_voice = voices.resolve(None)
    engine.synthesize("Warm-up.", engine_voice, None)


def build_manager(settings: Settings) -> ModelManager[SynthesisEngine]:
    """Settings-driven slot configuration.

    The default slot binds whichever engine deployment chose; the engines
    module owns everything model-specific. The reference engine needs no
    weights, so no ArtifactStore is wired yet — the Kokoro engine (step 4)
    brings its hash-pinned artifact spec and the store with it.
    """
    slots: tuple[SlotSpec[SynthesisEngine], ...] = (
        SlotSpec(
            slot="default",
            artifact=reference.ARTIFACT_ID,
            load=lambda _: reference.load_reference_synthesis_engine(),
        ),
    )
    return ModelManager(slots=slots, warm_up=synthesis_warm_up)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(
        service=SERVICE_NAME,
        service_version=__version__,
        log_level=settings.log_level,
        console_logs=settings.console_logs,
    )
    manager = build_manager(settings)
    pipeline = TextPipeline(max_text_chars=settings.max_text_chars)
    pool = WorkerPool(max_concurrency=settings.max_concurrency, max_queue=settings.max_queue)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await manager.startup()
        yield
        await manager.shutdown()
        pool.shutdown()

    app = FastAPI(title="IntelliAI TTS Runtime", lifespan=lifespan)
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
