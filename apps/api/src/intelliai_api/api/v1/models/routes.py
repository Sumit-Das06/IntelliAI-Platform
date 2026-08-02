"""GET /v1/models — a product catalog, never a registry dump.

The response exposes ONLY stable public product facts: the public model
id, its release date, and a customer-facing description. Artifact ids,
engine names, licenses, versions, and runtime topology are private
implementation — the whole point of the public-model/artifact split
(MODEL_IDENTITY; M2 refinement 5). OpenAI-compatible shapes, so SDK
`models.list()` works unmodified.
"""

import datetime
from typing import Any

from fastapi import APIRouter

from intelliai_api.api.deps import CurrentAuth, RegistryDep
from intelliai_api.registry import PublicModelRecord

router = APIRouter(prefix="/models", tags=["models"])


def _to_public(record: PublicModelRecord) -> dict[str, Any]:
    released = datetime.datetime.combine(record.released, datetime.time.min, tzinfo=datetime.UTC)
    return {
        "id": record.id,
        "object": "model",
        "created": int(released.timestamp()),
        "owned_by": "intelliai",
        "description": record.description,
    }


@router.get("")
async def list_models(auth: CurrentAuth, registry: RegistryDep) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [_to_public(record) for record in registry.list_models()],
    }


@router.get("/{model_id}")
async def retrieve_model(model_id: str, auth: CurrentAuth, registry: RegistryDep) -> dict[str, Any]:
    return _to_public(registry.public_model(model_id))
