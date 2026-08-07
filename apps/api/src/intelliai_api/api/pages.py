"""Human-facing pages served by the gateway — the IntelliAI console.

Deliberately outside ``/v1`` and outside the OpenAPI schema: these are
pages, not APIs. No bearer auth to VIEW them (each page asks for the key
it uses); the unauthenticated edge limiter still covers them like any
other public path. Packaged files, read once per process — no
StaticFiles mount, no directory semantics, no build step.
"""

from functools import lru_cache
from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

router = APIRouter()

# Shared console assets, served individually from an allowlist. A mount
# would add directory semantics (listings, traversal surface) for the
# sake of two files; an unknown name is a plain 404, not an error event.
_ASSET_TYPES = {
    "console.css": "text/css; charset=utf-8",
    "console.js": "text/javascript; charset=utf-8",
}
# Pages and assets revalidate on every load: at this scale, a stale shell
# after a deploy costs more than the kilobytes caching would save.
_NO_CACHE = {"Cache-Control": "no-cache"}


@lru_cache(maxsize=16)
def _static_text(*parts: str) -> str:
    resource = files("intelliai_api") / "static"
    for part in parts:
        resource = resource / part
    return resource.read_text(encoding="utf-8")


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """The platform's front door is Home."""
    return RedirectResponse("/console/home", status_code=307)


@router.get("/console", include_in_schema=False)
async def console_root() -> RedirectResponse:
    """The console's own root also lands on Home."""
    return RedirectResponse("/console/home", status_code=307)


@router.get("/console/home", include_in_schema=False)
async def console_home() -> HTMLResponse:
    """Home: welcome, quick actions, getting started, the catalogue."""
    return HTMLResponse(_static_text("console", "home.html"), headers=_NO_CACHE)


@router.get("/console/keys", include_in_schema=False)
async def console_keys() -> HTMLResponse:
    """API key management: create (shown once), list, revoke."""
    return HTMLResponse(_static_text("console", "keys.html"), headers=_NO_CACHE)


@router.get("/console/services", include_in_schema=False)
async def console_services() -> HTMLResponse:
    """The public product catalogue: IntelliAI services, never models."""
    return HTMLResponse(_static_text("console", "services.html"), headers=_NO_CACHE)


@router.get("/console/samples", include_in_schema=False)
async def console_samples() -> HTMLResponse:
    """Browse the organization's consented speech samples."""
    return HTMLResponse(_static_text("console", "samples.html"), headers=_NO_CACHE)


@router.get("/console/playground", include_in_schema=False)
async def console_playground() -> HTMLResponse:
    """The STT Studio — IntelliAI STT's primary product experience."""
    return HTMLResponse(_static_text("console", "studio.html"), headers=_NO_CACHE)


@router.get("/console/assets/{asset}", include_in_schema=False)
async def console_asset(asset: str) -> Response:
    media_type = _ASSET_TYPES.get(asset)
    if media_type is None:
        return PlainTextResponse("not found", status_code=404)
    return Response(_static_text("console", asset), media_type=media_type, headers=_NO_CACHE)


@router.get("/playground", include_in_schema=False)
async def playground_redirect() -> RedirectResponse:
    """The pre-console URL, kept alive: cohort bookmarks must not break."""
    return RedirectResponse("/console/playground", status_code=307)
