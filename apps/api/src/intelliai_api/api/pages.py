"""Human-facing pages served by the gateway — today, the playground.

Deliberately outside ``/v1`` and outside the OpenAPI schema: this is a
page, not an API. No bearer auth to VIEW it (the page itself asks for the
key it uses); the unauthenticated edge limiter still covers it like any
other public path. One packaged file, read once per process — no
StaticFiles mount, no directory semantics, no build step.
"""

from functools import lru_cache
from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@lru_cache(maxsize=1)
def _playground_html() -> str:
    return (files("intelliai_api") / "static" / "playground.html").read_text(encoding="utf-8")


@router.get("/playground", include_in_schema=False)
async def playground() -> HTMLResponse:
    """The mini console: record/upload → transcript → optional correction."""
    return HTMLResponse(_playground_html())
