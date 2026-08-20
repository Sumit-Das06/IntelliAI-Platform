"""POST /v1/audio/speech — IntelliAI's public text-to-speech API.

OpenAI-compatible request shape (`model`, `input`, `voice`, `speed`,
`response_format`): existing SDKs and habits work by changing only the
base URL and key. The response body is raw playable audio — never JSON,
never base64 — and carries NO internal headers: the runtime envelope is
gateway food (ADR-0020), not customer surface. v1 produces WAV;
`response_format` accepts exactly that, so a client asking for "mp3"
gets an honest validation error instead of mislabeled bytes.
"""

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from intelliai_api.api.deps import CurrentAuth, IdempotencyKey, SpeechDep

router = APIRouter(prefix="/audio", tags=["audio"])


class SpeechRequest(BaseModel):
    """Public request schema — tolerant of unknown fields (SDKs send
    extras like `instructions`; ignoring them mirrors the contract's
    tolerant-reader posture on the public edge)."""

    model_config = ConfigDict(extra="ignore")

    model: str = Field(description="Public model id, e.g. `intelliai-tts`.")
    input: str = Field(
        min_length=1,
        description=(
            "Text to speak — up to 2000 characters per request; longer "
            "text is refused with a validation error, never cut short."
        ),
    )
    voice: str | None = Field(
        default=None,
        description=(
            "Public voice id from GET /v1/audio/voices (e.g. "
            "`english-female`, `english-male`). Omit for the default voice."
        ),
    )
    speed: float | None = Field(default=None, gt=0, description="Speaking rate; 1.0 is normal.")
    response_format: Literal["wav"] = "wav"


@router.post("/speech")
async def create_speech(
    auth: CurrentAuth,
    service: SpeechDep,
    request: SpeechRequest,
    idempotency_key: IdempotencyKey,
) -> Response:
    """Turn text into speech.

    Returns raw `audio/wav` (mono, 16-bit, 24 kHz) — playable bytes,
    no JSON wrapper. Billing counts input characters; audio duration is
    measured telemetry only. Text beyond 2000 characters is refused with
    a clean validation error (never truncated).
    """
    outcome = await service.synthesize(
        auth=auth,
        public_model_id=request.model,
        text=request.input,
        voice=request.voice,
        speed=request.speed,
        idempotency_key=idempotency_key,
    )
    return Response(content=outcome.audio, media_type=outcome.media_type)
