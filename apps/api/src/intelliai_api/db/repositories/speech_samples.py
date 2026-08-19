"""Speech sample persistence — the flywheel's rows, org-scoped by law."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
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
        public_id: str | None = None,
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
        served_transcript: str | None = None,
    ) -> SpeechSample:
        """Create a sample in its birth state.

        ``current_transcript`` starts as WHAT THE USER WAS SHOWN, by rule,
        not by caller choice: ``original_transcript`` is the immutable
        machine output, and when a backend text post-stage (punctuation,
        M30) rewrote what was served, ``served_transcript`` carries that
        text and the current one evolves from IT. With no stage (the
        overwhelming default), served is None and current starts equal to
        original — the pre-M30 law unchanged. Status starts at the column
        default (collected); the caller records the matching lifecycle
        event via :meth:`record_event`. ``public_id`` may be supplied when
        the caller minted it first (the object key embeds it); omitted,
        the model default mints one.
        """
        minted: dict[str, str] = {"public_id": public_id} if public_id is not None else {}
        sample = SpeechSample(
            **minted,
            organization_id=organization_id,
            audio_key=audio_key,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size_bytes,
            original_transcript=original_transcript,
            current_transcript=served_transcript or original_transcript,
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

    async def list_for_user_identifier(
        self, organization_id: int, user_identifier: str
    ) -> Sequence[SpeechSample]:
        """Every sample this identity contributed, org-scoped.

        The erasure unit for a person's deletion request: under the pilot's
        one-key-per-person convention (docs/DATA_GOVERNANCE.md),
        ``user_identifier`` IS the person, and this list is exactly their
        data. Unbounded on purpose — erasure must see everything, and a
        pilot tenant's sample count is CLI-scale, not pagination-scale.
        """
        result = await self._session.execute(
            select(SpeechSample).where(
                SpeechSample.organization_id == organization_id,
                SpeechSample.user_identifier == user_identifier,
            )
        )
        return result.scalars().all()

    async def list_all_for_organization(self, organization_id: int) -> Sequence[SpeechSample]:
        """The tenant's complete collected data — the org-erasure unit.
        Unbounded like the per-person list, for the same reason."""
        result = await self._session.execute(
            select(SpeechSample).where(SpeechSample.organization_id == organization_id)
        )
        return result.scalars().all()

    async def delete_by_ids(self, sample_ids: Sequence[int]) -> int:
        """Hard-delete sample rows; events and dataset memberships follow
        via the schema's ON DELETE CASCADE (the privacy topology).

        A core DELETE on purpose: ORM-level deletion would try to manage
        the children itself, and the children's non-nullable FKs make the
        database's own cascade the only correct authority. Erasure is the
        single caller — nothing else on the platform deletes samples.
        """
        if not sample_ids:
            return 0
        result = await self._session.execute(
            delete(SpeechSample).where(SpeechSample.id.in_(list(sample_ids)))
        )
        return max(0, cast(CursorResult[Any], result).rowcount)

    async def list_events(self, sample_id: int) -> Sequence[SpeechSampleEvent]:
        """The sample's lifecycle history, oldest first — timeline order."""
        result = await self._session.execute(
            select(SpeechSampleEvent)
            .where(SpeechSampleEvent.sample_id == sample_id)
            .order_by(SpeechSampleEvent.occurred_at.asc(), SpeechSampleEvent.id.asc())
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
