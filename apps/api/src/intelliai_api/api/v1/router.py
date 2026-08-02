"""The /v1 aggregate router.

Domain packages register here; nothing outside ``api/`` is version-aware.
"""

from fastapi import APIRouter

from intelliai_api.api.v1.api_keys import router as api_keys_router
from intelliai_api.api.v1.audio import router as audio_router
from intelliai_api.api.v1.models import router as models_router
from intelliai_api.api.v1.organization import router as organization_router

router = APIRouter(prefix="/v1")
router.include_router(organization_router)
router.include_router(api_keys_router)
router.include_router(models_router)
router.include_router(audio_router)
