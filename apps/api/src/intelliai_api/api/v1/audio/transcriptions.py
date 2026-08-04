"""POST /v1/audio/transcriptions — IntelliAI's first customer-facing AI API.

OpenAI-compatible request and response shapes: existing SDKs and habits
work by changing only the base URL and key. The route is thin — form
parsing and response rendering; everything else is TranscriptionService.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from intelliai_api.api.deps import CurrentAuth, IdempotencyKey, TranscriptionDep

router = APIRouter(prefix="/audio", tags=["audio"])

ResponseFormat = Literal["json", "text", "verbose_json"]


@router.post("/transcriptions")
async def create_transcription(
    auth: CurrentAuth,
    service: TranscriptionDep,
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()],
    idempotency_key: IdempotencyKey,
    language: Annotated[str | None, Form()] = None,
    response_format: Annotated[ResponseFormat, Form()] = "json",
) -> Response:
    audio = await file.read()
    outcome = await service.transcribe(
        auth=auth,
        public_model_id=model,
        audio=audio,
        language=language,
        idempotency_key=idempotency_key,
    )
    result = outcome.result
    if response_format == "text":
        return PlainTextResponse(result.text)
    if response_format == "verbose_json":
        payload: dict[str, Any] = {
            "task": "transcribe",
            "language": result.language,
            "duration": result.duration_seconds,
            "text": result.text,
            "segments": [
                {
                    "id": index,
                    "start": segment.start_seconds,
                    "end": segment.end_seconds,
                    "text": segment.text,
                }
                for index, segment in enumerate(result.segments)
            ],
        }
    else:
        payload = {"text": result.text}
    return JSONResponse(payload)
