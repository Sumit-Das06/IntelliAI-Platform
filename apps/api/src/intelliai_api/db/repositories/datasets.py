"""Dataset persistence — definitions, immutable versions, and the ONE
eligibility query.

The consistency law lives here: :meth:`DatasetRepository.eligible_samples`
is the single builder of the eligibility WHERE clause, and BOTH the
preview aggregates and the freeze's ``INSERT … SELECT`` are built from
it. There is structurally no second implementation to drift, so the
preview can never promise a membership the freeze doesn't deliver.

Eligibility, from database state only (never object reads):

- the sample belongs to the organization (isolation, always first);
- its lifecycle is not ``rejected``/``archived`` — the only disqualifying
  states that exist today. No review workflow promotes samples to
  ``accepted`` yet, so requiring it would freeze empty versions forever;
  when review arrives, tightening happens HERE, in one place;
- audio is present by metadata: a stored key, more than zero bytes,
  more than zero measured seconds (object existence is the future
  export pipeline's fail-fast concern — eligibility never does I/O);
- a usable training transcript: ``current_transcript`` non-blank;
- a consent snapshot exists (``consented_at``) — structurally true for
  every stored sample (collection refuses unconsented storage), kept in
  the predicate as executable documentation of the law.

"Corrected" is defined exactly as the console defines it —
``current_transcript != original_transcript`` — so a "Corrected ✓"
badge on the Speech Samples page and a corrected count on a dataset can
never disagree. Language matches what the console shows for a sample:
detected first, else requested.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Select,
    case,
    func,
    insert,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased

from intelliai_api.db.models import (
    ClientSource,
    Dataset,
    DatasetVersion,
    DatasetVersionSample,
    SampleStatus,
    SpeechSample,
    SpeechSampleEvent,
)

#: What a breakdown key actually is: a real column (client_source) or
#: a computed expression (the coalesced language).
BreakdownKey = InstrumentedAttribute[Any] | ColumnElement[Any]

#: Lifecycle states a sample may be in and still enter a dataset —
#: everything except the two that mean "keep, never train on".
ELIGIBLE_STATUSES = (
    SampleStatus.COLLECTED,
    SampleStatus.VALIDATED,
    SampleStatus.ACCEPTED,
    SampleStatus.TRAINING,
)

#: The sample-side lineage event appended when a version freezes — the
#: vocabulary the speech_sample_events design reserved for this phase.
INCLUDED_IN_DATASET = "included_in_dataset"


def _sample_language() -> ColumnElement[str | None]:
    """The language a sample is presented under, console-consistent:
    detected first, else requested. NULL means neither was recorded."""
    return func.coalesce(SpeechSample.detected_language, SpeechSample.requested_language)


def _sample_corrected() -> ColumnElement[bool]:
    """Corrected exactly as the console badges it: the text changed."""
    return SpeechSample.current_transcript != SpeechSample.original_transcript


@dataclass(frozen=True)
class DatasetCriteria:
    """The validated filter vocabulary — the only criteria that exist.

    Every field is optional; ``None`` means "don't filter on this".
    The API layer validates shape/values; this value object translates
    them to SQL in exactly one place. Stored on datasets (and snapshotted
    onto versions) via :meth:`to_dict`, rebuilt via :meth:`from_dict`.
    """

    language: str | None = None
    client_source: ClientSource | None = None
    corrected: bool | None = None
    collected_from: date | None = None
    collected_until: date | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-storable form; unset criteria are omitted, not null-padded."""
        stored: dict[str, Any] = {}
        if self.language is not None:
            stored["language"] = self.language
        if self.client_source is not None:
            stored["client_source"] = self.client_source.value
        if self.corrected is not None:
            stored["corrected"] = self.corrected
        if self.collected_from is not None:
            stored["collected_from"] = self.collected_from.isoformat()
        if self.collected_until is not None:
            stored["collected_until"] = self.collected_until.isoformat()
        return stored

    @classmethod
    def from_dict(cls, stored: dict[str, Any]) -> "DatasetCriteria":
        """Rebuild from the JSONB column. Trusts the writer (ourselves):
        unknown keys are ignored rather than failing a read forever."""
        client = stored.get("client_source")
        collected_from = stored.get("collected_from")
        collected_until = stored.get("collected_until")
        return cls(
            language=stored.get("language"),
            client_source=ClientSource(client) if client is not None else None,
            corrected=stored.get("corrected"),
            collected_from=date.fromisoformat(collected_from) if collected_from else None,
            collected_until=date.fromisoformat(collected_until) if collected_until else None,
        )

    def predicates(self) -> list[ColumnElement[bool]]:
        """The criteria as SQL — used by nothing but eligible_samples()."""
        conditions: list[ColumnElement[bool]] = []
        if self.language is not None:
            conditions.append(_sample_language() == self.language)
        if self.client_source is not None:
            conditions.append(SpeechSample.client_source == self.client_source)
        if self.corrected is not None:
            corrected = _sample_corrected()
            conditions.append(corrected if self.corrected else ~corrected)
        if self.collected_from is not None:
            moment = datetime.combine(self.collected_from, time.min, tzinfo=UTC)
            conditions.append(SpeechSample.created_at >= moment)
        if self.collected_until is not None:
            # A bare date names a whole day (usage API convention): until
            # the 8th means THROUGH the 8th, so the boundary is the 9th.
            moment = datetime.combine(self.collected_until, time.min, tzinfo=UTC) + timedelta(
                days=1
            )
            conditions.append(SpeechSample.created_at < moment)
        return conditions


