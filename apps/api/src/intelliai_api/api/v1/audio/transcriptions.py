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
from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from intelliai_api.api.deps import CollectionDep, CurrentAuth, IdempotencyKey, TranscriptionDep
from intelliai_api.db.models import ClientSource

router = APIRouter(prefix="/audio", tags=["audio"])

ResponseFormat = Literal["json", "text", "verbose_json"]

SAMPLE_HEADER = "X-IntelliAI-Sample"
CLIENT_HEADER = "X-IntelliAI-Client"
CONTRIBUTION_HEADER = "X-IntelliAI-Contribution"


def _parse_client(header: str | None) -> tuple[ClientSource, str | None]:
    """``source[/version]`` — e.g. ``web`` or ``keyboard/1.4.0``.

    A labelling header must never be able to fail a transcription:
    absent, unknown, or malformed values fall back to the API default.
    """
    if header is None or not header.strip():
        return ClientSource.API, None
    source_part, _, version_part = header.strip().partition("/")
    try:
        source = ClientSource(source_part.strip().lower())
    except ValueError:
        return ClientSource.API, None
    return source, version_part.strip()[:64] or None


def _wants_contribution(header: str | None) -> bool:
    """Per-request training-data opt-out. Only the exact value ``off``
    (case-insensitive) opts out; absent, unknown, or malformed values
    preserve the existing behavior. Like the client label, this metadata
    header can only NARROW collection and must never fail a request —
    organization consent remains the ceiling enforced in the collection
    service."""
    return header is None or header.strip().lower() != "off"


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
    client: Annotated[str | None, Header(alias=CLIENT_HEADER)] = None,
    contribution: Annotated[str | None, Header(alias=CONTRIBUTION_HEADER)] = None,
) -> Response:
    started = time.monotonic()
    client_source, client_version = _parse_client(client)
    contribute = _wants_contribution(contribution)
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
        client_source=client_source,
        client_version=client_version,
        contribute=contribute,
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


class CorrectionRequest(BaseModel):
    """The user's improved transcript. Bounded generously: transcripts of
    a ≤25 MiB clip are KB-scale; 20k chars refuses only abuse."""

    corrected_text: str = Field(min_length=1, max_length=20_000)


class CorrectionResponse(BaseModel):
    id: str
    corrected_text: str
    last_modified_at: datetime


@router.post("/transcriptions/{sample_id}/correction")
async def correct_transcription(
    sample_id: str,
    body: CorrectionRequest,
    auth: CurrentAuth,
    collection: CollectionDep,
) -> CorrectionResponse:
    """Attach a human correction to a collected sample.

    The first source of human-labelled data: ``current_transcript``
    evolves, the machine's ``original_transcript`` never changes, and the
    lifecycle history gains a ``corrected`` event. Last write wins —
    re-correcting is a legitimate act, not a conflict.
    """
    sample = await collection.correct(
        auth=auth,
        sample_public_id=sample_id,
        corrected_text=body.corrected_text,
    )
    return CorrectionResponse(
        id=sample.public_id,
        corrected_text=sample.current_transcript,
        # The service always stamps it before returning; the cast states
        # that contract to the type checker without a runtime crutch.
        last_modified_at=cast(datetime, sample.last_modified_at),
    )
