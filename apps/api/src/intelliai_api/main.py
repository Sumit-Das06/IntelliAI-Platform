"""Application factory for the IntelliAI API gateway.

Run locally with:
    uvicorn --factory intelliai_api.main:create_app --reload
(or `make api` from the repository root).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from intelliai_api import __version__
from intelliai_api.api.middleware import RequestContextMiddleware
from intelliai_api.core.config import Settings, get_settings
from intelliai_api.core.logging import configure_logging

logger = structlog.get_logger("intelliai_api.lifecycle")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle.

    Resources that must exist before the first request are created before
    ``yield`` (database engine, shared HTTP clients — M0 steps 6-7) and torn
    down in reverse order after it. A failure here crashes the process before
    it accepts traffic, which is exactly what an orchestrator needs to see.
    """
    logger.info("app_started")
    yield
    logger.info("app_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully configured application instance.

    Args:
        settings: Configuration for this instance. ``None`` (the production
            path) loads validated settings from the environment; tests pass
            their own ``Settings`` and never touch process globals.
    """
    settings = settings if settings is not None else get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="IntelliAI Platform",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestContextMiddleware)

    # Routers are mounted here as they arrive: health (M0 step 6), then
    # /v1 domain routers (api/v1/speech in M2/M3, further domains after).

    return app
