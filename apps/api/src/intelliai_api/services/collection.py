"""DataCollectionService — where consented speech becomes a dataset.

Charter: owns the collection decision (kill switch, storage presence,
tenant consent), the object write, and the sample row + lifecycle event.
It never decides transcription, never touches billing, and NEVER raises
into the request path: customer success is always more important than
dataset collection, so every failure here is a structured log and a
``None``, and the customer's 200 stands.

Order of operations, fixed by design:

1. gates (enabled → storage → consent) — any miss returns None silently
2. mint the sample id, derive the deterministic object key from it
3. PUT the ORIGINAL bytes (slow I/O, no DB state yet — a failed put
   leaves nothing to clean up)
4. row + ``collected`` event inside a savepoint — a row failure rolls
   back to the savepoint, never poisoning the outer transaction that
   already holds the customer's usage event; the now-orphaned object is
   named in the log for the future lifecycle sweep
"""

import time
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import ResourceNotFoundError
from intelliai_api.core.time import utc_now
from intelliai_api.db.base import generate_public_id
from intelliai_api.db.models import ClientSource, CorrectionSource, SpeechSample
from intelliai_api.db.repositories import SpeechSampleRepository
from intelliai_api.registry import normalize_language
from intelliai_api.services.auth import AuthContext
from intelliai_api.services.transcription import TranscriptionOutcome
from intelliai_api.storage import ObjectStorage, StorageWriteError, object_key

logger = structlog.get_logger("intelliai_api.collection")


