"""Application factory for the IntelliAI API gateway.

Run locally with:
    uvicorn --factory intelliai_api.main:create_app --reload
(or `make api` from the repository root).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import Depends, FastAPI

from intelliai_api import __version__
from intelliai_api.api.deps import enforce_limits
from intelliai_api.api.edge import UnauthenticatedEdgeMiddleware
from intelliai_api.api.errors import register_error_handlers
from intelliai_api.api.health import router as health_router
from intelliai_api.api.middleware import RequestContextMiddleware
from intelliai_api.api.v1.router import router as v1_router
from intelliai_api.core.config import Settings, get_settings
from intelliai_api.core.health import HealthService, default_checks
from intelliai_api.core.logging import configure_logging
from intelliai_api.db.engine import create_engine, create_session_factory
from intelliai_api.limits import AdmissionController, RedisLimiterBackend
from intelliai_api.registry import default_registry
from intelliai_api.runtimes import HTTPRuntimeClient, RuntimeClient

logger = structlog.get_logger("intelliai_api.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup/shutdown lifecycle.

    The engine object is built in the factory (lazily, no I/O); its pool
    fills on first use. Shutdown drains and closes every pooled connection
    so Postgres never accumulates orphans from restarts — and every
    runtime client releases its transport pool.
    """
    logger.info("app_started")
    yield
    for client in app.state.runtime_clients.values():
        await client.close()
    await app.state.engine.dispose()
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
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.health = HealthService(default_checks(settings, engine))
    # The registry composes (and license-gates) at startup; runtime clients
    # are keyed by the capability-named service the registry routes to.
    app.state.registry = default_registry()
    runtime_clients: dict[str, RuntimeClient] = {
        "stt-runtime": HTTPRuntimeClient(
            base_url=settings.runtimes.stt_url,
            timeout_seconds=settings.runtimes.timeout_seconds,
        ),
        "tts-runtime": HTTPRuntimeClient(
            base_url=settings.runtimes.tts_url,
            timeout_seconds=settings.runtimes.timeout_seconds,
        ),
    }
    app.state.runtime_clients = runtime_clients
    app.state.limits = build_admission_controller(settings)

    # Middleware runs outermost-last: the edge guard is added AFTER the
    # request-context middleware so it runs INSIDE it, and a refused
    # request still gets a request id to quote.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(UnauthenticatedEdgeMiddleware, controller=app.state.limits)
    register_error_handlers(app)

    app.include_router(health_router)
    # Admission control is attached to the ROUTER, not to routes. A new
    # endpoint under /v1 therefore cannot forget to be rate limited —
    # enforcement is structural, and a test refuses the diff that removes
    # it (ADR-0022).
    app.include_router(v1_router, dependencies=[Depends(enforce_limits)])

    return app


def build_admission_controller(settings: Settings) -> AdmissionController:
    """Wire the limiter, with the timeouts that make failing open fast.

    ``socket_connect_timeout`` matters as much as ``socket_timeout``: a
    Redis host that is unreachable rather than merely slow must be
    discovered in milliseconds, not at the OS connect timeout.
    """
    if not settings.limits.enabled:
        logger.warning("ratelimit_disabled")
        return AdmissionController(None)
    client = aioredis.from_url(
        settings.redis.url.get_secret_value(),
        socket_timeout=settings.limits.socket_timeout_seconds,
        socket_connect_timeout=settings.limits.socket_timeout_seconds,
        retry_on_timeout=False,
    )
    return AdmissionController(RedisLimiterBackend(client), namespace=settings.limits.namespace)
