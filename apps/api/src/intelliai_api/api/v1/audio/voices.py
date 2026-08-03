"""GET /v1/audio/voices — the public voice catalog.

Product facts only, exactly like /v1/models: public voice id, the public
model that serves it, languages, description, release date. Engine voice
tokens, voice assets, embeddings, and runtime bindings are private
mechanics (M3 design review §5) — the leak-guard test makes that
CI-fatal.
"""

import datetime
from typing import Any

from fastapi import APIRouter

from intelliai_api.api.deps import CurrentAuth, RegistryDep
from intelliai_api.registry import PublicVoiceRecord

router = APIRouter(prefix="/audio", tags=["audio"])


def _to_public(record: PublicVoiceRecord) -> dict[str, Any]:
    released = datetime.datetime.combine(record.released, datetime.time.min, tzinfo=datetime.UTC)
    return {
        "id": record.id,
        "object": "voice",
        "model": record.model,
        "languages": list(record.languages),
        "description": record.description,
        "created": int(released.timestamp()),
    }


@router.get("/voices")
async def list_voices(auth: CurrentAuth, registry: RegistryDep) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [_to_public(record) for record in registry.list_voices()],
    }
