"""/v1/audio — the speech domain's public API surface."""

from fastapi import APIRouter

from intelliai_api.api.v1.audio import speech, transcriptions, voices

router = APIRouter()
router.include_router(transcriptions.router)
router.include_router(speech.router)
router.include_router(voices.router)

__all__ = ["router"]
