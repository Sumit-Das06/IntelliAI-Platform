"""Dataset, DatasetVersion, DatasetVersionSample — reproducible training data.

The distinction the whole design rests on: a **Dataset** is a logical
definition (a name and criteria over the organization's speech samples);
a **Dataset Version** is an immutable snapshot of exactly which samples
matched at one moment. Future fine-tuning consumes VERSIONS, never live
queries, which is what makes a training run reproducible forever.

Immutability, concretely: a version row and its membership rows are
written once, inside one transaction, and no code path updates or
deletes them afterwards — there is deliberately no repository verb for
it. New eligibility (more samples, later corrections) is expressed as
the NEXT version, never as an edit to an old one.

Membership references the canonical SpeechSample — audio is never
copied — but pins ``training_transcript`` (the sample's
``current_transcript`` at freeze time), because that is the one fact
that legitimately evolves after a freeze. A later correction improves
the NEXT version while the old version keeps training text identical to
what it froze; everything else a future trainer needs (audio reference,
languages, duration, provenance) is immutable on the sample row and is
read through the join.

Versions carry no status column: existence IS the state (frozen at
birth, in the freeze transaction). Training/trained/deployed belong to
the future fine-tuning run tables, which will reference versions —
never redefine them.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from functools import partial
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id


class DatasetStatus(StrEnum):
    """The dataset's lifecycle — deliberately the smallest honest set.

    No ``draft``: a dataset is usable the moment it is created, and no
    editing workflow exists that a draft state would describe. No
    deletion either — versions are lineage for future training runs, so
    retiring a dataset is ARCHIVED, never DROP.
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class Dataset(TimestampMixin, Base):
    """The logical definition: criteria over the organization's samples."""

    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_organization_id_created_at", "organization_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "ds")
    )

    # CASCADE like speech_samples, for the same reason: derived views of
    # collected data must never outlive the tenant (privacy-first).
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE")
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[DatasetStatus] = mapped_column(
        Enum(DatasetStatus, name="dataset_status", values_callable=lambda e: [m.value for m in e]),
        default=DatasetStatus.ACTIVE,
        server_default=DatasetStatus.ACTIVE.value,
    )

    # The validated filter definition (language, client_source, corrected,
    # collected_from/until), stored as data so future criteria arrive
    # additively. The vocabulary is owned by DatasetCriteria in the
    # repository layer — the single source of eligibility truth.
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    versions: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="dataset", order_by="DatasetVersion.version_number"
    )


class DatasetVersion(TimestampMixin, Base):
    """One immutable snapshot: exactly these samples, frozen at creation.

    ``criteria`` is copied from the dataset at freeze time so the version
    remains self-describing even if the dataset's definition changes
    later. ``sample_count``/``duration_seconds``/``statistics`` are
    computed FROM the frozen membership inside the freeze transaction —
    displayed numbers are the frozen truth, never a re-query.
    """

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "dsv")
    )

    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("datasets.id", ondelete="CASCADE")
    )

    #: 1, 2, 3, … within one dataset — the number humans cite ("v2").
    version_number: Mapped[int] = mapped_column(Integer)

    #: Who froze it: the acting API key's public id — the same identity
    #: convention as SpeechSample.user_identifier, and like it, a stable
    #: field a future login concept can populate without a migration.
    created_by: Mapped[str] = mapped_column(String(64))

    # ── Frozen aggregates (facts about the membership, at freeze) ──────
    sample_count: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    #: Descriptive breakdowns (languages, client sources, corrected
    #: count) — immutable statistics, never a live query.
    statistics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    #: The dataset's criteria as they stood when this version froze.
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")


class PreparationStatus(StrEnum):
    """The preparation's lifecycle — stored as TEXT, not a native enum,
    because the vocabulary is code-declarative and will grow (a future
    background executor adds ``pending``/``preparing``) without a
    migration — the same reasoning as ``organizations.plan``. Today's
    synchronous implementation only ever persists the two terminal
    states; the transient ones are reserved, documented vocabulary.
    """

    PENDING = "pending"  # reserved: queued for a future background executor
    PREPARING = "preparing"  # reserved: a future executor is running it
    READY = "ready"  # validated, manifest stored — immutable from here on
    FAILED = "failed"  # validation found invalid members; retryable


