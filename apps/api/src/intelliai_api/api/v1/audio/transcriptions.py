"""POST /v1/audio/transcriptions — IntelliAI's first customer-facing AI API.

OpenAI-compatible request and response shapes: existing SDKs and habits
work by changing only the base URL and key. The route is thin — form
parsing and response rendering; everything else is TranscriptionService.

Data collection rides AFTER a successful transcription and can never
fail it. The only public trace is one additive header,
``X-IntelliAI-Sample``, present exactly when a consented sample was
stored — the OpenAI-mirror response bodies stay byte-identical.
"""

import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from intelliai_api.api.deps import CollectionDep, CurrentAuth, IdempotencyKey, TranscriptionDep

router = APIRouter(prefix="/audio", tags=["audio"])

ResponseFormat = Literal["json", "text", "verbose_json"]

SAMPLE_HEADER = "X-IntelliAI-Sample"


@router.post("/transcriptions")
async def create_transcription(
    auth: CurrentAuth,
    service: TranscriptionDep,
    collection: CollectionDep,
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()],
    idempotency_key: IdempotencyKey,
    language: Annotated[str | None, Form()] = None,
    response_format: Annotated[ResponseFormat, Form()] = "json",
) -> Response:
    started = time.monotonic()
    audio = await file.read()
    outcome = await service.transcribe(
        auth=auth,
        public_model_id=model,
        audio=audio,
        language=language,
        idempotency_key=idempotency_key,
    )
    # Collection AFTER success, never able to fail the request: a None
    # here means "not collected" for any reason (switch, consent,
    # storage), and the customer's response is identical either way
    # except for the header's presence.
    sample_id = await collection.collect(
        auth=auth,
        audio=audio,
        content_type=file.content_type,
        filename=file.filename,
        requested_language=language,
        idempotency_key=idempotency_key,
        outcome=outcome,
        request_started=started,
    )
    headers = {SAMPLE_HEADER: sample_id} if sample_id is not None else None
    result = outcome.result
    if response_format == "text":
        return PlainTextResponse(result.text, headers=headers)
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
    return JSONResponse(payload, headers=headers)