@dataclass(frozen=True)
class EligibilityBreakdown:
    """One slice of the eligible set (per language, per client source)."""

    key: str | None
    samples: int
    duration_seconds: Decimal


@dataclass(frozen=True)
class EligibilityPreview:
    """What a version would freeze right now — same rules, same numbers."""

    matching_samples: int  # met the criteria (before eligibility gates)
    eligible_samples: int  # would enter a version created this instant
    corrected_samples: int
    duration_seconds: Decimal
    languages: list[EligibilityBreakdown]
    client_sources: list[EligibilityBreakdown]


@dataclass(frozen=True)
class MembershipStatistics:
    """Aggregates of a version's FROZEN membership, computed from the
    membership rows themselves — never from a re-run of the filter."""

    sample_count: int
    duration_seconds: Decimal
    corrected_samples: int
    languages: list[EligibilityBreakdown]
    client_sources: list[EligibilityBreakdown]


class DatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Datasets ─────────────────────────────────────────────────────

    async def create(
        self,
        *,
        organization_id: int,
        name: str,
        description: str | None,
        criteria: DatasetCriteria,
    ) -> Dataset:
        dataset = Dataset(
            organization_id=organization_id,
            name=name,
            description=description,
            criteria=criteria.to_dict(),
        )
        self._session.add(dataset)
        # flush, never commit: the transaction boundary belongs to the
        # caller (request scope), exactly like every other repository.
        await self._session.flush()
        return dataset

    async def get_for_organization(
        self, organization_id: int, public_id: str, *, for_update: bool = False
    ) -> Dataset | None:
        """Org-scoped fetch: a foreign org's dataset does not exist here.

        ``for_update`` locks the dataset row, serializing concurrent
        version creation — the lock, plus the (dataset_id,
        version_number) uniqueness backstop, is the whole concurrency
        story for version numbering.
        """
        query = select(Dataset).where(
            Dataset.organization_id == organization_id,
            Dataset.public_id == public_id,
        )
        if for_update:
            query = query.with_for_update()
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: int) -> Sequence[Dataset]:
        """Newest first, like every other console-facing list."""
        result = await self._session.execute(
            select(Dataset)
            .where(Dataset.organization_id == organization_id)
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
        )
        return result.scalars().all()

    # ── Eligibility: the single source of truth ─────────────────────

    def eligible_samples(
        self, organization_id: int, criteria: DatasetCriteria
    ) -> Select[tuple[int]]:
        """THE eligibility query — sample ids that would enter a version
        frozen right now. Preview aggregates wrap it; the freeze inserts
        from it. Nothing else may re-state these rules."""
        return select(SpeechSample.id).where(
            SpeechSample.organization_id == organization_id,
            SpeechSample.status.in_(ELIGIBLE_STATUSES),
            SpeechSample.audio_key != "",
            SpeechSample.file_size_bytes > 0,
            SpeechSample.duration_seconds > 0,
            func.btrim(SpeechSample.current_transcript) != "",
            # Structurally always true (collection refuses unconsented
            # storage); kept as executable documentation of the law.
            SpeechSample.consented_at.is_not(None),
            *criteria.predicates(),
        )

    async def preview(self, organization_id: int, criteria: DatasetCriteria) -> EligibilityPreview:
        """What would freeze right now, plus how many samples matched the
        criteria but failed an eligibility gate (the honest difference)."""
        eligible = self.eligible_samples(organization_id, criteria).subquery()

        totals = (
            await self._session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(SpeechSample.duration_seconds), 0),
                    func.coalesce(func.sum(case((_sample_corrected(), 1), else_=0)), 0),
                ).where(SpeechSample.id.in_(select(eligible.c.id)))
            )
        ).one()

        matching = (
            await self._session.execute(
                select(func.count()).where(
                    SpeechSample.organization_id == organization_id,
                    *criteria.predicates(),
                )
            )
        ).scalar_one()

        languages = await self._breakdown(
            _sample_language(), SpeechSample.id.in_(select(eligible.c.id))
        )
        client_sources = await self._breakdown(
            SpeechSample.client_source, SpeechSample.id.in_(select(eligible.c.id))
        )

        return EligibilityPreview(
            matching_samples=int(matching),
            eligible_samples=int(totals[0]),
            corrected_samples=int(totals[2]),
            duration_seconds=Decimal(totals[1]),
            languages=languages,
            client_sources=client_sources,
        )

    async def _breakdown(
        self, key: BreakdownKey, condition: ColumnElement[bool]
    ) -> list[EligibilityBreakdown]:
        rows = (
            await self._session.execute(
                select(
                    key,
                    func.count(),
                    func.coalesce(func.sum(SpeechSample.duration_seconds), 0),
                )
                .where(condition)
                .group_by(key)
                .order_by(func.count().desc())
            )
        ).all()
        return [
            EligibilityBreakdown(
                key=value.value if isinstance(value, ClientSource) else value,
                samples=int(count),
                duration_seconds=Decimal(seconds),
            )
            for value, count, seconds in rows
        ]

    # ── Versions: frozen once, never edited ──────────────────────────

    async def has_eligible_samples(self, organization_id: int, criteria: DatasetCriteria) -> bool:
        result = await self._session.execute(
            select(self.eligible_samples(organization_id, criteria).exists())
        )
        return bool(result.scalar_one())

    async def next_version_number(self, dataset_id: int) -> int:
        """Call under the dataset's FOR UPDATE lock, or the uniqueness
        constraint will veto the race the lock exists to prevent."""
        result = await self._session.execute(
            select(func.coalesce(func.max(DatasetVersion.version_number), 0)).where(
                DatasetVersion.dataset_id == dataset_id
            )
        )
        return int(result.scalar_one()) + 1

    async def create_version(
        self,
        *,
        dataset_id: int,
        version_number: int,
        created_by: str,
        criteria: DatasetCriteria,
    ) -> DatasetVersion:
        """The version row in its birth state; membership and the frozen
        aggregates are written by freeze_membership/apply_statistics
        inside the same transaction."""
        version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=version_number,
            created_by=created_by,
            sample_count=0,
            duration_seconds=Decimal("0"),
            statistics={},
            criteria=criteria.to_dict(),
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def freeze_membership(
        self, version_id: int, organization_id: int, criteria: DatasetCriteria
    ) -> None:
        """Membership as one INSERT…SELECT from THE eligibility query —
        the set is decided by the database in one statement, pinning
        each sample's current_transcript as its training text."""
        eligible = self.eligible_samples(organization_id, criteria)
        await self._session.execute(
            insert(DatasetVersionSample).from_select(
                ["dataset_version_id", "speech_sample_id", "training_transcript"],
                select(
                    literal(version_id),
                    SpeechSample.id,
                    SpeechSample.current_transcript,
                ).where(SpeechSample.id.in_(eligible)),
            )
        )

    async def membership_statistics(self, version_id: int) -> MembershipStatistics:
        """Aggregates of what was ACTUALLY frozen — computed from the
        membership rows, so the stored numbers cannot disagree with the
        stored membership. Corrected state compares the PINNED text to
        the sample's immutable original."""
        joined = DatasetVersionSample.speech_sample_id == SpeechSample.id
        member = DatasetVersionSample.dataset_version_id == version_id
        pinned_corrected = (
            DatasetVersionSample.training_transcript != SpeechSample.original_transcript
        )

        totals = (
            await self._session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(SpeechSample.duration_seconds), 0),
                    func.coalesce(func.sum(case((pinned_corrected, 1), else_=0)), 0),
                )
                .select_from(DatasetVersionSample)
                .join(SpeechSample, joined)
                .where(member)
            )
        ).one()

        async def grouped(key: BreakdownKey) -> list[EligibilityBreakdown]:
            rows = (
                await self._session.execute(
                    select(
                        key,
                        func.count(),
                        func.coalesce(func.sum(SpeechSample.duration_seconds), 0),
                    )
                    .select_from(DatasetVersionSample)
                    .join(SpeechSample, joined)
                    .where(member)
                    .group_by(key)
                    .order_by(func.count().desc())
                )
            ).all()
            return [
                EligibilityBreakdown(
                    key=value.value if isinstance(value, ClientSource) else value,
                    samples=int(count),
                    duration_seconds=Decimal(seconds),
                )
                for value, count, seconds in rows
            ]

        return MembershipStatistics(
            sample_count=int(totals[0]),
            duration_seconds=Decimal(totals[1]),
            corrected_samples=int(totals[2]),
            languages=await grouped(_sample_language()),
            client_sources=await grouped(SpeechSample.client_source),
        )

    async def record_inclusion_events(
        self, version_id: int, *, detail: dict[str, Any], occurred_at: datetime
    ) -> None:
        """Sample-side lineage: append ``included_in_dataset`` to every
        member's history in one INSERT…SELECT. Events are the samples'
        append-only truth — status is deliberately NOT touched (the
        ``training`` status belongs to actual future training runs)."""
        await self._session.execute(
            insert(SpeechSampleEvent).from_select(
                ["sample_id", "event", "detail", "occurred_at"],
                select(
                    DatasetVersionSample.speech_sample_id,
                    literal(INCLUDED_IN_DATASET),
                    literal(detail, type_=JSONB),
                    literal(occurred_at, type_=DateTime(timezone=True)),
                ).where(DatasetVersionSample.dataset_version_id == version_id),
            )
        )

    async def list_versions(self, dataset_id: int) -> Sequence[DatasetVersion]:
        """Latest first — the version you would train on next is on top."""
        result = await self._session.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
        )
        return result.scalars().all()

    async def get_version(self, dataset_id: int, version_public_id: str) -> DatasetVersion | None:
        """Scoped through the dataset — org isolation arrives with the
        dataset lookup, and a foreign version does not exist here."""
        result = await self._session.execute(
            select(DatasetVersion).where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.public_id == version_public_id,
            )
        )
        return result.scalar_one_or_none()

    async def latest_versions(self, dataset_ids: Sequence[int]) -> dict[int, DatasetVersion]:
        """The newest version per dataset, for list rows — one query."""
        if not dataset_ids:
            return {}
        ranked = (
            select(
                DatasetVersion,
                func.row_number()
                .over(
                    partition_by=DatasetVersion.dataset_id,
                    order_by=DatasetVersion.version_number.desc(),
                )
                .label("recency"),
            )
            .where(DatasetVersion.dataset_id.in_(dataset_ids))
            .subquery()
        )
        newest = aliased(DatasetVersion, ranked)
        versions = (
            (await self._session.execute(select(newest).where(ranked.c.recency == 1)))
            .scalars()
            .all()
        )
        return {version.dataset_id: version for version in versions}

    async def version_counts(self, dataset_ids: Sequence[int]) -> dict[int, int]:
        if not dataset_ids:
            return {}
        rows = (
            await self._session.execute(
                select(DatasetVersion.dataset_id, func.count())
                .where(DatasetVersion.dataset_id.in_(dataset_ids))
                .group_by(DatasetVersion.dataset_id)
            )
        ).all()
        return {dataset_id: int(count) for dataset_id, count in rows}

    async def sample_ids_for_version(self, version_id: int) -> list[int]:
        """The frozen membership, by internal sample id — test/audit seam."""
        result = await self._session.execute(
            select(DatasetVersionSample.speech_sample_id)
            .where(DatasetVersionSample.dataset_version_id == version_id)
            .order_by(DatasetVersionSample.speech_sample_id)
        )
        return [int(sample_id) for sample_id in result.scalars().all()]
