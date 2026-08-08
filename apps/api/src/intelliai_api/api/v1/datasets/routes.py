"""Dataset APIs — the minimal surface the console's Datasets page
demanded, and nothing more (UI-driven by decree).

Dataset = the logical definition (criteria over the organization's
speech samples). Dataset Version = the immutable snapshot a future
fine-tuning run will consume. The response shapes speak the public
product vocabulary — names, criteria, counts, durations, languages,
client sources. Producer internals (engine names, object keys, sample
lineage) never appear here, exactly as on every other surface.

No training, export, or download endpoints: this commit is the data
foundation, and the API surface says only what the UI needs said.
"""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from intelliai_api.api.deps import CurrentAuth, SessionDep
from intelliai_api.db.models import ClientSource, Dataset, DatasetVersion
from intelliai_api.db.repositories import DatasetRepository
from intelliai_api.db.repositories.datasets import DatasetCriteria, EligibilityPreview
from intelliai_api.services.datasets import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])

#: Language criteria accept what the platform records for a sample:
#: short BCP-47-ish codes ("en", "hi", "pt-BR"), never free text.
LanguageCode = Annotated[
    str, StringConstraints(min_length=2, max_length=16, pattern=r"^[A-Za-z][A-Za-z-]*$")
]


class DatasetCriteriaBody(BaseModel):
    """The filter vocabulary, validated closed: an unknown criterion is
    a 400 today rather than a silently ignored promise."""

    model_config = ConfigDict(extra="forbid")

    language: LanguageCode | None = None
    client_source: ClientSource | None = None
    corrected: bool | None = None
    collected_from: date | None = None
    collected_until: date | None = None

    def to_domain(self) -> DatasetCriteria:
        language = self.language.lower() if self.language is not None else None
        return DatasetCriteria(
            language=language,
            client_source=self.client_source,
            corrected=self.corrected,
            collected_from=self.collected_from,
            collected_until=self.collected_until,
        )


class CreateDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    criteria: DatasetCriteriaBody = Field(default_factory=DatasetCriteriaBody)


class DatasetVersionSummary(BaseModel):
    id: str
    version_number: int
    sample_count: int
    duration_seconds: float
    created_at: datetime


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    criteria: dict[str, Any]
    version_count: int
    latest_version: DatasetVersionSummary | None
    created_at: datetime
    updated_at: datetime


class DatasetListResponse(BaseModel):
    # Envelope (not a bare array) so pagination fields can arrive additively.
    data: list[DatasetResponse]


class EligibilitySlice(BaseModel):
    #: ``None`` for language means "none declared, none detected".
    key: str | None
    samples: int
    duration_seconds: float


class DatasetPreviewResponse(BaseModel):
    """What a version created right now would contain — computed by the
    same eligibility rules the freeze uses (one query, one truth)."""

    matching_samples: int
    eligible_samples: int
    corrected_samples: int
    duration_seconds: float
    languages: list[EligibilitySlice]
    client_sources: list[EligibilitySlice]


class DatasetVersionResponse(BaseModel):
    id: str
    version_number: int
    sample_count: int
    duration_seconds: float
    corrected_samples: int
    languages: list[EligibilitySlice]
    client_sources: list[EligibilitySlice]
    #: The dataset's criteria as they stood at the freeze — the version
    #: stays self-describing even if the dataset definition evolves.
    criteria: dict[str, Any]
    created_at: datetime
    created_by: str


class DatasetVersionListResponse(BaseModel):
    data: list[DatasetVersionResponse]


def _version_summary(version: DatasetVersion) -> DatasetVersionSummary:
    return DatasetVersionSummary(
        id=version.public_id,
        version_number=version.version_number,
        sample_count=version.sample_count,
        duration_seconds=round(float(version.duration_seconds), 3),
        created_at=version.created_at,
    )


