"""Speech sample persistence — the flywheel's rows, org-scoped by law."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.time import utc_now
from intelliai_api.db.models import ClientSource, SpeechSample, SpeechSampleEvent


class SpeechSampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: int,
        audio_key: str,
        duration_seconds: Decimal,
        file_size_bytes: int,
        original_transcript: str,
        model_name: str,
        client_source: ClientSource,
        user_identifier: str,
        consented_at: datetime,
        consent_reference: str | None = None,
        model_version: str | None = None,
        lineage: dict[str, Any] | None = None,
        requested_language: str | None = None,
        routed_language: str | None = None,
        detected_language: str | None = None,
        mime_type: str | None = None,
        codec: str | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
        client_version: str | None = None,
        app_locale: str | None = None,
        idempotency_key: str | None = None,
    ) -> SpeechSample:
        """Create a sample in its birth state.

        ``current_transcript`` starts equal to ``original_transcript`` by
        rule, not by caller choice: the original is the immutable machine
        output and the current one evolves from it. Status starts at the
        column default (collected); the caller records the matching
        lifecycle event via :meth:`record_event`.
        """
        sample = SpeechSample(
            organization_id=organization_id,
            audio_key=audio_key,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size_bytes,
            original_transcript=original_transcript,
            current_transcript=original_transcript,
            model_name=model_name,
            model_version=model_version,
            lineage=lineage or {},
            requested_language=requested_language,
            routed_language=routed_language,
            detected_language=detected_language,
            mime_type=mime_type,
            codec=codec,
            sample_rate=sample_rate,
            channels=channels,
            client_source=client_source,
            client_version=client_version,
            app_locale=app_locale,
            user_identifier=user_identifier,
            consented_at=consented_at,
            consent_reference=consent_reference,
            idempotency_key=idempotency_key,
        )
        self._session.add(sample)
        # flush, never commit: the transaction boundary belongs to the
        # caller (request scope), exactly like every other repository.
        await self._session.flush()
        return sample

    async def get_for_organization(
        self, organization_id: int, public_id: str
    ) -> SpeechSample | None:
        """Org-scoped fetch: a foreign org's sample does not exist here."""
        result = await self._session.execute(
            select(SpeechSample).where(
                SpeechSample.organization_id == organization_id,
                SpeechSample.public_id == public_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: int, *, limit: int = 50
    ) -> Sequence[SpeechSample]:
        """Newest first — the shape the future console history reads."""
        result = await self._session.execute(
            select(SpeechSample)
            .where(SpeechSample.organization_id == organization_id)
            .order_by(SpeechSample.created_at.desc(), SpeechSample.id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def record_event(
        self,
        sample_id: int,
        event: str,
        *,
        detail: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> SpeechSampleEvent:
        """Append one lifecycle event. Append is the only verb this table
        has — history is never updated and never deleted."""
        row = SpeechSampleEvent(
            sample_id=sample_id,
            event=event,
            detail=detail or {},
            occurred_at=occurred_at or utc_now(),
        )
        self._session.add(row)
        await self._session.flush()
        return row
