"""DatasetService — where eligible speech becomes reproducible versions.

Charter: owns the dataset lifecycle rules (create, archive, freeze) and
nothing else. It never decides eligibility — that is the repository's
single query — and it never touches audio: a version is rows and
references, and the future export/training pipeline resolves bytes
through the existing storage seam.

The freeze is the one operation with real invariants, all kept inside
the caller's single request transaction:

1. lock the dataset row (org-scoped FOR UPDATE) — concurrent freezes of
   the same dataset serialize instead of racing the version number;
2. refuse an empty freeze BEFORE creating anything — a version of
   nothing is a user error the preview already made visible;
3. insert the version, then its membership via INSERT…SELECT from THE
   eligibility query — the database decides the set in one statement;
4. write the frozen aggregates FROM the membership just inserted, so
   the stored numbers cannot disagree with the stored rows;
5. append ``included_in_dataset`` to every member's event history —
   sample-side lineage, status deliberately untouched.

Raising anywhere rolls the whole freeze back — there is no state in
which a version exists half-frozen.
"""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import (
    InvalidRequestError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import (
    Dataset,
    DatasetPreparation,
    DatasetStatus,
    DatasetVersion,
    PreparationStatus,
)
from intelliai_api.db.repositories.datasets import (
    DatasetCriteria,
    DatasetRepository,
    EligibilityPreview,
)
from intelliai_api.services.auth import AuthContext
from intelliai_api.storage import (
    ObjectStorage,
    StorageObjectMissingError,
    StorageReadError,
    StorageWriteError,
)

logger = structlog.get_logger("intelliai_api.datasets")

#: The manifest's wire format: one JSON object per line, UTF-8, LF.
MANIFEST_FORMAT = "jsonl"
MANIFEST_CONTENT_TYPE = "application/x-ndjson"

# Validation reason vocabulary — machine-readable, additive-only.
REASON_AUDIO_MISSING = "audio_missing"
REASON_TRANSCRIPT_MISSING = "transcript_missing"
REASON_LANGUAGE_MISSING = "language_missing"
REASON_DURATION_INVALID = "duration_invalid"
REASON_FOREIGN_SAMPLE = "foreign_sample"
REASON_MEMBERSHIP_MISMATCH = "membership_count_mismatch"


def preparation_artifact_key(
    *, organization_public_id: str, dataset_public_id: str, version_public_id: str
) -> str:
    """The manifest's deterministic key, version-addressed by design:

    ``datasets/{org}/{dataset}/{version}/manifest.jsonl``

    A sibling capability prefix to ``speech/`` (the layout the storage
    charter reserved for exactly this). Version-addressed rather than
    preparation-addressed on purpose: at most one preparation exists per
    version and its content is a pure function of the frozen membership,
    so a retry overwrites the key with byte-identical content — no
    orphaned objects, no ``latest.json`` ambiguity. The preparation ROW
    carries the identity; the checksum pins the content.
    """
    return (
        f"datasets/{organization_public_id}/{dataset_public_id}/{version_public_id}/manifest.jsonl"
    )


@dataclass(frozen=True)
class TrainingExample:
    """One resolved, validated line of the manifest — the shape a future
    fine-tuning loader consumes, deliberately model-agnostic."""

    id: str  # the sample's public id — the provenance link
    audio: str  # canonical object key; resolved via ObjectStorage
    text: str  # the PINNED training transcript, exactly as frozen
    language: str
    duration_seconds: float

    def line(self) -> str:
        # Fixed key order and compact separators: the serialization is
        # part of the checksum contract. ensure_ascii=False keeps Hindi
        # and Arabic text human-readable in the stored artifact.
        return json.dumps(
            {
                "id": self.id,
                "audio": self.audio,
                "text": self.text,
                "language": self.language,
                "duration_seconds": self.duration_seconds,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def manifest_bytes(examples: list[TrainingExample]) -> bytes:
    """The whole artifact, deterministically: caller-ordered lines, LF
    separated, trailing newline, UTF-8. Same members → same bytes,
    today and years from now."""
    return ("\n".join(example.line() for example in examples) + "\n").encode("utf-8")


def manifest_checksum(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class DatasetService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage | None = None) -> None:
        # Storage is optional because most dataset verbs never touch
        # bytes; only preparation needs it, and a disabled store (kill
        # switch) makes preparation honestly unavailable — never a crash.
        self._session = session
        self._storage = storage
        self._datasets = DatasetRepository(session)

    async def create_dataset(
        self,
        auth: AuthContext,
        *,
        name: str,
        description: str | None,
        criteria: DatasetCriteria,
    ) -> Dataset:
        dataset = await self._datasets.create(
            organization_id=auth.organization_id,
            name=name,
            description=description,
            criteria=criteria,
        )
        logger.info(
            "dataset.created",
            dataset_id=dataset.public_id,
            organization_id=auth.organization_public_id,
            criteria=dataset.criteria,
        )
        return dataset

    async def get_dataset(self, auth: AuthContext, dataset_public_id: str) -> Dataset:
        """Org-scoped or 404 — a foreign tenant's dataset does not exist
        from this caller's point of view (never 403: no existence leak)."""
        dataset = await self._datasets.get_for_organization(auth.organization_id, dataset_public_id)
        if dataset is None:
            raise ResourceNotFoundError(
                f"No dataset {dataset_public_id!r} exists in this organization.",
                code="dataset_not_found",
                param="dataset_id",
            )
        return dataset

    async def archive_dataset(self, auth: AuthContext, dataset_public_id: str) -> Dataset:
        """Retire from active use; versions remain readable forever.
        Idempotent — archiving an archived dataset returns it unchanged."""
        dataset = await self.get_dataset(auth, dataset_public_id)
        if dataset.status is not DatasetStatus.ARCHIVED:
            dataset.status = DatasetStatus.ARCHIVED
            await self._session.flush()
            # The UPDATE ran onupdate=now() server-side, expiring
            # updated_at; refresh it HERE, in async context, so response
            # shaping never triggers a sync lazy load (MissingGreenlet).
            await self._session.refresh(dataset)
            logger.info(
                "dataset.archived",
                dataset_id=dataset.public_id,
                organization_id=auth.organization_public_id,
            )
        return dataset

    async def preview(self, auth: AuthContext, dataset_public_id: str) -> EligibilityPreview:
        """What a version would freeze right now — computed by the SAME
        eligibility query the freeze uses, by construction."""
        dataset = await self.get_dataset(auth, dataset_public_id)
        criteria = DatasetCriteria.from_dict(dataset.criteria)
        return await self._datasets.preview(auth.organization_id, criteria)

    async def create_version(self, auth: AuthContext, dataset_public_id: str) -> DatasetVersion:
        """Freeze the currently eligible samples as the next version."""
        dataset = await self._datasets.get_for_organization(
            auth.organization_id, dataset_public_id, for_update=True
        )
        if dataset is None:
            raise ResourceNotFoundError(
                f"No dataset {dataset_public_id!r} exists in this organization.",
                code="dataset_not_found",
                param="dataset_id",
            )

        criteria = DatasetCriteria.from_dict(dataset.criteria)
        if not await self._datasets.has_eligible_samples(auth.organization_id, criteria):
            raise InvalidRequestError(
                "No samples are currently eligible for this dataset — nothing to freeze. "
                "Collect consented samples matching the criteria, then create a version.",
                code="dataset_version_empty",
                param="dataset_id",
            )

        version_number = await self._datasets.next_version_number(dataset.id)
        version = await self._datasets.create_version(
            dataset_id=dataset.id,
            version_number=version_number,
            created_by=auth.key_public_id,
            criteria=criteria,
        )
        await self._datasets.freeze_membership(version.id, auth.organization_id, criteria)

        statistics = await self._datasets.membership_statistics(version.id)
        version.sample_count = statistics.sample_count
        version.duration_seconds = statistics.duration_seconds
        version.statistics = {
            "corrected_samples": statistics.corrected_samples,
            "languages": [
                {
                    "key": entry.key,
                    "samples": entry.samples,
                    "duration_seconds": float(entry.duration_seconds),
                }
                for entry in statistics.languages
            ],
            "client_sources": [
                {
                    "key": entry.key,
                    "samples": entry.samples,
                    "duration_seconds": float(entry.duration_seconds),
                }
                for entry in statistics.client_sources
            ],
        }
        await self._session.flush()

        await self._datasets.record_inclusion_events(
            version.id,
            detail={
                "dataset_id": dataset.public_id,
                "dataset_version_id": version.public_id,
                "version_number": version_number,
            },
            occurred_at=utc_now(),
        )

        logger.info(
            "dataset.version_frozen",
            dataset_id=dataset.public_id,
            dataset_version_id=version.public_id,
            version_number=version_number,
            organization_id=auth.organization_public_id,
            sample_count=statistics.sample_count,
            duration_seconds=float(statistics.duration_seconds),
        )
        return version

    async def get_version(
        self, auth: AuthContext, dataset_public_id: str, version_public_id: str
    ) -> DatasetVersion:
        """Ownership flows through the dataset: org → dataset → version."""
        dataset = await self.get_dataset(auth, dataset_public_id)
        version = await self._datasets.get_version(dataset.id, version_public_id)
        if version is None:
            raise ResourceNotFoundError(
                f"No version {version_public_id!r} exists in this dataset.",
                code="dataset_version_not_found",
                param="version_id",
            )
        return version

    # ── Training-data preparation ────────────────────────────────────

    async def get_preparation(
        self, auth: AuthContext, dataset_public_id: str, version_public_id: str
    ) -> DatasetPreparation:
        """The version's singular preparation — ownership through the
        dataset chain, 404 when none has been run yet."""
        version = await self.get_version(auth, dataset_public_id, version_public_id)
        preparation = await self._datasets.get_preparation_for_version(version.id)
        if preparation is None:
            raise ResourceNotFoundError(
                f"Version {version_public_id!r} has no training-data preparation yet.",
                code="preparation_not_found",
                param="version_id",
            )
        return preparation

    async def prepare_version(
        self, auth: AuthContext, dataset_public_id: str, version_public_id: str
    ) -> DatasetPreparation:
        """Resolve the frozen membership into a validated, deterministic
        training manifest — or a recorded refusal.

        The reproducibility law, enforced by construction: this reads
        ONLY the membership rows and their pinned transcripts. It never
        re-runs eligibility, never reads current_transcript, never
        rebuilds membership — a version prepared today and re-prepared
        years later resolves to the same logical examples.

        Terminal semantics: READY is immutable (a second POST returns
        the existing preparation untouched — the artifact a fine-tuning
        run cites can never change under it); FAILED is retryable in
        place, because the fix (restoring an object, erasing a sample)
        lives outside this table.
        """
        dataset = await self.get_dataset(auth, dataset_public_id)
        version = await self._datasets.get_version(dataset.id, version_public_id)
        if version is None:
            raise ResourceNotFoundError(
                f"No version {version_public_id!r} exists in this dataset.",
                code="dataset_version_not_found",
                param="version_id",
            )

        existing = await self._datasets.get_preparation_for_version(version.id)
        if existing is not None and existing.status == PreparationStatus.READY.value:
            logger.info(
                "dataset.preparation_reused",
                dataset_id=dataset.public_id,
                dataset_version_id=version.public_id,
                preparation_id=existing.public_id,
            )
            return existing

        if self._storage is None:
            # The kill switch removed the storage seam at startup:
            # validation cannot check a single object, so the honest
            # answer is "unavailable", never a guessed verdict.
            raise ServiceUnavailableError(
                "Training-data preparation requires object storage, which is "
                "disabled on this deployment.",
                code="storage_unavailable",
            )

        members = await self._datasets.members_with_samples(version.id)
        if version.sample_count == 0 and not members:
            raise InvalidRequestError(
                "This version froze no samples — there is nothing to prepare.",
                code="dataset_version_empty",
                param="version_id",
            )

        preparation = existing or await self._datasets.create_preparation(
            organization_id=dataset.organization_id,
            dataset_id=dataset.id,
            dataset_version_id=version.id,
            created_by=auth.key_public_id,
        )

        errors: list[dict[str, str | None]] = []
        examples: list[TrainingExample] = []
        valid_duration = Decimal("0")
        languages: dict[str, int] = {}

        # Version-level integrity first: erasure CASCADEs through
        # membership, so fewer rows than the frozen count means samples
        # were deleted since the freeze. Named explicitly — a manifest
        # must never quietly claim a smaller version.
        if len(members) != version.sample_count:
            errors.append({"sample_id": None, "reason": REASON_MEMBERSHIP_MISMATCH})

        invalid_samples: set[str] = set()
        for member, sample in members:
            member_reasons: list[str] = []
            if sample.organization_id != dataset.organization_id:
                # Structurally impossible (freeze is org-scoped); checked
                # anyway because this table feeds training — belt AND braces.
                member_reasons.append(REASON_FOREIGN_SAMPLE)
            if not sample.audio_key:
                member_reasons.append(REASON_AUDIO_MISSING)
            else:
                try:
                    await self._storage.head(key=sample.audio_key)
                except StorageObjectMissingError:
                    member_reasons.append(REASON_AUDIO_MISSING)
                except StorageReadError as exc:
                    # Unreachable store ≠ absent object: no verdict is
                    # recorded, the whole run aborts retryably.
                    raise ServiceUnavailableError(
                        "Object storage did not answer while validating audio; "
                        "retry preparation shortly.",
                        code="storage_unavailable",
                    ) from exc
            if not member.training_transcript.strip():
                member_reasons.append(REASON_TRANSCRIPT_MISSING)
            language = sample.detected_language or sample.requested_language
            if not language:
                member_reasons.append(REASON_LANGUAGE_MISSING)
            duration = sample.duration_seconds
            if duration <= 0:
                member_reasons.append(REASON_DURATION_INVALID)

            if member_reasons:
                invalid_samples.add(sample.public_id)
                errors.extend(
                    {"sample_id": sample.public_id, "reason": reason} for reason in member_reasons
                )
                continue

            # Empty reasons ⟹ the language check above passed.
            language = cast(str, language)
            examples.append(
                TrainingExample(
                    id=sample.public_id,
                    audio=sample.audio_key,
                    text=member.training_transcript,
                    language=language,
                    duration_seconds=round(float(duration), 3),
                )
            )
            valid_duration += duration
            languages[language] = languages.get(language, 0) + 1

        now = utc_now()
        preparation.sample_count = version.sample_count
        preparation.valid_count = len(examples)
        preparation.invalid_count = len(invalid_samples)
        preparation.duration_seconds = valid_duration
        preparation.languages = dict(
            sorted(languages.items(), key=lambda entry: (-entry[1], entry[0]))
        )
        preparation.errors = list(errors)
        preparation.completed_at = now

        if errors:
            # NEVER silently skip: 997 valid of 1,000 is a FAILED
            # preparation with named reasons, not a smaller artifact.
            preparation.status = PreparationStatus.FAILED.value
            preparation.artifact_key = None
            preparation.manifest_checksum = None
            preparation.manifest_size_bytes = None
            await self._session.flush()
            logger.warning(
                "dataset.preparation_failed",
                dataset_id=dataset.public_id,
                dataset_version_id=version.public_id,
                preparation_id=preparation.public_id,
                sample_count=version.sample_count,
                valid_count=preparation.valid_count,
                invalid_count=preparation.invalid_count,
                error_count=len(errors),
            )
            return preparation

        data = manifest_bytes(examples)
        key = preparation_artifact_key(
            organization_public_id=auth.organization_public_id,
            dataset_public_id=dataset.public_id,
            version_public_id=version.public_id,
        )
        try:
            await self._storage.put(key=key, data=data, content_type=MANIFEST_CONTENT_TYPE)
        except StorageWriteError as exc:
            raise ServiceUnavailableError(
                "The training manifest could not be stored; retry preparation shortly.",
                code="storage_unavailable",
            ) from exc

        preparation.status = PreparationStatus.READY.value
        preparation.artifact_key = key
        preparation.manifest_checksum = manifest_checksum(data)
        preparation.manifest_size_bytes = len(data)
        await self._session.flush()
        logger.info(
            "dataset.preparation_ready",
            dataset_id=dataset.public_id,
            dataset_version_id=version.public_id,
            preparation_id=preparation.public_id,
            sample_count=version.sample_count,
            valid_count=preparation.valid_count,
            duration_seconds=float(valid_duration),
            manifest_checksum=preparation.manifest_checksum,
            manifest_size_bytes=preparation.manifest_size_bytes,
        )
        return preparation