class DatasetPreparation(TimestampMixin, Base):
    """One version's training-data preparation: validation verdict plus
    the manifest's identity. At most ONE per version (unique below) —
    the artifact a future fine-tuning run cites is singular, and READY
    is terminal: once the manifest exists it is never rebuilt, so the
    citation can never silently change meaning. A FAILED row may be
    retried in place (same identity, same version-addressed key).

    ``organization_id`` is denormalized from the dataset on purpose:
    every tenant-owned table carries its own scope column so no query
    ever infers isolation through a join (ADR-0010 discipline).
    """

    __tablename__ = "dataset_preparations"
    __table_args__ = (UniqueConstraint("dataset_version_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "prep")
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("datasets.id", ondelete="CASCADE")
    )
    dataset_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset_versions.id", ondelete="CASCADE")
    )

    status: Mapped[str] = mapped_column(String(16))

    #: Who ran it: the acting API key's public id — the same identity
    #: convention as versions' created_by.
    created_by: Mapped[str] = mapped_column(String(64))

    # ── Validation verdict ──────────────────────────────────────────────
    #: The version's frozen membership size at preparation time.
    sample_count: Mapped[int] = mapped_column(Integer)
    valid_count: Mapped[int] = mapped_column(Integer)
    invalid_count: Mapped[int] = mapped_column(Integer)
    #: Sum over the VALID examples — the artifact's duration.
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    #: {language_code: example_count} over the valid examples.
    languages: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    #: [{"sample_id": "smp_…" | null, "reason": "audio_missing"}, …] —
    #: machine-readable, empty when READY. sample_id is null only for
    #: version-level findings (membership_count_mismatch after erasure).
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    # ── Artifact identity (set when READY, never mutated after) ────────
    #: Version-addressed object key (datasets/{org}/{ds}/{dsv}/manifest.jsonl).
    #: Internal reference — never leaves the platform through public APIs.
    artifact_key: Mapped[str | None] = mapped_column(String(512))
    #: sha256:<hex> of the manifest bytes — the content identity a future
    #: fine-tuning run pins, so "same preparation" is verifiable.
    manifest_checksum: Mapped[str | None] = mapped_column(String(80))
    manifest_size_bytes: Mapped[int | None] = mapped_column(BigInteger)

    #: When the run reached a terminal status. Equals created_at within a
    #: breath today (synchronous); meaningful once an executor arrives.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetVersionSample(Base):
    """Membership: this sample belongs to this version, with this text.

    Append-only by design (no updated_at): rows are written by the
    freeze and never touched again. ``training_transcript`` is the
    pinned training text; every other training-relevant fact (audio
    reference, language, client source, duration, provenance) is
    immutable on the SpeechSample row and resolved through the join —
    snapshotting those would be duplication, not safety.

    The sample FK CASCADEs: if a sample is ever erased (tenant deletion
    today, per-sample privacy erasure tomorrow), its membership rows go
    with it — privacy law outranks reproducibility, and a version that
    lost samples to erasure should honestly shrink rather than dangle.
    """

    __tablename__ = "dataset_version_samples"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "speech_sample_id"),
        # Reverse lineage: "which dataset versions used this sample?"
        Index("ix_dataset_version_samples_speech_sample_id", "speech_sample_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset_versions.id", ondelete="CASCADE")
    )
    speech_sample_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("speech_samples.id", ondelete="CASCADE")
    )

    #: current_transcript at freeze time — corrected when the human had
    #: corrected it by then, the machine's text otherwise. Comparing it
    #: to the sample's immutable original_transcript yields the
    #: correction state without another column.
    training_transcript: Mapped[str] = mapped_column(Text)