def _to_dataset_response(
    dataset: Dataset, *, version_count: int, latest: DatasetVersion | None
) -> DatasetResponse:
    return DatasetResponse(
        id=dataset.public_id,
        name=dataset.name,
        description=dataset.description,
        status=dataset.status.value,
        criteria=dataset.criteria,
        version_count=version_count,
        latest_version=_version_summary(latest) if latest is not None else None,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _slices(entries: list[dict[str, Any]]) -> list[EligibilitySlice]:
    return [
        EligibilitySlice(
            key=entry.get("key"),
            samples=int(entry.get("samples", 0)),
            duration_seconds=round(float(entry.get("duration_seconds", 0.0)), 3),
        )
        for entry in entries
    ]


def _to_version_response(version: DatasetVersion) -> DatasetVersionResponse:
    statistics = version.statistics or {}
    return DatasetVersionResponse(
        id=version.public_id,
        version_number=version.version_number,
        sample_count=version.sample_count,
        duration_seconds=round(float(version.duration_seconds), 3),
        corrected_samples=int(statistics.get("corrected_samples", 0)),
        languages=_slices(statistics.get("languages", [])),
        client_sources=_slices(statistics.get("client_sources", [])),
        criteria=version.criteria,
        created_at=version.created_at,
        created_by=version.created_by,
    )


def _to_preview_response(preview: EligibilityPreview) -> DatasetPreviewResponse:
    return DatasetPreviewResponse(
        matching_samples=preview.matching_samples,
        eligible_samples=preview.eligible_samples,
        corrected_samples=preview.corrected_samples,
        duration_seconds=round(float(preview.duration_seconds), 3),
        languages=[
            EligibilitySlice(
                key=entry.key,
                samples=entry.samples,
                duration_seconds=round(float(entry.duration_seconds), 3),
            )
            for entry in preview.languages
        ],
        client_sources=[
            EligibilitySlice(
                key=entry.key,
                samples=entry.samples,
                duration_seconds=round(float(entry.duration_seconds), 3),
            )
            for entry in preview.client_sources
        ],
    )


@router.get("")
async def list_datasets(auth: CurrentAuth, session: SessionDep) -> DatasetListResponse:
    """The organization's datasets, newest first, each with its latest
    frozen version — the console table's exact shape."""
    repository = DatasetRepository(session)
    datasets = await repository.list_for_organization(auth.organization_id)
    ids = [dataset.id for dataset in datasets]
    latest = await repository.latest_versions(ids)
    counts = await repository.version_counts(ids)
    return DatasetListResponse(
        data=[
            _to_dataset_response(
                dataset,
                version_count=counts.get(dataset.id, 0),
                latest=latest.get(dataset.id),
            )
            for dataset in datasets
        ]
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: CreateDatasetRequest, auth: CurrentAuth, session: SessionDep
) -> DatasetResponse:
    """Define a dataset: a name and criteria. Nothing freezes yet —
    versions are explicit, separate acts."""
    service = DatasetService(session)
    dataset = await service.create_dataset(
        auth,
        name=body.name.strip(),
        description=body.description,
        criteria=body.criteria.to_domain(),
    )
    return _to_dataset_response(dataset, version_count=0, latest=None)


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str, auth: CurrentAuth, session: SessionDep) -> DatasetResponse:
    """One dataset with its latest-version summary."""
    service = DatasetService(session)
    dataset = await service.get_dataset(auth, dataset_id)
    repository = DatasetRepository(session)
    latest = await repository.latest_versions([dataset.id])
    counts = await repository.version_counts([dataset.id])
    return _to_dataset_response(
        dataset,
        version_count=counts.get(dataset.id, 0),
        latest=latest.get(dataset.id),
    )


@router.get("/{dataset_id}/preview")
async def preview_dataset(
    dataset_id: str, auth: CurrentAuth, session: SessionDep
) -> DatasetPreviewResponse:
    """The eligibility summary: what a version created right now would
    freeze. Same rules as the freeze itself — never a second opinion."""
    service = DatasetService(session)
    return _to_preview_response(await service.preview(auth, dataset_id))


@router.post("/{dataset_id}/archive")
async def archive_dataset(
    dataset_id: str, auth: CurrentAuth, session: SessionDep
) -> DatasetResponse:
    """Retire a dataset from active work. Its versions remain readable —
    lineage is forever. Idempotent, like every retire verb here."""
    service = DatasetService(session)
    dataset = await service.archive_dataset(auth, dataset_id)
    repository = DatasetRepository(session)
    latest = await repository.latest_versions([dataset.id])
    counts = await repository.version_counts([dataset.id])
    return _to_dataset_response(
        dataset,
        version_count=counts.get(dataset.id, 0),
        latest=latest.get(dataset.id),
    )


@router.post("/{dataset_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_dataset_version(
    dataset_id: str, auth: CurrentAuth, session: SessionDep
) -> DatasetVersionResponse:
    """Freeze the currently eligible samples as an immutable snapshot.

    Future corrections and new samples never change this version; they
    become the case for creating the next one.
    """
    service = DatasetService(session)
    return _to_version_response(await service.create_version(auth, dataset_id))


@router.get("/{dataset_id}/versions")
async def list_dataset_versions(
    dataset_id: str, auth: CurrentAuth, session: SessionDep
) -> DatasetVersionListResponse:
    """Every frozen version, latest first."""
    service = DatasetService(session)
    dataset = await service.get_dataset(auth, dataset_id)
    versions = await DatasetRepository(session).list_versions(dataset.id)
    return DatasetVersionListResponse(data=[_to_version_response(v) for v in versions])


@router.get("/{dataset_id}/versions/{version_id}")
async def get_dataset_version(
    dataset_id: str, version_id: str, auth: CurrentAuth, session: SessionDep
) -> DatasetVersionResponse:
    """One frozen version — ownership resolves through the dataset."""
    service = DatasetService(session)
    return _to_version_response(await service.get_version(auth, dataset_id, version_id))
