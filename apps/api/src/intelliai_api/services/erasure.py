"""ErasureService — the right to be forgotten, made executable.

Charter: owns the erasure sequence and nothing else. It never decides
consent (that gate lives in collection), never touches billing (the
usage ledger is a commercial record that survives erasure by law), and
is invoked ONLY by the operator CLI today — erasure is a deliberate,
audited act, not a public endpoint.

The policy it implements is docs/DATA_GOVERNANCE.md, approved for
Milestone 14A. Its one hard law:

    Privacy outranks reproducibility — and the exception must be LOUD.

A frozen Dataset Version is immutable against the moving world, but not
against a deletion request. Erasing a member therefore:

- deletes any stored manifest that carries the person's transcript and
  audio key, and marks its preparation FAILED with the machine-readable
  reason ``sample_erased`` — the version permanently, visibly records
  that it can no longer be trained on as frozen;
- deletes the audio object, then the sample row (events and membership
  rows follow via the schema's ON DELETE CASCADE);
- leaves the version's frozen statistics untouched: aggregates carry no
  personal data, and rewriting them would be silently editing history.
  The preparation layer is what tells the present-tense truth.

Ordering law: OBJECTS BEFORE ROWS. A crash between the two leaves a row
pointing at a deleted object — visible (audio 404s, preparation names
``audio_missing``) and retryable. Rows-first would leave orphaned
personal audio with no index pointing at it: undiscoverable, and
therefore unerasable. The worse failure mode loses.

Storage unreachable means ABORT, retry later — never "erased". The
whole run raises; nothing is half-forgotten silently.
"""

from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import ResourceNotFoundError, ServiceUnavailableError
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import Organization, PreparationStatus, SpeechSample
from intelliai_api.db.repositories import (
    ApiKeyRepository,
    DatasetRepository,
    OrganizationRepository,
    SpeechSampleRepository,
)
from intelliai_api.storage import ObjectStorage, StorageWriteError

logger = structlog.get_logger("intelliai_api.erasure")

#: The machine-readable reasons a preparation records when erasure
#: revokes its artifact. Additive vocabulary, like the validation reasons.
REASON_SAMPLE_ERASED = "sample_erased"
REASON_ORGANIZATION_ERASED = "organization_erased"

#: What an anonymized tenant is renamed to. The public id (needed by the
#: retained usage ledger's foreign key) stays; the human-chosen name goes.
ERASED_ORGANIZATION_NAME = "Erased Organization"


@dataclass
class ErasureReport:
    """What an erasure run actually did — printed by the CLI, asserted
    by tests. Counts, never content: the report must not re-leak what
    was just erased."""

    organization_public_id: str
    samples_erased: int = 0
    audio_objects_deleted: int = 0
    manifests_revoked: int = 0
    datasets_deleted: int = 0
    api_keys_revoked: int = 0
    memberships_removed: int = 0
    organization_anonymized: bool = False
    erased_sample_ids: list[str] = field(default_factory=list)