class DataCollectionService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage | None,
        *,
        enabled: bool,
    ) -> None:
        self._session = session
        self._storage = storage
        self._enabled = enabled
        self._samples = SpeechSampleRepository(session)

    async def collect(
        self,
        *,
        auth: AuthContext,
        audio: bytes,
        content_type: str | None,
        filename: str | None,
        requested_language: str | None,
        idempotency_key: str | None,
        outcome: TranscriptionOutcome,
        request_started: float,
        client_source: ClientSource = ClientSource.API,
        client_version: str | None = None,
        app_locale: str | None = None,
        contribute: bool = True,
    ) -> str | None:
        """Store one consented sample; return its public id, or None.

        ``request_started`` is a ``time.monotonic()`` reading taken at
        route entry — ``processing_time_ms`` on the collected event spans
        the whole request up to the moment collection finishes. It is
        operational metadata about the collection act, not a benchmark
        metric, which is why it lives in the event's detail and not in a
        metrics system.

        ``contribute`` is the caller's per-request opt-out (default True
        preserves every existing caller). It can only NARROW collection:
        the organization's ``data_consent`` remains the ceiling checked
        first, so a client can never opt IN to collection the tenant has
        not consented to.
        """
        try:
            return await self._collect(
                auth=auth,
                audio=audio,
                content_type=content_type,
                filename=filename,
                requested_language=requested_language,
                idempotency_key=idempotency_key,
                outcome=outcome,
                request_started=request_started,
                client_source=client_source,
                client_version=client_version,
                app_locale=app_locale,
                contribute=contribute,
            )
        except Exception:
            # The backstop for the one law this service exists to keep:
            # no defect in collection may ever surface to the customer.
            logger.exception(
                "collection.failed",
                organization_id=auth.organization_public_id,
            )
            return None

    async def _collect(
        self,
        *,
        auth: AuthContext,
        audio: bytes,
        content_type: str | None,
        filename: str | None,
        requested_language: str | None,
        idempotency_key: str | None,
        outcome: TranscriptionOutcome,
        request_started: float,
        client_source: ClientSource,
        client_version: str | None,
        app_locale: str | None,
        contribute: bool,
    ) -> str | None:
        # Gates, cheapest first. Silent by design: absence of collection
        # is a normal outcome, not an error.
        if not self._enabled or self._storage is None:
            return None
        organization = auth.organization
        # Organization consent is the CEILING — checked before the
        # per-request preference, so contribution can only narrow, never
        # widen, what the tenant consented to.
        if not organization.data_consent:
            return None
        # Per-request opt-out: this caller (e.g. a keyboard user who
        # turned "Improve IntelliAI STT" off) declined for THIS request.
        if not contribute:
            return None

        # The id is minted BEFORE the row exists because the object key
        # embeds it — the deterministic layout couples object and row by
        # identity, not by lookup.
        sample_public_id = generate_public_id("smp")
        now = utc_now()
        key = object_key(
            organization_public_id=organization.public_id,
            sample_public_id=sample_public_id,
            year=now.year,
            month=now.month,
            mime_type=content_type,
            filename=filename,
        )

        # ORIGINAL bytes, exactly as received — never the pipeline's
        # canonical rendering (model-agnosticism guardrail).
        try:
            await self._storage.put(key=key, data=audio, content_type=content_type)
        except StorageWriteError as exc:
            logger.warning(
                "collection.store_failed",
                organization_id=organization.public_id,
                key=key,
                error=str(exc),
            )
            return None

        lineage: dict[str, Any] = dict(outcome.lineage)
        try:
            async with self._session.begin_nested():
                sample = await self._samples.create(
                    organization_id=organization.id,
                    public_id=sample_public_id,
                    audio_key=key,
                    duration_seconds=Decimal(str(round(outcome.audio_seconds, 3))),
                    file_size_bytes=len(audio),
                    original_transcript=outcome.result.text,
                    model_name=str(lineage.get("artifact") or outcome.public_model_id),
                    model_version=_version_of(lineage),
                    lineage=lineage,
                    requested_language=requested_language,
                    routed_language=normalize_language(requested_language),
                    detected_language=outcome.result.language,
                    mime_type=content_type,
                    client_source=client_source,
                    client_version=client_version,
                    app_locale=app_locale,
                    user_identifier=auth.key_public_id,
                    consented_at=organization.data_consented_at or now,
                    consent_reference=organization.consent_reference,
                    idempotency_key=idempotency_key,
                )
                await self._samples.record_event(
                    sample.id,
                    "collected",
                    detail={
                        "processing_time_ms": _elapsed_ms(request_started),
                        "client_source": client_source.value,
                    },
                )
        except Exception:
            # The object above is now orphaned; name it so the future
            # lifecycle sweep can find it. The savepoint rollback keeps
            # the outer transaction — and the usage event in it — intact.
            logger.exception(
                "collection.record_failed",
                organization_id=organization.public_id,
                orphaned_key=key,
            )
            return None

        logger.info(
            "collection.stored",
            sample_id=sample_public_id,
            organization_id=organization.public_id,
            key=key,
            audio_seconds=round(outcome.audio_seconds, 3),
            language=outcome.result.language,
        )
        return sample_public_id

    async def correct(
        self,
        *,
        auth: AuthContext,
        sample_public_id: str,
        corrected_text: str,
        source: CorrectionSource = CorrectionSource.USER,
    ) -> SpeechSample:
        """Evolve ``current_transcript``; the original stays immutable.

        Unlike :meth:`collect`, this RAISES: correction is a customer-
        facing operation with a contract (404s, validation), not a silent
        side effect. Last write wins — the author is the same human
        refining an edit, and the machine's original is preserved on the
        row, so nothing is ever lost. Org-scoped: a foreign tenant's
        sample does not exist from this caller's point of view (404,
        never 403 — no existence disclosure).
        """
        sample = await self._samples.get_for_organization(auth.organization_id, sample_public_id)
        if sample is None:
            raise ResourceNotFoundError(
                f"No speech sample {sample_public_id!r} exists in this organization.",
                code="sample_not_found",
                param="sample_id",
            )
        sample.current_transcript = corrected_text
        sample.last_modified_at = utc_now()
        await self._session.flush()
        await self._samples.record_event(
            sample.id,
            "corrected",
            detail={"correction_source": source.value},
        )
        logger.info(
            "collection.corrected",
            sample_id=sample.public_id,
            organization_id=auth.organization_public_id,
            correction_source=source.value,
        )
        return sample


def _version_of(lineage: dict[str, Any]) -> str | None:
    version = lineage.get("artifact_version")
    return None if version is None else str(version)


def _elapsed_ms(request_started: float) -> int:
    return max(0, int((time.monotonic() - request_started) * 1000))
