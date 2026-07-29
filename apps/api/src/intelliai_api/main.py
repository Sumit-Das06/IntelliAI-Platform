"""Application factory for the IntelliAI API gateway.

Run locally with:
    uvicorn --factory intelliai_api.main:create_app --reload
(or `make api` from the repository root).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from intelliai_api import __version__


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle.

    Everything that must exist before the first request is created before
    ``yield`` (settings validation, database engine, shared HTTP clients —
    arriving in M0 steps 4-7) and torn down in reverse order after it.
    A failure here crashes the process before it accepts traffic, which is
    exactly what an orchestrator needs to see.
    """
    yield


def create_app() -> FastAPI:
    """Build a fully configured application instance.

    A factory rather than a module-level ``app``: importing this module has
    no side effects, and every caller (server, tests, scripts) gets its own
    isolated, independently configured instance.
    """
    app = FastAPI(
        title="IntelliAI Platform",
        version=__version__,
        lifespan=lifespan,
    )

    # Routers are mounted here as they arrive: health (M0 step 6), then
    # /v1 domain routers (audio in M2/M3, further domains after).

    return app
