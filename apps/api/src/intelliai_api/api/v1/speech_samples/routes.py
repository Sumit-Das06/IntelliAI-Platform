"""Speech sample read APIs — the minimal surface the console's Speech
Samples page demanded, and nothing more (UI-driven by decree).

Three reads, all org-scoped: list (newest first), detail with the
lifecycle timeline, and the original audio bytes. The response shape is
the PUBLIC view of a sample: transcripts, languages, client provenance,
consent snapshot. Producer internals — model names, versions, lineage,
object keys — never appear here; the public product rule applies to API
bodies exactly as it applies to pages.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel

from intelliai_api.api.deps import CurrentAuth, ObjectStorageDep, SessionDep
from intelliai_api.core.errors import ResourceNotFoundError
from intelliai_api.db.models import SpeechSample
from intelliai_api.db.repositories import SpeechSampleRepository
from intelliai_api.storage import StorageObjectMissingError

router = APIRouter(prefix="/speech-samples", tags=["speech-samples"])


class SampleEventResponse(BaseModel):
    event: str
    occurred_at: datetime


class SpeechSampleResponse(BaseModel):
    id: str
    created_at: datetime
    status: str
    requested_language: str | None
    detected_language: str | None
    client_source: str
    client_version: str | None
    duration_seconds: float
    mime_type: str | None
    file_size_bytes: int
    original_transcript: str
    current_transcript: str
    last_modified_at: datetime | None
    consent_reference: str | None


class SpeechSampleDetailResponse(SpeechSampleResponse):
    events: list[SampleEventResponse]


class SpeechSampleListResponse(BaseModel):
    # Envelope (not a bare array) so pagination fields can arrive additively.
    data: list[SpeechSampleResponse]


def _to_response(sample: SpeechSample) -> SpeechSampleResponse:
    return SpeechSampleResponse(
        id=sample.public_id,
        created_at=sample.created_at,
        status=sample.status.value,
        requested_language=sample.requested_language,
        detected_language=sample.detected_language,
        client_source=sample.client_source.value,
        client_version=sample.client_version,
        duration_seconds=float(sample.duration_seconds),
        mime_type=sample.mime_type,
        file_size_bytes=sample.file_size_bytes,
        original_transcript=sample.original_transcript,
        current_transcript=sample.current_transcript,
        last_modified_at=sample.last_modified_at,
        consent_reference=sample.consent_reference,
    )


async def _sample_or_404(
    session: SessionDep, auth: CurrentAuth, sample_id: str
) -> tuple[SpeechSampleRepository, SpeechSample]:
    repository = SpeechSampleRepository(session)
    sample = await repository.get_for_organization(auth.organization_id, sample_id)
    if sample is None:
        raise ResourceNotFoundError(
            f"No speech sample {sample_id!r} exists in this organization.",
            code="sample_not_found",
            param="sample_id",
        )
    return repository, sample


@router.get("")
async def list_speech_samples(
    auth: CurrentAuth,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SpeechSampleListResponse:
    """The organization's consented samples, newest first."""
    repository = SpeechSampleRepository(session)
    samples = await repository.list_for_organization(auth.organization_id, limit=limit)
    return SpeechSampleListResponse(data=[_to_response(sample) for sample in samples])


@router.get("/{sample_id}")
async def get_speech_sample(
    sample_id: str, auth: CurrentAuth, session: SessionDep
) -> SpeechSampleDetailResponse:
    """One sample with its lifecycle timeline, oldest event first."""
    repository, sample = await _sample_or_404(session, auth, sample_id)
    events = await repository.list_events(sample.id)
    return SpeechSampleDetailResponse(
        **_to_response(sample).model_dump(),
        events=[
            SampleEventResponse(event=event.event, occurred_at=event.occurred_at)
            for event in events
        ],
    )


@router.get("/{sample_id}/audio")
async def get_speech_sample_audio(
    sample_id: str, auth: CurrentAuth, session: SessionDep, storage: ObjectStorageDep
) -> Response:
    """The ORIGINAL audio bytes, exactly as the client's device produced
    them. ``private, no-store``: consented voice data never lingers in a
    shared cache."""
    _repository, sample = await _sample_or_404(session, auth, sample_id)
    audio_missing = ResourceNotFoundError(
        f"The audio for sample {sample_id!r} is not available.",
        code="sample_audio_not_found",
        param="sample_id",
    )
    # Storage disabled (kill switch) means the row exists but its bytes
    # are unreachable from this process — absent, from the caller's view.
    if storage is None:
        raise audio_missing
    try:
        data = await storage.get(key=sample.audio_key)
    except StorageObjectMissingError as exc:
        raise audio_missing from exc
    return Response(
        content=data,
        media_type=sample.mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )
