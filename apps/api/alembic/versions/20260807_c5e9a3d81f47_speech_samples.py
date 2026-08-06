"""speech samples: the flywheel's storage - one row per consented utterance

Revision ID: c5e9a3d81f47
Revises: a1f4d7b2c9e3
Create Date: 2026-08-07 11:30:00.000000

Two tables, one law: speech_samples.status is only the LATEST state;
speech_sample_events is the append-only historical truth. The samples FK
is CASCADE - deliberately opposite to the billing ledger's RESTRICT -
because collected data must never outlive its tenant, while billing
history must never disappear with one. original_transcript is immutable
(the machine's output as served); current_transcript evolves through
corrections and review. The consent columns are snapshots copied at
capture: future consent changes never rewrite what a sample was
collected under.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e9a3d81f47"
down_revision: str | None = "a1f4d7b2c9e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speech_samples",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "collected",
                "validated",
                "accepted",
                "rejected",
                "training",
                "archived",
                name="sample_status",
            ),
            server_default="collected",
            nullable=False,
        ),
        sa.Column("audio_key", sa.String(length=512), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("codec", sa.String(length=50), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("original_transcript", sa.Text(), nullable=False),
        sa.Column("current_transcript", sa.Text(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_language", sa.String(length=16), nullable=True),
        sa.Column("routed_language", sa.String(length=16), nullable=True),
        sa.Column("detected_language", sa.String(length=16), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=True),
        sa.Column("lineage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "client_source",
            sa.Enum("web", "keyboard", "api", name="client_source"),
            nullable=False,
        ),
        sa.Column("client_version", sa.String(length=64), nullable=True),
        sa.Column("app_locale", sa.String(length=16), nullable=True),
        sa.Column("user_identifier", sa.String(length=64), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_reference", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_speech_samples_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_speech_samples")),
        sa.UniqueConstraint("public_id", name=op.f("uq_speech_samples_public_id")),
    )
    op.create_index(
        "ix_speech_samples_organization_id_created_at",
        "speech_samples",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "speech_sample_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sample_id", sa.BigInteger(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sample_id"],
            ["speech_samples.id"],
            name=op.f("fk_speech_sample_events_speech_samples_sample_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_speech_sample_events")),
    )
    op.create_index(
        "ix_speech_sample_events_sample_id_occurred_at",
        "speech_sample_events",
        ["sample_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_speech_sample_events_sample_id_occurred_at", table_name="speech_sample_events"
    )
    op.drop_table("speech_sample_events")
    op.drop_index("ix_speech_samples_organization_id_created_at", table_name="speech_samples")
    op.drop_table("speech_samples")
    sa.Enum(name="client_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sample_status").drop(op.get_bind(), checkfirst=True)
