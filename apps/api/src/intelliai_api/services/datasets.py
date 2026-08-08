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

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import InvalidRequestError, ResourceNotFoundError
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import Dataset, DatasetStatus, DatasetVersion
from intelliai_api.db.repositories.datasets import (
    DatasetCriteria,
    DatasetRepository,
    EligibilityPreview,
)
from intelliai_api.services.auth import AuthContext

logger = structlog.get_logger("intelliai_api.datasets")


class DatasetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
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
