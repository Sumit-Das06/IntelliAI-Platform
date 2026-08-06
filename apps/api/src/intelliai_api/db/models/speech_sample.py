"""SpeechSample: one consented speech sample — the unit of the data flywheel.

One row = one utterance = one training sample. Deliberately NOT a
"session": the natural unit of both serving and training is the single
audio-with-reference pair, and grouping utterances would record temporal
context we refuse to know (privacy law). Future capabilities get sibling
tables (ocr_samples, translation_samples, ...), never a shared parent.

Two-table shape, one law: ``speech_samples.status`` is only the LATEST
state (a derived convenience, like the ledger's rollups);
``speech_sample_events`` is the append-only historical truth — the same
history-over-state discipline the usage ledger already lives by.

Model-agnostic by construction: ``model_name``/``model_version`` say who
produced the machine transcript (SQL-filterable), ``lineage`` carries the
full provenance object, and nothing in the row assumes any particular
engine. ``original_transcript`` is immutable — the machine's output as it
was served; ``current_transcript`` is where corrections, review, and
future tooling evolve the text.
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id


class SampleStatus(StrEnum):
    """The sample's current position in the data lifecycle.

    Latest state only — every transition is also an appended event. The
    vocabulary is append-only: renaming a member would reinterpret every
    row that carries it.
    """

    COLLECTED = "collected"  # stored with consent; corrections may attach
    VALIDATED = "validated"  # integrity, dedup, language checks passed
    ACCEPTED = "accepted"  # eligible for training dataset builds
    REJECTED = "rejected"  # failed validation/review; kept, never trained on
    TRAINING = "training"  # included in at least one training dataset build
    ARCHIVED = "archived"  # retired from active dataset consideration


class ClientSource(StrEnum):
    """Which client surface produced the sample. An acoustic/product fact
    (web recordings, keyboard dictation, and API uploads have different
    audio profiles), never a user-tracking dimension."""

    WEB = "web"
    KEYBOARD = "keyboard"
    API = "api"


class SpeechSample(TimestampMixin, Base):
    __tablename__ = "speech_samples"
    __table_args__ = (
        Index("ix_speech_samples_organization_id_created_at", "organization_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "smp")
    )

    # CASCADE, deliberately opposite to the billing ledger's RESTRICT:
    # collected data must never outlive its tenant (privacy-first), while
    # billing history must never disappear with one.
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE")
    )

    status: Mapped[SampleStatus] = mapped_column(
        Enum(SampleStatus, name="sample_status", values_callable=lambda e: [m.value for m in e]),
        default=SampleStatus.COLLECTED,
        server_default=SampleStatus.COLLECTED.value,
    )

    # The stored object holding the user's ORIGINAL uploaded bytes —
    # original codec and container, never the pipeline's canonical
    # rendering, so today's serving choices never fossilize into the
    # dataset (model-agnosticism guardrail).
    audio_key: Mapped[str] = mapped_column(String(512))

    # ── Audio metadata: facts that explain the AUDIO, never the user ────
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    codec: Mapped[str | None] = mapped_column(String(50))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)

    # ── Transcripts ─────────────────────────────────────────────────────
    # original_transcript is IMMUTABLE: the machine's output as served.
    # current_transcript starts equal to it and evolves through user
    # correction, review, and future tooling; last_modified_at records the
    # most recent evolution, whoever made it.
    original_transcript: Mapped[str] = mapped_column(Text)
    current_transcript: Mapped[str] = mapped_column(Text)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Languages ───────────────────────────────────────────────────────
    requested_language: Mapped[str | None] = mapped_column(String(16))
    routed_language: Mapped[str | None] = mapped_column(String(16))
    detected_language: Mapped[str | None] = mapped_column(String(16))

    # ── Producer: who transcribed this ──────────────────────────────────
    # name/version as columns for efficient SQL filtering; lineage as the
    # complete provenance object (decode config, runtime identity, ...).
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(32))
    lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # ── Client context ──────────────────────────────────────────────────
    client_source: Mapped[ClientSource] = mapped_column(
        Enum(ClientSource, name="client_source", values_callable=lambda e: [m.value for m in e])
    )
    client_version: Mapped[str | None] = mapped_column(String(64))
    app_locale: Mapped[str | None] = mapped_column(String(16))
    # Stable across every surface: today the acting API key's public id;
    # a future login or device registration populates the same field —
    # never a device-specific concept.
    user_identifier: Mapped[str] = mapped_column(String(64))

    # ── Consent snapshot ────────────────────────────────────────────────
    # Copied from the organization at capture. Snapshots, permanently:
    # future consent changes must never rewrite what a sample was
    # collected under.
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_reference: Mapped[str | None] = mapped_column(String(255))

    # Forensic deduplication of client retries; no uniqueness constraint —
    # a duplicate consented sample is benign, an aborted request is not.
    idempotency_key: Mapped[str | None] = mapped_column(String(255))

    events: Mapped[list["SpeechSampleEvent"]] = relationship(
        back_populates="sample", order_by="SpeechSampleEvent.occurred_at"
    )


class SpeechSampleEvent(Base):
    """Append-only lifecycle history — the historical truth per sample.

    Never updated, never deleted; a correction to history is a new event.
    Deliberately minimal: no public_id (internal, never projected), no
    updated_at (append-only rows have no updates). Not a workflow engine —
    rows are written inline by whatever code performs the transition.
    """

    __tablename__ = "speech_sample_events"
    __table_args__ = (
        Index("ix_speech_sample_events_sample_id_occurred_at", "sample_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("speech_samples.id", ondelete="CASCADE")
    )
    #: Open vocabulary carried as data, starting with: collected,
    #: corrected; Phase 4 adds validated/accepted/rejected/
    #: included_in_dataset; Phase 5 adds used_in_training.
    event: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    sample: Mapped[SpeechSample] = relationship(back_populates="events")