class ErasureService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage | None) -> None:
        self._session = session
        self._storage = storage
        self._samples = SpeechSampleRepository(session)
        self._datasets = DatasetRepository(session)
        self._organizations = OrganizationRepository(session)
        self._api_keys = ApiKeyRepository(session)

    # ── Public verbs ─────────────────────────────────────────────────

    async def erase_sample(
        self, *, organization_public_id: str, sample_public_id: str
    ) -> ErasureReport:
        """Erase one sample. 404 when it does not exist in this tenant —
        erasure is org-scoped exactly like every other read."""
        organization = await self._require_organization(organization_public_id)
        sample = await self._samples.get_for_organization(organization.id, sample_public_id)
        if sample is None:
            raise ResourceNotFoundError(
                f"No speech sample {sample_public_id!r} exists in this organization.",
                code="sample_not_found",
                param="sample_id",
            )
        report = ErasureReport(organization_public_id=organization.public_id)
        await self._erase_samples(organization, [sample], report)
        return report

    async def erase_user_data(
        self, *, organization_public_id: str, user_identifier: str
    ) -> ErasureReport:
        """Erase every sample one identity contributed — a person's
        deletion request under the pilot's one-key-per-person convention.
        Zero matches is a SUCCESS (their data is not there), not a 404:
        the goal state is 'nothing stored', and it already holds."""
        organization = await self._require_organization(organization_public_id)
        samples = await self._samples.list_for_user_identifier(organization.id, user_identifier)
        report = ErasureReport(organization_public_id=organization.public_id)
        await self._erase_samples(organization, list(samples), report)
        return report

    async def erase_organization(self, *, organization_public_id: str) -> ErasureReport:
        """Tenant erasure: every sample, every dataset artifact, every
        membership; keys revoked; the org row anonymized but KEPT.

        The row survives because the usage ledger's RESTRICT demands it —
        billing history must never disappear (ADR-0021), while collected
        data must never outlive its tenant. Data dies; the commercial
        skeleton remains. Operator user rows are untouched here: they may
        belong to other tenants, and per-user erasure is its own future
        verb (documented limitation, DATA_GOVERNANCE.md)."""
        organization = await self._require_organization(organization_public_id)
        report = ErasureReport(organization_public_id=organization.public_id)

        samples = await self._samples.list_all_for_organization(organization.id)
        await self._erase_samples(organization, list(samples), report)

        # Any manifest object the sample pass did not already revoke
        # (versions whose members were erased earlier, defensive sweep).
        for preparation in await self._datasets.preparations_with_artifacts(organization.id):
            if preparation.artifact_key is not None:
                await self._delete_object(preparation.artifact_key)
                report.manifests_revoked += 1
        report.datasets_deleted = await self._datasets.delete_all_for_organization(organization.id)

        now = utc_now()
        report.api_keys_revoked = await self._api_keys.revoke_all_for_organization(
            organization.id, now=now
        )
        report.memberships_removed = await self._organizations.remove_all_members(organization.id)

        # Anonymize, keep: the ledger's FK needs the row; nothing needs
        # the name. Consent state clears — there is no tenant left to
        # have granted it.
        organization.name = ERASED_ORGANIZATION_NAME
        organization.data_consent = False
        organization.data_consented_at = None
        organization.consent_reference = None
        organization.spend_limit = None
        await self._session.flush()
        report.organization_anonymized = True

        logger.info(
            "erasure.organization_erased",
            organization_id=organization.public_id,
            samples_erased=report.samples_erased,
            manifests_revoked=report.manifests_revoked,
            datasets_deleted=report.datasets_deleted,
            api_keys_revoked=report.api_keys_revoked,
            memberships_removed=report.memberships_removed,
        )
        return report

    # ── The shared sequence ──────────────────────────────────────────

    async def _erase_samples(
        self,
        organization: Organization,
        samples: list[SpeechSample],
        report: ErasureReport,
    ) -> None:
        if not samples:
            return
        sample_ids = [sample.id for sample in samples]

        # 1. Revoke every preparation whose stored manifest carries one
        #    of these samples: the manifest object holds the person's
        #    transcript text and audio key — it must die with the sample.
        for preparation in await self._datasets.preparations_referencing_samples(sample_ids):
            if preparation.artifact_key is not None:
                await self._delete_object(preparation.artifact_key)
                report.manifests_revoked += 1
            if preparation.status != PreparationStatus.FAILED.value:
                preparation.status = PreparationStatus.FAILED.value
                preparation.completed_at = utc_now()
            preparation.artifact_key = None
            preparation.manifest_checksum = None
            preparation.manifest_size_bytes = None
            preparation.errors = [
                *preparation.errors,
                {"sample_id": None, "reason": REASON_SAMPLE_ERASED},
            ]
        await self._session.flush()

        # 2. Audio objects — before rows, per the ordering law above.
        for sample in samples:
            if sample.audio_key:
                await self._delete_object(sample.audio_key)
                report.audio_objects_deleted += 1

        # 3. Rows. Events and dataset memberships cascade in the
        #    database; frozen version statistics deliberately stay.
        erased_public_ids = [sample.public_id for sample in samples]
        report.samples_erased = await self._samples.delete_by_ids(sample_ids)
        report.erased_sample_ids.extend(erased_public_ids)

        logger.info(
            "erasure.samples_erased",
            organization_id=organization.public_id,
            samples_erased=report.samples_erased,
            audio_objects_deleted=report.audio_objects_deleted,
            manifests_revoked=report.manifests_revoked,
            sample_ids=erased_public_ids,
        )

    # ── Plumbing ─────────────────────────────────────────────────────

    async def _require_organization(self, organization_public_id: str) -> Organization:
        organization = await self._organizations.get_by_public_id(organization_public_id)
        if organization is None:
            raise ResourceNotFoundError(
                f"No organization {organization_public_id!r} exists.",
                code="organization_not_found",
                param="organization_id",
            )
        return organization

    async def _delete_object(self, key: str) -> None:
        """One object gone, or the whole run aborts retryably. An
        unreachable store must never be recorded as an erasure."""
        if self._storage is None:
            raise ServiceUnavailableError(
                "Erasure requires object storage, which is disabled on this "
                "deployment. Enable the storage seam and retry.",
                code="storage_unavailable",
            )
        try:
            await self._storage.delete(key=key)
        except StorageWriteError as exc:
            raise ServiceUnavailableError(
                "Object storage did not answer while deleting; nothing has "
                "been recorded as erased. Retry when the store is reachable.",
                code="storage_unavailable",
            ) from exc
