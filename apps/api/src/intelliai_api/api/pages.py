"""Human-facing pages served by the gateway — the IntelliAI console.

Deliberately outside ``/v1`` and outside the OpenAPI schema: these are
pages, not APIs. No bearer auth to VIEW them (each page asks for the key
it uses); the unauthenticated edge limiter still covers them like any
other public path. Packaged files, read once per process — no
StaticFiles mount, no directory semantics, no build step.
"""

from functools import lru_cache
from importlib.resources import files
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from intelliai_api.registry import Registry
from intelliai_api.registry.records import LanguageStatus

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


@router.get("/console/status", include_in_schema=False)
async def console_status(request: Request) -> JSONResponse:
    """Deployment-honest launch status for the console pages (M41).

    The static pages carry PRODUCTION-SAFE defaults ("Coming Soon");
    this endpoint upgrades a service to "preview" only where THIS
    deployment's registry actually serves it — the staging profile
    composes the Hindi TTS proposal, production does not, so the same
    static console never over-claims on a production box. Product
    facts only (status + language codes): no artifacts, no engines,
    no routes. Unauthenticated like the pages themselves.
    """
    registry = cast(Registry, request.app.state.registry)
    tts_preview = registry.language_status("intelliai-tts", "hi") is LanguageStatus.AVAILABLE
    tts_languages = sorted(
        {
            language
            for record in registry.list_voices()
            if record.model == "intelliai-tts"
            for language in record.languages
        }
    )
    return JSONResponse(
        {
            "services": {
                "tts": {
                    "status": "preview" if tts_preview else "soon",
                    "languages": tts_languages,
                }
            }
        },
        headers=_NO_CACHE,
    )


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


@router.get("/console/datasets", include_in_schema=False)
async def console_datasets() -> HTMLResponse:
    """Curated datasets and their immutable versions — the training-data
    foundation for future IntelliAI STT fine-tuning."""
    return HTMLResponse(_static_text("console", "datasets.html"), headers=_NO_CACHE)


@router.get("/console/usage", include_in_schema=False)
async def console_usage() -> HTMLResponse:
    """API consumption analytics — never dataset statistics."""
    return HTMLResponse(_static_text("console", "usage.html"), headers=_NO_CACHE)


@router.get("/console/playground", include_in_schema=False)
async def console_playground() -> HTMLResponse:
    """The STT Studio — IntelliAI STT's primary product experience."""
    return HTMLResponse(_static_text("console", "studio.html"), headers=_NO_CACHE)


@router.get("/console/speech", include_in_schema=False)
async def console_speech() -> HTMLResponse:
    """The Speech Studio — IntelliAI TTS's product experience (M35).

    Served everywhere the console is served; where the TTS runtime is
    absent (production today), generation answers the honest 503 and the
    page says so — availability is deployment state, never page state.
    """
    return HTMLResponse(_static_text("console", "speech.html"), headers=_NO_CACHE)


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
